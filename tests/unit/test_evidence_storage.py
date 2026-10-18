"""Tests for Phase 4A admission, migration, and transaction semantics."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.ingestion.loaders.sec_manifest import load_registration_manifest
from app.storage.migrations.runner import apply_migrations
from app.storage.repositories.evidence_repository import (
    EvidenceAdmissionError,
    InMemoryEvidenceRepository,
    StorageConflictError,
)

ROOT = Path(__file__).resolve().parents[2]


def load_inputs():
    manifest = load_registration_manifest(ROOT / "data/manifests/sec_documents.v1.json")
    folder = ROOT / "data/processed/sec_evidence/v1"
    return (
        manifest,
        json.loads((folder / "run_metadata.json").read_text(encoding="utf-8")),
        [
            json.loads(
                (folder / f"{document.document_id}.json").read_text(encoding="utf-8")
            )
            for document in manifest.documents
        ],
    )


def test_real_phase_three_artifacts_persist_separately_and_idempotently():
    manifest, metadata, artifacts = load_inputs()
    repository = InMemoryEvidenceRepository()
    result = repository.persist_run(manifest, metadata, artifacts)
    assert (
        result.inserted
        and result.narrative_count == 938
        and result.table_count == 833
        and result.quarantine_count == 425
    )
    assert (
        repository.get_narrative_chunk(artifacts[0]["narrative_chunks"][0]["chunk_id"])[
            "validation_status"
        ]
        == "ADMITTED"
    )
    assert (
        repository.get_table_evidence(artifacts[0]["table_evidence"][0]["table_evidence_id"])[
            "header_association_status"
        ]
        == "NOT_ESTABLISHED"
    )
    assert repository.persist_run(manifest, metadata, artifacts).inserted is False


def test_quarantined_document_cannot_enter_approved_storage():
    manifest, metadata, artifacts = load_inputs()
    bad = copy.deepcopy(artifacts)
    bad[0]["admission_status"] = "QUARANTINED"
    with pytest.raises(EvidenceAdmissionError):
        InMemoryEvidenceRepository().persist_run(manifest, metadata, bad)


def test_duplicate_chunk_rolls_back_memory_transaction():
    manifest, metadata, artifacts = load_inputs()
    bad = copy.deepcopy(artifacts)
    bad[0]["narrative_chunks"][1]["chunk_id"] = bad[0]["narrative_chunks"][0]["chunk_id"]
    repository = InMemoryEvidenceRepository()
    with pytest.raises(StorageConflictError):
        repository.persist_run(manifest, metadata, bad)
    assert not repository.runs and not repository.narrative


class FakeCursor:
    def __init__(self):
        self.executed = []
        self.rows = {}

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchone(self):
        return None

    def close(self):
        pass


class FakeConnection:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def test_numbered_postgresql_migration_is_applied_transactionally():
    connection = FakeConnection()
    applied = apply_migrations(connection, ROOT / "app/storage/migrations")
    assert applied == ("001", "002", "003", "004")
    assert connection.committed and not connection.rolled_back
    text = "\n".join(query for query, _ in connection.cursor_obj.executed)
    assert "financial_table_cells" in text and "quarantine_records" in text
