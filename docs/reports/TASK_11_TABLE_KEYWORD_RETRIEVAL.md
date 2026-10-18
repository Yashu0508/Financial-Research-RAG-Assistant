# Task 11 — Structure-preserving PostgreSQL table keyword retrieval

## Scope

Task 11 implements only a PostgreSQL lexical baseline for admitted financial
table evidence. It does not implement semantic/vector retrieval, hybrid search,
reranking, answer generation, citation rendering, API routes, or UI behavior.
Raw filings, parser artifacts, evidence artifacts, and both narrative evaluation
datasets remain unchanged.

## Storage and result contract

Migration `003_table_keyword_retrieval.sql` adds
`financial_table_search_documents`. It is a versioned (`1.0`) derived search
projection keyed by `table_evidence_id`; it maps back to the original
`financial_table_evidence` record and never replaces structured evidence. It
stores only contract-approved searchable display fields: caption, preceding
heading text, observed period-header text, table-level unit hints, and ordered
raw cell text. A PostgreSQL English GIN expression index supports lookup, and a
document/projection-version index supports joins/filtering. The migration
transactionally backfills existing admitted, source-consistent tables.

`PostgresTableKeywordRetriever` returns a result type distinct from narrative
`KeywordSearchResult`. Each result includes stable table/document/source IDs,
HTML locator/index, registered filing metadata, caption/heading, units/periods,
warnings, validation status, parser/chunker identity, score, and ordered raw
rows/cells. Cells retain display text, kind, spans, and locators. Results are
restricted to `ADMITTED` tables whose registered and projection source hashes
match. Quarantine records are not joined or searched.

The database currently persists table-level, not cell-level, unit hints. The
retriever returns all stored table-level observed hints and never invents
cell-level units. `header_association_status` remains `NOT_ESTABLISHED`; no
numeric interpretation, row-label normalization, or header-to-cell association
is claimed.

## Search behavior

The baseline tokenizes a natural-language query to alphanumeric lexical tokens,
passes a token-OR `to_tsquery('english', %s)` as a parameter, and ranks with
`ts_rank_cd`. This avoids treating filter/context words in table questions as
mandatory raw-table content. Tie-breaking is rank descending, then document ID,
original HTML table index, and table evidence ID ascending. Supported exact
filters are ticker, form type, reporting-period end, document ID, and table
evidence ID. Query input is never interpolated into SQL.

This is a deliberately simple lexical baseline. It can return non-relevant
candidates for unanswerable queries and cannot understand accounting semantics.

## Table benchmark measurement

The evaluator uses only `table_retrieval_judgments.v1.json`; narrative labels
are never passed to it. It validates case/status/table IDs/document/source
references/filters via the existing table-judgment validator, supports multiple
relevant table records, runs every query at a fixed limit of ten, and excludes
unanswerable cases from metric denominators.

Guarded live run against `financial_rag_dev`:

| Field | Result |
| --- | --- |
| Dataset ID/version | `sec-table-retrieval-judgments-v1` / `1.0` |
| Dataset SHA-256 | `f9ae4e874a239d556dc944fe3a6307fb876040d2847f8c39731370b3958f8ff5` |
| Retrieval mode | `postgres_english_financial_table_keyword_v1` |
| Answerable / unanswerable | 8 / 2 |
| Recall@5 / Recall@10 | 0.875 / 0.875 |
| Precision@5 | 0.175 |
| MRR | 0.71875 |

Seven of eight answerable cases retrieved a judged table in the top five. The
unretrieved case is the unfiltered cross-company annual-income-statement query;
this is a known limitation of the bare lexical baseline. The two unanswerable
questions returned candidates but have no judged target and do not affect the
reported metrics. These small manually reviewed results are diagnostic, not a
production-quality or representative quality claim.

## Guarded migration and live corpus

`python scripts/bootstrap_local_development_corpus.py` ran through the existing
guarded workflow against only `financial_rag_dev` / `financial_rag_dev` schema
as role `yatharth`. It applied migration `003`, retained the existing evidence
run with `inserted=False`, and verified 10 documents, 938 narrative chunks, 833
tables, and 425 quarantines. No test wrote to or cleaned up the persistent
corpus.

## Validation

Executed checks:

- `python -m pytest tests/unit/test_table_keyword_retrieval.py
  tests/unit/test_table_evaluation.py tests/unit/test_table_judgments.py -q` —
  **8 passed**.
- Windows `python -m pytest -q` — **79 passed, 1 skipped**, with the existing
  Starlette warning; the skip is expected because that interpreter lacks the
  PostgreSQL driver.
- WSL `/tmp/financial-rag-pgtest-venv/bin/python -m pytest tests/unit -q` —
  **79 passed**, with the existing Starlette warning.
- WSL isolated-schema PostgreSQL tests for migration repeatability, structured
  table retrieval/quarantine exclusion, and table evaluation — **3 passed**.
  A post-run query found **0** `evidence_test_%` schemas.
- `python -m ruff check app scripts tests`, `python -m compileall -q app
  scripts tests`, and `python scripts/validate_sec_registration_manifest.py`
  — passed; the manifest reports **10 VALID** sources.

Read-only post-bootstrap inspection of the guarded persistent schema found all
three migrations (`001`, `002`, `003`) and **833** table search projections.

## Next milestone

The next appropriate milestone is a measured comparison or improvement to this
keyword baseline only after defining a justified query/ranking ablation and
additional table judgments. Do not jump to semantic retrieval or answer
generation without expanding evaluation and resolving the remaining structural
interpretation limitations.
