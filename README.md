# Financial Research RAG Assistant

An evidence-first research project over ten locally registered Apple and Microsoft SEC filings. It currently provides immutable-source validation, structure-preserving parsing, guarded PostgreSQL evidence persistence, separate narrative and table retrieval baselines, local semantic retrieval, deterministic RRF fusion, and local bounded reranking.

> **Current status:** retrieval and a bounded provider-neutral grounded-generation contract are implemented. Citation identity/provenance validation and explicit abstention are implemented; claim-entailment validation, a query API, and a Streamlit UI are not. See the [roadmap](docs/DEVELOPMENT_PLAN.md) and [Phase 8 report](docs/reports/PHASE_8_GROUNDED_GENERATION.md).

## What is implemented

| Area | Status | Important boundary |
| --- | --- | --- |
| Registered SEC sources | Verified | Ten local source files are hash-checked; raw source bytes are never changed. |
| Parsing and evidence preparation | Implemented | Narrative blocks and structured financial tables remain separate evidence types. |
| PostgreSQL persistence | Implemented | Persistent development work is restricted to the configured non-public schema; isolated tests use generated schemas only. |
| Narrative retrieval | Implemented | PostgreSQL keyword, local semantic, RRF, and bounded cross-encoder reranking are separate modes. |
| Table retrieval | Implemented | Keyword-only structured table retrieval; it does not establish numeric/header semantics. |
| Generation / citations / abstention | Implemented | Bounded narrative evidence only; citations resolve from trusted records, while factual entailment is not verified. |
| HTTP query API / UI | Not implemented | The sole application endpoint is `GET /health`. |

## Supported environment

`pyproject.toml` requires Python `>=3.11,<3.14`. The complete retrieval workflow was most recently exercised in WSL Ubuntu with Python 3.12.3 and PostgreSQL 16 with pgvector 0.6.0. The Windows checkout supports source validation, lint, compilation, and tests when dependencies are installed; the documented persistent corpus workflow is WSL-oriented.

## Install

Create an isolated environment and install the feature sets needed for the work you intend to run. `pyproject.toml` is canonical; `requirements.txt` installs only the project `dev` extra.

```bash
# WSL / Linux example, from the repository root
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,storage,semantic,generation]"
```

For PowerShell activation, use `./.venv/Scripts/Activate.ps1`. The HTML parser dependencies are already part of `dev` and may also be installed with the explicit `verification` extra.

## Local configuration and database safety

Copy `.env.example` to ignored `.env` only after choosing a dedicated database, role, and non-public application schema. Never use `financial_rag_test` for the persistent corpus, and do not use `public` as the application schema.

```text
APP_ENV=development
DATABASE_URL=dbname=financial_rag_dev user=<non_superuser_role>
DEVELOPMENT_DATABASE_NAME=financial_rag_dev
DEVELOPMENT_DATABASE_ROLE=<non_superuser_role>
DEVELOPMENT_DATABASE_SCHEMA=financial_rag_dev
SEMANTIC_MODEL_CACHE_DIR=/absolute/path/outside/the/repository/model-cache
# Required only when making an authorized generation request:
LLM_PROVIDER=openai
OPENAI_API_KEY=<local secret only>
LLM_MODEL=gpt-5.4
LLM_TIMEOUT_SECONDS=30
LLM_MAX_OUTPUT_TOKENS=800
```

PostgreSQL must be running and pgvector must already be installed by an administrator. The project neither creates a database/role nor enables the extension automatically. The guarded bootstrap validates the connected database/role, refuses `financial_rag_test` and `public`, creates only the named application schema when allowed, applies migrations in that schema, and performs idempotent corpus persistence:

```bash
python scripts/bootstrap_local_development_corpus.py
```

See [the local development database runbook](docs/LOCAL_DEVELOPMENT_DATABASE.md) for prerequisite commands, failure meanings, and its safety contract.

## Immutable source and evidence workflow

The following commands do not download filings or rewrite their raw HTML/companion directories.

```bash
python scripts/validate_sec_registration_manifest.py
python scripts/parse_registered_sec_html.py
python scripts/prepare_sec_evidence.py
```

Parser output is versioned under `data/processed/sec_parsed/v1/`; prepared evidence is versioned under `data/processed/sec_evidence/v1/`. Recreating either is an explicit operation, not a prerequisite for read-only retrieval evaluation.

## Retrieval and evaluations

All commands below require the guarded development configuration and an already bootstrapped corpus. They are read-only. Use the v2 narrative dataset explicitly when comparing retrieval modes; the keyword evaluator defaults to the older v1 diagnostic dataset.

```bash
# Narrative keyword
python scripts/search_sec_evidence.py revenue --ticker AAPL --form-type 10-K --limit 5
python scripts/evaluate_keyword_retrieval.py --dataset data/evaluation/keyword_retrieval.v2.json

# Structured tables (separate result type and separate labels)
python scripts/search_sec_tables.py revenue --ticker AAPL --form-type 10-K --limit 5
python scripts/evaluate_table_retrieval.py

# Local semantic / fusion / reranking narrative evaluations
python scripts/evaluate_semantic_retrieval.py
python scripts/evaluate_hybrid_retrieval.py --branch-depth 50
python scripts/evaluate_hybrid_reranking.py --candidate-depth 50 --rerank-depth 20
```

The narrative v2 dataset must hash to:

```text
d79de57f251a10de5797276e42b7d4fc6236124b9c268badc8477c538a6f1c9f
```

Verify it without changing the file:

```powershell
(Get-FileHash data/evaluation/keyword_retrieval.v2.json -Algorithm SHA256).Hash.ToLower()
```

Historical measurements and freshly reproduced measurements must be kept distinct. The latest Phase 8 reproduction results and methodology are in [the readiness audit](docs/reports/PHASE_8_READINESS_AUDIT.md). These small manually judged benchmarks are diagnostic; they do not establish production retrieval quality or financial correctness.

## Local models and offline operation

Semantic retrieval requires the exact cached snapshot of `sentence-transformers/all-MiniLM-L6-v2` revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. Bounded reranking requires the exact cached snapshot of `cross-encoder/ms-marco-MiniLM-L6-v2` revision `233902d25c440f23af6f7d6e94d2946bac0bee0a`. Both loaders use exact local snapshot paths and `local_files_only=True`; they fail rather than downloading a substitute. Do not commit model weights or caches.

## Verification

```bash
python -m ruff check app scripts tests
python -m compileall -q app scripts tests
python -m pytest tests/unit -q
# Requires TEST_POSTGRES_DSN and only creates generated evidence_test_* schemas:
python -m pytest tests/integration -q
```

The integration suite belongs to the disposable `financial_rag_test` target and must never point at the persistent corpus. See [scripts/README.md](scripts/README.md) for the detailed CLI contracts.

## Existing application entry point

Only the health route exists today:

```bash
python -m uvicorn app.main:app --reload
# GET http://127.0.0.1:8000/health
```

There is no query endpoint and no runnable Streamlit application. Those remain Phase 9 work.

## Limitations

- Retrieval is separate from generation. Generation validates citation identity and provenance, but does not prove factual claim entailment.
- Narrative and table evidence have separate retrieval contracts and benchmarks; they are not mixed.
- Table header association remains `NOT_ESTABLISHED`; no numeric interpretation is inferred.
- Semantic/reranking model caches and PostgreSQL/pgvector are local prerequisites, not repository contents.
- The evaluated corpus is limited to ten filings and small manually judged datasets.
- A full Phase 7B live isolated-integration rerun has not yet been recorded after its implementation; see the audit for the exact validation status.

## Roadmap

The authoritative sequence is [docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md). The actual next feature phase is Phase 8: grounded generation, citations, and abstention. Documentation/portfolio demonstration is Phase 11, not Phase 8.
