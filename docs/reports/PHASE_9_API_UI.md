# Phase 9 — Typed FastAPI Query Delivery and Thin UI

## Verified request flow

`POST /query` accepts only `question`, optional `ticker`, `form_type`, and
`reporting_period_end`. The strict Pydantic model rejects extra fields, so a
caller cannot submit evidence, citations, URLs, retrieval scores, or reranker
scores. Questions are trimmed, limited to 1,000 characters, and tickers are
normalized to uppercase.

The production dependency validates the guarded persistent-development target,
uses the server-owned narrative keyword + semantic RRF retriever and bounded
cross-encoder reranker, then passes at most five resulting narrative records to
the Phase 8 service. The existing retriever bounds remain 50 fusion candidates
and 20 reranked candidates; callers cannot configure either depth. Table and
quarantined evidence are excluded by the narrative contracts. Keyword SQL now
also explicitly requires `n.validation_status = 'ADMITTED'` and an equality
match between the chunk and registered-document source hashes. Semantic SQL
already has those checks.

Reranked results retain their document identity under `.candidate`; Phase 9B
corrected the adapter to use that trusted identity when looking up a source URL.
URLs and source hashes therefore originate only from the manifest and retrieved
record, never from the request or provider output. The Phase 8 service validates
the source hash against its manifest-derived mapping before provider use, and
resolves citation IDs only from the supplied trusted evidence. Unknown,
malformed, missing, quarantined, or source-inconsistent evidence/citations
produce a typed abstention rather than a trusted answer.

Dependency construction errors occur before a FastAPI route handler. Phase 9B
corrected this path to emit the same generic HTTP 503 used for request-time
pipeline failures; it does not expose configuration diagnostics, stack traces,
prompts, credentials, or raw evidence. The request-scoped read-only PostgreSQL
connection is closed after the pipeline returns (including failure paths).

`ui/app.py` imports only the HTTP client. It POSTs to `API_BASE_URL/query` and
has no database, retrieval, model, or provider imports. It displays answer,
abstention, and generic error states, and renders a citation link only when the
typed API response contains a source URL.

## Tests and checks actually run

```text
python -m pytest tests/unit/test_query_api.py tests/unit/test_ui_client.py \
  tests/unit/test_health.py tests/unit/test_postgres_keyword_retriever.py \
  tests/unit/test_grounded_generation.py -q
# 41 passed, 1 existing Starlette/httpx deprecation warning

python -m pytest tests/unit -q
# 122 passed, 1 existing warning

wsl.exe -d Ubuntu -- bash -lc '... TEST_POSTGRES_DSN="dbname=financial_rag_test user=yatharth" ... pytest tests/integration/test_postgres_evidence_storage.py -q'
# 10 passed in 93.17s

wsl.exe -d Ubuntu -- bash -lc '... TEST_POSTGRES_DSN="dbname=financial_rag_test user=yatharth" ... pytest -q'
# 132 passed, 1 existing warning in 101.35s

python -m ruff check app ui tests
python -m compileall -q app ui tests
python scripts/validate_sec_registration_manifest.py
# all passed; manifest reports 10 VALID sources
```

Post-integration inspection found **0** generated `evidence_test_*` schemas in
the disposable `financial_rag_test` database. The guarded, read-only keyword
v2 evaluation also executed unchanged: dataset SHA-256
`d79de57f251a10de5797276e42b7d4fc6236124b9c268badc8477c538a6f1c9f`, 20
answerable / 3 unanswerable cases, Recall@5 0.05, Recall@10 0.05,
Precision@5 0.01, and MRR 0.05.

## Remaining limitation

All API/UI and provider cases above use deterministic fakes; no OpenAI request,
credential, model download, raw source change, processed-artifact change,
benchmark-label change, migration, or persistent-corpus write occurred. Live
provider behavior remains unverified until an authorized request is deliberately
made. Citation validation establishes evidence identity and provenance, not
natural-language claim entailment.
