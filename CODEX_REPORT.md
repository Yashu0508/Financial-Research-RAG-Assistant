# Codex handoff report

## 1. Project identity and objective

**Project:** Financial Research RAG Assistant with Evidence-Based Answers

**Objective:** Build a maintainable research assistant for official financial filings that retrieves traceable evidence, produces evidence-grounded answers with citations, and explicitly abstains when the corpus does not support an answer.

The repository is currently an architecture scaffold, not a functioning RAG assistant.

## 2. Task performed

This run created the initial repository structure, package boundaries, foundational documentation, dependency/configuration files, a minimal FastAPI `/health` endpoint, typed optional settings, two unit tests, data-directory sentinels, and this handoff report. Git was initialized on branch `main`. No commit was created.

This run did not download filings, access the SEC, install/start PostgreSQL, load models, call an LLM, select an LLM provider, create database migrations, or implement ingestion, retrieval, generation, evaluation, or UI behavior.

## 3. Workspace inspection

Before modification, `D:\Financial Research RAG Assistant` was empty, including hidden-file inspection. It was not a Git repository. Therefore:

- No existing files or directories required preservation or adaptation.
- No files were overwritten, moved, or deleted.
- No architectural conflicts were discovered.
- The requested structure was created directly in the existing workspace rather than adding a redundant `financial-research-rag/` nested directory.
- Available interpreter: Python 3.13.16; pip 26.2.1.

## 4. Final directory tree

Generated caches and the internal `.git/` directory are omitted from this readable tree; every project file is shown.

```text
Financial Research RAG Assistant/
|-- .env.example
|-- .gitignore
|-- CHANGELOG.md
|-- CODEX_REPORT.md
|-- README.md
|-- pyproject.toml
|-- requirements.txt
|-- app/
|   |-- __init__.py
|   |-- main.py
|   |-- api/
|   |   |-- __init__.py
|   |   |-- routes/
|   |   |   |-- __init__.py
|   |   |   `-- health.py
|   |   `-- schemas/
|   |       |-- __init__.py
|   |       `-- health.py
|   |-- core/
|   |   |-- __init__.py
|   |   `-- config.py
|   |-- ingestion/
|   |   |-- __init__.py
|   |   |-- loaders/__init__.py
|   |   |-- parsers/__init__.py
|   |   |-- cleaning/__init__.py
|   |   |-- chunking/__init__.py
|   |   `-- validation/__init__.py
|   |-- retrieval/
|   |   |-- __init__.py
|   |   |-- keyword/__init__.py
|   |   |-- semantic/__init__.py
|   |   |-- hybrid/__init__.py
|   |   `-- reranking/__init__.py
|   |-- generation/
|   |   |-- __init__.py
|   |   |-- providers/__init__.py
|   |   |-- prompts/__init__.py
|   |   |-- citations/__init__.py
|   |   `-- abstention/__init__.py
|   |-- storage/
|   |   |-- __init__.py
|   |   |-- repositories/__init__.py
|   |   `-- migrations/.gitkeep
|   `-- evaluation/
|       |-- __init__.py
|       |-- metrics/__init__.py
|       |-- retrieval/__init__.py
|       |-- answers/__init__.py
|       `-- reporting/__init__.py
|-- data/
|   |-- raw/sec_filings/
|   |   |-- Apple/.gitkeep
|   |   `-- Microsoft/.gitkeep
|   |-- processed/.gitkeep
|   |-- indexes/.gitkeep
|   `-- evaluation/.gitkeep
|-- docs/
|   |-- ARCHITECTURE.md
|   |-- DATA_DICTIONARY.md
|   `-- DEVELOPMENT_PLAN.md
|-- reports/.gitkeep
|-- scripts/README.md
|-- tests/
|   |-- unit/
|   |   |-- test_config.py
|   |   `-- test_health.py
|   |-- integration/.gitkeep
|   `-- regression/.gitkeep
`-- ui/README.md
```

## 5. Architecture decisions

- **Offline ownership:** `app.ingestion` will load immutable manifest entries, parse formats, clean/validate content, and create section-aware chunks. `app.storage` will own persistence boundaries and PostgreSQL/pgvector adapters.
- **Online ownership:** independent keyword and semantic retrievers will return a shared provenance-rich candidate contract. Hybrid fusion consumes their results; reranking consumes a bounded fused set. Generation receives selected evidence only.
- **Evidence store:** PostgreSQL/pgvector is a dependency used by both retrievers for documents, passages, filters, full-text data, and vectors—not a downstream step after retrieval.
- **Provenance:** stable document/chunk identifiers, source URLs, content hashes, parser/model versions, and best-available source locations are carried from ingestion through citation resolution. Page numbers remain nullable.
- **Generation boundary:** provider-specific adapters will implement a future inward-facing protocol. No provider, SDK, or fake generation implementation exists now.
- **Abstention:** designed as an explicit decision after evidence and citation validation, not merely prompt language.
- **Evaluation:** future evaluation calls public component interfaces and uses versioned datasets; production components do not depend on evaluation modules.
- **Configuration:** `pydantic-settings` reads environment variables and optional `.env`; all external-service values default to `None`, so importing/health checks need no secrets or database.
- **Dependency source:** `pyproject.toml` is canonical. `requirements.txt` delegates to `-e .[dev]`, avoiding a contradictory second version list.
- **Deferred packages:** Streamlit, database drivers, pgvector, Sentence Transformers, PyMuPDF/HTML parsers, and any LLM SDK are intentionally omitted until a phase exercises them.
- **Raw-data policy:** files under `data/raw/sec_filings/` are ignored by default while directory sentinels are tracked. A future versioned manifest will preserve source URLs and hashes for reproducibility.

Material deviations from the illustrative tree:

1. Used the existing workspace as the project root rather than nesting another project directory.
2. Added `app/api/routes/health.py` and `app/api/schemas/health.py` because the required real endpoint benefits from separated route/schema responsibilities.
3. Added real unit tests instead of `tests/unit/.gitkeep`.
4. Used `app/storage/migrations/.gitkeep` rather than making migrations a Python package before a migration tool is selected.
5. Initialized Git because version control is an explicit technology choice; no automatic commit was made.

## 6. Files created or modified

- `README.md`: objective, status, architecture summary, directory guide, PowerShell setup, commands, phases, limitations, and raw-data policy.
- `docs/ARCHITECTURE.md`: intended offline/online pipelines, dependencies, provenance, and technology rationale.
- `docs/DATA_DICTIONARY.md`: intended document and passage metadata/nullability/traceability contract.
- `docs/DEVELOPMENT_PLAN.md`: eleven sequential phases with objective, dependencies, deliverables, and acceptance criteria.
- `pyproject.toml`: canonical project metadata, exact scaffold/dev versions, package discovery, pytest, and Ruff configuration.
- `requirements.txt`: installer entry point delegating to the canonical project plus `dev` extra.
- `.env.example`: empty/non-secret future setting placeholders.
- `.gitignore`: environment/cache/editor/log/generated-artifact exclusions and documented local raw-filing policy.
- `app/core/config.py`: functional typed settings foundation; external settings are optional.
- `app/main.py`, `app/api/routes/health.py`, `app/api/schemas/health.py`: functional minimal FastAPI app and health contract.
- `tests/unit/test_health.py`, `tests/unit/test_config.py`: functional unit checks.
- `CHANGELOG.md`: initial unreleased change record.
- `ui/README.md`, `scripts/README.md`: scope/ownership notes only.
- Package `__init__.py` files: generated architectural namespace markers/docstrings only; no fake retrieval or generation behavior.
- `.gitkeep` files: generated placeholders for intentionally empty data, migration, report, integration-test, and regression-test directories.
- `CODEX_REPORT.md`: authoritative factual handoff.

All files above were created in this run; none existed previously.

## 7. Dependencies and environment

- Detected: Python 3.13.16, pip 26.2.1 on Windows.
- Canonically declared runtime: FastAPI 0.139.0, pydantic-settings 2.14.2, Uvicorn 0.34.0.
- Canonically declared development/test: HTTPX 0.28.1, pytest 8.4.2, Ruff 0.16.10.
- Those exact packages/versions were already present in the global interpreter and were used for validation.
- No dependency installation command was run; no network download was needed.
- PostgreSQL/pgvector and all deferred parsing/model/UI/provider dependencies were not installed or checked by this task.
- No virtual environment was created; setup instructions recommend one for normal development.

## 8. Verification results

Commands actually executed (from the repository root):

| Command | Result |
| --- | --- |
| `Get-ChildItem -Force` and `rg --files -uu` before changes | Pass: workspace contained no files/folders. |
| `git status --short --branch` before changes | Expected failure: not a Git repository. |
| `python --version` | Pass: `Python 3.13.16`. |
| `python -m pip --version` | Pass: pip 26.2.1. |
| `python -m pip show fastapi pydantic pydantic-settings uvicorn pytest httpx ruff` | Pass: required validation packages were available. |
| `python -m compileall -q app tests` (final) | Pass, exit 0, no diagnostics. |
| `python -m pytest` (final) | Pass: 2 collected, 2 passed in 0.21s; 1 upstream deprecation warning. |
| `python -m ruff check app tests` (initial) | Failed: one `E501` at `app/api/routes/health.py:14`; line was wrapped. |
| `python -m ruff check app tests` (final) | Pass: `All checks passed!`. |
| `python -c "import tomllib; ..."` | Pass: parsed project name and `>=3.11,<3.14`. |
| Direct `TestClient(app).get('/health')` | Pass: HTTP 200 and `{'status': 'ok', 'detail': 'Application scaffold is running; RAG is not implemented.'}`. |
| Credential-free `Settings(_env_file=None)` import/creation | Pass: development default, null database URL, no API key. |
| `.env` recursive check | Pass: no `.env` files found. |
| Common credential-signature scan with `rg` | Pass: no common credential signatures found. |
| `git check-ignore -v ...` | Pass: `.env`, sample raw filing, and generated processed file are ignored; `.gitkeep` sentinels are unignored. |
| `git ls-files --others --exclude-standard` | Pass: expected scaffold files are trackable; ignored caches/data absent. |
| `git init` / final `git status --short --branch` | Pass: empty repository initialized on `main`; all scaffold files remain untracked and no commit exists. |

The final pytest run emitted `StarletteDeprecationWarning`: the installed FastAPI test client currently uses `httpx` and advises a future `httpx2` migration. It did not fail the test or endpoint. This dependency transition should be revisited when the upstream stack stabilizes.

Commands not run:

- `python -m pip install -r requirements.txt`: skipped because exact declared validation dependencies were already installed; avoiding an unnecessary environment mutation/download.
- Live Uvicorn server: skipped because the in-process FastAPI TestClient made a genuine HTTP request against the ASGI application and validated the same route deterministically.
- PostgreSQL/database checks: out of scope; no database is required or configured.
- Streamlit/model/parser checks: packages and implementations are intentionally deferred.

## 9. Known limitations and unresolved decisions

- Only configuration and `/health` are implemented. All RAG behavior is absent by design.
- No documents or manifest exist yet; the planned ten filings may be incomplete.
- Manifest format/ID rules, parser choice per source format, chunking policy, database schema/migration tool, embedding/reranking models, fusion algorithm, score thresholds, LLM provider, citation policy details, and evaluation dataset remain open.
- Exact pins worked in the inspected global Python 3.13 environment, but a fresh isolated environment was not installed in this run.
- The TestClient stack raises a non-failing deprecation warning concerning future `httpx2` migration.
- Raw reports are intentionally local-only by default. Their future manifest may be tracked, but licensing/data policy must be reviewed before sharing source files.
- Git has no commit yet; the user retains control over the initial commit and identity/configuration.

## 10. Next recommended action

**Implement the document manifest and local-only ingestion registration (phase 2).**

Prerequisites: the user should place any available official filings under the documented company directories and provide/confirm their official SEC source URLs; it is acceptable for some planned files to remain missing.

Acceptance criteria: define and validate a versioned manifest; compute source hashes without modifying files; report missing/duplicate/mismatched entries; preserve authoritative filing metadata and source URLs; make reruns idempotent; add unit tests; do not automatically download filings.

## 11. ChatGPT handoff summary

The empty workspace at `D:\Financial Research RAG Assistant` now contains a Git-initialized architecture scaffold for an evidence-based filing RAG assistant. The only working application behavior is `GET /health`, assembled in `app/main.py` and `app/api/routes/health.py`; typed optional settings are in `app/core/config.py`. `pyproject.toml` is canonical and `requirements.txt` delegates to its dev extra. Architecture, metadata contracts, and the phased roadmap are in `docs/ARCHITECTURE.md`, `docs/DATA_DICTIONARY.md`, and `docs/DEVELOPMENT_PLAN.md`. Raw filings are local-only and Git-ignored, with tracked company directory sentinels.

Validation on Python 3.13.16: compileall exit 0; Ruff final pass; pytest 2 passed with one FastAPI/Starlette TestClient deprecation warning; direct `/health` request returned HTTP 200 and the explicit scaffold-only message; optional settings imported with no database/API key; no `.env` or common credential signatures were found. No packages were installed and no commit was made.

Open decisions include the manifest format/IDs, source parser strategy, schema/migration tooling, model/provider selections, ranking/abstention thresholds, and evaluation set. The next task should be phase 2: a versioned, local-only, idempotent document manifest/registration workflow using user-supplied official filings and source URLs, with no automated SEC download.

## 12. Update history

- **2026-10-17 08:54 IST:** Created the complete initial architecture scaffold, initialized Git, implemented and validated the minimal health/config foundations, recorded scope boundaries and next action.
- **2026-10-17 11:10 IST:** Added offline verification for the ten local SEC HTML filings, generated a manifest/report, and confirmed all ten pass the defined automated identity and extraction checks with manual table review still outstanding.

## SEC Document Verification

### Scope and method

This run performed only read-only source verification and extraction-quality assessment. It did not implement ingestion, chunking, embeddings, indexes, database migrations, retrieval, generation, API routes, or UI features. No network access or document download was used.

Each expected HTML file was read as bytes, sized, and SHA-256 hashed. Beautiful Soup 4.15.0 with lxml 6.1.1 parsed inline-XBRL HTML; hidden/non-visible elements were removed before visible text normalization. Inline-XBRL DEI facts were preferred for company, form, and reporting-period detection. Heuristics checked error-page language, text volume/readability, encoding replacement characters, likely truncation, suspicious repeated long blocks, five financial-section classes, and tables containing useful labels plus multiple numeric values.

Automated table checks establish only that labels and numeric content survived extraction. They do not validate row/column/date/value alignment or numeric accuracy; manual spot-checking remains mandatory.

### Files created or changed

- `app/ingestion/validation/sec_document_verifier.py` — maintainable read-only verification logic, expected corpus definition, stable manifest schema, report renderer, and fixed-output orchestration.
- `scripts/verify_sec_documents.py` — offline PowerShell-friendly CLI; writes only beneath `data/processed/document_verification/`.
- `scripts/README.md` — documented the exact local command, output paths, and read-only/network-free behavior.
- `tests/unit/test_sec_document_verifier.py` — five synthetic-fixture tests for identity, missing files, SEC error pages, headings, and CSV schema.
- `pyproject.toml` — added exact Beautiful Soup/lxml versions under optional `verification` dependencies and the development test set. Both packages were already installed; no install/download occurred.
- `data/processed/document_verification/document_manifest.csv` — generated 10-row source manifest.
- `data/processed/document_verification/document_verification_report.md` — generated evidence/excerpt report.
- `CODEX_REPORT.md` — added this section and update-history entry.

`.gitignore`, raw HTML files, and accompanying `_files` folders were not modified. No commit was created.

### Actual corpus findings

All ten expected files exist, are non-empty, match expected company/form/reporting-period identity, contain substantial readable text, expose all five expected section classes, and contain at least two table candidates with useful financial labels and numeric values. Automated result: **10 PASS, 0 REVIEW, 0 FAIL**.

| Document | Bytes | Extracted characters | Words | Identity | Extraction | Tables | Overall |
| --- | ---: | ---: | ---: | --- | --- | --- | --- |
| `msft-2022-10k` | 6,220,761 | 342,588 | 52,294 | PASS | PASS | PASS | PASS |
| `msft-2023-10k` | 9,964,742 | 337,252 | 51,421 | PASS | PASS | PASS | PASS |
| `msft-2024-10k` | 6,866,959 | 354,478 | 53,770 | PASS | PASS | PASS | PASS |
| `msft-fy2024-q1-10q` | 4,967,583 | 182,443 | 27,804 | PASS | PASS | PASS | PASS |
| `msft-fy2024-q2-10q` | 5,678,168 | 209,062 | 32,225 | PASS | PASS | PASS | PASS |
| `aapl-2022-10k` | 2,056,684 | 215,588 | 33,149 | PASS | PASS | PASS | PASS |
| `aapl-2023-10k` | 1,566,509 | 200,588 | 30,945 | PASS | PASS | PASS | PASS |
| `aapl-2024-10k` | 1,527,537 | 204,310 | 31,388 | PASS | PASS | PASS | PASS |
| `aapl-fy2024-q1-10q` | 746,169 | 56,380 | 8,939 | PASS | PASS | PASS | PASS |
| `aapl-fy2024-q2-10q` | 898,671 | 58,815 | 9,520 | PASS | PASS | PASS | PASS |

The Microsoft reports use the company-specific heading `Cash Flows Statements`; the verifier explicitly supports this alongside `Statements of Cash Flows`. No SEC viewer/error page, identity mismatch, unusually short extraction, replacement-character warning, truncation marker, suspicious long-block duplication, or missing expected section remained in the final results.

### Commands and results

- `python -m pip show beautifulsoup4 lxml html5lib` — available locally: Beautiful Soup 4.15.0, lxml 6.1.1, html5lib 1.1. Beautiful Soup/lxml were selected; no new package was installed.
- `python -m pytest tests\unit\test_sec_document_verifier.py -q` — focused result: 5 passed.
- First `python -m ruff check ...` — failed on one import modernization and line-length findings; corrected.
- First `python scripts\verify_sec_documents.py` — failed with `ModuleNotFoundError: No module named 'app'` when executed from an uninstalled checkout; the entry point now adds its repository root before importing application code.
- Final `python scripts\verify_sec_documents.py` — exit 0: verified 10 documents, `{'PASS': 10}`; wrote the two expected paths.
- `python -m compileall -q app scripts tests` — exit 0, no diagnostics.
- `python -m ruff check app scripts tests` — `All checks passed!`.
- `python -m pytest` — 7 collected, 7 passed in 0.45 seconds, with the previously known single FastAPI/Starlette TestClient deprecation warning.
- Repeated verifier run plus SHA-256 comparison — deterministic: manifest SHA-256 `278eef6c60ceec2db1339118baec5f705f9b2bd5c0c81ded91c73ffafcba4726`; report SHA-256 `21dc5899793c3599957deaaf84e1b7bed99d5ed0a4c3e3993522f5130e719b82` before and after regeneration.
- Manifest/current-source SHA-256 comparison — 10 rows, 0 raw hash mismatches.
- One combined PowerShell validation wrapper reported a shell quoting error while formatting the status summary, after compile/lint/tests/determinism had already passed. The corrected integrity/status command then passed with 10 PASS and 0 hash mismatches; this was a command-formatting failure, not a verifier failure.

During early inspection, a command intended to show only initial HTML lines emitted excessive content because SEC inline-XBRL files can store most markup on one physical line. It made no changes to source files. All subsequent inspection used bounded parser-derived excerpts, and generated reports contain only short excerpts.

### Generated outputs

- `D:\Financial Research RAG Assistant\data\processed\document_verification\document_manifest.csv` — 3,578 bytes, required stable CSV schema and one row per expected filing.
- `D:\Financial Research RAG Assistant\data\processed\document_verification\document_verification_report.md` — 15,815 bytes, method, summary, per-document identity/extraction evidence, sanitized excerpts, manual checks, and recommendation.

### Source integrity and unresolved limitations

- Pre-verification and final HTML sizes/SHA-256 values match; the final manifest also has zero mismatches against current source files.
- Verification code opens source files only for byte reads and writes only to the fixed processed-output directory.
- Original HTML filenames and companion `_files` directories remain in place and were not renamed, moved, deleted, or overwritten.
- PASS means the defined automated source-identity and extraction heuristics passed. It does not prove that every table cell is semantically aligned or numerically accurate.
- Manual review should compare at least one income statement, balance sheet, and cash-flow table per source against extracted ordering, including units, column dates, signs/parentheses, and row/value alignment.
- Browser-saved companion resources appear unnecessary for normalized text extraction, but this should be confirmed during the manual visual spot-check.

### Recommendation

The corpus is ready for the next ingestion-design step **subject to the documented manual table spot-check**. No automated fix or document replacement is currently indicated, and there are no REVIEW or FAIL documents to resolve.

## Financial Table QA Preparation

### Scope and status

Prepared an offline human-review package for the income statement, balance sheet, and cash-flow statement candidate in each of the ten verified local SEC filings. This package is a review aid only: no financial table is manually verified, no numeric or semantic accuracy claim is made, and every one of the 30 checks remains **PENDING HUMAN REVIEW**.

The source files were read only. No network access, SEC download, package installation, raw-file rename, or raw-file modification occurred. The builder writes only beneath `data/processed/document_verification/table_qa/`.

### Deliverables

- `data/processed/document_verification/table_qa/table_qa_review.html` — self-contained, offline review page with a source-grid/normalized-text comparison, local source links, candidate metadata, risks, and per-check human-review prompts.
- `data/processed/document_verification/table_qa/table_qa_checklist.md` — 30 unchecked, writable review entries, one for every document/category pair.
- `data/processed/document_verification/table_qa/table_qa_summary.json` — machine-readable candidate-selection and review-state summary.

### Automated preparation results

The builder completed with 30 candidate selections: **FOUND = 30, AMBIGUOUS = 0, NOT FOUND = 0**. `FOUND` means only that the selector found a likely source HTML table; it is not a completed review or a verification of values, dates, units, signs, or alignment.

Post-build package validation confirmed exactly 30 unique document/category pairs, 30 `PENDING HUMAN REVIEW` states, 30 expandable HTML sections, 30 checklist items, and no external `http`, `https`, or protocol-relative links in the review page. Microsoft FY2024 income-statement and Apple FY2024 cash-flow candidates were spot-inspected as selection outputs; both are labelled `FOUND` and still require human comparison.

The selector preserves basic source-cell text and `colspan`/`rowspan` structure in the review page and renders cell text escaped. The comparison page deliberately calls out the principal extraction limitation: the current normalized representation is flattened and cannot by itself prove visual row/column alignment.

### Source integrity

SHA-256 comparisons were run before and after this QA work against the existing document manifest. Both checks found **10 matching files and 0 mismatches**. The raw SEC inputs and companion folders remain unchanged.

### Commands and validation

- `python scripts\build_table_qa.py` — completed; prepared 30 pending human checks with `{'FOUND': 30}`.
- `python -m pytest tests\unit\test_financial_table_qa.py -q` — 6 passed.
- Package-structure validation — passed: 30 unique checks, all pending, offline links only.
- `python -m pytest -q` — 13 passed in 0.38s, with one pre-existing FastAPI/Starlette TestClient deprecation warning.
- `python -m ruff check app\ingestion\validation\financial_table_qa.py scripts\build_table_qa.py tests\unit\test_financial_table_qa.py` — all checks passed.
- `python -m compileall -q app\ingestion\validation\financial_table_qa.py scripts\build_table_qa.py tests\unit\test_financial_table_qa.py` — passed.

One early ad-hoc validation command used stale field names and another over-constrained a source preview; both command checks failed before the corrected structural validation passed. These were validation-command issues, not build or artifact failures.

### Required manual action and remaining limits

Open `table_qa_review.html`, expand each of the 30 checks, compare the reconstructed source grid with the normalized text and local filing context, then record findings in `table_qa_checklist.md`. Review at least statement selection, row labels, dates/period columns, units, parentheses/signs, totals, and value alignment. Do not edit raw filings.

The package does not replace a human accounting review, does not validate figures against another source, does not resolve visual semantics hidden in styling, and does not turn candidates into ingestion-ready ground truth. Those limitations remain until a reviewer records results for all applicable entries.

## 13. Update history

- **2026-10-17 12:59 IST:** Prepared the offline financial-table extraction QA package for all ten verified SEC filings, preserving raw-source hashes; 30 candidate checks are ready for manual review.

## Ingestion Readiness Inspection

### Scope

This inspection was read-only. It reviewed `CODEX_REPORT.md`, `pyproject.toml`, `requirements.txt`, the complete `app/` package tree, operational scripts, architecture/data-contract/roadmap documentation, and the unit tests. It did not add dependencies, implement ingestion, download data, add credentials, or modify raw filings.

### Current implementation inventory

Implemented today:

- `app/main.py`, `app/api/routes/health.py`, and `app/api/schemas/health.py` provide only a FastAPI `/health` endpoint that explicitly reports the scaffold state.
- `app/core/config.py` provides optional typed settings for environment, database, LLM, embedding, and reranker configuration. It does not connect to any service.
- `app/ingestion/validation/sec_document_verifier.py` performs read-only local HTML verification: byte hashing, identity detection using inline-XBRL/visible text, visible-text normalization, section heuristics, error/truncation/duplication checks, and coarse financial-table quality checks. It writes the existing verification CSV/report; it is not an ingestion loader or canonical parser.
- `app/ingestion/validation/financial_table_qa.py` selects likely statement tables, preserves a basic HTML cell grid including spans, renders escaped offline review HTML/Markdown/JSON, and keeps human-review state. It is a QA aid, not a production table model or indexed representation.
- `scripts/verify_sec_documents.py` and `scripts/build_table_qa.py` are safe local entry points for those two validation/QA workflows. `scripts/README.md` explicitly states that ingestion and indexing scripts are not implemented.
- The ten-row `document_manifest.csv` is a verification artifact containing expected/detected identity, hashes, extraction counts, section flags, and statuses. It is not yet the versioned registration manifest described by the architecture contract because it lacks a complete authoritative source URL/acquisition/processing lifecycle contract.

Present as package boundaries or documentation only:

- `app/ingestion/loaders`, `parsers`, `cleaning`, and `chunking` contain namespace markers only; there is no loader, HTML parser abstraction, cleaning pipeline, section detector for production use, or deterministic chunker.
- `app/storage/repositories` and `app/storage/migrations` contain no persistence implementation or schema. PostgreSQL/pgvector is an architectural choice only.
- `app/retrieval/keyword`, `semantic`, `hybrid`, and `reranking` contain no retrieval implementation or index integration.
- `app/generation`, `app/evaluation`, and `ui` contain boundaries/documentation only. There is no answer generation, citation resolver, abstention engine, query endpoint, embedding model, LLM provider, or UI behavior.

### Manual QA and source integrity

`data/processed/document_verification/table_qa/table_qa_checklist.md` is present and now records 30 checked entries with 30 pass findings and no remaining `PENDING HUMAN REVIEW` entries. The three QA artifacts remain available under the same `table_qa/` directory. SHA-256 comparison of every raw filing against the verification manifest found **10 manifest rows, 0 mismatches**. No raw HTML or companion resource was written, renamed, moved, or deleted.

### Recommended staged ingestion plan

1. **Freeze contracts and registration.** Define a versioned manifest separate from the verification report with stable `document_id`, issuer/ticker, form, filing date, reporting period, fiscal metadata, official source URL, repository-relative local path, acquisition timestamp, source SHA-256, parser configuration/version, and lifecycle status. Reject duplicates and identity/hash conflicts; make reruns idempotent.
2. **Add immutable source loading.** Implement a loader that reads only manifest-approved local files, rechecks the source hash before processing, records byte/encoding diagnostics, and never overwrites raw inputs. Add explicit missing/changed/unsupported-source outcomes.
3. **Build a structure-preserving HTML parser.** Parse visible narrative blocks and tables separately. Retain DOM/table identity, source HTML table index, heading/context, row and column order, `rowspan`/`colspan`, cell text, units, date headers, and stable character/anchor locators. Keep the manually reviewed statement candidates as fixtures and do not flatten tables into prose-only chunks.
4. **Normalize with reversible derived artifacts.** Clean whitespace and presentation noise while retaining raw cell text, normalized text, source offsets/anchors, parser version, and a deterministic representation hash. Preserve inline-XBRL facts as optional evidence rather than silently replacing displayed values.
5. **Validate before indexing.** Add schema, identity, structural, numeric, table-alignment, duplicate, and reproducibility checks. A failed document/table should be quarantined with diagnostics rather than indexed as trusted evidence. Produce deterministic document/table/section artifacts beneath a versioned processed directory.
6. **Chunk by evidence unit.** Use section-aware narrative chunks and table-aware records. A table chunk should carry document/table IDs, statement category, units, period columns, row labels, structured cells, a citation-ready text rendering, and source locator. Define deterministic overlap/size rules and stable `chunk_id` derived from document hash plus parser/chunker versions.
7. **Persist and index.** After local artifact acceptance, add migrations and repository interfaces for documents, tables, passages, processing runs, and provenance. Start with a transparent PostgreSQL full-text/keyword index; add vectors only after embedding model/version and reproducibility policy are selected. Enforce uniqueness and prevent mixed parser/chunker/embedding versions.
8. **Gate retrieval readiness.** Build a small judged query set from the ten filings, benchmark keyword retrieval with issuer/form/period filters, then add semantic retrieval and hybrid/reranking only after the keyword baseline and provenance checks are stable.

### Tests required before retrieval and answer generation

- Manifest tests: schema/version validation, duplicate IDs, duplicate hashes, missing files, changed bytes, identity mismatch, source-URL preservation, and idempotent reruns.
- Parser fixtures: visible/hidden HTML, inline-XBRL metadata, split headings, malformed markup, nested tables, multiple tables, `rowspan`/`colspan`, units, date headers, parentheses/negative values, and companion-resource independence.
- Determinism tests: same source/config produces byte-identical derived artifacts, stable IDs, stable ordering, and reproducible hashes; parser/chunker version changes produce an explicit new version.
- Provenance tests: every narrative/table chunk resolves to one document, source file/hash, section/table identity, and locator; no citation can point outside supplied evidence.
- Quality/gating tests: failed identity/hash/structure checks cannot enter the index; incomplete tables are quarantined; all 30 manually passed QA cases remain represented in parser fixtures.
- Storage/index tests: migration from empty database, constraints, transactional writes, idempotent re-ingestion, full-text indexing, metadata filters, and isolated integration fixtures.
- Retrieval contract tests: ranking shape, issuer/form/period filters, empty/unsupported queries, provenance preservation, deterministic keyword results, and later semantic/hybrid score/version reporting.
- Generation gate tests (after retrieval only): selected evidence is the sole model input, citations resolve to retrieved chunks, unsupported questions abstain, no credentials are needed at import, and answer/citation behavior is regression-tested against a versioned evaluation set.

### Commands run and results

- Read-only file/tree inspection with `Get-ChildItem`, `rg --files`, and bounded `Get-Content` reads — completed.
- Raw integrity/checklist inspection PowerShell command — **10 manifest rows, 0 raw hash mismatches; checklist exists; 30 checked items; 30 pass findings; 0 pending mentions**.
- `python -m pytest -q` — **13 passed**, with the known non-failing FastAPI/Starlette TestClient deprecation warning.
- `python -m ruff check app scripts tests` — **All checks passed**.
- `python -m compileall -q app scripts tests` — passed with no diagnostics.
- `rg` placeholder scan — confirmed future/package-boundary language and no unimplemented ingestion/retrieval behavior beyond the existing verifier and QA utilities.

### Recommended next action

Before retrieval work, implement only phase 1 of the plan: the versioned manifest/registration contract and immutable local loader, with its tests and deterministic derived-run metadata. Then implement the structure-preserving HTML parser and chunk fixtures. Do not add embeddings, database indexing, retrieval, or answer generation until parser output, provenance, reproducibility, and ingestion gates are passing.

## Phase 1 — Versioned SEC Registration Manifest and Immutable Local Loader

### Scope and outcome

Implemented the Phase 1 registration contract and immutable local source checker only. No HTML parser, cleaning pipeline, chunker, database, embeddings, retrieval, generation, UI, credential, or network behavior was added. The new workflow treats the existing verification CSV as an input reference only; it does not repurpose it as the registration contract.

### Files created or changed

- `data/manifests/sec_documents.v1.json` — tracked schema-`1.0` registration manifest for the ten local filings.
- `app/ingestion/loaders/sec_manifest.py` — standard-library manifest validator plus read-only, hash/size checking loader.
- `scripts/validate_sec_registration_manifest.py` — documented PowerShell-friendly validation CLI with explicit exit codes.
- `tests/unit/test_sec_registration_manifest.py` — nine synthetic-file tests for manifest and loader behavior.
- `docs/SEC_REGISTRATION_MANIFEST.md` — contract, nullability, lifecycle, source-status, and CLI documentation.
- `docs/DATA_DICTIONARY.md`, `docs/DEVELOPMENT_PLAN.md`, and `scripts/README.md` — updated to distinguish the completed registration slice from deferred parsing/indexing work.
- `CODEX_REPORT.md` — this implementation record.

### Registration manifest contract

The manifest has `schema_version`, `manifest_id`, and ten `documents` entries. Each document has a stable existing `document_id`, company, curated ticker, form type, required reporting-period end date, safe project-relative local HTML path, immutable source SHA-256, immutable byte size, registration metadata, `registered` processing status, and validation warnings. It permits explicit `null` for filing date, fiscal year/quarter, official SEC source URL, and acquisition timestamp.

No filing date, accession number, fiscal year/quarter, acquisition time, or official SEC URL was guessed. Those unavailable values remain null with a warning. Company/form/reporting-period identity, source paths, hashes, and byte sizes were registered from the already verified local corpus. The manifest validator rejects unsupported schema versions, duplicate document IDs/paths, unsafe paths, malformed hashes, invalid dates, unsupported statuses, and invalid metadata shapes.

The only Phase 1 manifest lifecycle state is `registered`. A source check has a separate result: `VALID`, `MISSING`, `CHANGED`, `UNREADABLE`, or `INVALID_PATH`. A mismatch produces `CHANGED` diagnostics and does not repair or overwrite the registered hash.

### Immutable loader and CLI behavior

`check_registered_sources` reads only files explicitly approved by the manifest below `data/raw/sec_filings/`, computes current byte size and SHA-256, and returns structured per-document identity/results. It makes no network calls and writes neither the manifest nor the raw source. Calls are deterministic and idempotent for unchanged inputs.

Run from the repository root:

```powershell
python scripts\validate_sec_registration_manifest.py
```

The CLI reports a manifest/source summary and uses exit code `0` only when every source is valid, `1` for missing/changed/unreadable/unsafe sources, and `2` for manifest validation errors. It neither downloads files nor automatically registers changed bytes.

### Validation results

- `python scripts\validate_sec_registration_manifest.py` — **10 registered documents; `VALID=10`**.
- `python -m pytest tests\unit\test_sec_registration_manifest.py -q` — **9 passed**. Coverage includes valid loading, unsupported schema version, duplicate IDs, missing source, changed source/hash mismatch, valid size/hash, unsafe paths, idempotent checks/no raw mutation, and CLI exit codes/diagnostics.
- `python -m pytest -q` — **22 passed**, with the pre-existing non-failing FastAPI/Starlette TestClient deprecation warning.
- `python -m ruff check app scripts tests` — **All checks passed**.
- `python -m compileall -q app scripts tests` — passed with no diagnostics.
- Final registration-manifest/raw-file byte size and SHA-256 comparison — **10 registered documents, 0 mismatches**.

No package was installed or changed. Raw HTML filings, companion `_files` folders, and the completed 30-table human QA checklist were not modified. No Git commit was created.

### Remaining limitations and next task

The manifest intentionally lacks confirmed filing dates, official SEC URLs, acquisition timestamps, and some fiscal metadata. Those fields require authoritative confirmation before they may be populated. Registration validates bytes and identity metadata but does not parse source content, produce derived artifacts, or make content queryable.

**Next recommended task:** implement the structure-preserving HTML parser and deterministic derived-artifact contract. It should consume only `VALID` registrations, retain narrative locations and complete table structure (cells, spans, labels, date headers, units, and source locators), promote the 30 manually passed table checks into parser regression fixtures, and quarantine parse/structure failures. Do not add chunking, database storage, embeddings, or retrieval in that task.

## 14. Update history

- **2026-10-17:** Implemented the versioned SEC registration manifest and immutable local loader; all ten registered local sources validate without mutation.

## Structure-Preserving SEC HTML Parser

### Scope and outcome

Implemented the registered-source SEC HTML parser only. It consumes the versioned registration manifest, rechecks each source with the immutable loader, and parses only sources whose current status is `VALID`. It does not implement independent cleaning, chunking, storage, indexes, embeddings, retrieval, generation, API query routes, UI behavior, or network access.

The real corpus run parsed all **10** registered documents with status **`PARSED`**: **7,589** visible narrative blocks, **833** structured tables, **0** warnings, and **0** quarantined tables. The parser regression map checked all **30** previously human-reviewed statement-table candidates (three per filing) against their existing QA table index and preview cell structure. This confirms parser structural preservation relative to the established manual QA baseline; it does not independently re-certify accounting correctness.

### Files created or changed

- `app/ingestion/parsers/sec_html_parser.py` — parser configuration, deterministic IDs/locators, visible HTML handling, narrative/table contracts, structural validation/quarantine records, QA regression-map loading, deterministic serialization, atomic writes, and run metadata.
- `scripts/parse_registered_sec_html.py` — local CLI for manifest-backed parsing with explicit status/count reporting and non-zero source/quarantine outcomes.
- `tests/unit/test_sec_html_parser.py` — focused synthetic and QA-map regression tests.
- `docs/ARCHITECTURE.md`, `docs/DATA_DICTIONARY.md`, `docs/DEVELOPMENT_PLAN.md`, and `scripts/README.md` — updated parser boundaries, artifacts, locators, commands, and remaining scope.
- `data/processed/sec_parsed/v1/` — generated local derived artifacts: ten `<document_id>.json` files and `run_metadata.json`. These are processed artifacts and remain Git-ignored.
- `CODEX_REPORT.md` — this factual implementation record.

No dependency changed or was installed. The parser uses the already declared Beautiful Soup and lxml packages.

### Parser contract and preservation design

`ParserConfig` is explicitly versioned (`1.0`) and hashed from canonical configuration JSON. Its current 200-character visible-narrative threshold is a **warning floor**, not a trust pass: it detects unexpectedly empty/minimal narrative while preserving usable tables and without silently equating a warning with success. The threshold is covered by synthetic parser cases; malformed source recovery also yields an explicit warning rather than unqualified trust.

Visible narrative is represented separately as typed `heading`, `paragraph`, and `list_item` records in parsed source order. Scripts, styles, templates, head content, `hidden`, `aria-hidden=true`, and display/visibility-hidden content are removed before extraction. Leaf `div` content is retained when it is the only available visible structural text, which is necessary for the Apple browser-saved filings. Each narrative record includes the manifest document ID/source SHA-256, parser/configuration identity, stable ID, source DOM tag, parser-order locator, optional original HTML `id`, heading context, and text.

Tables remain structured records rather than flattened prose. A retained table has a deterministic table ID, original one-based DOM table index, optional source HTML `id`, caption, preceding heading, observed unit hints, observed period/date-header text, ordered rows, ordered cells, `th`/`td` distinction, raw displayed cell text, `rowspan`, `colspan`, and row/cell structural locators. The parser does not fabricate empty cells, date values, units, negative semantics, accounting labels, anchors, or page numbers. Parenthesized values and comma formatting remain exactly as displayed by the extracted cell text.

Narrative locators have the form `element:<visible narrative ordinal>:<DOM tag>` and identify parser source order after only demonstrably hidden markup is removed; they are not raw-file byte offsets. Table locators have the form `table:<one-based DOM table order>/row:<one-based row>/cell:<one-based direct cell>` and are structural HTML pointers, not fabricated page numbers or HTML anchors.

### Validation, quarantine, and QA regression mapping

Source validation failures (`MISSING`, `CHANGED`, `UNREADABLE`, or `INVALID_PATH`) return a separate `source_validation_failure` record and are never parsed. A document with no visible narrative and no usable tables is a `document_quarantine` with `QUARANTINED` status. Structurally unusable tables (for example invalid/non-positive spans or no usable direct cells) are placed only in `quarantined_tables`, with a reason code and diagnostic; they do not appear in trusted `tables` output. Non-fatal conditions—such as parser recovery after a missing closing HTML marker, inconsistent row spans, or nested-table markup—produce `PARSED_WITH_WARNINGS` rather than `PARSED`.

The parser loads the existing QA summary plus completed checklist. It requires exactly 30 selected QA candidates, ten document mappings with three tables each, and 30 human `PASS` entries. For every candidate, it checks that the recorded original table index exists and that the QA preview’s non-empty cell text is structurally preserved in the corresponding parsed source rows. The existing QA artifact was sufficient for this mapping; it does not contain a canonical accounting schema, so the parser correctly does not invent one.

### Artifacts and reproducibility

Derived output is restricted to `data/processed/sec_parsed/v1/`; custom output paths are rejected unless they resolve beneath the project’s `data/processed/` root. Each document JSON uses canonical JSON key ordering/separators and contains no operational timestamp. Stable IDs derive from document ID, registered source SHA-256, and explicit structural positions. `run_metadata.json` records parser/configuration version/hash, manifest identity, status counts, deterministic per-document artifact SHA-256 values, and a separate operational timestamp. Writes use a temporary sibling file followed by atomic replacement where supported; unchanged substantive document content is not rewritten.

Two unchanged full-corpus runs produced identical per-document artifact hashes. The run timestamp may change, by design, but is explicitly excluded from the substantive artifact hashes.

### Commands and results

- `python -m pytest tests\unit\test_sec_html_parser.py -q` — **9 passed**. Coverage includes visible/hidden/script/style handling, heading/paragraph/list order, table indices, nested/malformed markup warnings, spans, empty cells, period/unit/parenthesized numeric display, deterministic IDs, source hash mismatch/missing handling, output-path containment, quarantine separation, and the 30-candidate QA mapping.
- `python scripts\parse_registered_sec_html.py` — **10 `PARSED`**, 7,589 narrative blocks, 833 tables, 0 warnings, 0 quarantined tables; outputs written below the versioned processed directory.
- Repeated unchanged `python scripts\parse_registered_sec_html.py` plus artifact-hash comparison — **passed**; all deterministic document artifact hashes matched.
- `python -m pytest -q` — **31 passed**, with the existing non-failing FastAPI/Starlette TestClient deprecation warning.
- `python -m ruff check app scripts tests` — **All checks passed**.
- `python -m compileall -q app scripts tests` — passed with no diagnostics.
- `python scripts\validate_sec_registration_manifest.py` and final raw hash comparison — **10 `VALID`, 0 raw-hash mismatches**.
- Final QA integrity check — **30 checked entries and 30 PASS entries**; the checklist was not modified.
- `git diff --check` — passed.

### Remaining limitations and next task

This parser preserves source structure but intentionally does not define a cleaned canonical text layer, table semantic model, chunks, token counts, storage schema, database, full-text index, embeddings, retrieval, citations, answer generation, or UI. HTML structural locators may change if an externally changed source is re-registered; the source SHA-256 in every artifact prevents confusing artifacts from different source bytes. Browser companion-resource independence is supported for the current static HTML parsing path but has not been asserted by deleting or modifying companion folders.

**Next recommended task:** implement deterministic, section-aware chunking over only `PARSED`/approved parser artifacts. Keep narrative chunks separate from table-aware evidence records, retain all parser provenance and locators, define stable chunk identifiers/versioning and explicit chunk validation/quarantine, and add fixtures for the 30 reviewed tables. Do not add database storage, embeddings, retrieval, or generation in that task.

## 15. Update history

- **2026-10-17:** Implemented the deterministic, structure-preserving registered SEC HTML parser; all ten valid sources parsed and the 30 reviewed table candidates passed structural regression mapping.

## Section-Aware Evidence Chunking

Implemented deterministic evidence preparation from only manifest-approved, hash-valid, compatible `PARSED` parser artifacts. The new chunker writes separate narrative chunks and structured financial-table evidence under `data/processed/sec_evidence/v1/`, while preserving provenance, parser locators, table rows/cells/spans, and explicit quarantine records. It does not implement storage, indexing, embeddings, retrieval, generation, or UI.

Actual corpus result: all 10 documents were admitted as `ADMITTED_WITH_QUARANTINED_RECORDS`, producing 938 narrative chunks and 833 table-evidence records. The 425 quarantined records are explicit low-information browser-rendered page-label blocks; there were no document-level source, parser compatibility, table-structure, or QA regression failures. All 30 manually reviewed statement-table candidates passed the evidence structural/provenance mapping.

The chunking configuration is version `1.0`, with 1,800 target / 2,400 maximum / 300 minimum Unicode-character chunk sizes, zero overlap, heading-boundary isolation, deterministic whitespace splitting for long blocks, and explicit low-information quarantine. Repeated unchanged corpus runs produced matching substantive evidence artifact hashes. Validation completed with 8 focused tests and 39 full-suite tests passing; Ruff and compileall passed. Raw-source hashes remain valid for all 10 registrations, and the 30-entry PASS QA checklist was unchanged.

Full design, command results, limitations, and next task: `docs/reports/TASK_03_SECTION_AWARE_CHUNKING.md`.

## 16. Update history

- **2026-10-17:** Implemented deterministic, section-aware narrative chunks and structured financial-table evidence for the approved SEC parser corpus; documented explicit low-information quarantines and reproducible artifact hashes.

## Evidence Storage Architecture (Phase 4A)

Implemented a PostgreSQL-compatible persistence contract for approved Phase 3 evidence, using transactional numbered SQL migrations and a repository boundary. Narrative chunks and structured financial tables are persisted separately; table rows/cells remain relational and quarantines are stored separately from the approved corpus. The schema preserves source hashes, stable IDs, structural locators, parser/chunker identities, and processing-run artifact inventories. No full-text indexing, embeddings, retrieval, generation, API, or UI work was added.

The `storage` optional dependency declares the PostgreSQL driver; no database service or credentials are required at import. Unit tests use an explicitly non-PostgreSQL in-memory behavioral double plus a migration-runner fake. Live PostgreSQL migration/constraint integration remains required before production use. Full details: `docs/reports/TASK_04A_EVIDENCE_STORAGE.md`.

## 17. Update history

- **2026-10-17:** Implemented Phase 4A PostgreSQL-compatible approved-evidence storage schema, transactional migration runner, repository boundary, and isolated persistence tests.

## PostgreSQL Integration Validation (Task 04B)

Added an opt-in, isolated PostgreSQL integration suite for the Phase 4A migration and repository contracts. It creates only a random disposable schema in a dedicated `TEST_POSTGRES_DSN` database. Live validation subsequently ran successfully on PostgreSQL 16 in the dedicated WSL `financial_rag_test` database as role `yatharth`: 3 integration tests passed and the full WSL suite passed 46 tests. Generated schemas were confirmed cleaned up; raw source registration remains 10/10 valid. Full results and remaining concurrency limitation: `docs/reports/TASK_04B_POSTGRESQL_INTEGRATION.md`.

## 18. Update history

- **2026-10-17:** Added opt-in PostgreSQL integration validation coverage; live execution remains blocked pending a dedicated isolated database and storage driver.

## Retrieval Architecture Planning (Task 05)

Planning review confirms that manifest verification, structure-preserving parsing, manual table QA, and deterministic section-aware evidence artifacts are complete offline. PostgreSQL storage and integration coverage remain unverified on a real engine; the opt-in suite was skipped because no isolated service, driver, or test DSN is available. Since the intended keyword baseline depends on a populated PostgreSQL evidence store, the recommended next task is completion of live Task 04B validation—not embeddings or generation. No API keys are needed. Detailed status and the exact follow-on prompt: `docs/reports/TASK_05_RETRIEVAL_PLAN.md`.

## 19. Update history

- **2026-10-17:** Recorded retrieval planning; live PostgreSQL validation remains the prerequisite to keyword retrieval implementation.

## PostgreSQL Test Setup Readiness (Task 04C)

Read-only setup inspection found WSL2 Ubuntu and `winget`, but no PostgreSQL installation/service, Docker/Podman, PostgreSQL driver, or configured test DSN. The existing integration fixture is schema-isolated and safe only for a dedicated disposable database because its cleanup drops a generated schema with `CASCADE`; it must never target production or shared data. WSL2 PostgreSQL is the least intrusive available option after explicit approval. No setup action or database connection occurred. Detailed findings: `docs/reports/TASK_04C_POSTGRESQL_SETUP.md`.

## 20. Update history

- **2026-10-17:** Completed read-only PostgreSQL setup readiness review; awaiting approval for a dedicated test environment.

## Live PostgreSQL Validation Completion

The dedicated WSL PostgreSQL 16 environment is now validated for Phase 4A persistence. `psycopg 3.2.10` connected as the non-superuser test role `yatharth`; migration/reapplication, migration-hash refusal, full evidence persistence, provenance reads, idempotency, quarantine isolation, and rollback behavior passed in real PostgreSQL. The complete WSL suite passed 46 tests. No retrieval work was started.

## 21. Update history

- **2026-10-17:** Completed live PostgreSQL validation for Task 04A/04B in the dedicated test database; keyword retrieval baseline is now the next implementation step.

## Keyword Retrieval Baseline (Task 06)

Implemented PostgreSQL English full-text retrieval over admitted narrative chunks only. Migration `002` adds a GIN expression index and document-filter index; the read-only retriever returns stable evidence and provenance fields with parameterized query/filter inputs, validated result limits, and deterministic tie-breaking. Financial tables remain structured and quarantines remain excluded. Live PostgreSQL integration coverage now includes retrieval ranking/filter/empty-query cases: 5 integration tests passed, alongside 50 unit tests, Ruff, compileall, and 10 valid source registrations. This is a correctness baseline, not a measured retrieval-quality claim. Full commands, limitations, and CLI usage: `docs/reports/TASK_06_KEYWORD_RETRIEVAL.md`.

## 22. Update history

- **2026-10-17:** Implemented and live-validated the PostgreSQL narrative keyword retrieval baseline; retrieval evaluation remains the next step.

## Keyword Retrieval Evaluation (Task 07)

Implemented a versioned, manually grounded three-case evaluation dataset for the Task 06 narrative keyword baseline. Each label resolves to an actual Apple or Microsoft admitted narrative chunk and structural source locator. The read-only evaluator reports Recall@5, Recall@10, Precision@5, and MRR. Executed in a generated PostgreSQL schema populated from unchanged evidence artifacts, the baseline measured Recall@5/10 **0.3333**, Precision@5 **0.0667**, and MRR **0.3333**; this small diagnostic result is not a quality benchmark. Full dataset method, commands, and limitations: `docs/reports/TASK_07_KEYWORD_RETRIEVAL_EVALUATION.md`.

## 23. Update history

- **2026-10-17:** Added Task 07 versioned keyword-retrieval evaluation and recorded the first measured lexical baseline.

## Safe Local Development Database Workflow (Task 08)

Implemented a guarded persistent-local-development database workflow without
initializing a persistent corpus. The new development-target guard requires an
explicit `APP_ENV=development`, configured expected database/role/schema names,
and a database URL. It rejects `financial_rag_test`, `public`, unsafe
identifiers, missing settings, and a server identity mismatch before migration
or persistence. It applies the configured non-public schema explicitly to
migration, persistence, retrieval, and evaluation connections.

`scripts/bootstrap_local_development_corpus.py` reuses immutable manifest
validation, evidence artifact hash checks, numbered migrations, idempotent
persistence, count readback, and a read-only keyword smoke search. It reports
evaluation as not executed; evaluation remains a separate read-only command.
No raw source, processed evidence artifact, or disposable integration schema
was changed as a persistent corpus.

Files added/updated include `app/storage/development.py`,
`app/storage/development_workflow.py`, the bootstrap CLI, the existing storage,
search, and evaluation CLIs, settings/example configuration, the local database
runbook, Task 08 report, roadmap, architecture note, and guard tests.

Actual checks: focused Task 08 guard tests passed; the final Windows suite
passed 64 tests with 1 expected PostgreSQL-driver skip and 1 existing Starlette
warning; Ruff, compileall, and manifest validation passed. In WSL PostgreSQL
16, each of the six existing isolated-schema integration tests passed when run
against the dedicated disposable `financial_rag_test` database as `yatharth`.
The integration cleanup check found zero `evidence_test_*` schemas afterward.
The bootstrap command itself correctly refused this workstation's missing
explicit development-target configuration before connecting; no separate
persistent development database was available, so live persistent-corpus
initialization is not claimed.

**Next recommended task:** Task 09, expand the judged retrieval benchmark while
preserving Task 07 v1. Do not begin semantic retrieval, embeddings, hybrid
retrieval, reranking, or answer generation.

- **2026-10-17:** Implemented Task 08 safety guards and documentation; persistent development-corpus initialization awaits an operator-provisioned dedicated target.

### Task 08 live initialization completion

The dedicated `financial_rag_dev` PostgreSQL 16 database was subsequently
verified as owned by the existing non-superuser `yatharth` role. Its initially
absent `financial_rag_dev` schema was created only by the guarded bootstrap.
The ignored local `.env` contains no password and configures peer-authenticated
`yatharth` access, the exact database name, and the explicit non-public schema.

The first guarded bootstrap applied migrations `001` and `002`, persisted the
approved evidence run `evidence-cc131af805dcc2b10e55e33f`, and verified 10
documents, 938 narrative chunks, 833 table-evidence records, and 425 quarantine
records. The read-only retrieval smoke test returned one candidate. A second
bootstrap was idempotent: no migrations, `inserted=False`, the same run ID, and
unchanged verified counts. Explicit schema-scoped verification confirmed the
schema owner, both migration records, and one processing run.

The documented Apple 10-K keyword search returned five candidates. Task 07 v1
evaluation executed against the persistent corpus and measured Recall@5/10
0.3333, Precision@5 0.0667, and MRR 0.3333; those figures remain diagnostic,
not a quality benchmark. Focused Task 08 tests (10), manifest validation (10
`VALID`), Ruff, and compileall passed in WSL. `financial_rag_test` was not used
or modified for this persistent corpus.

- **2026-10-17:** Completed live Task 08 development-corpus initialization and idempotency verification. Task 09 remains next.

## Versioned Judged Retrieval Benchmark v2 (Task 09)

Task 09 is complete for the existing narrative PostgreSQL keyword baseline.
`data/evaluation/keyword_retrieval.v2.json` preserves Task 07 v1 and adds 23
manually reviewed cases: 20 answerable narrative cases and 3 explicitly
unanswerable cases. It covers both issuers, 10-K/10-Q filings, financial
performance, operations, risks, and capital return. Every answerable reference
contains a narrative evidence type, chunk ID, document ID, source SHA-256, and
source locator validated against the admitted evidence artifact. Two cases have
multiple relevant chunks: Apple supply-chain risks (four) and Microsoft cloud
execution risks (two).

The evaluator now treats missing v1 status as answerable, excludes explicitly
unanswerable cases from Recall@5, Recall@10, Precision@5, and MRR denominators,
and reports answerable/unanswerable counts, dataset SHA-256, and retrieval mode.
It rejects non-narrative/table labels in the narrative evaluator. No table
relevance labels or table retrieval were added because the table retrieval
contract remains unimplemented.

Live v2 execution against the guarded persistent `financial_rag_dev` corpus
used dataset SHA-256
`d79de57f251a10de5797276e42b7d4fc6236124b9c268badc8477c538a6f1c9f`
and mode `postgres_english_narrative_keyword`. Measured results: 20 answerable,
3 unanswerable, Recall@5/10 **0.0500**, Precision@5 **0.0100**, and MRR
**0.0500**. These are diagnostic measurements of the unchanged lexical
baseline, not production-quality or statistically representative claims. The
v1 CLI compatibility run retained its prior metrics: Recall@5/10 0.3333,
Precision@5 0.0667, and MRR 0.3333.

Actual validation: WSL unit suite **70 passed**; the live isolated-schema
PostgreSQL versioned-evaluation integration test **1 passed**; manifest
validation reported **10 VALID** sources; Windows full suite **70 passed, 1
skipped** (no `psycopg` in that interpreter); Ruff and compileall passed. Raw
filings and existing processed evidence were not modified. Full methodology and
limitations: `docs/reports/TASK_09_RETRIEVAL_BENCHMARK_V2.md`.

**Next recommended milestone:** define a table-evidence retrieval contract and
separate table relevance labels before table retrieval or a semantic-retrieval
comparison.

- **2026-10-17:** Implemented and measured Task 09 narrative benchmark v2; table evidence remains deliberately out of scope.

## Table-Evidence Retrieval Contract and Benchmark Preparation (Task 10)

Task 10 audited the Task 09 v2 result before defining the table path. The
answerable/unanswerable denominator logic is correct: the 3 explicit
unanswerable cases are excluded from metrics, leaving 20 answerable cases. All
v2 chunk IDs, source hashes, locators, and registered metadata filters resolve
to the admitted narrative evidence. The repeated live result remains Recall@5
and Recall@10 **0.0500**, Precision@5 **0.0100**, and MRR **0.0500**. Of the
20 answerable cases, 17 return no lexical candidate, 2 return only non-relevant
candidates, and 1 retrieves a judged chunk. This documents the current
all-terms PostgreSQL English full-text baseline's lexical limitation; it is not
a label, provenance, denominator, or filter defect.

The audit added a date-normalized manifest-filter validation guard to the
narrative evaluation CLI. It also adds a separate `table_retrieval_judgments.v1`
dataset with 8 answerable and 2 unanswerable manually reviewed table cases,
including one multi-relevant case. The new contract requires admitted
`financial_table` evidence, stable IDs/source hashes/structural locators, raw
rows/cells/spans, observed units/periods, registered filing metadata, and clear
quarantine separation. Table judgments remain validation-only: Task 10 does
not add a table index or retriever and makes no table-retrieval quality claim.

Focused table/evaluation unit tests passed **15 tests**; the Windows suite
passed **75 tests with 1 expected PostgreSQL-driver skip**, and the WSL unit
suite passed **75 tests**. The isolated live PostgreSQL versioned-evaluation
test passed (**1 test**) and left **0** `evidence_test_%` schemas. Ruff,
compileall, and manifest validation passed; the manifest still reports **10
VALID** sources. Raw filings and existing processed artifacts were not modified.
The complete audit, contract, dataset details, and deferred work are in
`docs/reports/TASK_10_TABLE_EVIDENCE_RETRIEVAL_CONTRACT.md` and
`docs/TABLE_EVIDENCE_RETRIEVAL_CONTRACT.md`.

**Next recommended milestone:** implement a narrow, structure-preserving
PostgreSQL table keyword-retrieval baseline that returns the contract's raw
context and executes the separate table benchmark. Do not combine it with
semantic retrieval or answer generation.

- **2026-10-17:** Completed Task 10 table-evidence contract, provenance-checked
  table judgments, and Task 09 baseline audit; table retrieval remains deferred.

## Structure-Preserving PostgreSQL Table Keyword Retrieval (Task 11)

Task 11 implements the narrow table-retrieval baseline defined by Task 10.
Migration `003_table_keyword_retrieval.sql` adds the versioned `1.0`
`financial_table_search_documents` projection, English GIN full-text index, and
document/version index. The projection is derived only from admitted table
caption/heading context, observed periods/table-level units, and ordered raw
cell text; it maps directly back to the original structured table evidence and
does not replace it. The guarded persistent bootstrap applied `003` to only
`financial_rag_dev` / `financial_rag_dev` schema as `yatharth`, retained the
existing run (`inserted=False`), verified 10 documents / 938 narrative chunks /
833 tables / 425 quarantines, and a read-only inspection confirmed 833 search
projections plus migrations `001`–`003`.

`PostgresTableKeywordRetriever` searches only source-consistent `ADMITTED`
tables and returns a distinct structured result type: document/source/table IDs,
HTML locators/index, filing metadata, caption/heading, period/unit text,
warnings, validation/configuration identity, and ordered raw rows/cells with
kind/spans/locators. It does not infer units, numeric meanings, row labels, or
header associations; `NOT_ESTABLISHED` header status remains explicit.
Quarantines are excluded. Search uses parameterized English token-OR lexical
matching with `ts_rank_cd` and deterministic table tie-breaking; exact ticker,
form, period, document, and table filters are supported.

The separate table evaluator ran the preserved Task 10 dataset in the guarded
persistent corpus. Dataset `sec-table-retrieval-judgments-v1` SHA-256
`f9ae4e874a239d556dc944fe3a6307fb876040d2847f8c39731370b3958f8ff5` has 8
answerable and 2 unanswerable cases. Measured baseline: Recall@5/10 **0.875**,
Precision@5 **0.175**, MRR **0.71875**. The cross-company annual-income-table
case was not retrieved; unanswerable cases can still return lexical candidates
but are correctly outside metric denominators. These figures are diagnostic,
not an accounting-interpretation or production-quality claim.

Actual checks: focused table tests **8 passed**; Windows suite **79 passed, 1
skipped** (missing driver); WSL unit suite **79 passed**; three isolated live
PostgreSQL tests (migration, structure/quarantine, evaluator) **passed**, with
zero `evidence_test_%` schemas afterward. Ruff, compileall, and manifest
validation passed; all 10 sources remain VALID. Raw filings and processed
evidence artifacts were not modified.

Full design, commands, limitations, and results:
`docs/reports/TASK_11_TABLE_KEYWORD_RETRIEVAL.md`.

**Next recommended milestone:** perform a documented table-keyword ranking/query
ablation and expand table judgments before considering semantic retrieval. Keep
header association and numeric interpretation out of scope.

- **2026-10-18:** Implemented and live-measured structured PostgreSQL table
  keyword retrieval while preserving table provenance and raw structure.

## Phase 6 — Local Semantic Narrative Retrieval

Implemented local, PostgreSQL/pgvector semantic retrieval for admitted narrative
evidence only. Migration `004_semantic_narrative_retrieval.sql` adds
configuration-keyed child embedding records and a qualified HNSW cosine index.
The pgvector extension is installed in `public`, while application tables stay
in the guarded non-public `financial_rag_dev` schema; all vector SQL qualifies
`public.vector`, `public.vector_cosine_ops`, and `OPERATOR(public.<=>)` so the
existing restrictive search path is not weakened.

The fixed local model is `sentence-transformers/all-MiniLM-L6-v2` revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, dimension 384, normalized cosine
vectors. Actual tested versions: Sentence Transformers 6.1.0, Transformers
5.20.1, PyTorch 2.14.1+cpu, NumPy 2.5.4, psycopg 3.2.10, PostgreSQL 16.15, and
pgvector 0.6.0. The loader requires the pinned cached snapshot outside the
repository and uses local-only loading; it never downloads or silently changes
the revision.

The 256-token model limit is handled without changing evidence: every original
narrative chunk is tokenized with offsets and represented by deterministic,
non-overlapping 254-content-token child segments with stable IDs, parent chunk
ID, measured character span, input hash, document ID, source SHA-256, and
configuration hash. The guarded backfill revalidates all raw manifest sources,
requires source-consistent admitted chunks, is idempotent, and never embeds
quarantine records. Retrieval aggregates child hits to the best parent chunk,
keeps document/source/section/locator provenance, supports exact ticker/form/
period/document filters, parameterizes SQL, and uses deterministic ties. A
fixed per-transaction `hnsw.ef_search=1000` prevents filtered candidate loss in
this small corpus.

Live guarded backfill against only `financial_rag_dev` / `financial_rag_dev` as
`yatharth` applied migration `004` and stored **1,810** segments for **938**
chunks under configuration hash
`a92cf01525bc94b752c001f242a107eb9a774c5d168f8cf9e72e649d1095294e`.
Readback: migrations `001`–`004`; 10 documents, 938 narratives, 833 tables,
425 quarantines, one semantic configuration, and zero embedded/document source
hash mismatches. The preserved narrative keyword v2 run remains Recall@5/10
0.05, Precision@5 0.01, MRR 0.05.

Semantic v2 evaluation preserved dataset SHA-256
`d79de57f251a10de5797276e42b7d4fc6236124b9c268badc8477c538a6f1c9f` and
measured 20 answerable / 3 unanswerable cases in mode
`postgres_pgvector_cosine_narrative_semantic_v1`: Recall@5 **0.65**,
Recall@10 **0.90**, Precision@5 **0.14**, MRR **0.5904166666666667**. The small
manual benchmark indicates improvement for this exact configuration only; it is
not a representative quality, accounting-correctness, or production claim.

Files added/updated: migration `004`; semantic config/embedding/repository/
retriever modules; backfill, semantic search, and semantic-evaluation CLIs;
semantic unit and live integration tests; dependency/configuration declarations;
the Phase 6 plan/runbook/report. No raw filing, processed evidence artifact,
or benchmark label was modified. Focused checks passed (**16**); WSL units
passed (**84**); Windows passed (**84**, 1 expected driver skip); Ruff,
compileall, and the 10-source manifest check passed. The complete isolated
PostgreSQL integration suite passed **10 tests in 102.27s** against only
`financial_rag_test`, and post-run cleanup found **0** `evidence_test_%`
schemas.

Known limitations: child windows are non-overlapping, this is CPU-only and has
no latency study, the benchmark is small, and tables remain separate. Phase 7
hybrid fusion and bounded reranking is the next milestone; do not begin it in
this phase.

## Phase 7 — Hybrid Retrieval and Bounded Reranking

> **Historical Phase 7 record:** the deferred-reranking statements below were
> accurate when this section was written. They were superseded by Phase 7B,
> which implemented the pinned local reranker; see the Phase 7B section and the
> Phase 8 readiness audit for the current validation status.

Phase 7 adds a narrative-only, deterministic Reciprocal Rank Fusion (RRF)
baseline without altering the independent keyword/semantic retrievers,
embeddings, database schema, corpus, raw filings, or v2 labels. The hybrid
contract deduplicates by stable `chunk_id`, rejects conflicting immutable
document/source-hash/text provenance, retains original evidence provenance, and
adds inspectable `keyword_rank`, `semantic_rank`, and `rrf_score` fields.

RRF uses one-based branch ranks and `score = sum(1 / (60 + rank))`; both
branches run at an explicit default depth of 50 (validated 1–100) and public
limits remain 1–100. Ties sort by document ID, chunk sequence, and chunk ID.
Both branches receive the existing ticker/form/reporting-period filters. Empty
branches are valid, but malformed results or a failed branch raise explicit
errors rather than silently returning a partial hybrid result.

The guarded persistent `financial_rag_dev` evaluation used the unchanged v2
dataset SHA-256 `d79de57f251a10de5797276e42b7d4fc6236124b9c268badc8477c538a6f1c9f`
(20 answerable, 3 unanswerable). RRF mode
`rrf_narrative_keyword_semantic_v1` measured Recall@5 **0.65**, Recall@10
**0.90**, Precision@5 **0.14**, and MRR **0.5892261904761905**. It matches the
semantic baseline's Recall/Precision but is slightly below its MRR
(0.5904166666666667); no hybrid improvement is claimed. The keyword baseline
remains 0.05 / 0.05 / 0.01 / 0.05. Unanswerable candidates remain visible in
per-case diagnostics but excluded from metric denominators.

Bounded reranking is **not implemented**: inspection of the approved external
cache found only the pinned embedding model, not a pinned local reranker. No
new model was downloaded, substituted, or called remotely. This phase is thus
partially complete. Reranker selection/revision/cache admission, CPU test,
overlength policy, bounded cap, failure fallback, and evaluation remain required
before calling Phase 7 complete.

Changed files include the RRF retriever/result contract, hybrid evaluation CLI,
RRF unit tests, an isolated live hybrid integration assertion, development plan,
scripts runbook, and `docs/reports/PHASE_7_HYBRID_RETRIEVAL.md`. Focused hybrid
tests passed (**23**); full WSL unit validation passed (**87**, one existing
Starlette warning); Ruff, compileall, and immutable manifest validation passed
(**10 VALID**). The complete isolated PostgreSQL suite passed **10 tests in
104.15s**; its generated schemas were verified cleaned up afterward. The final
Windows suite passed **87**, with **1 expected integration skip** (no local
psycopg) and the existing Starlette warning. No persistent corpus writes
occurred.

**Historical next action (completed by Phase 7B):** select and explicitly admit
one pinned local CPU reranker, then implement only bounded reranking against the
preserved benchmark.

## Phase 7B — Pinned Local Bounded Reranking

Completed local bounded narrative reranking with
`cross-encoder/ms-marco-MiniLM-L6-v2` revision
`233902d25c440f23af6f7d6e94d2946bac0bee0a` (Apache-2.0), cached outside the
repository and loaded offline from its exact snapshot. The reranker receives
only bounded RRF candidates, windows original evidence text for the 512-token
pair limit, preserves identities/provenance and trailing hybrid order, and
keeps raw reranker scores distinct from RRF scores. No database migration or
corpus write occurred.

The unchanged v2 hash is `d79de57f251a10de5797276e42b7d4fc6236124b9c268badc8477c538a6f1c9f`.
With candidate depth 50 and rerank depth 20, actual evaluation measured Recall@5
0.75, Recall@10 0.90, Precision@5 0.15, MRR 0.6972222222 (20 answerable / 3
unanswerable), in 28.94 seconds including local loads. This is a small-benchmark
result, not a production-quality guarantee. Details: `docs/reports/PHASE_7B_RERANKING.md`.

## Phase 8 Readiness Audit — Grounded Generation, Citations, and Abstention

The authoritative roadmap defines Phase 8 as grounded generation, citations,
and abstention; final documentation/portfolio demonstration is Phase 11. This
audit therefore does **not** mark Phase 8 complete. No generation provider
protocol/adapter, prompt layer, citation resolver/validator, abstention policy,
answer-level evaluation, query endpoint, or UI exists yet. `GET /health` is the
only application route.

The audit updated the root README, architecture document, and scripts runbook
to reflect the actual retrieval implementation and safe WSL/PostgreSQL/model
workflow. It did not change raw filings, parsed/evidence artifacts, the
benchmark, database schema/corpus, or model cache. The unchanged narrative v2
benchmark SHA-256 is
`d79de57f251a10de5797276e42b7d4fc6236124b9c268badc8477c538a6f1c9f`; the
manifest validation command again reported all 10 registered sources `VALID`.

Fresh WSL checks: Ruff passed; compileall exited 0; unit suite passed **89**
with one existing Starlette/httpx deprecation warning. Exact cached snapshots
for `sentence-transformers/all-MiniLM-L6-v2@1110a243fdf4706b3f48f1d95db1a4f5529b4d41`
and `cross-encoder/ms-marco-MiniLM-L6-v2@233902d25c440f23af6f7d6e94d2946bac0bee0a`
loaded with `local_files_only=True`. Fresh v2 persistent-corpus results were:
semantic 0.65/0.90/0.14/0.5904166667; RRF 0.65/0.90/0.14/0.5892261905; and
RRF plus reranking 0.75/0.90/0.15/0.6972222222 (Recall@5, Recall@10,
Precision@5, MRR), with the reranking evaluation completing in 27.78 seconds.
These remain small-benchmark retrieval diagnostics only.

Phase 7B is implemented but remains **partially validated**: it has focused
unit tests and a fresh offline/persistent-corpus evaluation, but not yet a
dedicated isolated PostgreSQL reranker integration assertion or complete
ablation/latency analysis. Full audit detail and exact commands are in
`docs/reports/PHASE_8_READINESS_AUDIT.md`.

The Phase 8 audit's explicitly configured isolated integration rerun passed
**10 tests in 137.29 seconds** against only `financial_rag_test`; post-run
inspection found **0** `evidence_test_*` schemas. The first attempt was an
honest one-test skip because `TEST_POSTGRES_DSN` was absent from that shell.
An in-process FastAPI health smoke check returned HTTP 200 and the expected
health-only payload.

**Next recommended milestone:** implement the bounded provider-independent
Phase 8 grounded-generation/citation/abstention contract after selecting one
separately configured provider adapter. Do not start API/UI work first.

## Phase 8 — Grounded Generation, Citation Validation, and Abstention

Implemented a bounded, provider-neutral narrative-generation contract and one
explicit OpenAI Responses adapter. The configuration is `LLM_PROVIDER=openai`,
`OPENAI_API_KEY` (secret only), and `LLM_MODEL=gpt-5.4`; it uses the optional
`openai==3.34.0` SDK and `store=False`. The SDK is lazy-loaded, so imports and
routine tests require neither a key nor the SDK. No live provider request was
authorized or made.

`GroundedGenerationService` accepts only a validated, bounded collection of
`ADMITTED` narrative evidence (10 items / 12,000 characters), checks each
document against trusted source-hash provenance, and supplies deterministic JSON
to the provider. It keeps retrieval and reranker scores separate from confidence.
Provider output must be a bounded JSON shape. Citation IDs resolve only to
supplied evidence; returned source URLs, hashes, locators, and filing identity
come only from trusted application-side records. Unknown/missing citations,
invalid provenance, malformed or oversized output, empty evidence, and provider
failure/abstention produce explicit machine-readable abstentions. This validates
citation identity/provenance, not natural-language claim entailment.

Added fake-provider tests covering valid and duplicate citations, prompt-like
instructions inside evidence, malformed/oversized output, unknown/missing IDs,
quarantine/source-hash rejection, empty evidence, provider failure, missing
configuration, and no provider/model fallback. Focused tests passed **15**;
WSL units passed **103** with one existing Starlette/httpx warning. Ruff check,
compileall, and manifest validation passed; the protected v2 SHA-256 remained
`d79de57f251a10de5797276e42b7d4fc6236124b9c268badc8477c538a6f1c9f`.

The complete WSL suite with the disposable `financial_rag_test` DSN passed
**113 tests in 137.15 seconds**, with the same one existing warning. Its
generated-schema cleanup left **0** `evidence_test_*` schemas. This Phase 8
work made no persistent-corpus write.

`ruff check` and compileall passed. A separately run repository-wide
`ruff format --check app tests` reported nine pre-existing files that would be
reformatted outside this scope; they were left untouched, while all Phase 8
files passed targeted format validation.

No raw source, processed artifact, retrieval benchmark, persistent corpus,
schema, or migration was changed. No query endpoint or UI was added; those are
Phase 9. The exact contract, limits, configuration, official SDK reference,
tests, and live-provider limitation are in
`docs/reports/PHASE_8_GROUNDED_GENERATION.md`.

**Next recommended milestone:** Phase 9 typed FastAPI query delivery and thin
UI integration, after deliberately wiring an approved ranked-evidence source
to this Phase 8 service. Do not treat cited answers as entailment-verified.

## Phase 9 — Typed FastAPI Query Endpoint and Thin UI

Implemented `POST /query` with a strict typed request contract. Only question
and supported filing filters are accepted; client evidence, citation metadata,
URLs, and scores are rejected. The server-side dependency builds the existing
guarded narrative RRF-plus-reranker path, derives source URLs/hashes from the
manifest, and passes bounded admitted evidence to Phase 8 generation. It keeps
tables excluded. Configuration/retrieval failures fail closed with a generic
503; valid unanswered queries preserve explicit abstentions.

Added an optional Streamlit client in `ui/app.py`; it calls the API only and
does not import database, retrieval, or provider code. The initial focused
API/UI/health test run passed **3** tests with one existing warning; it was
superseded by the Phase 9B hardening results below. No live query/provider call
was made, and no source, benchmark, evidence artifact, schema, or corpus row
changed. Details and run commands: `docs/reports/PHASE_9_API_UI.md`.

### Phase 9B — End-to-End Verification and Integration-Test Hardening

Phase 9B independently traced the public flow from strict request validation
through guarded narrative RRF + bounded reranking, manifest-derived evidence
provenance, Phase 8 generation/citation validation/abstention, typed response,
and the HTTP-only Streamlit client. It found and fixed a real delivery defect:
reranked results retain `document_id` on their `.candidate`, while the original
adapter attempted to read it from the wrapper. The corrected adapter now uses
the trusted candidate identity for manifest URL resolution. It also corrected
dependency-construction failures to return the promised generic **503** rather
than an unhandled pre-route 500, closes request-scoped read-only connections,
and adds explicit admission/source-hash predicates to PostgreSQL keyword
retrieval. App and health descriptions now accurately report query delivery.

The expanded deterministic tests cover answered/abstained responses; blank,
whitespace, and overlong questions; rejected client evidence/citation/URL/score
fields; no-evidence/provider-failure/unknown-citation abstentions; internal
failure secrecy; missing configuration; server-side result and reranker bounds;
trusted manifest URL mapping; source-hash mismatch; connection closure; UI
answer/abstention/HTTP-failure/malformed-response states; and keyword SQL
admission/hash predicates. Focused checks passed **41** tests (one existing
Starlette/httpx deprecation warning); Windows units passed **122**; isolated
PostgreSQL integration passed **10 in 93.17s**; and the final full WSL suite passed
**132 in 101.35s** (one existing warning). Ruff, compileall, and manifest
validation passed. The manifest remains **10 VALID** and cleanup confirmed
**0** `evidence_test_*` schemas in `financial_rag_test`.

The protected narrative v2 hash remains
`d79de57f251a10de5797276e42b7d4fc6236124b9c268badc8477c538a6f1c9f`.
The actual guarded keyword evaluation remained unchanged: 20 answerable / 3
unanswerable, Recall@5/10 **0.05**, Precision@5 **0.01**, MRR **0.05**.
No raw filing, processed artifact, benchmark label, migration, or persistent
corpus row was changed. No OpenAI/provider call was authorized or made; live
provider behavior therefore remains unverified. Citation checks establish
identifier/provenance, not claim entailment. The full Phase 9B record is in
`docs/reports/PHASE_9_API_UI.md`.

## Phase 10 — Evaluation, Regression Testing, and Hardening

Phase 10 preserves the narrative v2 benchmark byte-for-byte at SHA-256
`d79de57f251a10de5797276e42b7d4fc6236124b9c268badc8477c538a6f1c9f` and
adds empty-result/no-relevant diagnostics. Fresh guarded measurements reproduced
keyword (0.05/0.05/0.01/0.05), semantic (0.65/0.90/0.14/0.5904), RRF
(0.65/0.90/0.14/0.5892), and RRF+rereanking (0.75/0.90/0.15/0.6972)
(R@5/R@10/P@5/MRR). Reranking at depths 50/20 passed a documented
small-corpus regression gate that also fixes the expected hash and 20/3
answerable/unanswerable denominators.

Added `grounded_answer_quality.v1.json` (SHA-256
`eef44ea5a9e8a0afc09a3bb3a3fd8243ffa6edf17bedf54548589c7050c98d1a`) and a
deterministic fixture evaluator. It provenance-checks three answerable narrative
references and reports 3/3 required-point/citation-contract passes plus 1/1
expected abstention. These are mock/fixture contract results, not live-provider
quality or semantic-entailment results. See
`docs/reports/PHASE_10_EVALUATION_HARDENING.md`.

### Gemini provider integration

Added the optional official `google-genai==2.31.0` dependency and a lazy
`GeminiProvider` selected only by `LLM_PROVIDER=gemini`. It reads the secret
only as `GEMINI_API_KEY`, uses the existing provider-neutral output contract,
and never falls back to OpenAI. `LLM_MODEL` remains provider-selected; the
documented example is `gemini-2.5-flash`. Mocked generation/API/UI validation
passed **35** tests (one existing warning), Ruff and compileall passed, and
`.env` was confirmed ignored without reading or printing it. No Gemini request
was made. Phase 10's final WSL and isolated integration reruns remain pending.
