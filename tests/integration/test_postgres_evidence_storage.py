"""Opt-in PostgreSQL integration tests for Phase 4A evidence persistence.

Set TEST_POSTGRES_DSN to a dedicated disposable database.  Tests create and
drop only a random schema within that database, never public objects.
"""

from __future__ import annotations

import copy
import json
import os
import uuid
from datetime import date
from pathlib import Path

import pytest

from app.evaluation.retrieval.keyword_evaluation import evaluate_keyword_retriever
from app.evaluation.retrieval.table_evaluation import evaluate_table_keyword_retriever
from app.ingestion.loaders.sec_manifest import load_registration_manifest
from app.retrieval.hybrid import ReciprocalRankFusionRetriever
from app.retrieval.keyword import KeywordSearchFilters, PostgresKeywordRetriever
from app.retrieval.semantic import PostgresSemanticRetriever, SemanticEmbeddingConfiguration
from app.retrieval.semantic.embeddings import encode_texts, prepare_embedding_segments
from app.retrieval.table import PostgresTableKeywordRetriever, TableSearchFilters
from app.storage.migrations.runner import MigrationError, apply_migrations
from app.storage.repositories.evidence_repository import (
    EvidenceAdmissionError,
    PostgresEvidenceRepository,
)
from app.storage.repositories.semantic_embedding_repository import (
    PostgresSemanticEmbeddingRepository,
    SemanticStorageError,
)

psycopg = pytest.importorskip("psycopg", reason="psycopg storage extra is not installed")

ROOT = Path(__file__).resolve().parents[2]
DSN = os.environ.get("TEST_POSTGRES_DSN")
if not DSN:
    pytest.skip(
        "TEST_POSTGRES_DSN is not configured for an isolated database", allow_module_level=True
    )


def _inputs() -> tuple[object, dict[str, object], list[dict[str, object]]]:
    manifest = load_registration_manifest(ROOT / "data/manifests/sec_documents.v1.json")
    evidence_dir = ROOT / "data/processed/sec_evidence/v1"
    metadata = json.loads((evidence_dir / "run_metadata.json").read_text(encoding="utf-8"))
    artifacts = [
        json.loads((evidence_dir / f"{document.document_id}.json").read_text(encoding="utf-8"))
        for document in manifest.documents
    ]
    return manifest, metadata, artifacts


@pytest.fixture()
def isolated_database():
    """Yield one connection scoped to a newly-created disposable schema."""

    schema = f"evidence_test_{uuid.uuid4().hex}"
    with psycopg.connect(DSN) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE SCHEMA "{schema}"')
            cursor.execute(f'SET search_path TO "{schema}"')
        connection.commit()
        try:
            yield connection
        finally:
            connection.rollback()
            with connection.cursor() as cursor:
                cursor.execute(f'DROP SCHEMA "{schema}" CASCADE')
            connection.commit()


def _count(connection, table: str) -> int:
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        return cursor.fetchone()[0]


def test_migrations_are_repeatable_and_detect_changed_script(isolated_database, tmp_path):
    migrations = ROOT / "app/storage/migrations"
    assert apply_migrations(isolated_database, migrations) == ("001", "002", "003", "004")
    assert apply_migrations(isolated_database, migrations) == ()
    changed = tmp_path / "migrations"
    changed.mkdir()
    source = (migrations / "001_evidence_storage.sql").read_text(encoding="utf-8")
    (changed / "001_evidence_storage.sql").write_text(f"{source}\n-- altered", encoding="utf-8")
    with pytest.raises(MigrationError):
        apply_migrations(isolated_database, changed)


def test_full_corpus_persistence_preserves_evidence_and_is_idempotent(isolated_database):
    apply_migrations(isolated_database, ROOT / "app/storage/migrations")
    manifest, metadata, artifacts = _inputs()
    repository = PostgresEvidenceRepository(isolated_database)
    result = repository.persist_run(manifest, metadata, artifacts)
    assert (result.narrative_count, result.table_count, result.quarantine_count) == (938, 833, 425)
    assert _count(isolated_database, "registered_documents") == 10
    assert _count(isolated_database, "narrative_chunks") == 938
    assert _count(isolated_database, "financial_table_evidence") == 833
    assert _count(isolated_database, "quarantine_records") == 425
    chunk = artifacts[0]["narrative_chunks"][0]
    table = artifacts[0]["table_evidence"][0]
    stored_chunk = repository.get_narrative_chunk(chunk["chunk_id"])
    stored_table = repository.get_table_evidence(table["table_evidence_id"])
    assert stored_chunk["source_sha256"] == chunk["source_sha256"]
    assert stored_table["source_locator"] == table["source_locator"]
    assert repository.persist_run(manifest, metadata, artifacts).inserted is False
    assert _count(isolated_database, "processing_runs") == 1


def test_invalid_admission_and_mid_document_failure_leave_no_records(isolated_database):
    apply_migrations(isolated_database, ROOT / "app/storage/migrations")
    manifest, metadata, artifacts = _inputs()
    rejected = copy.deepcopy(artifacts)
    rejected[0]["admission_status"] = "QUARANTINED"
    repository = PostgresEvidenceRepository(isolated_database)
    with pytest.raises(EvidenceAdmissionError):
        repository.persist_run(manifest, metadata, rejected)
    assert _count(isolated_database, "processing_runs") == 0
    invalid = copy.deepcopy(artifacts)
    invalid[0]["narrative_chunks"][1]["chunk_id"] = invalid[0]["narrative_chunks"][0]["chunk_id"]
    with pytest.raises(Exception):
        repository.persist_run(manifest, metadata, invalid)
    assert _count(isolated_database, "processing_runs") == 0
    assert _count(isolated_database, "narrative_chunks") == 0
    assert _count(isolated_database, "financial_table_evidence") == 0


def test_keyword_retrieval_ranks_and_filters_admitted_narrative(isolated_database):
    apply_migrations(isolated_database, ROOT / "app/storage/migrations")
    manifest, metadata, artifacts = _inputs()
    PostgresEvidenceRepository(isolated_database).persist_run(manifest, metadata, artifacts)
    retriever = PostgresKeywordRetriever(isolated_database)
    results = retriever.search(
        "revenue",
        KeywordSearchFilters(
            ticker="AAPL", form_type="10-K", reporting_period_end=date(2024, 9, 28)
        ),
        2,
    )
    assert 1 <= len(results) <= 2
    assert all(
        result.ticker == "AAPL"
        and result.form_type == "10-K"
        and result.reporting_period_end == date(2024, 9, 28)
        for result in results
    )
    assert all("revenue" in result.text.lower() for result in results)
    assert results == sorted(
        results, key=lambda result: (-result.rank, result.document_id, result.chunk_sequence)
    )


def test_keyword_retrieval_empty_and_no_match_queries(isolated_database):
    apply_migrations(isolated_database, ROOT / "app/storage/migrations")
    manifest, metadata, artifacts = _inputs()
    PostgresEvidenceRepository(isolated_database).persist_run(manifest, metadata, artifacts)
    retriever = PostgresKeywordRetriever(isolated_database)
    assert retriever.search("  ") == []
    assert retriever.search("unmatchabletermzzzz") == []


def test_table_keyword_retrieval_preserves_structure_and_excludes_quarantine(isolated_database):
    apply_migrations(isolated_database, ROOT / "app/storage/migrations")
    manifest, metadata, artifacts = _inputs()
    PostgresEvidenceRepository(isolated_database).persist_run(manifest, metadata, artifacts)
    retriever = PostgresTableKeywordRetriever(isolated_database)
    results = retriever.search(
        "revenue",
        TableSearchFilters(ticker="AAPL", form_type="10-K", reporting_period_end=date(2024, 9, 28)),
        5,
    )
    assert results
    assert all(
        result.validation_status == "ADMITTED"
        and result.source_sha256
        and result.rows
        and result.ticker == "AAPL"
        for result in results
    )
    assert all(
        cell.source_locator and cell.text is not None
        for result in results
        for row in result.rows
        for cell in row.cells
    )
    assert results == sorted(
        results,
        key=lambda result: (
            -result.rank,
            result.document_id,
            result.original_html_table_index,
            result.table_evidence_id,
        ),
    )
    assert retriever.search("unmatchabletermzzzz") == []


def test_versioned_keyword_evaluation_runs_against_persisted_evidence(isolated_database):
    apply_migrations(isolated_database, ROOT / "app/storage/migrations")
    manifest, metadata, artifacts = _inputs()
    PostgresEvidenceRepository(isolated_database).persist_run(manifest, metadata, artifacts)
    report = evaluate_keyword_retriever(
        PostgresKeywordRetriever(isolated_database),
        ROOT / "data/evaluation/keyword_retrieval.v1.json",
    )
    assert len(report.case_results) == 3
    assert all(
        0 <= value <= 1
        for value in (report.recall_at_5, report.recall_at_10, report.precision_at_5, report.mrr)
    )
    v2_report = evaluate_keyword_retriever(
        PostgresKeywordRetriever(isolated_database),
        ROOT / "data/evaluation/keyword_retrieval.v2.json",
    )
    assert (v2_report.answerable_case_count, v2_report.unanswerable_case_count) == (20, 3)


def test_versioned_table_evaluation_runs_against_persisted_evidence(isolated_database):
    apply_migrations(isolated_database, ROOT / "app/storage/migrations")
    manifest, metadata, artifacts = _inputs()
    PostgresEvidenceRepository(isolated_database).persist_run(manifest, metadata, artifacts)
    report = evaluate_table_keyword_retriever(
        PostgresTableKeywordRetriever(isolated_database),
        ROOT / "data/evaluation/table_retrieval_judgments.v1.json",
    )
    assert (report.answerable_case_count, report.unanswerable_case_count) == (8, 2)
    assert all(
        0 <= value <= 1
        for value in (report.recall_at_5, report.recall_at_10, report.precision_at_5, report.mrr)
    )


class _SemanticTokenizer:
    def __call__(self, text, **kwargs):
        return {"input_ids": [1], "offset_mapping": [(0, len(text))]}

    def num_special_tokens_to_add(self, pair=False):
        return 2


class _SemanticModel:
    tokenizer = _SemanticTokenizer()

    def encode(self, texts, **kwargs):
        return [[1.0] + [0.0] * 383 for _ in texts]


def test_semantic_pgvector_retrieval_uses_isolated_schema(isolated_database):
    """Exercise qualified vector type/operator/index behavior on pgvector 0.6.x."""

    apply_migrations(isolated_database, ROOT / "app/storage/migrations")
    manifest, metadata, artifacts = _inputs()
    PostgresEvidenceRepository(isolated_database).persist_run(manifest, metadata, artifacts)
    configuration = SemanticEmbeddingConfiguration(
        "test-model", "test-revision", 384, True, 256, "test-policy", "a", "b", "c", "d"
    )
    model = _SemanticModel()
    repository = PostgresSemanticEmbeddingRepository(isolated_database)
    repository.assert_no_source_hash_mismatch()
    repository.register_configuration(configuration)
    source = repository.eligible_narrative_sources()[0]
    segments = prepare_embedding_segments(
        source.chunk_id, source.text, model.tokenizer, configuration
    )
    vectors = encode_texts(model, [segment.text for segment in segments], configuration, 1)
    assert repository.insert_segments(configuration, source, segments, vectors) == (1, 0)
    assert repository.insert_segments(configuration, source, segments, vectors) == (0, 1)
    results = PostgresSemanticRetriever(isolated_database, model, configuration).search(
        "revenue", limit=1
    )
    assert results and results[0].chunk_id == source.chunk_id
    hybrid = ReciprocalRankFusionRetriever(
        PostgresKeywordRetriever(isolated_database),
        PostgresSemanticRetriever(isolated_database, model, configuration),
        branch_depth=2,
    )
    assert hybrid.search("revenue", limit=1)[0].chunk_id == source.chunk_id
    with isolated_database.cursor() as cursor:
        cursor.execute(
            "SELECT indexdef FROM pg_indexes WHERE indexname = "
            "'narrative_embedding_segments_cosine_hnsw_idx'"
        )
        assert "vector_cosine_ops" in cursor.fetchone()[0]


def test_semantic_backfill_refuses_source_hash_mismatch(isolated_database):
    apply_migrations(isolated_database, ROOT / "app/storage/migrations")
    manifest, metadata, artifacts = _inputs()
    PostgresEvidenceRepository(isolated_database).persist_run(manifest, metadata, artifacts)
    with isolated_database.cursor() as cursor:
        cursor.execute(
            "UPDATE narrative_chunks SET source_sha256 = %s WHERE chunk_id = %s",
            ("0" * 64, artifacts[0]["narrative_chunks"][0]["chunk_id"]),
        )
    with pytest.raises(SemanticStorageError, match="source-hash mismatch"):
        PostgresSemanticEmbeddingRepository(isolated_database).assert_no_source_hash_mismatch()
