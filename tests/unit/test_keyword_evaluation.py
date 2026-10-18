"""Metric and versioned-label tests for keyword retrieval evaluation."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.evaluation.retrieval.keyword_evaluation import (
    ANSWERABLE,
    UNANSWERABLE,
    EvaluationDataError,
    evaluate_keyword_retriever,
    load_keyword_evaluation_dataset,
    validate_keyword_evaluation_filters,
    validate_keyword_evaluation_references,
)
from app.retrieval.keyword import KeywordSearchResult

ROOT = Path(__file__).resolve().parents[2]


class FakeRetriever:
    def __init__(self, ids_by_query):
        self.ids_by_query = ids_by_query

    def search(self, query, filters, limit):
        return [
            KeywordSearchResult(
                chunk_id,
                "doc",
                "a" * 64,
                "text",
                {},
                [],
                0,
                "MSFT",
                "Microsoft",
                "10-K",
                date(2024, 6, 30),
                1.0,
            )
            for chunk_id in self.ids_by_query[query][:limit]
        ]


def test_metrics_are_computed_at_fixed_cutoffs(tmp_path):
    dataset = {
        "dataset_id": "test",
        "dataset_version": "1",
        "cases": [
            {
                "case_id": "first",
                "question": "one",
                "filters": {},
                "expected_relevant_evidence": [{"chunk_id": "a"}],
            },
            {
                "case_id": "second",
                "question": "two",
                "filters": {},
                "expected_relevant_evidence": [{"chunk_id": "b"}],
            },
        ],
    }
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(dataset), encoding="utf-8")
    report = evaluate_keyword_retriever(FakeRetriever({"one": ["a"], "two": ["x", "b"]}), path)
    assert report.recall_at_5 == report.recall_at_10 == 1.0
    assert report.precision_at_5 == 0.2
    assert report.mrr == 0.75


def test_existing_dataset_has_three_grounded_cases():
    dataset_id, version, cases = load_keyword_evaluation_dataset(
        ROOT / "data/evaluation/keyword_retrieval.v1.json"
    )
    assert (dataset_id, version, len(cases)) == ("sec-keyword-retrieval-v1", "1.0", 3)
    assert all(case.expected_chunk_ids and case.status == ANSWERABLE for case in cases)


def test_versioned_labels_reference_actual_admitted_evidence():
    payload = json.loads(
        (ROOT / "data/evaluation/keyword_retrieval.v1.json").read_text(encoding="utf-8")
    )
    for case in payload["cases"]:
        for expected in case["expected_relevant_evidence"]:
            artifact = json.loads(
                (
                    ROOT / "data/processed/sec_evidence/v1" / f"{expected['document_id']}.json"
                ).read_text(encoding="utf-8")
            )
            chunk = next(
                item
                for item in artifact["narrative_chunks"]
                if item["chunk_id"] == expected["chunk_id"]
            )
            assert chunk["document_id"] == expected["document_id"]
            assert chunk["source_elements"][0]["source_locator"] == expected["source_locator"]
    validate_keyword_evaluation_references(
        ROOT / "data/evaluation/keyword_retrieval.v1.json",
        ROOT / "data/processed/sec_evidence/v1",
    )
    validate_keyword_evaluation_filters(
        ROOT / "data/evaluation/keyword_retrieval.v1.json",
        ROOT / "data/manifests/sec_documents.v1.json",
    )


def test_v2_dataset_is_grounded_and_separates_answerable_cases():
    path = ROOT / "data/evaluation/keyword_retrieval.v2.json"
    dataset_id, version, cases = load_keyword_evaluation_dataset(path)
    assert (dataset_id, version, len(cases)) == ("sec-keyword-retrieval-v2", "2.0", 23)
    assert sum(case.status == ANSWERABLE for case in cases) == 20
    assert sum(case.status == UNANSWERABLE for case in cases) == 3
    assert sum(len(case.expected_chunk_ids) > 1 for case in cases) == 2
    validate_keyword_evaluation_references(path, ROOT / "data/processed/sec_evidence/v1")
    validate_keyword_evaluation_filters(path, ROOT / "data/manifests/sec_documents.v1.json")


def test_unanswerable_cases_are_reported_outside_metric_denominators(tmp_path):
    dataset = {
        "dataset_id": "test-v2",
        "dataset_version": "2.0",
        "cases": [
            {
                "case_id": "answerable",
                "status": "answerable",
                "question": "one",
                "filters": {},
                "expected_relevant_evidence": [
                    {
                        "evidence_type": "narrative",
                        "chunk_id": "a",
                        "document_id": "doc",
                        "source_sha256": "a" * 64,
                        "source_locator": "element:1:p",
                    }
                ],
            },
            {
                "case_id": "unanswerable",
                "status": "unanswerable",
                "question": "two",
                "filters": {},
                "expected_relevant_evidence": [],
            },
        ],
    }
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(dataset), encoding="utf-8")
    report = evaluate_keyword_retriever(FakeRetriever({"one": ["a"], "two": ["x"]}), path)
    assert (report.answerable_case_count, report.unanswerable_case_count) == (1, 1)
    assert report.recall_at_5 == report.recall_at_10 == report.mrr == 1.0
    assert report.precision_at_5 == 0.2
    assert report.case_results[1].returned_chunk_ids == ("x",)


@pytest.mark.parametrize(
    "evidence",
    [
        [{"evidence_type": "table", "chunk_id": "t", "document_id": "d", "source_locator": "x"}],
        [
            {
                "evidence_type": "narrative",
                "chunk_id": "a",
                "document_id": "d",
                "source_locator": "x",
            }
        ]
        * 2,
    ],
)
def test_table_and_duplicate_narrative_judgments_are_rejected(tmp_path, evidence):
    dataset = {
        "dataset_id": "invalid",
        "dataset_version": "1.0",
        "cases": [
            {
                "case_id": "case",
                "question": "question",
                "filters": {},
                "expected_relevant_evidence": evidence,
            }
        ],
    }
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(dataset), encoding="utf-8")
    with pytest.raises(EvaluationDataError):
        load_keyword_evaluation_dataset(path)


def test_reference_validation_rejects_inconsistent_source_locator(tmp_path):
    payload = json.loads(
        (ROOT / "data/evaluation/keyword_retrieval.v2.json").read_text(encoding="utf-8")
    )
    payload["cases"][0]["expected_relevant_evidence"][0]["source_locator"] = "element:missing:p"
    path = tmp_path / "invalid-v2.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(EvaluationDataError, match="source locator"):
        validate_keyword_evaluation_references(path, ROOT / "data/processed/sec_evidence/v1")


def test_filter_validation_rejects_document_metadata_mismatch(tmp_path):
    payload = json.loads(
        (ROOT / "data/evaluation/keyword_retrieval.v2.json").read_text(encoding="utf-8")
    )
    payload["cases"][0]["filters"]["ticker"] = "MSFT"
    path = tmp_path / "invalid-filter-v2.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(EvaluationDataError, match="ticker"):
        validate_keyword_evaluation_filters(path, ROOT / "data/manifests/sec_documents.v1.json")


def test_v1_metrics_remain_compatible_and_reports_are_deterministic():
    path = ROOT / "data/evaluation/keyword_retrieval.v1.json"
    retriever = FakeRetriever(
        {
            "What does Microsoft's 2024 filing say about cash from operations?": [],
            "What was the Microsoft Cloud gross margin percentage in 2024?": [
                "781b962ce0fc9d395f307b25"
            ],
            "How do Apple's product and services gross margins differ?": [],
        }
    )
    first = evaluate_keyword_retriever(retriever, path)
    second = evaluate_keyword_retriever(retriever, path)
    assert first == second
    assert (first.answerable_case_count, first.unanswerable_case_count) == (3, 0)
    assert (first.recall_at_5, first.recall_at_10, first.precision_at_5, first.mrr) == (
        1 / 3,
        1 / 3,
        1 / 15,
        1 / 3,
    )


def test_malformed_labels_are_rejected(tmp_path):
    path = tmp_path / "labels.json"
    path.write_text('{"dataset_id":"x","dataset_version":"1","cases":[]}', encoding="utf-8")
    with pytest.raises(EvaluationDataError):
        load_keyword_evaluation_dataset(path)
