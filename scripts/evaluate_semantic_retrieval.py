"""Evaluate local semantic narrative retrieval against preserved v2 judgments."""

from __future__ import annotations

import argparse
import json
import sys
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
    from app.retrieval.semantic import (
        PostgresSemanticRetriever,
        current_embedding_configuration,
        load_pinned_model,
    )
    from app.storage.development import (
        DevelopmentDatabaseError,
        development_target_from_settings,
        prepare_development_connection,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=Path("data/evaluation/keyword_retrieval.v2.json")
    )
    args = parser.parse_args(argv)
    settings = get_settings()
    dataset = args.dataset if args.dataset.is_absolute() else ROOT / args.dataset
    try:
        target = development_target_from_settings(settings)
        if not settings.semantic_model_cache_dir:
            raise ValueError("SEMANTIC_MODEL_CACHE_DIR must be configured.")
        configuration = current_embedding_configuration()
        model = load_pinned_model(Path(settings.semantic_model_cache_dir), configuration)
        validate_keyword_evaluation_references(dataset, ROOT / "data/processed/sec_evidence/v1")
        validate_keyword_evaluation_filters(dataset, ROOT / "data/manifests/sec_documents.v1.json")
    except (DevelopmentDatabaseError, OSError, ValueError, RuntimeError) as exc:
        print(f"Semantic evaluation preflight failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    try:
        import psycopg

        with psycopg.connect(settings.database_url) as connection:
            prepare_development_connection(connection, target, create_schema=False)
            report = evaluate_keyword_retriever(
                PostgresSemanticRetriever(connection, model, configuration),
                dataset,
                retrieval_mode="postgres_pgvector_cosine_narrative_semantic_v1",
            )
    except (DevelopmentDatabaseError, OSError, ValueError, RuntimeError) as exc:
        print(f"Semantic evaluation failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    payload = asdict(report)
    payload["semantic_configuration"] = configuration.payload
    payload["semantic_configuration_hash"] = configuration.configuration_hash
    print(json.dumps(payload, default=str, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
