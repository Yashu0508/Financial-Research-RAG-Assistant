"""Read-only cosine retrieval over locally generated narrative embeddings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from app.retrieval.keyword import DEFAULT_RESULT_LIMIT, MAX_RESULT_LIMIT

from .config import SemanticEmbeddingConfiguration
from .embeddings import encode_texts, prepare_embedding_segments, vector_literal


class SemanticRetrievalError(ValueError):
    """Raised for invalid semantic-retrieval inputs or incompatible storage."""


class Cursor(Protocol):
    def execute(self, query: str, params: tuple[object, ...]) -> object: ...
    def fetchall(self) -> list[tuple[Any, ...]]: ...
    def close(self) -> None: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...


@dataclass(frozen=True)
class SemanticSearchFilters:
    ticker: str | None = None
    form_type: str | None = None
    reporting_period_end: date | None = None
    document_id: str | None = None


@dataclass(frozen=True)
class SemanticSearchResult:
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
    similarity: float
    embedding_id: str
    segment_index: int
    character_start: int
    character_end: int
    configuration_hash: str


def _limit(limit: int) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_RESULT_LIMIT:
        raise SemanticRetrievalError(f"limit must be an integer from 1 through {MAX_RESULT_LIMIT}.")
    return limit


def _filters(filters: object) -> SemanticSearchFilters:
    ticker = getattr(filters, "ticker", None)
    form_type = getattr(filters, "form_type", None)
    reporting_period_end = getattr(filters, "reporting_period_end", None)
    document_id = getattr(filters, "document_id", None)
    if ticker:
        ticker = ticker.upper()
        if not ticker.isalpha():
            raise SemanticRetrievalError("ticker must contain alphabetic characters only.")
    if document_id is not None and (not isinstance(document_id, str) or not document_id.strip()):
        raise SemanticRetrievalError("document_id must be a non-empty string when provided.")
    return SemanticSearchFilters(ticker, form_type, reporting_period_end, document_id)


class PostgresSemanticRetriever:
    """Return parent narrative chunks, ranking the best source-preserving segment."""

    def __init__(
        self, connection: Connection, model: Any, configuration: SemanticEmbeddingConfiguration
    ) -> None:
        self.connection = connection
        self.model = model
        self.configuration = configuration

    def search(
        self,
        query: str,
        filters: object = SemanticSearchFilters(),
        limit: int = DEFAULT_RESULT_LIMIT,
    ) -> list[SemanticSearchResult]:
        if not isinstance(query, str):
            raise SemanticRetrievalError("query must be a string.")
        if not query.strip():
            return []
        checked_filters = _filters(filters)
        limit = _limit(limit)
        segments = prepare_embedding_segments(
            "semantic-query", query, self.model.tokenizer, self.configuration
        )
        vectors = encode_texts(
            self.model, [segment.text for segment in segments], self.configuration, 16
        )
        best: dict[str, SemanticSearchResult] = {}
        # A parent chunk can have several stored segments. Over-fetch segment
        # candidates before collapsing them so the public result limit remains
        # a limit on evidence chunks, not on arbitrary child windows.
        candidate_limit = min(400, max(limit, limit * 4))
        for vector in vectors:
            for result in self._search_vector(
                vector_literal(vector), checked_filters, candidate_limit
            ):
                current = best.get(result.chunk_id)
                if current is None or self._sort_key(result) < self._sort_key(current):
                    best[result.chunk_id] = result
        return sorted(best.values(), key=self._sort_key)[:limit]

    @staticmethod
    def _sort_key(result: SemanticSearchResult) -> tuple[float, str, int, int]:
        return (-result.similarity, result.document_id, result.chunk_sequence, result.segment_index)

    def _search_vector(
        self, vector: str, filters: SemanticSearchFilters, limit: int
    ) -> list[SemanticSearchResult]:
        predicates = [
            "s.configuration_hash = %s",
            "s.source_sha256 = d.source_sha256",
            "n.source_sha256 = d.source_sha256",
            "n.validation_status = 'ADMITTED'",
        ]
        params: list[object] = [vector, self.configuration.configuration_hash]
        if filters.ticker is not None:
            predicates.append("d.ticker = %s")
            params.append(filters.ticker)
        if filters.form_type is not None:
            predicates.append("d.form_type = %s")
            params.append(filters.form_type)
        if filters.reporting_period_end is not None:
            predicates.append("d.reporting_period_end = %s")
            params.append(filters.reporting_period_end)
        if filters.document_id is not None:
            predicates.append("n.document_id = %s")
            params.append(filters.document_id)
        params.append(limit)
        sql = f"""
            SELECT n.chunk_id, n.document_id, n.source_sha256, n.text,
                   n.section_heading, n.source_elements, n.chunk_sequence,
                   d.ticker, d.company, d.form_type, d.reporting_period_end,
                   1 - (s.embedding OPERATOR(public.<=>) %s::public.vector) AS similarity,
                   s.embedding_id, s.segment_index, s.character_start, s.character_end,
                   s.configuration_hash
            FROM narrative_embedding_segments AS s
            JOIN narrative_chunks AS n ON n.chunk_id = s.chunk_id
            JOIN registered_documents AS d ON d.document_id = n.document_id
            WHERE {" AND ".join(predicates)}
            ORDER BY similarity DESC, n.document_id ASC, n.chunk_sequence ASC, s.segment_index ASC
            LIMIT %s
        """
        cursor = self.connection.cursor()
        try:
            # pgvector HNSW can return too few filtered candidates at its default
            # ef_search.  The fixed corpus is small, so use the extension's
            # maximum supported probe count for repeatable filtered evaluation.
            cursor.execute("SELECT set_config('hnsw.ef_search', %s, true)", ("1000",))
            cursor.execute(sql, tuple(params))
            return [SemanticSearchResult(*row) for row in cursor.fetchall()]
        finally:
            cursor.close()
