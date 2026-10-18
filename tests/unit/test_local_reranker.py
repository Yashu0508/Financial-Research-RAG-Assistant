from __future__ import annotations

from datetime import date

import pytest

from app.retrieval.hybrid import HybridSearchResult
from app.retrieval.reranking import (
    BoundedCrossEncoderReranker,
    RerankerConfiguration,
    RerankingError,
)


class Tokenizer:
    def __call__(self, text, **kwargs):
        return {
            "input_ids": list(range(len(text.split()))),
            "offset_mapping": [(i, i + 1) for i in range(len(text.split()))],
        }


class Model:
    tokenizer = Tokenizer()

    def predict(self, pairs, **kwargs):
        return [float(index) for index, _ in enumerate(pairs)]


def config():
    return RerankerConfiguration("m", "r", 8, 4, "s", "t", "p")


def candidate(value, seq=0):
    return HybridSearchResult(
        value,
        "doc",
        "a" * 64,
        value,
        {},
        [],
        seq,
        "MSFT",
        "Microsoft",
        "10-K",
        date(2024, 6, 30),
        1.0,
        None,
        1,
    )


def test_bounded_reranking_preserves_tail_and_scores():
    out = BoundedCrossEncoderReranker(Model(), config()).rerank(
        "q", [candidate("a"), candidate("longer", 1), candidate("tail", 2)], 2
    )
    assert [x.chunk_id for x in out] == ["longer", "a", "tail"]
    assert out[2].reranked_window_count == 0


def test_invalid_depth_duplicate_and_long_query_fail():
    r = BoundedCrossEncoderReranker(Model(), config())
    with pytest.raises(RerankingError):
        r.rerank("q", [candidate("a")], 0)
    with pytest.raises(RerankingError):
        r.rerank("q", [candidate("a"), candidate("a")], 1)
    with pytest.raises(RerankingError):
        r.rerank("a b c d e", [candidate("a")], 1)
