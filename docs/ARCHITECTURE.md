# Architecture

## Current implementation boundary

The project is an evidence-retrieval system over immutable local SEC filings. It implements bounded narrative generation, citation-identity/provenance validation, explicit abstention, a typed `POST /query` API, and a thin Streamlit HTTP client. A retrieved candidate is still **not** a supported answer or a verified citation by itself.

```text
Registered immutable SEC HTML
  -> hash/size validation
  -> structure-preserving parser
  -> section-aware narrative chunks + structured table evidence
  -> guarded PostgreSQL persistence
  -> keyword / semantic narrative retrieval -----\
  -> structured-table keyword retrieval            -> RRF -> bounded reranking
                                                        |
                                                        v
                                           ranked evidence
                                                        |
                                                        v
                         Phase 8: provider adapter -> citation validation -> answer or abstention

                         typed query API -> thin UI
```

## Offline evidence pipeline

1. **Manifest and integrity.** `data/manifests/sec_documents.v1.json` holds stable document identity and registered local source metadata. `app.ingestion.loaders.sec_manifest` rechecks SHA-256 and byte size before a source can be parsed. Raw filing files and companion directories are never rewritten.
2. **Parsing.** `app.ingestion.parsers.sec_html_parser` consumes only registered `VALID` sources. It writes versioned parser artifacts under `data/processed/sec_parsed/v1/`, keeps visible narrative blocks distinct from table records, and preserves source locators, DOM/table positions, spans, displayed cell text, and parser/configuration provenance. Quarantined parser/table records are explicit.
3. **Evidence preparation.** `app.ingestion.chunking.sec_evidence_chunker` converts compatible parsed artifacts into deterministic narrative chunks and structured financial-table evidence under `data/processed/sec_evidence/v1/`. Admission and quarantine remain separate; this stage does not interpret financial values.
4. **Storage.** Numbered migrations `001`–`004` and `EvidenceRepository` persist documents, admitted narrative/table evidence, and quarantines in PostgreSQL. Development commands first validate configured database, role, and non-public schema identity. Isolated tests use generated schemas in the disposable test database instead.
5. **Semantic embedding.** Migration `004` stores versioned child segments for admitted narrative chunks only. The pinned local embedding model creates deterministic offset windows; retrieval aggregates them back to their parent chunks. No table embeddings exist.

## Retrieval contracts

### Narrative

`PostgresKeywordRetriever`, `PostgresSemanticRetriever`, `ReciprocalRankFusionRetriever`, and `HybridRerankingRetriever` work only on admitted narrative parent chunks with document/source hash, section, source elements, and filing metadata.

- Keyword uses parameterized PostgreSQL English full-text search.
- Semantic uses pgvector cosine distance with the pinned local embedding configuration.
- RRF combines keyword and semantic rank lists (`k=60`), keeps component ranks and an inspectable RRF score, and deterministically breaks ties.
- The cross-encoder reranker receives a bounded RRF candidate set (default candidate/rerank depths 50/20), scores deterministic token windows from original candidate text, and retains a raw reranker score separately from the RRF score.

### Tables

`PostgresTableKeywordRetriever` returns a separate structured contract. It searches an admitted-table projection constructed from caption/heading context, observed period/unit strings, and ordered raw display-cell text. Results retain ordered rows/cells, cell kind/spans/locators, source/table identity, warnings, validation status, and parser/chunker identity. The table contract does not infer values, units, row labels, or header-to-cell association; header association remains `NOT_ESTABLISHED`.

Table and narrative relevance datasets, evaluators, result types, and metrics are intentionally separate.

## Provenance and safety

Every admitted retrieval result preserves `document_id` and registered `source_sha256`; narrative results also preserve `chunk_id`, while table results preserve stable table evidence and HTML-table identities. Source locators report structural positions actually observed in HTML; they do not invent page numbers or semantic relationships.

Persistent corpus commands require an explicit `APP_ENV=development`, matching database/role/schema settings, and a non-public schema. They refuse the disposable `financial_rag_test` database. Read-only retrieval/evaluation commands retain those identity checks. Integration tests must use `TEST_POSTGRES_DSN` and generated `evidence_test_*` schemas; no test may target the persistent development corpus.

## Generation boundary

Phase 8 supplies only bounded, admitted narrative evidence to a provider-neutral
generation contract. The OpenAI Responses adapter is selected explicitly through
environment settings and lazy-loads its optional SDK. The model can return only
evidence IDs; application code resolves all citation provenance/URLs from trusted
records. Missing/unknown citations, provenance mismatch, malformed output,
provider errors, and empty evidence yield explicit abstentions. This is citation
identity/provenance validation, not semantic claim-entailment validation. No
provider-specific types escape the adapter, and imports need no credential.

Phase 9 exposes a deliberately wired ranked-evidence-to-generation flow via
FastAPI. The Streamlit UI is an HTTP-only client: it does not connect to the
database, load models, or call a provider SDK.

See [the development plan](DEVELOPMENT_PLAN.md) for acceptance criteria and [the Phase 8 readiness audit](reports/PHASE_8_READINESS_AUDIT.md) for the current verified status.
