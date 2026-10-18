"""Read-only local semantic search over guarded development narrative evidence."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    from app.core.config import get_settings
    from app.retrieval.semantic import (
        PostgresSemanticRetriever,
        SemanticSearchFilters,
        current_embedding_configuration,
        load_pinned_model,
    )
    from app.storage.development import (
        DevelopmentDatabaseError,
        development_target_from_settings,
        prepare_development_connection,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--ticker")
    parser.add_argument("--form-type")
    parser.add_argument("--reporting-period-end")
    parser.add_argument("--document-id")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)
    settings = get_settings()
    try:
        target = development_target_from_settings(settings)
        if not settings.semantic_model_cache_dir:
            raise ValueError("SEMANTIC_MODEL_CACHE_DIR must be configured.")
        configuration = current_embedding_configuration()
        model = load_pinned_model(Path(settings.semantic_model_cache_dir), configuration)
        period = (
            date.fromisoformat(args.reporting_period_end) if args.reporting_period_end else None
        )
        filters = SemanticSearchFilters(args.ticker, args.form_type, period, args.document_id)
    except (DevelopmentDatabaseError, OSError, ValueError, RuntimeError) as exc:
        print(f"Semantic retrieval preflight failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    try:
        import psycopg

        with psycopg.connect(settings.database_url) as connection:
            prepare_development_connection(connection, target, create_schema=False)
            results = PostgresSemanticRetriever(connection, model, configuration).search(
                args.query, filters, args.limit
            )
    except (DevelopmentDatabaseError, OSError, ValueError, RuntimeError) as exc:
        print(f"Semantic retrieval failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps([asdict(item) for item in results], default=str, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
