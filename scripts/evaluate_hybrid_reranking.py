"""Evaluate bounded pinned-local reranking over the RRF narrative candidate set."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    from app.core.config import get_settings
    from app.evaluation.retrieval.keyword_evaluation import (
        evaluate_keyword_retriever,
        validate_keyword_evaluation_filters,
        validate_keyword_evaluation_references,
    )
    from app.evaluation.retrieval.regression_gates import assert_reranking_v2_gate
    from app.retrieval.hybrid import ReciprocalRankFusionRetriever
    from app.retrieval.keyword import PostgresKeywordRetriever
    from app.retrieval.reranking import (
        BoundedCrossEncoderReranker,
        HybridRerankingRetriever,
        current_reranker_configuration,
        load_pinned_reranker,
    )
    from app.retrieval.semantic import (
        PostgresSemanticRetriever,
        current_embedding_configuration,
        load_pinned_model,
    )
    from app.storage.development import (
        development_target_from_settings,
        prepare_development_connection,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-depth", type=int, default=50)
    parser.add_argument("--rerank-depth", type=int, default=20)
    args = parser.parse_args(argv)
    settings = get_settings()
    dataset = ROOT / "data/evaluation/keyword_retrieval.v2.json"
    started = time.perf_counter()
    try:
        target = development_target_from_settings(settings)
        if not settings.semantic_model_cache_dir:
            raise ValueError("SEMANTIC_MODEL_CACHE_DIR must be configured.")
        cache = Path(settings.semantic_model_cache_dir)
        ec = current_embedding_configuration()
        em = load_pinned_model(cache, ec)
        rc = current_reranker_configuration()
        rm = load_pinned_reranker(cache, rc)
        validate_keyword_evaluation_references(dataset, ROOT / "data/processed/sec_evidence/v1")
        validate_keyword_evaluation_filters(dataset, ROOT / "data/manifests/sec_documents.v1.json")
        import psycopg

        with psycopg.connect(settings.database_url) as connection:
            prepare_development_connection(connection, target, create_schema=False)
            hybrid = ReciprocalRankFusionRetriever(
                PostgresKeywordRetriever(connection),
                PostgresSemanticRetriever(connection, em, ec),
                branch_depth=args.candidate_depth,
            )
            reranked = HybridRerankingRetriever(
                hybrid,
                BoundedCrossEncoderReranker(rm, rc),
                candidate_depth=args.candidate_depth,
                rerank_depth=args.rerank_depth,
            )
            report = evaluate_keyword_retriever(
                reranked, dataset, retrieval_mode="rrf_cross_encoder_narrative_v1"
            )
    except Exception as exc:
        print(f"Reranking evaluation failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    try:
        assert_reranking_v2_gate(report)
    except ValueError as exc:
        print(f"Reranking regression gate failed: {exc}", file=sys.stderr)
        return 3
    payload = asdict(report)
    payload.update(
        {
            "candidate_depth": reranked.candidate_depth,
            "rerank_depth": reranked.rerank_depth,
            "reranker_configuration": asdict(rc),
            "reranker_configuration_hash": rc.configuration_hash,
            "elapsed_seconds": time.perf_counter() - started,
            "regression_gate": "passed",
        }
    )
    print(json.dumps(payload, default=str, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
