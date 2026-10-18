"""Unit tests for PostgreSQL keyword-retrieval input and result contracts."""

from __future__ import annotations

from datetime import date

import pytest

from app.retrieval.keyword import (
    KeywordRetrievalError,
    KeywordSearchFilters,
    PostgresKeywordRetriever,
)


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.sql = ""
        self.params = ()
        self.closed = False

    def execute(self, query, params):
        self.sql = query
        self.params = params

    def fetchall(self):
        return self.rows

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, rows):
        self.cursor_value = FakeCursor(rows)

    def cursor(self):
        return self.cursor_value


def test_keyword_result_preserves_provenance_and_parameterizes_query():
    row = (
        "chunk-1",
        "aapl-2024-10k",
        "a" * 64,
        "Revenue increased.",
        {"text": "Revenue"},
        [{"source_locator": "element:1:p"}],
        3,
        "AAPL",
        "Apple Inc.",
        "10-K",
        date(2024, 9, 28),
        0.42,
    )
    connection = FakeConnection([row])
    result = PostgresKeywordRetriever(connection).search(
        "revenue; drop table narrative_chunks", KeywordSearchFilters(ticker="aapl"), 2
    )
    assert result[0].chunk_id == "chunk-1"
    assert result[0].section_heading == {"text": "Revenue"}
    assert "revenue; drop" not in connection.cursor_value.sql
    assert "n.validation_status = 'ADMITTED'" in connection.cursor_value.sql
    assert "n.source_sha256 = d.source_sha256" in connection.cursor_value.sql
    assert connection.cursor_value.params == ("revenue; drop table narrative_chunks", "AAPL", 2)
    assert connection.cursor_value.closed


def test_blank_query_returns_no_results_without_database_access():
    connection = FakeConnection([])
    assert PostgresKeywordRetriever(connection).search("   ") == []
    assert connection.cursor_value.sql == ""


@pytest.mark.parametrize("limit", [0, 101, True, "5"])
def test_invalid_limit_is_rejected(limit):
    with pytest.raises(KeywordRetrievalError):
        PostgresKeywordRetriever(FakeConnection([])).search("revenue", limit=limit)


def test_invalid_ticker_is_rejected():
    with pytest.raises(KeywordRetrievalError):
        PostgresKeywordRetriever(FakeConnection([])).search(
            "revenue", KeywordSearchFilters(ticker="MSFT; DROP")
        )
