# Local development evidence database

Task 08 defines one persistent local development corpus target. It is separate
from the disposable integration-test database `financial_rag_test`.

## Safety contract

All development database commands require these exact non-secret settings. In
particular, `APP_ENV=development` must be explicitly present; its application
default is not accepted as authorization for database operations:

```text
APP_ENV=development
DATABASE_URL=dbname=financial_rag_dev user=financial_rag_dev
DEVELOPMENT_DATABASE_NAME=financial_rag_dev
DEVELOPMENT_DATABASE_ROLE=financial_rag_dev
DEVELOPMENT_DATABASE_SCHEMA=financial_rag_dev
```

The actual database and role names may differ, but the three `DEVELOPMENT_*`
values must match the connected PostgreSQL server values exactly. Names must be
lowercase PostgreSQL identifiers. `public` is never accepted as the corpus
schema, and `financial_rag_test` is always refused as a development database.
Do not put passwords in `.env.example` or source control; use local PostgreSQL
authentication or a local, ignored `.env` file.

The commands verify `current_database()` and `current_user`, set the explicit
schema search path to `<development schema>, pg_catalog`, and then operate only
through that connection. Bootstrap may create the configured schema if absent;
it never drops a database/schema, truncates tables, or deletes source/evidence
data. The existing disposable integration tests continue to use only random
`evidence_test_*` schemas inside `financial_rag_test`.

## WSL/PostgreSQL prerequisite

PostgreSQL must already be installed and running. A developer or database
administrator must create a dedicated database and non-superuser role before
using the project commands. Example commands, run as the PostgreSQL OS/admin
account and adapted to local policy:

```bash
createuser --login financial_rag_dev
createdb --owner=financial_rag_dev financial_rag_dev
```

These commands are not run by this project and do not reuse the integration
database. Grant only the privileges needed by the dedicated role. In WSL, run
the Python commands below from `/mnt/d/Financial Research RAG Assistant` using
the project environment with the `storage` extra installed.

## Bootstrap and verification

Copy `.env.example` to ignored `.env`, set the four database values, then run:

```powershell
python scripts\bootstrap_local_development_corpus.py
```

The command has distinct stages:

1. validates registered source hashes and evidence-artifact hashes;
2. validates database, role, and schema identity;
3. creates only the configured schema when it does not exist;
4. applies numbered migrations in that schema;
5. persists the approved evidence idempotently;
6. reads back document, narrative, table, and quarantine counts; and
7. performs a read-only `revenue` keyword smoke search.

It reports evaluation as **not executed**. A successful connection alone is not
reported as a migrated or populated corpus. Rerunning unchanged inputs is safe:
migrations are rechecked and an identical evidence run is not inserted again.

Common failures:

- `APP_ENV must be exactly 'development'`: use the development-only settings.
- `financial_rag_test is disposable...`: create/configure a separate persistent
  development database.
- `must not be public`: choose a dedicated non-public schema.
- `Connected target does not match...`: correct the DSN or the matching
  `DEVELOPMENT_*` values; do not override the guard.
- missing-table errors on search/evaluation: run bootstrap first.

## Read-only retrieval and evaluation

After successful bootstrap, the following use the same guarded target and
explicit schema:

```powershell
python scripts\search_sec_evidence.py revenue --ticker AAPL --form-type 10-K --limit 5
python scripts\evaluate_keyword_retrieval.py
```

Both commands refuse missing/unsafe development settings and make no corpus
changes. The evaluation command runs the existing Task 07 v1 dataset; it is a
small diagnostic benchmark, not a retrieval-quality approval.
