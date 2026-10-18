"""Metrics and answerability separation for table retrieval evaluation."""

from __future__ import annotations

import json

from app.evaluation.retrieval.table_evaluation import evaluate_table_keyword_retriever


class Result:
    def __init__(self, table_evidence_id):
        self.table_evidence_id = table_evidence_id


class FakeRetriever:
    def __init__(self, results):
        self.results = results

    def search(self, query, filters, limit):
        return [Result(value) for value in self.results[query][:limit]]


def _evidence(identifier, index, parser_id):
    return {
        "evidence_type": "table",
        "table_evidence_id": identifier,
        "document_id": "d",
        "source_sha256": "a" * 64,
        "source_locator": f"table:{index}",
        "original_html_table_index": index,
        "parser_table_id": parser_id,
    }


def test_table_metrics_support_multiple_relevance_and_unanswerable_cases(tmp_path):
    payload = {
        "dataset_id": "tables", "dataset_version": "1.0", "cases": [
            {
                "case_id": "one", "status": "answerable", "question": "one", "filters": {},
                "expected_relevant_evidence": [_evidence("a", 1, "p"), _evidence("b", 2, "q")],
            },
            {
                "case_id": "two", "status": "unanswerable", "question": "two", "filters": {},
                "expected_relevant_evidence": [],
            },
        ],
    }
    path = tmp_path / "tables.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    report = evaluate_table_keyword_retriever(
        FakeRetriever({"one": ["x", "b", "a"], "two": ["x"]}), path
    )
    assert (report.answerable_case_count, report.unanswerable_case_count) == (1, 1)
    assert report.recall_at_5 == report.recall_at_10 == 1
    assert report.precision_at_5 == 2 / 5
    assert report.mrr == 1 / 2
    assert report.case_results[1].returned_table_evidence_ids == ("x",)
