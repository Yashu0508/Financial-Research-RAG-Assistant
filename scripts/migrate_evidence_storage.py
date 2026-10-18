"""Apply the local numbered PostgreSQL evidence-storage migrations."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from app.core.config import get_settings
    from app.storage.development import (
        DevelopmentDatabaseError,
        development_target_from_settings,
        prepare_development_connection,
    )

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
    from app.storage.migrations.runner import apply_migrations

    try:
        with psycopg.connect(settings.database_url) as connection:
            prepare_development_connection(
                connection, target, create_schema=True
            )
            versions = apply_migrations(connection, ROOT / "app" / "storage" / "migrations")
    except Exception as exc:
        print(f"Migration failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print("Applied migrations: " + (", ".join(versions) if versions else "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
