"""Validation tests for separate, non-executable table retrieval judgments."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.evaluation.retrieval.table_judgments import (
    ANSWERABLE,
    UNANSWERABLE,
    TableJudgmentDataError,
    load_table_judgments,
    validate_table_judgment_references,
)

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "data/evaluation/table_retrieval_judgments.v1.json"
EVIDENCE = ROOT / "data/processed/sec_evidence/v1"
MANIFEST = ROOT / "data/manifests/sec_documents.v1.json"


def test_table_judgments_are_grounded_and_separate_from_narrative_evaluation():
    dataset_id, version, cases = load_table_judgments(DATASET)
    assert (dataset_id, version, len(cases)) == ("sec-table-retrieval-judgments-v1", "1.0", 10)
    assert sum(case.status == ANSWERABLE for case in cases) == 8
    assert sum(case.status == UNANSWERABLE for case in cases) == 2
    assert sum(len(case.expected_tables) > 1 for case in cases) == 1
    validate_table_judgment_references(DATASET, EVIDENCE, MANIFEST)


def test_table_judgments_reject_duplicate_or_narrative_evidence(tmp_path):
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    payload["cases"][0]["expected_relevant_evidence"] *= 2
    duplicate_path = tmp_path / "duplicate.json"
    duplicate_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(TableJudgmentDataError, match="unique"):
        load_table_judgments(duplicate_path)

    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    payload["cases"][0]["expected_relevant_evidence"][0]["evidence_type"] = "narrative"
    type_path = tmp_path / "wrong-type.json"
    type_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(TableJudgmentDataError, match="evidence_type"):
        load_table_judgments(type_path)


def test_table_judgments_reject_provenance_and_filter_mismatches(tmp_path):
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    payload["cases"][0]["expected_relevant_evidence"][0]["source_locator"] = "table:999"
    provenance_path = tmp_path / "bad-provenance.json"
    provenance_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(TableJudgmentDataError, match="provenance"):
        validate_table_judgment_references(provenance_path, EVIDENCE, MANIFEST)

    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    payload["cases"][0]["filters"]["ticker"] = "MSFT"
    filter_path = tmp_path / "bad-filter.json"
    filter_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(TableJudgmentDataError, match="ticker"):
        validate_table_judgment_references(filter_path, EVIDENCE, MANIFEST)


def test_table_judgments_require_financial_table_artifact_type(tmp_path):
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    payload["cases"] = [payload["cases"][0]]
    dataset_path = tmp_path / "one-case.json"
    dataset_path.write_text(json.dumps(payload), encoding="utf-8")
    artifact = json.loads((EVIDENCE / "aapl-2024-10k.json").read_text(encoding="utf-8"))
    table_id = payload["cases"][0]["expected_relevant_evidence"][0]["table_evidence_id"]
    next(item for item in artifact["table_evidence"] if item["table_evidence_id"] == table_id)[
        "evidence_type"
    ] = "narrative"
    artifact_path = tmp_path / "aapl-2024-10k.json"
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
    with pytest.raises(TableJudgmentDataError, match="provenance"):
        validate_table_judgment_references(dataset_path, tmp_path, MANIFEST)
