"""Run read-only keyword retrieval over persisted structured financial tables."""

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
    from app.retrieval.keyword import KeywordRetrievalError
    from app.retrieval.table import PostgresTableKeywordRetriever, TableSearchFilters
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
    parser.add_argument("--table-evidence-id")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)
    settings = get_settings()
    try:
        target = development_target_from_settings(settings)
        filters = TableSearchFilters(
            ticker=args.ticker,
            form_type=args.form_type,
            reporting_period_end=date.fromisoformat(args.reporting_period_end)
            if args.reporting_period_end
            else None,
            document_id=args.document_id,
            table_evidence_id=args.table_evidence_id,
        )
        import psycopg

        with psycopg.connect(settings.database_url) as connection:
            prepare_development_connection(connection, target, create_schema=False)
            results = PostgresTableKeywordRetriever(connection).search(
                args.query, filters, args.limit
            )
    except (DevelopmentDatabaseError, KeywordRetrievalError, ValueError, ImportError) as exc:
        print(f"Table retrieval failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps([asdict(result) for result in results], default=str, indent=2, sort_keys=True))
    print(f"Candidates: {len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
