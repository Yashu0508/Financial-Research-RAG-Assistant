"""Read-only PostgreSQL full-text retrieval for admitted narrative evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

MAX_RESULT_LIMIT = 100
DEFAULT_RESULT_LIMIT = 10
TEXT_SEARCH_CONFIGURATION = "english"


class KeywordRetrievalError(ValueError):
    """Raised for invalid baseline keyword-retrieval inputs."""


class Cursor(Protocol):
    def execute(self, query: str, params: tuple[object, ...]) -> object: ...
    def fetchall(self) -> list[tuple[Any, ...]]: ...
    def close(self) -> None: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...


@dataclass(frozen=True)
class KeywordSearchFilters:
    """Optional registration metadata filters supported by the current schema."""

    ticker: str | None = None
    form_type: str | None = None
    reporting_period_end: date | None = None


@dataclass(frozen=True)
class KeywordSearchResult:
    """Narrative evidence candidate with provenance required by future citation work."""

    chunk_id: str
    document_id: str
    source_sha256: str
    text: str
    section_heading: dict[str, Any]
    source_elements: list[dict[str, Any]]
    chunk_sequence: int
    ticker: str
    company: str
    form_type: str
    reporting_period_end: date
    rank: float


def _validate_limit(limit: int) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_RESULT_LIMIT:
        raise KeywordRetrievalError(f"limit must be an integer from 1 through {MAX_RESULT_LIMIT}.")
    return limit


def _validate_filters(filters: KeywordSearchFilters) -> KeywordSearchFilters:
    ticker = filters.ticker.upper() if filters.ticker else None
    if ticker is not None and not ticker.isalpha():
        raise KeywordRetrievalError("ticker must contain alphabetic characters only.")
    return KeywordSearchFilters(ticker, filters.form_type, filters.reporting_period_end)


class PostgresKeywordRetriever:
    """Use PostgreSQL English FTS and rank coverage without mutating corpus data."""

    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def search(
        self,
        query: str,
        filters: KeywordSearchFilters = KeywordSearchFilters(),
        limit: int = DEFAULT_RESULT_LIMIT,
    ) -> list[KeywordSearchResult]:
        """Return ranked narrative evidence; blank queries intentionally return no candidates."""

        if not isinstance(query, str):
            raise KeywordRetrievalError("query must be a string.")
        normalized_query = query.strip()
        if not normalized_query:
            return []
        filters = _validate_filters(filters)
        limit = _validate_limit(limit)
        predicates = [
            "to_tsvector('english', n.text) @@ query.query",
            "n.validation_status = 'ADMITTED'",
            "n.source_sha256 = d.source_sha256",
        ]
        params: list[object] = [normalized_query]
        if filters.ticker is not None:
            predicates.append("d.ticker = %s")
            params.append(filters.ticker)
        if filters.form_type is not None:
            predicates.append("d.form_type = %s")
            params.append(filters.form_type)
        if filters.reporting_period_end is not None:
            predicates.append("d.reporting_period_end = %s")
            params.append(filters.reporting_period_end)
        params.append(limit)
        sql = f"""
            WITH query AS (
                SELECT websearch_to_tsquery('english', %s) AS query
            )
            SELECT n.chunk_id, n.document_id, n.source_sha256, n.text,
                   n.section_heading, n.source_elements, n.chunk_sequence,
                   d.ticker, d.company, d.form_type, d.reporting_period_end,
                   ts_rank_cd(to_tsvector('english', n.text), query.query) AS rank
            FROM narrative_chunks AS n
            JOIN registered_documents AS d ON d.document_id = n.document_id
            CROSS JOIN query
            WHERE {" AND ".join(predicates)}
            ORDER BY rank DESC, n.document_id ASC, n.chunk_sequence ASC
            LIMIT %s
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute(sql, tuple(params))
            return [KeywordSearchResult(*row) for row in cursor.fetchall()]
        finally:
            cursor.close()
