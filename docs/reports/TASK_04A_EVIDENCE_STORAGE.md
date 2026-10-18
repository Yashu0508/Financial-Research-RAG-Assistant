# Task 04A — Evidence Storage Architecture and Persistence

## Outcome

Phase 4A implements PostgreSQL-compatible persistence for the actual Phase 3 evidence contract. It does not implement retrieval, full-text indexing, vectors, embeddings, generation, API routes, UI, or any network operation.

## Design

- `app/storage/migrations/001_evidence_storage.sql` creates relational registered-document, processing-run, admitted narrative, table, row, cell, and quarantine tables. Constraints preserve source hashes, statuses, table spans/kinds, identity uniqueness, and foreign-key relationships.
- `app/storage/migrations/runner.py` applies numbered SQL files transactionally and refuses an already-applied version whose script hash has changed.
- `app/storage/repositories/evidence_repository.py` provides a repository protocol, PostgreSQL DB-API implementation, and intentionally isolated in-memory test double. It accepts only registered documents with matching source hashes and `ADMITTED` / `ADMITTED_WITH_QUARANTINED_RECORDS` evidence. Quarantined documents are rejected; quarantined child records are recorded only in `quarantine_records`.
- Repeating identical metadata produces a deterministic processing-run ID and is a no-op. Conflicting registered document hashes and duplicate evidence IDs fail and roll back.
- `scripts/migrate_evidence_storage.py` and `scripts/persist_sec_evidence.py` use `DATABASE_URL`, never hard-code a credential, validate current source hashes and evidence artifact hashes before persistence, and fail safely when configuration/driver is absent.

## Files changed

`pyproject.toml`; `app/storage/migrations/001_evidence_storage.sql`; `app/storage/migrations/runner.py`; `app/storage/repositories/evidence_repository.py`; `app/storage/repositories/__init__.py`; both storage scripts; `tests/unit/test_evidence_storage.py`; architecture, data dictionary, development plan, and `CODEX_REPORT.md`.

## Validation

Commands actually run:

- `python -m pytest -q` — **43 passed**; one existing FastAPI/Starlette deprecation warning.
- `python -m ruff check app scripts tests` — **All checks passed**.
- `python -m compileall -q app scripts tests` — passed with no diagnostics.
- `python scripts/validate_sec_registration_manifest.py` — **10 `VALID`**, zero source-integrity failures.
- `python scripts/migrate_evidence_storage.py` and `python scripts/persist_sec_evidence.py` — each safely exited because `DATABASE_URL` is not configured; neither attempted a connection or wrote data.
- QA checklist inspection — present with **30 `PASS`** entries.

The focused tests use the unchanged ten-document Phase 3 artifact set and assert 938 narrative chunks, 833 tables, and 425 quarantined records. They also cover admission rejection, duplicate-ID rollback, deterministic re-ingestion, and migration transaction invocation. PostgreSQL was not available locally, so no live migration, FK/check constraint, or repository integration test is claimed. PostgreSQL-specific SQL remains unexecuted pending a configured isolated service.

## Limitations and next task

Install the declared `storage` optional dependency and run migrations against an isolated PostgreSQL service before production use. Then add PostgreSQL integration tests for constraints, concurrency, and rollback. Phase 4B may add a transparent keyword-indexing design only after that integration coverage; it must not add semantic retrieval or generation prematurely.
