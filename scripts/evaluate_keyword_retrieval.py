"""Evaluate persisted PostgreSQL keyword retrieval against versioned labels."""

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
    """Print reproducible metrics; evaluation is read-only."""
    from app.core.config import get_settings
    from app.evaluation.retrieval.keyword_evaluation import (
        evaluate_keyword_retriever,
        validate_keyword_evaluation_filters,
        validate_keyword_evaluation_references,
    )
    from app.retrieval.keyword import PostgresKeywordRetriever
    from app.storage.development import (
        DevelopmentDatabaseError,
        development_target_from_settings,
        prepare_development_connection,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=Path("data/evaluation/keyword_retrieval.v1.json")
    )
    args = parser.parse_args(argv)
    settings = get_settings()
    try:
        target = development_target_from_settings(settings)
    except DevelopmentDatabaseError as exc:
        print(f"Development target validation failed: {exc}", file=sys.stderr)
        return 2
    dataset = args.dataset if args.dataset.is_absolute() else ROOT / args.dataset
    try:
        import psycopg
    except ImportError:
        print(
            "PostgreSQL driver is not installed; install the storage optional dependency.",
            file=sys.stderr,
        )
        return 2
    try:
        validate_keyword_evaluation_references(
            dataset, ROOT / "data" / "processed" / "sec_evidence" / "v1"
        )
        validate_keyword_evaluation_filters(
            dataset, ROOT / "data" / "manifests" / "sec_documents.v1.json"
        )
        with psycopg.connect(settings.database_url) as connection:
            prepare_development_connection(
                connection, target, create_schema=False
            )
            report = evaluate_keyword_retriever(PostgresKeywordRetriever(connection), dataset)
    except (DevelopmentDatabaseError, OSError, ValueError) as exc:
        print(f"Keyword evaluation failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(asdict(report), default=str, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
