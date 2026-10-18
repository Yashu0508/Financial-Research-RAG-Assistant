"""RRF fusion contracts independent of PostgreSQL/model execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from app.retrieval.hybrid import (
    HybridBranchError,
    HybridRetrievalError,
    ReciprocalRankFusionRetriever,
)


@dataclass(frozen=True)
class Candidate:
    chunk_id: str
    document_id: str = "doc"
    source_sha256: str = "a" * 64
    text: str = "text"
    section_heading: dict = None  # type: ignore[assignment]
    source_elements: list = None  # type: ignore[assignment]
    chunk_sequence: int = 0
    ticker: str = "MSFT"
    company: str = "Microsoft"
    form_type: str = "10-K"
    reporting_period_end: date = date(2024, 6, 30)

    def __post_init__(self):
        object.__setattr__(self, "section_heading", self.section_heading or {"text": "Heading"})
        object.__setattr__(
            self, "source_elements", self.source_elements or [{"source_locator": "x"}]
        )


class Retriever:
    def __init__(self, values):
        self.values = values
        self.calls = []

    def search(self, query, filters, limit):
        self.calls.append((query, filters, limit))
        if isinstance(self.values, Exception):
            raise self.values
        return self.values


def test_rrf_deduplicates_and_preserves_branch_ranks_and_provenance():
    keyword = Retriever([Candidate("a", chunk_sequence=2), Candidate("b", chunk_sequence=1)])
    semantic = Retriever([Candidate("b", chunk_sequence=1), Candidate("c", chunk_sequence=0)])
    results = ReciprocalRankFusionRetriever(keyword, semantic, branch_depth=2).search(
        "revenue", limit=3
    )
    assert [item.chunk_id for item in results] == ["b", "a", "c"]
    assert results[0].keyword_rank == 2 and results[0].semantic_rank == 1
    assert results[0].rrf_score == pytest.approx(1 / 62 + 1 / 61)
    assert results[0].source_elements == [{"source_locator": "x"}]
    assert keyword.calls[0][2] == semantic.calls[0][2] == 2


def test_empty_branches_ties_and_limits_are_deterministic():
    results = ReciprocalRankFusionRetriever(
        Retriever([Candidate("z", document_id="z")]),
        Retriever([Candidate("a", document_id="a")]),
        branch_depth=2,
    ).search("risk", limit=2)
    assert [item.chunk_id for item in results] == ["a", "z"]
    assert ReciprocalRankFusionRetriever(Retriever([]), Retriever([])).search(" ") == []
    with pytest.raises(HybridRetrievalError):
        ReciprocalRankFusionRetriever(Retriever([]), Retriever([]), branch_depth=0)
    with pytest.raises(HybridRetrievalError):
        ReciprocalRankFusionRetriever(Retriever([]), Retriever([]), rrf_constant=0)


def test_failures_and_malformed_or_conflicting_provenance_are_explicit():
    with pytest.raises(HybridBranchError, match="Keyword"):
        ReciprocalRankFusionRetriever(Retriever(RuntimeError("bad")), Retriever([])).search("q")
    with pytest.raises(HybridRetrievalError, match="malformed"):
        ReciprocalRankFusionRetriever(Retriever([object()]), Retriever([])).search("q")
    with pytest.raises(HybridRetrievalError, match="disagree"):
        ReciprocalRankFusionRetriever(
            Retriever([Candidate("same", text="one")]), Retriever([Candidate("same", text="two")])
        ).search("q")
