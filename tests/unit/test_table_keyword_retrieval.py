"""Unit coverage for structure-preserving table keyword retrieval."""

from __future__ import annotations

from datetime import date

import pytest

from app.retrieval.keyword import KeywordRetrievalError
from app.retrieval.table import PostgresTableKeywordRetriever, TableSearchFilters
from app.storage.table_search_projection import build_table_search_text


class FakeCursor:
    def __init__(self, rows, calls):
        self.rows = rows
        self.calls = calls

    def execute(self, query, params):
        self.calls.append((query, params))

    def fetchall(self):
        return self.rows

    def close(self):
        return None


class FakeConnection:
    def __init__(self, result_rows, structure_rows):
        self.result_rows = result_rows
        self.structure_rows = structure_rows
        self.calls = []
        self.count = 0

    def cursor(self):
        self.count += 1
        return FakeCursor(self.result_rows if self.count == 1 else self.structure_rows, self.calls)


def _candidate(table_id="table-1"):
    return (
        table_id,
        "doc-1",
        "a" * 64,
        "parser-1",
        4,
        "table:4",
        None,
        {"text": "Statement"},
        ["in millions"],
        ["2024"],
        "NOT_ESTABLISHED",
        [],
        [],
        "1.0",
        "b" * 64,
        "1.0",
        "c" * 64,
        "ADMITTED",
        "AAPL",
        "Apple",
        "10-K",
        date(2024, 9, 28),
        0.5,
    )


def test_projection_uses_only_ordered_contract_display_fields():
    table = {
        "caption": "Income statement",
        "preceding_heading": {"text": "Results"},
        "period_header_text": ["2024"],
        "unit_hints": ["in millions"],
        "rows": [{"cells": [{"text": "Revenue"}, {"text": "1,000"}]}],
    }
    assert build_table_search_text(table) == (
        "Income statement Results 2024 in millions Revenue 1,000"
    )


def test_table_retrieval_uses_parameterized_filters_and_preserves_rows():
    structure = [
        (
            "table-1", 1, "table:4/row:1", "cell-1", 1,
            "table:4/row:1/cell:1", "header", "Revenue", 1, 2,
        ),
        (
            "table-1", 1, "table:4/row:1", "cell-2", 2,
            "table:4/row:1/cell:2", "data", "1,000", 1, 1,
        ),
    ]
    connection = FakeConnection([_candidate()], structure)
    results = PostgresTableKeywordRetriever(connection).search(
        "revenue",
        TableSearchFilters(
            "aapl", "10-K", date(2024, 9, 28), "doc-1", "table-1"
        ),
        5,
    )
    assert results[0].rows[0].cells[0].text == "Revenue"
    assert results[0].rows[0].cells[1].colspan == 1
    sql, params = connection.calls[0]
    assert "document_record.ticker = %s" in sql
    assert "table_record.document_id = %s" in sql
    assert "table_record.table_evidence_id = %s" in sql
    assert "aapl" not in sql and "doc-1" not in sql
    assert params == (
        "revenue",
        "1.0",
        "AAPL",
        "10-K",
        date(2024, 9, 28),
        "doc-1",
        "table-1",
        5,
    )


def test_table_retrieval_is_deterministic_and_rejects_invalid_inputs():
    connection = FakeConnection([_candidate("table-2"), _candidate("table-1")], [])
    retriever = PostgresTableKeywordRetriever(connection)
    first = retriever.search("revenue", limit=2)
    assert [result.table_evidence_id for result in first] == ["table-2", "table-1"]
    assert retriever.search("  ") == []
    with pytest.raises(KeywordRetrievalError):
        retriever.search("revenue", limit=0)
    with pytest.raises(KeywordRetrievalError):
        retriever.search("revenue", TableSearchFilters(table_evidence_id=" "))
