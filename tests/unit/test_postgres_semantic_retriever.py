"""SQL/result contracts for semantic retrieval without a live database."""

from __future__ import annotations

from datetime import date

import pytest

from app.retrieval.semantic.config import SemanticEmbeddingConfiguration
from app.retrieval.semantic.postgres_semantic_retriever import (
    PostgresSemanticRetriever,
    SemanticRetrievalError,
    SemanticSearchFilters,
)


class Tokenizer:
    def __call__(self, text, **kwargs):
        return {"input_ids": [1], "offset_mapping": [(0, len(text))]}

    def num_special_tokens_to_add(self, pair=False):
        return 2


class Model:
    tokenizer = Tokenizer()

    def encode(self, texts, **kwargs):
        return [[0.5, 0.5, 0.5, 0.5] for _ in texts]


class Cursor:
    def __init__(self, rows):
        self.rows, self.sql, self.params = rows, "", ()

    def execute(self, sql, params):
        self.sql, self.params = sql, params

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class Connection:
    def __init__(self, rows):
        self.cursor_value = Cursor(rows)

    def cursor(self):
        return self.cursor_value


def _configuration():
    return SemanticEmbeddingConfiguration("model", "rev", 4, True, 4, "policy", "a", "b", "c", "d")


def test_query_is_parameterized_and_result_retains_provenance():
    row = (
        "chunk",
        "doc",
        "a" * 64,
        "text",
        {},
        [{"source_locator": "element:1:p"}],
        0,
        "AAPL",
        "Apple",
        "10-K",
        date(2024, 9, 28),
        0.9,
        "embedding",
        0,
        0,
        4,
        "b" * 64,
    )
    connection = Connection([row])
    result = PostgresSemanticRetriever(connection, Model(), _configuration()).search(
        "revenue; DROP TABLE", SemanticSearchFilters(ticker="aapl", document_id="doc"), 2
    )
    assert result[0].chunk_id == "chunk"
    assert "DROP TABLE" not in connection.cursor_value.sql
    assert "OPERATOR(public.<=>)" in connection.cursor_value.sql
    assert connection.cursor_value.params[1] == _configuration().configuration_hash
    assert connection.cursor_value.params[-1] == 8  # segment over-fetch before parent aggregation


def test_blank_query_and_invalid_filters_or_limits_are_rejected():
    connection = Connection([])
    retriever = PostgresSemanticRetriever(connection, Model(), _configuration())
    assert retriever.search(" ") == []
    with pytest.raises(SemanticRetrievalError):
        retriever.search("x", SemanticSearchFilters(ticker="AAPL;DROP"))
    with pytest.raises(SemanticRetrievalError):
        retriever.search("x", limit=0)
