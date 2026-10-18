"""Evaluate read-only structured-table keyword retrieval against table labels."""

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
    from app.evaluation.retrieval.table_evaluation import evaluate_table_keyword_retriever
    from app.evaluation.retrieval.table_judgments import validate_table_judgment_references
    from app.retrieval.table import PostgresTableKeywordRetriever
    from app.storage.development import (
        DevelopmentDatabaseError,
        development_target_from_settings,
        prepare_development_connection,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=ROOT / "data/evaluation/table_retrieval_judgments.v1.json"
    )
    args = parser.parse_args(argv)
    settings = get_settings()
    try:
        validate_table_judgment_references(
            args.dataset,
            ROOT / "data/processed/sec_evidence/v1",
            ROOT / "data/manifests/sec_documents.v1.json",
        )
        target = development_target_from_settings(settings)
        import psycopg

        with psycopg.connect(settings.database_url) as connection:
            prepare_development_connection(connection, target, create_schema=False)
            report = evaluate_table_keyword_retriever(
                PostgresTableKeywordRetriever(connection), args.dataset
            )
    except (DevelopmentDatabaseError, ImportError, OSError, ValueError) as exc:
        print(f"Table evaluation failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(asdict(report), default=str, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
