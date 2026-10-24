# Development plan

Each phase begins only after its dependencies and prior acceptance criteria are satisfied. This file is a roadmap, not a claim that future phases are implemented.

## 1. Scaffold and environment validation

- **Objective:** Establish package boundaries, configuration, documentation, and an executable health check.
- **Dependencies:** Python 3.11-3.13 and Git.
- **Deliverables:** Repository scaffold, dependency metadata, `/health`, basic tests, handoff report.
- **Acceptance criteria:** Modules compile; configuration imports without secrets/services; health test passes; actual checks are documented.

## 2. Document manifest and ingestion

- **Objective:** Register the ten manually downloaded official filings and validate local source identity without network automation.
- **Dependencies:** User-provided filings and authoritative source URLs; phase 1.
- **Status:** Phase 1 manifest/immutable-loader slice completed. Parsing, cleaning, chunking, and storage remain separate later work.
- **Deliverables:** Versioned manifest schema/example, loader, hash verification, duplicate/idempotency rules, tests.
- **Acceptance criteria:** Each available file has validated metadata and hash; missing files are reported honestly; reruns do not duplicate records or mutate source files.

## 3. Parsing, cleaning, validation, and chunking

- **Status:** Structure-preserving parsing and deterministic section-aware evidence chunking for registered local SEC HTML are complete. Cleaning as a separate stage, PDF parsing, and storage remain deferred.
- **Objective:** Produce high-quality, provenance-rich passages from PDF/HTML inputs.
- **Dependencies:** Valid manifest entries; selected parser dependencies.
- **Deliverables:** Format parsers, cleaning rules, quality checks, section-aware chunker, derived artifact versioning, fixtures/tests.
- **Acceptance criteria:** Representative filings parse deterministically; chunks retain document/section/location provenance; failures are explicit; raw bytes remain unchanged.

## 4. Database schema and storage

- **Status:** Phase 4A/04B persistence and isolated live PostgreSQL validation are complete. Task 08 adds the separate guarded persistent-local-development workflow; indexing beyond the Task 06 keyword baseline remains deferred.
- **Objective:** Persist documents, passages, processing state, full-text fields, and future vectors.
- **Dependencies:** Confirmed metadata/chunk contracts; accessible PostgreSQL with pgvector.
- **Deliverables:** Reviewed schema, migrations, repository interfaces/implementation, transactional/idempotent writes, integration tests.
- **Acceptance criteria:** Fresh migration and rollback path are tested; constraints enforce provenance; re-ingestion is safe; integration tests use an isolated database.

## 5. Keyword retrieval baseline

- **Status:** PostgreSQL English full-text baseline and Task 07's small, versioned three-case evaluation set are implemented and exercised in the isolated live database integration suite. Results are a diagnostic baseline, not a quality benchmark.
- **Objective:** Build a transparent PostgreSQL full-text baseline.
- **Dependencies:** Populated evidence store; evaluation query set draft.
- **Deliverables:** Query normalization/filtering, FTS ranking, shared candidate contract, baseline evaluation.
- **Acceptance criteria:** Company/form/period filters work; ranked results include provenance; metrics are reproducible and keyword retrieval is testable independently.

### Task 08 — safe local development database workflow

- **Status:** Implemented and live-validated in the dedicated `financial_rag_dev` database and non-public `financial_rag_dev` schema.
- **Objective:** Reproduce a persistent local evidence corpus without risking the disposable integration database, `public`, or an arbitrary connection target.
- **Deliverables:** Explicit development target configuration; database/role/schema guard; schema-scoped migration, persistence, retrieval, and evaluation CLIs; idempotent bootstrap/readback verification; developer runbook and tests.
- **Acceptance criteria:** Unsafe targets fail before mutation; bootstrap reuses manifest/evidence integrity checks and is idempotent; live initialization is reported only after execution against a dedicated development target.

### Task 09 — versioned judged retrieval benchmark v2

- **Status:** Implemented for the existing PostgreSQL narrative keyword baseline.
- **Objective:** Expand the manually grounded narrative benchmark without changing Task 07 v1, and distinguish answerable retrieval judgments from explicitly unanswerable questions.
- **Deliverables:** `keyword_retrieval.v2.json`; artifact-provenance validation; multiple-relevance and unanswerable-case evaluation support; dataset hash/mode/count reporting; tests and measured persistent-corpus run.
- **Acceptance criteria:** Every v2 answerable label resolves to exactly one admitted narrative chunk with matching document, source hash, and locator; unanswerable cases have no target labels and are excluded from retrieval metric denominators; table evidence is rejected by the narrative evaluator; v1 interpretation remains compatible.

### Task 10 — table-evidence retrieval contract and benchmark preparation

- **Status:** Implemented as a contract and separate validation-only benchmark; table retrieval itself remains unimplemented.
- **Objective:** Preserve structured financial-table evidence, provenance, and evaluation separation before adding a table retrieval method.
- **Deliverables:** A documented table-evidence result/admission contract; separately versioned table judgments; artifact/manifest provenance validation; Task 09 metric and filter audit.
- **Acceptance criteria:** A table label resolves only to admitted structured table evidence with matching source/document/table provenance; quarantined records cannot be trusted evidence; table labels do not enter narrative metrics; no table-retrieval performance is claimed before a retriever executes.

### Task 11 — structure-preserving PostgreSQL table keyword retrieval

- **Status:** Implemented and measured against the separate table benchmark.
- **Objective:** Provide a narrow, deterministic lexical baseline over admitted financial-table evidence without collapsing it into narrative text.
- **Deliverables:** Versioned table search projection/index, structured table result contract, guarded retrieval/evaluation CLIs, separate table metrics, isolated PostgreSQL tests, and persistent-corpus measurement.
- **Acceptance criteria:** Only admitted source-consistent tables are searchable; results retain table/document provenance plus ordered raw rows/cells; filters and deterministic ranking work; quarantines remain excluded; table metrics remain separate from narrative metrics.

## 6. Semantic retrieval

- **Status:** Implemented and measured for admitted narrative evidence only. Table semantic retrieval remains out of scope.
- **Objective:** Add locally reproducible embedding retrieval.
- **Dependencies:** Valid chunks, pgvector schema, explicitly selected Sentence Transformer and version.
- **Deliverables:** Batched embedding job, vector metadata/versioning, semantic retriever, evaluation comparison.
- **Acceptance criteria:** Embeddings are reproducible/versioned; stale/mixed vectors are prevented; semantic retrieval is benchmarked independently against the same query set.

### Phase 6 implementation — local semantic narrative retrieval

- **Status:** Implemented against the guarded `financial_rag_dev` corpus.
- **Deliverables:** Migration `004`, pinned local CPU model configuration, deterministic token-offset windows, source-consistent idempotent backfill, pgvector cosine retrieval, v2 evaluation CLI, isolated pgvector integration coverage, and operating documentation.
- **Acceptance criteria:** Only admitted narrative chunks with matching registered source hashes are embedded; every vector has model/configuration/source identity; input longer than the 256-token model limit is represented by deterministic child segments with measured parent spans; result limits apply after parent-chunk aggregation; unanswerable labels remain outside metric denominators.

## 7. Hybrid fusion and reranking

- **Status:** RRF fusion and pinned, local bounded narrative reranking are implemented and measured on the v2 narrative benchmark. Validation coverage for the new reranker remains narrower than the complete Phase 7 acceptance scope; see `docs/reports/PHASE_7B_RERANKING.md` and the Phase 8 readiness audit.
- **Objective:** Combine complementary candidate sets and improve final evidence ordering.
- **Dependencies:** Phases 5-6 and judged retrieval examples.
- **Deliverables:** Configurable fusion, bounded reranking, component ablations, latency/quality report.
- **Acceptance criteria:** Fusion/reranking inputs and scores are inspectable; each stage can be disabled; improvements are measured without invented metrics.

### Phase 7 implementation — narrative RRF fusion

- **Status:** Implemented with bounded local reranking. The RRF layer remains independently usable and evaluated; reranking uses a separately pinned local snapshot and preserves component-score distinction.
- **Deliverables:** A provenance-preserving hybrid result contract, explicit branch
  depth/candidate limits, RRF `k=60`, guarded v2 evaluation CLI, and independent
  branch/fusion failure tests.
- **Acceptance criteria:** Stable chunk-ID deduplication, deterministic tie-breaking,
  branch errors that are not silently hidden, and v2 metrics using unchanged labels.

## 8. Grounded generation, citations, and abstention

- **Status:** Implemented with a provider-neutral, narrative-only contract and an explicitly configured OpenAI Responses adapter. The active documented configuration is `gpt-6-astra`; the pinned SDK uses bounded retries for transient failures. Fake-provider tests cover citation identity/provenance validation, provider errors, and explicit abstentions; live OpenAI access remains unverified. Citation validation does not establish claim entailment.
- **Objective:** Generate only from supplied evidence and return verified citations or an explicit abstention.
- **Dependencies:** Stable ranked evidence contract; chosen provider protocol and evaluation cases.
- **Deliverables:** Provider-independent interface, one separately configured adapter, prompts, citation resolver/validator, abstention policy, tests.
- **Acceptance criteria:** No credential is required at import; every cited identifier resolves to supplied evidence; unsupported/insufficient cases abstain; provider-specific types do not escape the adapter.

## 9. FastAPI and Streamlit integration

- **Status:** Complete after Phase 9B verification. Typed `/query` delivery and a thin Streamlit HTTP client are covered with deterministic mocks; live generation remains unverified without an authorized provider request. No UI/database/model logic is duplicated client-side.
- **Objective:** Expose real pipeline behavior through typed HTTP and a thin demonstration UI.
- **Dependencies:** Operational phases 4-8.
- **Deliverables:** Query endpoint, error/abstention schemas, dependency wiring, Streamlit client, integration tests.
- **Acceptance criteria:** UI contains no retrieval/generation logic; responses distinguish answers from abstentions; errors do not leak secrets; end-to-end tests cover supported and unsupported questions.

## 10. Evaluation, regression testing, and hardening

- **Status:** Implemented with deterministic answer-contract fixtures, preserved retrieval measurements, and a small-corpus reranking regression gate; final full-suite and isolated-integration reruns after this phase remain required before completion. Live-provider/semantic-entailment evaluation remains out of scope.
- **Objective:** Make retrieval, grounding, citation quality, abstention, and operational behavior measurable.
- **Dependencies:** End-to-end system and reviewed evaluation set.
- **Deliverables:** Versioned datasets, metric implementations, regression thresholds, security/performance checks, reproducible reports.
- **Acceptance criteria:** Reports identify corpus/config/model versions; regressions fail visibly; evaluation separates retrieval from answer failures; no synthetic result is presented as measured fact.

## 11. Documentation and portfolio demonstration

- **Objective:** Present design choices, evidence, limitations, and reproducible usage for technical review.
- **Dependencies:** Hardened evaluated system.
- **Deliverables:** Updated architecture/runbooks, demo workflow, results with methodology, trade-off narrative.
- **Acceptance criteria:** A fresh setup can reproduce the documented workflow; claims link to actual checks/results; known limitations and data/licensing policy are explicit.
