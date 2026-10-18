"""Run read-only PostgreSQL keyword retrieval over persisted narrative evidence."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _optional_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def main(argv: list[str] | None = None) -> int:
    """Search configured storage without changing the database or source artifacts."""

    from app.core.config import get_settings
    from app.retrieval.keyword import (
        KeywordRetrievalError,
        KeywordSearchFilters,
        PostgresKeywordRetriever,
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
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)
    settings = get_settings()
    try:
        target = development_target_from_settings(settings)
    except DevelopmentDatabaseError as exc:
        print(f"Development target validation failed: {exc}", file=sys.stderr)
        return 2
    try:
        import psycopg
    except ImportError:
        print(
            "PostgreSQL driver is not installed; install the storage optional dependency.",
            file=sys.stderr,
        )
        return 2
    try:
        filters = KeywordSearchFilters(
            ticker=args.ticker,
            form_type=args.form_type,
            reporting_period_end=_optional_date(args.reporting_period_end),
        )
        with psycopg.connect(settings.database_url) as connection:
            prepare_development_connection(
                connection, target, create_schema=False
            )
            results = PostgresKeywordRetriever(connection).search(args.query, filters, args.limit)
    except (DevelopmentDatabaseError, KeywordRetrievalError, ValueError) as exc:
        print(f"Keyword retrieval failed: {exc}", file=sys.stderr)
        return 2
    for result in results:
        print(
            f"{result.rank:.6f}\t{result.document_id}\t{result.chunk_id}\t"
            f"{result.section_heading.get('locator')}\t{result.section_heading.get('text')}"
        )
    print(f"Candidates: {len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
