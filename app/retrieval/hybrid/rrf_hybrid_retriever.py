"""Deterministic Reciprocal Rank Fusion for narrative keyword and semantic results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.retrieval.keyword import DEFAULT_RESULT_LIMIT, MAX_RESULT_LIMIT, KeywordSearchFilters

RRF_CONSTANT = 60
DEFAULT_BRANCH_DEPTH = 50


class HybridRetrievalError(ValueError):
    """Raised when fusion inputs/configuration cannot produce trustworthy evidence."""


class HybridBranchError(RuntimeError):
    """Raised when one source retriever fails; fusion must not mask the failure."""


class NarrativeRetriever(Protocol):
    def search(self, query: str, filters: KeywordSearchFilters, limit: int) -> list[Any]: ...


@dataclass(frozen=True)
class HybridSearchResult:
    """Fused parent chunk retaining original provenance and branch ranks."""

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
    reporting_period_end: object
    rrf_score: float
    keyword_rank: int | None
    semantic_rank: int | None


def _check_limit(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_RESULT_LIMIT:
        raise HybridRetrievalError(f"{name} must be an integer from 1 through {MAX_RESULT_LIMIT}.")
    return value


def _candidate_from(result: Any, *, rank: int) -> dict[str, Any]:
    required = (
        "chunk_id",
        "document_id",
        "source_sha256",
        "text",
        "section_heading",
        "source_elements",
        "chunk_sequence",
        "ticker",
        "company",
        "form_type",
        "reporting_period_end",
    )
    missing = [field for field in required if not hasattr(result, field)]
    if missing or not isinstance(getattr(result, "chunk_id", None), str):
        raise HybridRetrievalError("Retriever returned a malformed narrative evidence result.")
    return {field: getattr(result, field) for field in required} | {"rank": rank}


class ReciprocalRankFusionRetriever:
    """Fuse independent narrative retrievers without altering either source.

    Score: ``sum(1 / (RRF_CONSTANT + rank))`` for each branch appearance. Ranks
    are one-based. Equal scores tie-break on stable document/chunk positions.
    """

    def __init__(
        self,
        keyword_retriever: NarrativeRetriever,
        semantic_retriever: NarrativeRetriever,
        *,
        branch_depth: int = DEFAULT_BRANCH_DEPTH,
        rrf_constant: int = RRF_CONSTANT,
    ) -> None:
        self.keyword_retriever = keyword_retriever
        self.semantic_retriever = semantic_retriever
        self.branch_depth = _check_limit(branch_depth, "branch_depth")
        if isinstance(rrf_constant, bool) or not isinstance(rrf_constant, int) or rrf_constant < 1:
            raise HybridRetrievalError("rrf_constant must be a positive integer.")
        self.rrf_constant = rrf_constant

    def search(
        self,
        query: str,
        filters: KeywordSearchFilters = KeywordSearchFilters(),
        limit: int = DEFAULT_RESULT_LIMIT,
    ) -> list[HybridSearchResult]:
        if not isinstance(query, str):
            raise HybridRetrievalError("query must be a string.")
        if not query.strip():
            return []
        limit = _check_limit(limit, "limit")
        try:
            keyword_results = self.keyword_retriever.search(query, filters, self.branch_depth)
        except Exception as exc:
            raise HybridBranchError(
                "Keyword retrieval failed; no fused result was returned."
            ) from exc
        try:
            semantic_results = self.semantic_retriever.search(query, filters, self.branch_depth)
        except Exception as exc:
            raise HybridBranchError(
                "Semantic retrieval failed; no fused result was returned."
            ) from exc
        fused: dict[str, dict[str, Any]] = {}
        for branch, branch_results in (
            ("keyword", keyword_results),
            ("semantic", semantic_results),
        ):
            if not isinstance(branch_results, list):
                raise HybridRetrievalError("Retriever must return a list of narrative results.")
            for rank, raw in enumerate(branch_results, start=1):
                candidate = _candidate_from(raw, rank=rank)
                current = fused.get(candidate["chunk_id"])
                if current is None:
                    current = candidate | {
                        "rrf_score": 0.0,
                        "keyword_rank": None,
                        "semantic_rank": None,
                    }
                    fused[candidate["chunk_id"]] = current
                else:
                    for field in ("document_id", "source_sha256", "text"):
                        if current[field] != candidate[field]:
                            raise HybridRetrievalError(
                                "Retrievers disagree about immutable provenance for one chunk ID."
                            )
                rank_field = f"{branch}_rank"
                if current[rank_field] is None:
                    current[rank_field] = rank
                    current["rrf_score"] += 1 / (self.rrf_constant + rank)
        results = [
            HybridSearchResult(
                item["chunk_id"],
                item["document_id"],
                item["source_sha256"],
                item["text"],
                item["section_heading"],
                item["source_elements"],
                item["chunk_sequence"],
                item["ticker"],
                item["company"],
                item["form_type"],
                item["reporting_period_end"],
                item["rrf_score"],
                item["keyword_rank"],
                item["semantic_rank"],
            )
            for item in fused.values()
        ]
        return sorted(
            results,
            key=lambda item: (
                -item.rrf_score,
                item.document_id,
                item.chunk_sequence,
                item.chunk_id,
            ),
        )[:limit]
