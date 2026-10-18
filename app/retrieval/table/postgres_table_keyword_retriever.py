"""Read-only PostgreSQL keyword retrieval for admitted financial-table evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from app.retrieval.keyword import MAX_RESULT_LIMIT, KeywordRetrievalError
from app.storage.table_search_projection import TABLE_SEARCH_PROJECTION_VERSION

TABLE_KEYWORD_RETRIEVAL_MODE = "postgres_english_financial_table_keyword_v1"
TEXT_SEARCH_CONFIGURATION = "english"


def _or_query(value: str) -> str:
    """Produce a parameterized lexical OR query from natural-language tokens."""

    return " | ".join(re.findall(r"[A-Za-z0-9]+", value))


class Cursor(Protocol):
    def execute(self, query: str, params: tuple[object, ...]) -> object: ...
    def fetchall(self) -> list[tuple[Any, ...]]: ...
    def close(self) -> None: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...


@dataclass(frozen=True)
class TableSearchFilters:
    """Exact registered-document and stable-table filters for table retrieval."""

    ticker: str | None = None
    form_type: str | None = None
    reporting_period_end: date | None = None
    document_id: str | None = None
    table_evidence_id: str | None = None


@dataclass(frozen=True)
class TableKeywordCell:
    cell_id: str
    cell_index: int
    source_locator: str
    cell_kind: str
    text: str
    rowspan: int
    colspan: int


@dataclass(frozen=True)
class TableKeywordRow:
    row_index: int
    source_locator: str
    cells: tuple[TableKeywordCell, ...]


@dataclass(frozen=True)
class TableKeywordSearchResult:
    """Structured table candidate; raw cells remain un-interpreted evidence."""

    table_evidence_id: str
    document_id: str
    source_sha256: str
    parser_table_id: str
    original_html_table_index: int
    source_locator: str
    caption: str | None
    preceding_heading: dict[str, Any] | None
    unit_hints: list[Any]
    period_header_text: list[str]
    header_association_status: str
    table_warnings: list[Any]
    inherited_source_warnings: list[Any]
    parser_version: str
    parser_configuration_hash: str
    chunking_version: str
    chunking_configuration_hash: str
    validation_status: str
    ticker: str
    company: str
    form_type: str
    reporting_period_end: date
    rank: float
    rows: tuple[TableKeywordRow, ...]


def _validate_filters(filters: TableSearchFilters) -> TableSearchFilters:
    ticker = filters.ticker.upper() if filters.ticker else None
    if ticker is not None and not ticker.isalpha():
        raise KeywordRetrievalError("ticker must contain alphabetic characters only.")
    for value, name in (
        (filters.document_id, "document_id"),
        (filters.table_evidence_id, "table_evidence_id"),
    ):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise KeywordRetrievalError(f"{name} must be a non-empty string when provided.")
    return TableSearchFilters(
        ticker,
        filters.form_type,
        filters.reporting_period_end,
        filters.document_id.strip() if filters.document_id else None,
        filters.table_evidence_id.strip() if filters.table_evidence_id else None,
    )


class PostgresTableKeywordRetriever:
    """Rank only admitted, source-consistent tables and return their raw structure."""

    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def search(
        self,
        query: str,
        filters: TableSearchFilters = TableSearchFilters(),
        limit: int = 10,
    ) -> list[TableKeywordSearchResult]:
        if not isinstance(query, str):
            raise KeywordRetrievalError("query must be a string.")
        query = query.strip()
        if not query:
            return []
        lexical_query = _or_query(query)
        if not lexical_query:
            return []
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= MAX_RESULT_LIMIT
        ):
            raise KeywordRetrievalError(
                f"limit must be an integer from 1 through {MAX_RESULT_LIMIT}."
            )
        filters = _validate_filters(filters)
        predicates = [
            "to_tsvector('english', projection.search_text) @@ search_query.query",
            "table_record.validation_status = 'ADMITTED'",
            "document_record.source_sha256 = table_record.source_sha256",
            "projection.document_id = table_record.document_id",
            "projection.source_sha256 = table_record.source_sha256",
            "projection.projection_version = %s",
        ]
        params: list[object] = [lexical_query, TABLE_SEARCH_PROJECTION_VERSION]
        for predicate, value in (
            ("document_record.ticker = %s", filters.ticker),
            ("document_record.form_type = %s", filters.form_type),
            ("document_record.reporting_period_end = %s", filters.reporting_period_end),
            ("table_record.document_id = %s", filters.document_id),
            ("table_record.table_evidence_id = %s", filters.table_evidence_id),
        ):
            if value is not None:
                predicates.append(predicate)
                params.append(value)
        params.append(limit)
        sql = f"""
            WITH search_query AS (
                SELECT to_tsquery('english', %s) AS query
            )
            SELECT table_record.table_evidence_id, table_record.document_id,
                   table_record.source_sha256, table_record.parser_table_id,
                   table_record.original_html_table_index, table_record.source_locator,
                   table_record.caption, table_record.preceding_heading,
                   table_record.unit_hints, table_record.period_header_text,
                   table_record.header_association_status, table_record.table_warnings,
                   table_record.inherited_source_warnings, table_record.parser_version,
                   table_record.parser_configuration_hash, table_record.chunking_version,
                   table_record.chunking_configuration_hash, table_record.validation_status,
                   document_record.ticker, document_record.company, document_record.form_type,
                   document_record.reporting_period_end,
                   ts_rank_cd(
                       to_tsvector('english', projection.search_text), search_query.query
                   ) AS rank
            FROM financial_table_search_documents AS projection
            JOIN financial_table_evidence AS table_record
              ON table_record.table_evidence_id = projection.table_evidence_id
            JOIN registered_documents AS document_record
              ON document_record.document_id = table_record.document_id
            CROSS JOIN search_query
            WHERE {" AND ".join(predicates)}
            ORDER BY rank DESC, table_record.document_id ASC,
                     table_record.original_html_table_index ASC,
                     table_record.table_evidence_id ASC
            LIMIT %s
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute(sql, tuple(params))
            candidates = cursor.fetchall()
        finally:
            cursor.close()
        rows_by_table = self._rows_for([candidate[0] for candidate in candidates])
        return [
            TableKeywordSearchResult(*candidate, rows_by_table.get(candidate[0], ()))
            for candidate in candidates
        ]

    def _rows_for(self, table_ids: list[str]) -> dict[str, tuple[TableKeywordRow, ...]]:
        if not table_ids:
            return {}
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                "SELECT row_record.table_evidence_id, row_record.row_index, "
                "row_record.source_locator, cell.cell_id, cell.cell_index, "
                "cell.source_locator, cell.cell_kind, cell.text, cell.rowspan, cell.colspan "
                "FROM financial_table_rows AS row_record "
                "JOIN financial_table_cells AS cell ON cell.table_evidence_id = "
                "row_record.table_evidence_id AND cell.row_index = row_record.row_index "
                "WHERE row_record.table_evidence_id = ANY(%s) "
                "ORDER BY row_record.table_evidence_id, row_record.row_index, cell.cell_index",
                (table_ids,),
            )
            records = cursor.fetchall()
        finally:
            cursor.close()
        grouped: dict[str, dict[int, tuple[str, list[TableKeywordCell]]]] = {}
        for record in records:
            table_id, row_index, row_locator, *cell_record = record
            cell = TableKeywordCell(*cell_record)
            row = grouped.setdefault(table_id, {}).setdefault(row_index, (row_locator, []))
            row[1].append(cell)
        return {
            table_id: tuple(
                TableKeywordRow(row_index, locator, tuple(cells))
                for row_index, (locator, cells) in sorted(rows.items())
            )
            for table_id, rows in grouped.items()
        }
