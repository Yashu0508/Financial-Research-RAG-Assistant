# Financial Research RAG Assistant

An evidence-oriented financial research assistant for official SEC filings. It validates registered Apple and Microsoft filing HTML, extracts provenance-rich narrative and financial-table evidence, retrieves with PostgreSQL full-text and local vector search, and returns grounded answers with validated citations or explicit abstention.

## Problem statement

Financial analysts and researchers need to answer precise questions from long SEC filings, but the relevant evidence is distributed across narrative disclosures, risk factors, management discussion, and financial tables. Conventional keyword search can miss semantically related passages, while generic LLM answers can lose the filing, reporting period, units, signs, or table context behind a claim.

This project solves the problem of producing traceable answers from a bounded corpus of official Apple and Microsoft filings. It validates and preserves filing structure, keeps narrative evidence separate from financial-table evidence, combines lexical and semantic retrieval, reranks the strongest candidates, and generates an answer only from supplied evidence. Every returned citation is resolved against trusted source metadata; when the corpus does not provide sufficient support, the system abstains instead of presenting an unsupported conclusion.

## Architecture

~~~mermaid
flowchart LR
  SEC[Registered SEC HTML] --> V[Hash and metadata validation]
  V --> P[Structure-preserving parser]
  P --> E[Narrative chunks + table evidence]
  E --> DB[(PostgreSQL + pgvector)]
  DB --> K[Keyword retrieval]
  DB --> S[Semantic narrative retrieval]
  K --> R[RRF k=60]
  S --> R
  R --> X[Bounded cross-encoder reranking]
  X --> C[Evidence context]
  C --> G[OpenAI Responses adapter]
  G --> CV[Citation/provenance validation]
  CV --> A[Cited answer or abstention]
  API[FastAPI POST /query] --> C
  UI[Streamlit HTTP client] --> API
~~~

The ingestion path protects source identity before parsing. Narrative and table evidence remain separate through storage and retrieval. Narrative candidates can pass through semantic retrieval, RRF, and reranking; tables use a separate structured keyword contract. Generation receives bounded admitted narrative evidence, while application code resolves provider-returned evidence IDs to trusted metadata.

## Workflow

1. Validate registered source metadata, byte size, and SHA-256.
2. Parse valid SEC HTML while preserving sections, tables, locators, and provenance.
3. Produce deterministic narrative chunks and structured tables; quarantine unreliable records.
4. Persist admitted evidence and versioned narrative vectors in a guarded PostgreSQL schema.
5. Accept a question with optional ticker, form, and reporting-period filters.
6. Retrieve, fuse, and optionally rerank provenance-rich candidates.
7. Build bounded context and call the configured provider.
8. Validate citations and return an answer, warnings, or abstention.

## Retrieval and grounding

Keyword retrieval supports exact filing terminology; local semantic retrieval supports related phrasing. RRF combines ranked lists with k=60, retaining branch ranks and deterministic tie-breaking. A bounded local cross-encoder reranks fused narrative candidates while preserving the original RRF score.

The provider-neutral generation contract allows citations only to supplied evidence IDs. Unknown IDs, provenance mismatches, malformed output, provider failures, empty evidence, and unsupported questions become safe abstentions. Citation validation checks identity and provenance, not semantic claim entailment; the system does not claim hallucination-free generation.

## Financial evidence

Financial values are meaningful only with row labels, periods, units, signs, and column relationships. Parsed table records preserve displayed cell text, row/cell spans, locators, headings, period-header strings, and unit hints. Quarantine and admission are explicit. Tables are not flattened into ordinary narrative text, and header-to-cell association remains NOT_ESTABLISHED.

## Technology stack

| Technology | Purpose |
|---|---|
| Python 3.11–3.13 | Application, ingestion, retrieval, evaluation, and tests |
| FastAPI / Uvicorn | Typed HTTP delivery |
| PostgreSQL / pgvector | Evidence persistence, full-text, and vector search |
| Beautiful Soup / lxml | SEC HTML parsing |
| Sentence Transformers / PyTorch | Embeddings and local reranking |
| OpenAI Responses API | Configured grounded-generation adapter |
| Streamlit | Thin HTTP client UI |
| pytest / Ruff | Tests and quality checks |

## Repository structure

~~~text
app/api/          FastAPI routes, schemas, and query wiring
app/core/         Settings
app/ingestion/    Manifest validation, parsing, and chunking
app/retrieval/    Keyword, semantic, table, hybrid, reranking
app/storage/      PostgreSQL repositories and migrations
app/generation/   Providers, prompts, citations, abstention
app/evaluation/   Retrieval and answer contracts
ui/               Streamlit client
scripts/          Validation, persistence, search, evaluation CLIs
data/             Manifest and versioned evaluation data
docs/             Architecture, contracts, runbooks, reports
tests/            Unit and opt-in PostgreSQL integration tests
~~~

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md), [the SEC manifest](data/manifests/sec_documents.v1.json), and [scripts/README.md](scripts/README.md).

## Corpus and setup

The pilot corpus contains ten locally registered Apple and Microsoft filings: FY2022–FY2024 annual filings and available quarterly filings. It is a bounded dataset, not exhaustive SEC coverage.

Prerequisites: Python 3.11–3.13, Git, PostgreSQL with pgvector installed, and exact local model snapshots for semantic retrieval/reranking.

~~~bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,storage,semantic,generation,ui]"
cp .env.example .env
python scripts/validate_sec_registration_manifest.py
python scripts/parse_registered_sec_html.py
python scripts/prepare_sec_evidence.py
python scripts/bootstrap_local_development_corpus.py
~~~

For PowerShell activation use .\.venv\Scripts\Activate.ps1. The bootstrap refuses the disposable financial_rag_test database and public schema. Read [docs/LOCAL_DEVELOPMENT_DATABASE.md](docs/LOCAL_DEVELOPMENT_DATABASE.md) first.

## Configuration

Copy [.env.example](.env.example) to an ignored .env; never commit credentials.

| Variable | Purpose | Required |
|---|---|---|
| APP_ENV | Guarded development workflow | Persistence |
| DATABASE_URL | PostgreSQL target | Persistence |
| DEVELOPMENT_DATABASE_NAME / ROLE / SCHEMA | Expected safe target identity | Persistence |
| LLM_PROVIDER | Provider selection; active value is openai | Generation |
| OPENAI_API_KEY | Local provider secret | Live generation |
| LLM_MODEL | Active model: gpt-6-astra | Generation |
| LLM_TIMEOUT_SECONDS | Provider timeout; default 30 | No |
| LLM_MAX_OUTPUT_TOKENS | Output bound; default 800 | No |
| SEMANTIC_MODEL_CACHE_DIR | Exact local model snapshots | Semantic retrieval |
| SEMANTIC_EMBEDDING_BATCH_SIZE | Backfill batch size; default 16 | No |

## Usage

~~~bash
python -m uvicorn app.main:app --reload
streamlit run ui/app.py
~~~

POST /query accepts question (1–1000 characters), optional ticker, form_type (10-K/10-Q), and reporting_period_end. Responses contain status (answered/abstained), answer, citations, warnings, and an optional abstention reason. The Streamlit client sends HTTP only; it does not access the database, models, or provider SDK.

Example questions: How did cash from operations change across annual filings? Which supply-chain risks does a filing disclose? Which evidence supports a reported financial-statement value?

## Evaluation

The canonical narrative dataset [keyword_retrieval.v2.json](data/evaluation/keyword_retrieval.v2.json) contains 20 answerable and 3 unanswerable manually judged cases. Unanswerable cases are excluded from retrieval denominators.

| Mode | Recall@5 | Recall@10 | Precision@5 | MRR |
|---|---:|---:|---:|---:|
| Keyword | 0.05 | 0.05 | 0.01 | 0.05 |
| Semantic | 0.65 | 0.90 | 0.14 | 0.5904 |
| RRF | 0.65 | 0.90 | 0.14 | 0.5892 |
| RRF + cross-encoder | 0.75 | 0.90 | 0.15 | 0.6972 |

The separate table keyword benchmark reports Recall@5/10 0.875/0.875, Precision@5 0.175, and MRR 0.71875 over eight answerable cases. These are diagnostic retrieval measurements, not financial accuracy, answer faithfulness, production quality, latency, or cost. See [Phase 10](docs/reports/PHASE_10_EVALUATION_HARDENING.md) and [Task 11](docs/reports/TASK_11_TABLE_KEYWORD_RETRIEVAL.md).

## Testing

~~~bash
python -m ruff check app scripts tests
python -m compileall -q app scripts tests
python -m pytest tests/unit -q
# Optional isolated PostgreSQL suite; requires TEST_POSTGRES_DSN
python -m pytest tests/integration -q
~~~

Integration tests create generated evidence_test_* schemas and must never target the persistent development corpus. Unit coverage includes ingestion, storage contracts, retrieval, generation/citation validation, API, and UI behavior. Live provider access is not implied by passing tests.

## Limitations and security

The corpus is small and registered locally. Table header association is not established; table semantic retrieval is out of scope. Exact local model snapshots are required. Citation validation does not prove entailment. Live provider behavior, broader answer-quality evaluation, and production monitoring require additional authorized validation.

Keep .env and API keys outside version control. Use a dedicated non-test database and non-public schema. The application does not claim authentication, encryption, access isolation, or deletion guarantees not supported by the implementation.

## License and references

Package metadata declares a proprietary license; no open-source license is asserted. References: [SEC EDGAR](https://www.sec.gov/edgar/search/), [SEC API documentation](https://www.sec.gov/edgar/sec-api-documentation), [pgvector](https://github.com/pgvector/pgvector), [FastAPI](https://fastapi.tiangolo.com/), [Sentence Transformers](https://www.sbert.net/), and [OpenAI Python API reference](https://developers.openai.com/api/reference/python/).

