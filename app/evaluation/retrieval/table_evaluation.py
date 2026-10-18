"""Metrics for the separate structured-table retrieval benchmark."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.evaluation.retrieval.table_judgments import (
    ANSWERABLE,
    TableJudgmentCase,
    load_table_judgments,
)
from app.retrieval.table import TableKeywordSearchResult, TableSearchFilters

TABLE_EVALUATED_RETRIEVAL_MODE = "postgres_english_financial_table_keyword_v1"


class TableRetriever(Protocol):
    def search(
        self, query: str, filters: TableSearchFilters, limit: int
    ) -> list[TableKeywordSearchResult]: ...


@dataclass(frozen=True)
class TableEvaluationCaseResult:
    case_id: str
    status: str
    returned_table_evidence_ids: tuple[str, ...]
    relevant_at_5: int
    relevant_at_10: int
    first_relevant_rank: int | None


@dataclass(frozen=True)
class TableEvaluationReport:
    dataset_id: str
    dataset_version: str
    dataset_sha256: str
    evaluated_retrieval_mode: str
    answerable_case_count: int
    unanswerable_case_count: int
    recall_at_5: float
    recall_at_10: float
    precision_at_5: float
    mrr: float
    case_results: tuple[TableEvaluationCaseResult, ...]


def _filters(case: TableJudgmentCase) -> TableSearchFilters:
    return TableSearchFilters(
        ticker=case.filters.ticker,
        form_type=case.filters.form_type,
        reporting_period_end=case.filters.reporting_period_end,
    )


def evaluate_table_keyword_retriever(
    retriever: TableRetriever, dataset_path: Path
) -> TableEvaluationReport:
    """Evaluate answerable table labels; unanswerable cases remain separate."""

    dataset_id, version, cases = load_table_judgments(dataset_path)
    results: list[TableEvaluationCaseResult] = []
    answerable: list[TableEvaluationCaseResult] = []
    for case in cases:
        returned = retriever.search(case.question, _filters(case), 10)
        identifiers = tuple(result.table_evidence_id for result in returned)
        relevant = {item.table_evidence_id for item in case.expected_tables}
        ranks = [index for index, value in enumerate(identifiers, 1) if value in relevant]
        result = TableEvaluationCaseResult(
            case.case_id,
            case.status,
            identifiers,
            sum(value in relevant for value in identifiers[:5]),
            sum(value in relevant for value in identifiers[:10]),
            ranks[0] if ranks else None,
        )
        results.append(result)
        if case.status == ANSWERABLE:
            answerable.append(result)
    if not answerable:
        raise ValueError("Table evaluation requires at least one answerable case.")
    count = len(answerable)
    dataset_hash = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    return TableEvaluationReport(
        dataset_id,
        version,
        dataset_hash,
        TABLE_EVALUATED_RETRIEVAL_MODE,
        count,
        len(cases) - count,
        sum(item.relevant_at_5 > 0 for item in answerable) / count,
        sum(item.relevant_at_10 > 0 for item in answerable) / count,
        sum(item.relevant_at_5 / 5 for item in answerable) / count,
        sum(1 / item.first_relevant_rank for item in answerable if item.first_relevant_rank)
        / count,
        tuple(results),
    )
