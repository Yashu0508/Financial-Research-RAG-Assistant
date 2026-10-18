# Task 08 — Safe local development database workflow

## Outcome

Task 08 adds a guarded workflow for a persistent local evidence corpus. It is
separate from the disposable PostgreSQL integration target `financial_rag_test`.
The workflow was initialized and verified on PostgreSQL 16 in the dedicated
`financial_rag_dev` database as the non-superuser `yatharth` role.

## Implementation

- `Settings` now carries non-secret expected development database, role, and
  schema names.
- `app.storage.development` requires an explicit `APP_ENV=development`, a DSN,
  a lowercase configured database/role/schema, a non-`public` schema, and a
  database other than `financial_rag_test`.
- Before any selected operational command proceeds, it queries
  `current_database()` and `current_user`, creates the configured schema only
  during bootstrap/migration, and sets `search_path` to the explicit schema and
  `pg_catalog`. A mismatch fails before `CREATE SCHEMA`, migrations, or
  persistence.
- `scripts/bootstrap_local_development_corpus.py` validates source and evidence
  hashes, migrates, persists idempotently, verifies counts, and runs a read-only
  keyword smoke search. Evaluation intentionally remains a separate read-only
  command, so its execution status cannot be confused with bootstrap success.
- Migration, persistence, search, and evaluation CLIs use the same guarded
  target/schema selection.

## Required local configuration

```text
APP_ENV=development
DATABASE_URL=dbname=financial_rag_dev user=financial_rag_dev
DEVELOPMENT_DATABASE_NAME=financial_rag_dev
DEVELOPMENT_DATABASE_ROLE=financial_rag_dev
DEVELOPMENT_DATABASE_SCHEMA=financial_rag_dev
```

The values are examples, not embedded credentials. The actual PostgreSQL
database and non-superuser role must be created outside the project. The
dedicated development database must not be `financial_rag_test`.

## Commands

```powershell
python scripts\bootstrap_local_development_corpus.py
python scripts\search_sec_evidence.py revenue --ticker AAPL --form-type 10-K --limit 5
python scripts\evaluate_keyword_retrieval.py
```

The first command reports source validation, migration, persistence, corpus
verification, and retrieval smoke-test status separately. It never reports
evaluation as complete; run the final command explicitly after bootstrap.

## Validation actually executed

- `python -m pytest tests/unit/test_development_database.py -q` — 10 passed.
- `python -m pytest -q` — 64 passed, 1 skipped because the Windows interpreter
  lacks `psycopg`; one existing Starlette warning.
- `python -m ruff check app scripts tests` — passed.
- `python -m compileall -q app scripts tests` — passed.
- `python scripts/validate_sec_registration_manifest.py` — 10 registered,
  `VALID=10`.
- WSL PostgreSQL 16 (`financial_rag_test`, role `yatharth`) isolated-schema
  integration tests passed individually: migration repeatability, full corpus
  persistence/idempotency, rollback, keyword ranking/filtering, empty/no-match
  behavior, and Task 07 evaluation. A post-run query found zero
  `evidence_test_*` schemas.
- `python scripts/bootstrap_local_development_corpus.py` without a configured
  target — correctly refused before connecting: explicit `APP_ENV=development`
  is required.

## Limitation and next milestone

The existing `financial_rag_test` database remains disposable and was not used
as a persistent corpus. The local ignored `.env` contains only the non-secret
peer-authentication development target configuration. The development schema is
created by bootstrap and is owned by `yatharth`; no credential was stored in
the repository.

### Live initialization and verification

- Verified database identity: `financial_rag_dev`, current role `yatharth`,
  owner `yatharth`; the role is a login role without superuser, role-creation,
  or database-creation privileges.
- Bootstrap first run: migrations `001` and `002` applied; approved corpus
  inserted with processing run `evidence-cc131af805dcc2b10e55e33f`; readback
  matched **10** documents, **938** narrative chunks, **833** table-evidence
  records, and **425** quarantine records; the read-only retrieval smoke test
  returned one candidate.
- Bootstrap second run: no migrations applied and `inserted=False`; the same
  run identity and counts were preserved.
- Schema verification after explicit `search_path` selection found schema
  `financial_rag_dev` owned by `yatharth`, migration versions `001` and `002`,
  and exactly one processing run.
- The documented Apple 10-K keyword command returned five candidates. Task 07
  v1 evaluation executed against this corpus and measured Recall@5/10 `0.3333`,
  Precision@5 `0.0667`, and MRR `0.3333`. These remain diagnostic metrics, not
  a quality claim.
- Focused workflow guard tests passed (**10**); source validation reported all
  **10** registrations `VALID`; Ruff and compileall passed in the WSL project
  environment.

Task 09 remains the next milestone: expand the judged versioned retrieval
benchmark while preserving Task 07 v1.
