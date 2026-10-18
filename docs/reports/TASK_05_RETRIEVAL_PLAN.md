# Task 05 — Retrieval Architecture Planning

## Inspection scope

This was a planning-only review of the ingestion, parser, chunker, storage migration/repository, PostgreSQL integration tests, `CODEX_REPORT.md`, and Task 03/04 reports. No raw filing, manifest, parser artifact, evidence artifact, database, dependency, or runtime configuration was changed.

## Actual project status

### Complete and validated offline

- The versioned registration manifest covers ten local Apple and Microsoft SEC filings. The immutable loader rechecks byte size and SHA-256 before processing; the latest documented validation has all ten `VALID`.
- HTML parsing is restricted to registered valid files. Its deterministic artifacts retain narrative structure separately from structured table data, source locators, spans, source hash, parser identity, and explicit quarantine outcomes.
- Manual QA covers 30 statement-table candidates; the completed checklist records 30 `PASS` results. Parser and chunker regression checks map those candidates to preserved structure and provenance.
- Deterministic evidence chunking consumes compatible parsed artifacts and writes separate narrative chunks and table-evidence records. The current corpus comprises ten admitted documents, 938 narrative chunks, 833 table-evidence records, and 425 explicitly quarantined low-information records. The chunker preserves raw table cells and does not invent header semantics.
- Unit/static validation was last documented as 43 passing tests, plus Ruff and compileall. The existing FastAPI/Starlette warning is non-failing.

### Implemented but not verified against PostgreSQL

- Phase 4A supplies a PostgreSQL-compatible schema, transactional numbered migration runner, repository, persistence/migration scripts, and an optional `psycopg` dependency.
- The schema separates registered documents, processing runs, admitted narrative chunks, table evidence, relational table rows/cells, and quarantines. It has no full-text or vector index.
- An opt-in PostgreSQL integration suite exists. It uses a generated schema in an explicitly supplied test database and covers migrations, changed-script rejection, full-corpus persistence, provenance reload, idempotency, and rollback.
- No integration test ran against PostgreSQL. Task 04B found no local PostgreSQL service, `psql`, Docker/Podman, `psycopg`, `testcontainers`, or `TEST_POSTGRES_DSN`; the suite was skipped. Therefore neither PostgreSQL migration semantics nor repository transaction/constraint behavior is proven on a live engine.

### Not implemented

- Database deployment/migration execution and corpus persistence to PostgreSQL.
- Keyword/full-text retrieval, a shared retrieval-candidate contract, query normalization, metadata filtering, score/rank policy, retrieval evaluation queries, and retrieval result formatting.
- Embeddings, pgvector, semantic retrieval, hybrid fusion, reranking, citation resolution, answer generation, question API routes, and UI.

## Recommended next task

**Complete live Task 04B PostgreSQL integration validation in a dedicated disposable database, fixing any discovered storage defects, before implementing keyword retrieval.**

This is the smallest practical next step because the planned keyword baseline is PostgreSQL full-text retrieval over the persisted approved corpus. Building FTS on top of a migration/repository contract that has never executed on PostgreSQL would obscure storage failures as retrieval failures. The existing opt-in test suite and report already specify safe isolation: a test-only DSN and a generated per-test schema, never `public` or a production database.

After live validation passes, the next implementation should be **Task 06: a keyword retrieval baseline**. It should add only a versioned FTS migration/index, a read-only keyword repository/retriever contract, explicit company/form/reporting-period filters, provenance-rich ranked candidates, and a small evaluated query fixture. It must continue to exclude quarantines and preserve the narrative/table distinction. No embedding, vector, or LLM dependency is needed for that baseline.

## Dependency answers

- **Is PostgreSQL setup a blocker now?** Yes, for the recommended next task and for a PostgreSQL FTS baseline. It is not a blocker for further planning or pure unit-contract design, but live storage correctness should be established before retrieval implementation.
- **Are API keys needed now?** No. PostgreSQL uses a test-only local/isolated database credential, not an API key. Keyword retrieval needs no model or external-service key.
- **Are embeddings or vector databases needed now?** No. They are later-phase work after a measurable keyword baseline.

## Exact next implementation prompt

```text
# Task 04B completion — Live PostgreSQL integration validation

Complete Task 04B against a dedicated disposable PostgreSQL database only. Use the existing opt-in integration suite and TEST_POSTGRES_DSN; do not use public, shared, or production data. Install only the declared storage dependency if needed, run the PostgreSQL integration tests, migration CLI, persistence CLI, and complete quality suite. Diagnose and fix only genuine storage/migration/repository defects found against PostgreSQL. Preserve raw SEC filings, registration manifest, parser artifacts, and Phase 3 evidence artifacts. Do not add retrieval, full-text indexes, embeddings, vectors, LLMs, APIs, or UI. Update TASK_04B_POSTGRESQL_INTEGRATION.md and CODEX_REPORT.md with the actual database environment, commands, results, defects, and remaining limitations. If no dedicated database is available, stop after safe inspection and report the exact blocker without claiming integration coverage.
```
