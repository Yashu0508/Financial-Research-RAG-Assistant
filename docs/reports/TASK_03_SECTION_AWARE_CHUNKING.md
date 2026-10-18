# Task 03: Deterministic, Section-Aware Evidence Chunking

## Objective and implemented scope

Implemented an offline evidence-preparation stage that consumes only registered, hash-valid SEC parser artifacts. It emits two distinct evidence types: section-aware narrative chunks and structure-preserving financial-table evidence. It does not implement cleaning as a separate pipeline, databases, indexes, embeddings, retrieval, generation, APIs, UI, or any network behavior.

## Files created, modified, and generated

- Created `app/ingestion/chunking/sec_evidence_chunker.py` and `scripts/prepare_sec_evidence.py`.
- Created `tests/unit/test_sec_evidence_chunker.py`.
- Updated `docs/ARCHITECTURE.md`, `docs/DATA_DICTIONARY.md`, `docs/DEVELOPMENT_PLAN.md`, `scripts/README.md`, and `CODEX_REPORT.md`.
- Generated Git-ignored artifacts beneath `data/processed/sec_evidence/v1/`: ten document JSON artifacts and `run_metadata.json`.

No raw filing, companion directory, registration manifest, parser artifact, or table-QA artifact was modified.

## Admission and data contracts

The chunker derives input artifact paths from the registration manifest document IDs; it does not scan for unregistered documents. For each registered document it rechecks the immutable source hash/size, verifies the parser-run artifact hash from parser metadata, requires parser version compatibility, requires parser status `PARSED`, and cross-checks document ID, source SHA-256, and parser configuration hash.

Failure results are explicit `evidence_document_quarantine` records. Source statuses such as `CHANGED` are reported as `SOURCE_CHANGED`, and malformed/missing/incompatible parser artifacts receive their own reason codes. Quarantined narrative/table records are kept outside trusted evidence arrays.

`narrative_chunk` records retain document/source identity, parser identity, chunker identity, sequence, exact parser-derived text, heading context, ordered source-element IDs/locators/tags, and inherited source warnings. `financial_table` records retain the original parser table index/locator, caption, heading, units, period text, rows, cells, raw display strings, cell kind, spans, and structural locators. Header association is explicitly `NOT_ESTABLISHED`; no financial semantics are inferred.

## Chunking configuration and ID decisions

`ChunkingConfig` version `1.0` has target/max/min sizes of 1,800/2,400/300 Unicode Python-string characters, zero overlap, `never_cross_heading` segmentation, deterministic whitespace-boundary splitting for long parser blocks, and a three-alphanumeric-character low-information floor. The sizes are conservative initial limits to keep chunks readable while preserving source elements; they are configuration values rather than quality claims and can be changed without modifying the algorithm.

Heading boundaries are never crossed. Complete paragraphs/list items remain intact unless a single parser block exceeds the maximum, in which case it is split at whitespace without overlap and retains a shared parser-element reference plus fragment positions. Low-information items, such as standalone page-number blocks in browser-saved filings, are retained as explicit quarantine records rather than silently discarded.

Stable chunk IDs include document/source SHA-256, parser version/configuration hash, chunking configuration hash, sequence, and chunk text. Table-evidence IDs include the same provenance/configuration identity plus parser table identity/index. JSON serialization is canonical and deterministic; per-document content hashes exclude operational timestamps. Atomic sibling-temp replacement avoids partial successful writes, and unchanged substantive artifacts are not rewritten.

## Commands and actual results

- `python scripts\prepare_sec_evidence.py` — 10 evidence documents, all `ADMITTED_WITH_QUARANTINED_RECORDS`; 938 narrative chunks, 833 table-evidence records, and 425 quarantined records.
- Repeated unchanged `python scripts\prepare_sec_evidence.py` plus run-metadata hash comparison — passed; all per-document substantive evidence hashes matched.
- `python -m pytest tests\unit\test_sec_evidence_chunker.py -q` — 8 passed.
- `python -m pytest -q` — 39 passed, with one existing non-failing FastAPI/Starlette TestClient deprecation warning.
- `python -m ruff check app scripts tests` — all checks passed.
- `python -m compileall -q app scripts tests` — passed with no diagnostics.

## Source integrity and QA baseline

The existing manifest validator remained `VALID=10`; final raw source SHA-256 comparison found zero mismatches. The table-QA checklist remains 30 checked entries with 30 `PASS` results.

The chunker loads the completed QA mapping and validates that each candidate’s original table index and preview non-empty cell text remain present in admitted structured table evidence. All 30 candidates passed this structural/provenance check. This regression confirms preservation against the existing human-review baseline; it does not independently validate accounting meaning or figures.

## Quarantine, warnings, and limitations

The run had no document-level integrity, parser-compatibility, or table-structure failure. Its 425 quarantined records are `LOW_INFORMATION_BLOCK` narrative items, chiefly standalone browser-rendered page labels such as `2`, `3`, and similar values. They do not block document admission because the documents retain substantial approved narrative/table evidence. No source/parser warning was promoted to an unqualified success.

The evidence contract does not yet provide an independent cleaned-text layer, semantic section taxonomy, trusted row-header/column-header association, token counts, table-row evidence, storage schema, indexing, embeddings, retrieval, citations, answer generation, or UI. Character limits apply to parser-normalized text, not raw source byte offsets. Parser structural locators remain the best available source locations and are not page numbers or guaranteed original HTML anchors.

## Recommended next phase

Review and implement the persistence schema/repository boundary for approved evidence only. That work should preserve this document/table separation and every provenance/version field, use migrations and isolated integration tests, and keep indexing, embeddings, retrieval, and generation out of scope until storage integrity is established.
