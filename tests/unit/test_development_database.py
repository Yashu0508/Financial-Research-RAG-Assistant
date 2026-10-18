"""Safety contracts for the persistent local development corpus target."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.storage.development import (
    DevelopmentDatabaseError,
    DevelopmentTarget,
    development_target_from_settings,
    prepare_development_connection,
)
from app.storage.development_workflow import (
    CorpusCounts,
    CorpusVerificationError,
    verify_corpus_counts,
)
from scripts.migrate_evidence_storage import main as migrate_main
from scripts.persist_sec_evidence import main as persist_main


def _settings(**overrides: str) -> Settings:
    values = {
        "app_env": "development",
        "database_url": "dbname=financial_rag_dev user=rag_dev",
        "development_database_name": "financial_rag_dev",
        "development_database_role": "rag_dev",
        "development_database_schema": "financial_rag_dev",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"app_env": "test"}, "APP_ENV"),
        ({"development_database_name": "financial_rag_test"}, "disposable"),
        ({"development_database_schema": "public"}, "must not be public"),
        ({"development_database_schema": "MixedCase"}, "lowercase"),
        ({"development_database_role": ""}, "Missing required"),
    ],
)
def test_development_target_requires_explicit_safe_configuration(overrides, message):
    with pytest.raises(DevelopmentDatabaseError, match=message):
        development_target_from_settings(_settings(**overrides))


def test_development_target_requires_explicit_development_confirmation():
    settings = Settings(
        _env_file=None,
        database_url="dbname=financial_rag_dev user=rag_dev",
        development_database_name="financial_rag_dev",
        development_database_role="rag_dev",
        development_database_schema="financial_rag_dev",
    )
    with pytest.raises(DevelopmentDatabaseError, match="explicitly set"):
        development_target_from_settings(settings)


class FakeCursor:
    def __init__(self, identity=("financial_rag_dev", "rag_dev"), schema="financial_rag_dev"):
        self.identity = identity
        self.schema = schema
        self.executed: list[tuple[str, object]] = []
        self._last_query = ""

    def execute(self, query, params=None):
        self.executed.append((query, params))
        self._last_query = query

    def fetchone(self):
        if "current_database" in self._last_query:
            return self.identity
        if "current_schema" in self._last_query:
            return (self.schema,)
        return None

    def close(self):
        pass


class FakeConnection:
    def __init__(self, **kwargs):
        self.cursor_obj = FakeCursor(**kwargs)

    def cursor(self):
        return self.cursor_obj


def test_connection_mismatch_refuses_before_schema_mutation():
    connection = FakeConnection(identity=("wrong_database", "rag_dev"))
    with pytest.raises(DevelopmentDatabaseError, match="does not match"):
        prepare_development_connection(
            connection,
            DevelopmentTarget("financial_rag_dev", "rag_dev", "financial_rag_dev"),
            create_schema=True,
        )
    queries = [query for query, _ in connection.cursor_obj.executed]
    assert queries == ["SELECT current_database(), current_user"]


def test_connection_applies_only_the_requested_schema():
    connection = FakeConnection()
    prepare_development_connection(
        connection,
        DevelopmentTarget("financial_rag_dev", "rag_dev", "financial_rag_dev"),
        create_schema=True,
    )
    queries = [query for query, _ in connection.cursor_obj.executed]
    assert 'CREATE SCHEMA IF NOT EXISTS "financial_rag_dev"' in queries
    assert 'SET search_path TO "financial_rag_dev", pg_catalog' in queries
    assert all("public" not in query for query in queries)


def test_mutating_commands_refuse_unsafe_configuration_before_connecting(monkeypatch):
    unsafe = _settings(app_env="test")
    monkeypatch.setattr("app.core.config.get_settings", lambda: unsafe)
    assert migrate_main() == 2
    assert persist_main() == 2


class CountCursor:
    def __init__(self, row):
        self.row = row

    def execute(self, query, params=None):
        self.query = query

    def fetchone(self):
        return self.row

    def close(self):
        pass


class CountConnection:
    def __init__(self, row):
        self.cursor_obj = CountCursor(row)

    def cursor(self):
        return self.cursor_obj


def test_corpus_verification_requires_exact_approved_counts():
    expected = CorpusCounts(10, 938, 833, 425)
    assert verify_corpus_counts(CountConnection((10, 938, 833, 425)), expected) == expected
    with pytest.raises(CorpusVerificationError, match="do not match"):
        verify_corpus_counts(CountConnection((10, 937, 833, 425)), expected)
