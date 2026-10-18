"""Guards for the explicitly configured persistent development corpus target.

The disposable integration-test database is deliberately not accepted here.  These
helpers are for local developer commands only; tests continue to create random
schemas through ``TEST_POSTGRES_DSN``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import Settings

_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_DISPOSABLE_TEST_DATABASE = "financial_rag_test"


class DevelopmentDatabaseError(RuntimeError):
    """Raised when a command is not pointed at the approved development target."""


class Cursor(Protocol):
    def execute(self, query: str, params: tuple[object, ...] | None = ...) -> object: ...
    def fetchone(self) -> Any: ...
    def close(self) -> None: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...


@dataclass(frozen=True)
class DevelopmentTarget:
    """Non-secret identity of the database and schema approved for local work."""

    database_name: str
    role_name: str
    schema_name: str


def development_target_from_settings(settings: Settings) -> DevelopmentTarget:
    """Require an explicit, non-disposable local development target."""

    if settings.app_env != "development" or "app_env" not in settings.model_fields_set:
        raise DevelopmentDatabaseError(
            "APP_ENV must be explicitly set to exactly 'development'."
        )
    if not settings.database_url:
        raise DevelopmentDatabaseError("DATABASE_URL must be configured.")
    values = {
        "DEVELOPMENT_DATABASE_NAME": settings.development_database_name,
        "DEVELOPMENT_DATABASE_ROLE": settings.development_database_role,
        "DEVELOPMENT_DATABASE_SCHEMA": settings.development_database_schema,
    }
    missing = [name for name, value in values.items() if not isinstance(value, str) or not value]
    if missing:
        raise DevelopmentDatabaseError("Missing required setting(s): " + ", ".join(missing) + ".")
    target = DevelopmentTarget(
        database_name=settings.development_database_name or "",
        role_name=settings.development_database_role or "",
        schema_name=settings.development_database_schema or "",
    )
    for label, value in (
        ("DEVELOPMENT_DATABASE_NAME", target.database_name),
        ("DEVELOPMENT_DATABASE_ROLE", target.role_name),
        ("DEVELOPMENT_DATABASE_SCHEMA", target.schema_name),
    ):
        if not _IDENTIFIER.fullmatch(value):
            raise DevelopmentDatabaseError(f"{label} must be a lowercase PostgreSQL identifier.")
    if target.database_name == _DISPOSABLE_TEST_DATABASE:
        raise DevelopmentDatabaseError(
            "financial_rag_test is disposable integration-test storage, not a development corpus."
        )
    if target.schema_name == "public":
        raise DevelopmentDatabaseError("DEVELOPMENT_DATABASE_SCHEMA must not be public.")
    return target


def _quote_identifier(identifier: str) -> str:
    """Quote an identifier after strict validation; never accept arbitrary SQL syntax."""

    if not _IDENTIFIER.fullmatch(identifier):
        raise DevelopmentDatabaseError("Unsafe PostgreSQL identifier.")
    return f'"{identifier}"'


def prepare_development_connection(
    connection: Connection, target: DevelopmentTarget, *, create_schema: bool
) -> None:
    """Verify server identity and set one explicit schema for this connection.

    Schema creation is allowed only after database and role checks.  This helper
    never drops, truncates, or deletes anything.
    """

    cursor = connection.cursor()
    try:
        cursor.execute("SELECT current_database(), current_user")
        identity = cursor.fetchone()
        if not identity or identity[0] != target.database_name or identity[1] != target.role_name:
            actual_database = identity[0] if identity else "<unavailable>"
            actual_role = identity[1] if identity else "<unavailable>"
            raise DevelopmentDatabaseError(
                "Connected target does not match requested development target "
                f"(database={actual_database!r}, role={actual_role!r})."
            )
        quoted_schema = _quote_identifier(target.schema_name)
        if create_schema:
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {quoted_schema}")
        cursor.execute(f"SET search_path TO {quoted_schema}, pg_catalog")
        cursor.execute("SELECT current_schema()")
        selected = cursor.fetchone()
        if not selected or selected[0] != target.schema_name:
            raise DevelopmentDatabaseError("Requested development schema is unavailable.")
    finally:
        cursor.close()
