"""Pinned offline cross-encoder reranking for bounded narrative candidates."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any

from app.retrieval.hybrid import HybridRetrievalError, HybridSearchResult

MODEL_ID = "cross-encoder/ms-marco-MiniLM-L6-v2"
MODEL_REVISION = "233902d25c440f23af6f7d6e94d2946bac0bee0a"
MODEL_MAX_SEQUENCE_LENGTH = 512
QUERY_CONTENT_LIMIT = 128
MAX_RERANK_DEPTH = 50


class RerankingError(RuntimeError):
    """Raised when pinned offline reranking cannot be performed safely."""


@dataclass(frozen=True)
class RerankerConfiguration:
    model_id: str
    model_revision: str
    max_sequence_length: int
    query_content_limit: int
    sentence_transformers_version: str
    transformers_version: str
    torch_version: str

    @property
    def configuration_hash(self) -> str:
        return hashlib.sha256(
            json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


def current_reranker_configuration() -> RerankerConfiguration:
    return RerankerConfiguration(
        MODEL_ID,
        MODEL_REVISION,
        MODEL_MAX_SEQUENCE_LENGTH,
        QUERY_CONTENT_LIMIT,
        version("sentence-transformers"),
        version("transformers"),
        version("torch"),
    )


def load_pinned_reranker(cache_dir: Path, configuration: RerankerConfiguration) -> Any:
    if not cache_dir.is_absolute():
        raise RerankingError("SEMANTIC_MODEL_CACHE_DIR must be an absolute path.")
    snapshot = (
        cache_dir
        / "models--cross-encoder--ms-marco-MiniLM-L6-v2"
        / "snapshots"
        / configuration.model_revision
    )
    if not snapshot.is_dir() or any(
        not (snapshot / name).is_file()
        for name in ("config.json", "model.safetensors", "tokenizer.json")
    ):
        raise RerankingError("Pinned reranker assets are unavailable in the local cache.")
    try:
        from sentence_transformers import CrossEncoder

        return CrossEncoder(
            str(snapshot), max_length=configuration.max_sequence_length, local_files_only=True
        )
    except Exception as exc:
        raise RerankingError("Pinned local reranker could not be loaded offline.") from exc


@dataclass(frozen=True)
class RerankedSearchResult:
    candidate: HybridSearchResult
    reranker_score: float
    reranked_window_count: int

    @property
    def chunk_id(self) -> str:
        return self.candidate.chunk_id


def _windows(tokenizer: Any, text: str, capacity: int) -> list[str]:
    offsets = tokenizer(
        text, add_special_tokens=False, return_offsets_mapping=True, truncation=False
    )["offset_mapping"]
    return [
        text[part[0][0] : part[-1][1]]
        for start in range(0, len(offsets), capacity)
        if (part := [(int(a), int(b)) for a, b in offsets[start : start + capacity] if b > a])
    ]


class BoundedCrossEncoderReranker:
    def __init__(
        self, model: Any, configuration: RerankerConfiguration, *, batch_size: int = 8
    ) -> None:
        if (
            not isinstance(batch_size, int)
            or isinstance(batch_size, bool)
            or not 1 <= batch_size <= 32
        ):
            raise RerankingError("Reranker batch size must be an integer from 1 through 32.")
        self.model, self.configuration, self.batch_size = model, configuration, batch_size

    def rerank(
        self, query: str, candidates: list[HybridSearchResult], depth: int
    ) -> list[RerankedSearchResult]:
        if not isinstance(query, str) or not query.strip():
            raise RerankingError("Reranker query must be non-empty text.")
        if (
            not isinstance(depth, int)
            or isinstance(depth, bool)
            or not 1 <= depth <= MAX_RERANK_DEPTH
        ):
            raise RerankingError("rerank_depth must be an integer from 1 through 50.")
        if len({item.chunk_id for item in candidates}) != len(candidates):
            raise RerankingError("Hybrid candidates must have unique chunk IDs.")
        query_ids = self.model.tokenizer(query, add_special_tokens=False, truncation=False)[
            "input_ids"
        ]
        if len(query_ids) > self.configuration.query_content_limit:
            raise RerankingError("Query exceeds the reranker's documented content-token limit.")
        selected, trailing = candidates[:depth], candidates[depth:]
        capacity = self.configuration.max_sequence_length - len(query_ids) - 3
        if selected and capacity <= 0:
            raise RerankingError("Query leaves no token capacity for narrative evidence.")
        pairs: list[tuple[str, str]] = []
        mapping: list[int] = []
        counts: list[int] = []
        for index, candidate in enumerate(selected):
            windows = _windows(self.model.tokenizer, candidate.text, capacity)
            if not windows:
                raise RerankingError("Candidate text cannot be represented for reranking.")
            pairs.extend((query, window) for window in windows)
            mapping.extend([index] * len(windows))
            counts.append(len(windows))
        scores = [
            float(value)
            for value in self.model.predict(
                pairs, batch_size=self.batch_size, show_progress_bar=False
            )
        ]
        if len(scores) != len(pairs) or not all(math.isfinite(value) for value in scores):
            raise RerankingError("Reranker returned malformed scores.")
        best = [-math.inf] * len(selected)
        for index, score in zip(mapping, scores, strict=True):
            best[index] = max(best[index], score)
        ranked = [
            RerankedSearchResult(item, best[index], counts[index])
            for index, item in enumerate(selected)
        ]
        ranked.sort(
            key=lambda item: (-item.reranker_score, -item.candidate.rrf_score, item.chunk_id)
        )
        return ranked + [RerankedSearchResult(item, math.nan, 0) for item in trailing]


class HybridRerankingRetriever:
    def __init__(
        self,
        hybrid: Any,
        reranker: BoundedCrossEncoderReranker,
        *,
        candidate_depth: int = 50,
        rerank_depth: int = 20,
    ) -> None:
        if not isinstance(candidate_depth, int) or not 1 <= candidate_depth <= 100:
            raise HybridRetrievalError("candidate_depth must be an integer from 1 through 100.")
        if (
            not isinstance(rerank_depth, int)
            or not 1 <= rerank_depth <= MAX_RERANK_DEPTH
            or rerank_depth > candidate_depth
        ):
            raise HybridRetrievalError(
                "rerank_depth must be 1 through 50 and no greater than candidate_depth."
            )
        self.hybrid, self.reranker, self.candidate_depth, self.rerank_depth = (
            hybrid,
            reranker,
            candidate_depth,
            rerank_depth,
        )

    def search(self, query: str, filters: Any, limit: int) -> list[RerankedSearchResult]:
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise HybridRetrievalError("limit must be an integer from 1 through 100.")
        candidates = self.hybrid.search(query, filters, max(limit, self.candidate_depth))
        return self.reranker.rerank(query, candidates, min(self.rerank_depth, len(candidates)))[
            :limit
        ]
