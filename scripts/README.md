# Scripts

This directory contains explicit operational entry points. Scripts delegate to typed application modules, are safe to rerun where practical, and report failures clearly.

## Query API and thin UI

Phase 9 exposes server-ranked narrative evidence through the typed API. The
request body accepts only `question`, optional `ticker`, `form_type`, and
`reporting_period_end`; it never accepts caller-provided evidence or citation
metadata. The production dependency requires the guarded local development
configuration, locally cached retrieval/reranking models, and the explicit
Phase 8 provider configuration.

```powershell
python -m pip install -e ".[storage,semantic,generation,ui]"
python -m uvicorn app.main:app --reload
streamlit run ui/app.py
```

The UI uses `API_BASE_URL` (default `http://127.0.0.1:8000`) and calls only
`POST /query`; it does not access PostgreSQL, retrieval code, or a model SDK.
Without valid local configuration, the API returns a generic 503. See
`docs/reports/PHASE_9_API_UI.md` for limits and verification status.

## Grounded generation contract

Phase 8 provides the generation service behind the Phase 9 API. Configure
only the explicit OpenAI adapter in ignored `.env` when an authorized live call
is required:

```text
LLM_PROVIDER=openai
OPENAI_API_KEY=<secret>
LLM_MODEL=gpt-6-astra
LLM_TIMEOUT_SECONDS=30
LLM_MAX_OUTPUT_TOKENS=800
```

Install its optional dependency with `python -m pip install -e ".[generation]"`.
The pinned SDK receives the configured timeout and at most two SDK-managed
retries for retryable transient failures; it does not select another provider
or model.
The service imports the SDK lazily and tests use a fake provider, so no key or
network call is required for ordinary validation. It accepts only bounded,
admitted narrative evidence, validates source-hash provenance against a trusted
application-side mapping, and resolves model citation IDs into trusted metadata.
Missing/unknown citations, malformed output, provider failures, or inadequate
evidence yield an explicit abstention. It validates citation identity and
provenance—not whether every natural-language claim is entailed by evidence.
See `docs/reports/PHASE_8_GROUNDED_GENERATION.md`.

## Persistent local development corpus

Use only a dedicated development database and a non-public schema. Do not use
the disposable `financial_rag_test` integration database as a persistent
corpus. See [LOCAL_DEVELOPMENT_DATABASE.md](../docs/LOCAL_DEVELOPMENT_DATABASE.md)
for prerequisites, safe configuration, WSL setup, and failure meanings.

```powershell
python scripts\bootstrap_local_development_corpus.py
```

Bootstrap validates the registered SEC sources and evidence hashes, verifies the
configured database/role/schema identity, applies migrations, persists the
approved corpus idempotently, verifies counts, and executes a read-only keyword
smoke query. It does not execute evaluation.

## PostgreSQL keyword retrieval

After bootstrapping admitted evidence in the guarded development target,
run the read-only narrative keyword baseline:

```powershell
python scripts\search_sec_evidence.py revenue --ticker AAPL --form-type 10-K --limit 5
```

The script requires the development settings documented above and the `storage` optional dependency. It uses parameterized
PostgreSQL English full-text search and prints ranked candidate IDs plus heading provenance. It
never writes to the database, flattens financial tables, searches quarantined evidence, or reads
raw source files. `--reporting-period-end` accepts an ISO date. A blank or no-match query returns
zero candidates; `--limit` must be 1 through 100.

## Keyword retrieval evaluation

Evaluate a database that already contains approved evidence against the versioned labels:

```powershell
python scripts\evaluate_keyword_retrieval.py
python scripts\evaluate_keyword_retrieval.py --dataset data/evaluation/keyword_retrieval.v2.json
```

The command requires the same guarded development settings and `storage` dependency as search. It
is read-only, validates every answerable label against the admitted artifact provenance, and prints
the dataset hash, retrieval mode, answerable/unanswerable counts, Recall@5, Recall@10,
Precision@5, MRR, and per-case retrieved IDs. Unanswerable cases are reported but excluded from
retrieval-metric denominators. The v1 labels remain a three-case diagnostic set; v2 expands
narrative-only judgments but remains a small benchmark rather than a production-quality claim.

## Structured table keyword retrieval

After guarded bootstrap has applied migration `003`, search only admitted,
structured financial tables without flattening the returned evidence:

```powershell
python scripts\search_sec_tables.py revenue --ticker AAPL --form-type 10-K --limit 5
python scripts\search_sec_tables.py cash --document-id aapl-2024-10k --limit 5
```

The versioned projection indexes only table caption/preceding-heading text,
observed period and table-level unit hints, and ordered raw cell display text.
It uses PostgreSQL English lexical token-OR matching and coverage ranking.
Returned JSON includes the original table/document/source identity, filing
metadata, validation/warning/configuration fields, and ordered raw rows/cells
with locators and spans. It does not establish header associations, normalize
amounts, or infer missing units. Supported exact filters are ticker, form type,
reporting-period end, document ID, and table evidence ID.

Evaluate only the separate table labels:

```powershell
python scripts\evaluate_table_retrieval.py
```

This guarded, read-only command validates `table_retrieval_judgments.v1.json`
against admitted artifacts and manifest provenance, then reports table-only
Recall@5, Recall@10, Precision@5, MRR, dataset hash, retrieval mode, and
answerable/unanswerable counts. It never feeds table labels into the narrative
evaluator. Unanswerable cases are reported but excluded from metric denominators.

## Local semantic narrative retrieval

Phase 6 uses only the pinned local CPU model
`sentence-transformers/all-MiniLM-L6-v2` at revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`; it does not use an API key or
download a model while running. Install the declared optional dependencies in
the WSL virtual environment and configure an absolute, pre-populated cache:

```powershell
/tmp/financial-rag-pgtest-venv/bin/python -m pip install -e ".[dev,storage,semantic]"
# .env (ignored): SEMANTIC_MODEL_CACHE_DIR=/home/yatharth/.cache/financial-rag-models
python scripts/backfill_semantic_embeddings.py
python scripts/search_sec_semantic_evidence.py "cash from operations" --ticker MSFT --limit 5
python scripts/evaluate_semantic_retrieval.py
```

The guarded backfill validates every raw registered source, verifies the development
database/role/non-public schema, applies migration `004`, and only embeds admitted
narrative chunks whose stored source hash matches the registered document. It stores
`public.vector(384)` values only in the configured application schema. The pgvector
extension remains in `public`, so SQL qualifies its type and cosine operator without
adding `public` to the guarded search path. The original chunks are never changed.

The model accepts 256 word pieces including special tokens. The backfill tokenizes
every chunk with offset mapping and creates stable, non-overlapping windows of at
most 254 content tokens, each mapped to its unchanged parent chunk and measured
character span. Retrieval scores child segments but returns the best result per parent
chunk. A fixed `hnsw.ef_search=1000` is set per read-only search transaction so
filtered queries remain repeatable for this small corpus; the HNSW cosine index is
still available for growth. Semantic results are narrative-only and retain original
chunk/document/source/locator provenance. Tables, hybrid fusion, reranking, and
answer generation remain out of scope.

## Hybrid narrative RRF retrieval

Evaluate the guarded narrative hybrid baseline after semantic embeddings exist:

```powershell
python scripts/evaluate_hybrid_retrieval.py --branch-depth 50
```

The hybrid retriever calls the independent keyword and semantic branches with
the same supported ticker/form/reporting-period filters, then deduplicates by
stable `chunk_id`. Its score is the sum of `1 / (60 + rank)` for each branch in
which a chunk appears; ranks are one-based. Equal scores sort by document ID,
chunk sequence, then chunk ID. `--branch-depth` is validated from 1 through
100; public result limits remain 1 through 100. A failing branch is an explicit
error, never a silently successful partial result. Returned candidates preserve
the source/document/hash/text/locator provenance from the source retrievers.

## Local bounded cross-encoder reranking

After semantic embeddings and the exact local reranker snapshot are available,
evaluate bounded narrative reranking:

```powershell
python scripts\evaluate_hybrid_reranking.py --candidate-depth 50 --rerank-depth 20
```

The reranker is `cross-encoder/ms-marco-MiniLM-L6-v2` revision
`233902d25c440f23af6f7d6e94d2946bac0bee0a`. It is loaded only from the exact
snapshot beneath `SEMANTIC_MODEL_CACHE_DIR` with `local_files_only=True`; a
missing snapshot is an error, not a reason to download or substitute a model.
It receives only a bounded RRF candidate set, creates deterministic windows for
the original narrative text, and returns raw cross-encoder scores separately
from RRF scores. It is narrative-only, read-only, and does not change the
corpus or embeddings. Use the v2 dataset/metrics printed by the command only
as a small-benchmark diagnostic, not as an answer-quality claim.

## SEC registration manifest

Validate the tracked Phase 1 registration contract and immutable local source bytes:

```powershell
python scripts\validate_sec_registration_manifest.py
```

The command reads `data/manifests/sec_documents.v1.json` and approved files beneath
`data/raw/sec_filings/`. It has no network behavior and never rewrites registered hashes or raw
files. Exit code `0` means all sources match; `1` reports missing/changed/unreadable sources; `2`
reports an invalid manifest. See `docs/SEC_REGISTRATION_MANIFEST.md` for the contract.

## Structure-preserving SEC HTML parser

Parse only registered sources whose current source hash and byte size are valid:

```powershell
python scripts\parse_registered_sec_html.py
```

The parser writes deterministic substantive artifacts beneath `data/processed/sec_parsed/v1/`:

- `<document_id>.json` — separate visible narrative blocks, structured tables, and explicit quarantined tables.
- `run_metadata.json` — parser/configuration identity, per-document artifact hashes, run status counts, and an operational timestamp.

Use `--output-dir data/processed/<approved-subdirectory>` only for a project-local processed-data path; paths outside `data/processed/` are rejected. The parser uses the versioned registration manifest, rechecks each source before reading, has no network behavior, and never changes raw HTML, companion resources, or registration hashes. It exits non-zero for source-integrity failure or a document quarantine. See the parser section of `CODEX_REPORT.md` for locator and structural-validation limits.

## Section-aware evidence preparation

Prepare evidence only from manifest-approved, hash-verified sources and compatible `PARSED` parser artifacts:

```powershell
python scripts\prepare_sec_evidence.py
```

The command writes `data/processed/sec_evidence/v1/<document_id>.json` plus run metadata. Narrative chunks and structured financial-table evidence remain separate. Low-information parser blocks and structurally invalid tables are recorded in `quarantined_evidence`; a document itself is fatal only when it cannot admit any trusted evidence or source/parser integrity fails. `--output-dir` is accepted only beneath `data/processed/`. The command never reads unregistered raw files, accesses the network, or changes existing source/parser/QA artifacts.

## SEC source verification

Run the offline, read-only corpus check from the repository root:

```powershell
python scripts\verify_sec_documents.py
```

It reads the ten expected local HTML files and regenerates only:

- `data/processed/document_verification/document_manifest.csv`
- `data/processed/document_verification/document_verification_report.md`

The command performs no network requests and does not modify raw filings or their companion folders.

## Financial table QA package

After document verification, build the offline human-review package:

```powershell
python scripts\build_table_qa.py
```

The command reads the existing manifest and verified local filings. It writes exactly three review
artifacts under `data/processed/document_verification/table_qa/`. Automated selection does not mark
financial values as verified; all checklist items begin as `PENDING HUMAN REVIEW`.
