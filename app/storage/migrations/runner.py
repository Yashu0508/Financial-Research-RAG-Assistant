"""Small transactional runner for numbered PostgreSQL schema migrations."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol


class Cursor(Protocol):
    def execute(self, query: str, params: object = ...) -> object: ...
    def fetchone(self) -> object: ...
    def close(self) -> None: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


class MigrationError(RuntimeError):
    pass


def migration_files(directory: Path) -> tuple[Path, ...]:
    files = tuple(sorted(directory.glob("[0-9][0-9][0-9]_*.sql")))
    if not files:
        raise MigrationError(f"No SQL migrations found in {directory}")
    return files


def apply_migrations(connection: Connection, directory: Path) -> tuple[str, ...]:
    cursor = connection.cursor()
    applied: list[str] = []
    try:
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, script_sha256 CHAR(64) NOT NULL, applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)"  # noqa: E501
        )
        for path in migration_files(directory):
            version = path.name.split("_", 1)[0]
            script = path.read_text(encoding="utf-8")
            digest = hashlib.sha256(script.encode()).hexdigest()
            cursor.execute(
                "SELECT script_sha256 FROM schema_migrations WHERE version = %s", (version,)
            )
            row = cursor.fetchone()
            if row:
                existing = row[0] if isinstance(row, tuple) else row["script_sha256"]
                if existing != digest:
                    raise MigrationError(f"Applied migration {version} has different content.")
                continue
            cursor.execute(script)
            cursor.execute(
                "INSERT INTO schema_migrations (version, script_sha256) VALUES (%s, %s)",
                (version, digest),
            )
            applied.append(version)
        connection.commit()
        return tuple(applied)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
