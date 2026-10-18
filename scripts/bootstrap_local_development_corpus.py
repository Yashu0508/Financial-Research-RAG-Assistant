"""Safely initialize or verify the approved evidence corpus in one development schema."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    """Validate inputs, migrate, persist idempotently, verify counts, and smoke-test search."""

    from app.core.config import get_settings
    from app.retrieval.keyword import PostgresKeywordRetriever
    from app.storage.development import (
        DevelopmentDatabaseError,
        development_target_from_settings,
        prepare_development_connection,
    )
    from app.storage.development_workflow import expected_counts, verify_corpus_counts
    from app.storage.migrations.runner import apply_migrations
    from app.storage.repositories.evidence_repository import (
        PostgresEvidenceRepository,
        StorageError,
    )
    from scripts.persist_sec_evidence import load_approved_evidence

    settings = get_settings()
    try:
        target = development_target_from_settings(settings)
        manifest, metadata, artifacts = load_approved_evidence()
    except (DevelopmentDatabaseError, OSError, ValueError, KeyError) as exc:
        print(f"Development corpus preflight failed: {type(exc).__name__}: {exc}", file=sys.stderr)
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
        with psycopg.connect(settings.database_url) as connection:
            prepare_development_connection(connection, target, create_schema=True)
            versions = apply_migrations(connection, ROOT / "app" / "storage" / "migrations")
            result = PostgresEvidenceRepository(connection).persist_run(
                manifest, metadata, artifacts
            )
            counts = verify_corpus_counts(connection, expected_counts(artifacts))
            smoke_results = PostgresKeywordRetriever(connection).search("revenue", limit=1)
    except (DevelopmentDatabaseError, OSError, ValueError, StorageError, RuntimeError) as exc:
        print(f"Development corpus bootstrap failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(
        f"Target: database={target.database_name} role={target.role_name} "
        f"schema={target.schema_name}"
    )
    print("Migrated: " + (", ".join(versions) if versions else "none (already current)"))
    print(f"Persisted: inserted={result.inserted}; run_id={result.run_id}")
    print(
        "Corpus verified: "
        f"documents={counts.documents}; narratives={counts.narrative_chunks}; "
        f"tables={counts.tables}; quarantines={counts.quarantines}"
    )
    print(f"Retrieval smoke test: executed; candidates={len(smoke_results)}")
    print("Evaluation: not executed; run scripts/evaluate_keyword_retrieval.py separately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
