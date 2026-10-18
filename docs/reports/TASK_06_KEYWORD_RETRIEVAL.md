# Task 06 — PostgreSQL Keyword / Full-Text Retrieval Baseline

## Outcome

Implemented a read-only PostgreSQL-native keyword baseline over admitted narrative chunks. It does not add embeddings, pgvector, external services, LLMs, answer generation, API routes, or UI work. Original SEC sources, parser artifacts, and Phase 3 evidence artifacts were not modified.

## Design

- Migration `002_keyword_retrieval.sql` adds a GIN expression index on `to_tsvector('english', narrative_chunks.text)` and a B-tree index for the registered-document metadata filters `(ticker, form_type, reporting_period_end)`.
- `PostgresKeywordRetriever` uses `websearch_to_tsquery('english', %s)` and `ts_rank_cd` with explicit tie-breaking by document ID and chunk sequence. Query text and filters are always query parameters; only fixed, code-owned SQL predicates are composed.
- The English configuration supplies stemming and stop-word handling appropriate for an initial English SEC filing corpus. It does not recognize accounting synonyms, ticker aliases, numeric/table semantics, or domain-specific terms beyond PostgreSQL lexical processing.
- Only admitted narrative chunks are searchable. Financial tables remain relational, structured evidence and are intentionally not flattened into prose; quarantines have no retrieval path. Results preserve chunk/document/source IDs, stored text, heading/source-element provenance, chunk sequence, issuer/form/period metadata, and rank.
- Filters are limited to fields implemented reliably in `registered_documents`: ticker, form type, and reporting-period end. Limits are validated from 1 through 100; blank queries return no candidates without a database call.

## Files changed

- `app/storage/migrations/002_keyword_retrieval.sql`
- `app/retrieval/keyword/postgres_keyword_retriever.py`
- `app/retrieval/keyword/__init__.py`
- `scripts/search_sec_evidence.py` and `scripts/README.md`
- `tests/unit/test_postgres_keyword_retriever.py`
- `tests/integration/test_postgres_evidence_storage.py`
- `docs/ARCHITECTURE.md`, `docs/DATA_DICTIONARY.md`, `docs/DEVELOPMENT_PLAN.md`, and `CODEX_REPORT.md`

## Reproducible live validation

The dedicated WSL PostgreSQL 16 database was used only through the existing generated-schema fixture. The test role was `yatharth`; the session-only DSN was `dbname=financial_rag_test user=yatharth`. No DSN password was recorded.

- `python -m pytest tests/unit/test_postgres_keyword_retriever.py -q` — **7 passed**.
- Windows unit suite: `python -m pytest tests/unit -q` — **50 passed**, with one existing non-failing FastAPI/Starlette deprecation warning.
- WSL unit suite: `/tmp/financial-rag-pgtest-venv/bin/python -m pytest tests/unit -q` — **50 passed**, with the same warning.
- Live PostgreSQL integration tests, split only to stay within the terminal execution window: all **5 passed**. This includes migration reapplication/hash rejection, full-corpus persistence/idempotency, transaction rollback, ranked AAPL 10-K narrative retrieval for `revenue` with reporting-period filter `2024-09-28`, and blank/no-match behavior.
- WSL Ruff: `python -m ruff check app scripts tests` — passed.
- WSL compileall: `python -m compileall -q app scripts tests` — passed.
- WSL manifest validator: `python scripts/validate_sec_registration_manifest.py` — **10 `VALID`**.
- Post-test cleanup query found **0** `evidence_test_*` schemas.

The `revenue` integration case is a reproducible contract check, not an evaluation of retrieval quality. No relevance labels, recall, precision, latency benchmark, or ranking-quality metric has yet been created.

## Running retrieval

For a database that has already received the Phase 3 corpus through the approved persistence workflow, set `DATABASE_URL` only in the active shell and run:

```powershell
python scripts\search_sec_evidence.py revenue --ticker AAPL --form-type 10-K --limit 5
```

The isolated integration database is intentionally cleaned after each test, so it is not a persistent corpus for the CLI. The CLI is read-only and will return no rows until a separately configured, migrated database has persisted approved evidence.

## Remaining limitations and next step

The baseline has no financial-table keyword strategy, query evaluation dataset, metadata filtering by unregistered fiscal fields, concurrent-ingestion coverage, semantic retrieval, hybrid fusion, reranking, citations, or answer generation. The next step should be to define a small, versioned retrieval evaluation dataset with judged evidence targets and use it to measure this keyword baseline before adding semantic retrieval.
