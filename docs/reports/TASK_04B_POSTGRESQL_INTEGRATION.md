# Task 04B — PostgreSQL Integration Validation

## Outcome

Live PostgreSQL validation completed successfully on 2026-10-17 after the user provisioned a dedicated WSL Ubuntu PostgreSQL 16 test database. The integration suite ran through `psycopg 3.2.10` as the ordinary PostgreSQL role `yatharth`, using local peer authentication and the test-only DSN `dbname=financial_rag_test user=yatharth`. No password was placed in source or output.

## Integration test design

`tests/integration/test_postgres_evidence_storage.py` is separate from unit tests and is deliberately skipped unless both the `psycopg` optional dependency and `TEST_POSTGRES_DSN` are available. It uses a random schema per test in the supplied dedicated test database, sets `search_path` to that schema, and drops only that known generated schema during cleanup. It never alters `public` or a production database.

When enabled, it exercises the real PostgreSQL engine for migration application/reapplication, changed migration script refusal, full Phase 3 corpus persistence, row/cell/quarantine counts, provenance and locator reload, idempotent repeated persistence, invalid-admission rejection, and rollback after a duplicate chunk ID fails partway through a write.

## Actual commands and results

- WSL identity check: `psql -d financial_rag_test -U yatharth -Atc "SELECT current_user, current_database();"` — **`yatharth|financial_rag_test`**.
- `TEST_POSTGRES_DSN='dbname=financial_rag_test user=yatharth' /tmp/financial-rag-pgtest-venv/bin/python -m pytest tests/integration/test_postgres_evidence_storage.py -q` — **3 passed** against PostgreSQL 16.
- The full WSL validation command with the same session-only DSN — `python -m pytest -q`, Ruff, compileall, and source-manifest validation — **46 passed**, **1 existing non-failing FastAPI/Starlette deprecation warning**, Ruff passed, compileall passed, and **10 `VALID`** source registrations.
- Read-only cleanup check: `SELECT count(*) FROM pg_namespace WHERE nspname LIKE 'evidence_test_%';` — **0**, confirming the integration fixture removed each generated test schema.
- Existing Phase 3 evidence and raw filings were read only; no source, manifest, parser, or chunk artifacts were changed.

## Required approved setup for live validation

1. Provision a dedicated disposable PostgreSQL database whose contents may be discarded; do not use a shared or production database.
2. Install the declared project extra: `python -m pip install -e ".[storage]"`.
3. In PowerShell, set the test-only DSN for the current process: `$env:TEST_POSTGRES_DSN = "postgresql://test_user:...@localhost:5432/financial_rag_test"`.
4. Run `python -m pytest tests/integration/test_postgres_evidence_storage.py -q` followed by the full suite and quality checks.

Do not commit the DSN or password. The test suite creates and removes only random `evidence_test_*` schemas in that designated test database.

## Remaining limitation

Live PostgreSQL migration, changed-migration refusal, full-corpus persistence, provenance reload, idempotency, quarantine separation, and rollback on a duplicate evidence identifier are now verified. The current integration suite does not exercise simultaneous multi-connection ingestion contention, and it does not test future full-text/vector indexes because neither is in scope or implemented. No indexing, embeddings, retrieval, generation, API, or UI code was added.
