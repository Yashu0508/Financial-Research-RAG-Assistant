# Task 10 — Table-evidence retrieval contract and benchmark preparation

## Scope

Task 10 audits the Task 09 narrative-keyword measurements, defines the table-evidence result contract, and prepares separate table judgments. It does not implement table retrieval, a table index, embeddings, semantic or hybrid retrieval, reranking, answer generation, or UI behavior. Raw SEC filings and existing parsed/evidence artifacts were not changed.

## Task 09 audit

`keyword_retrieval.v1.json` is unchanged. The v2 dataset has 23 cases: 20 answerable and 3 unanswerable. The evaluator's definition is correct: only answerable cases contribute to Recall@5, Recall@10, Precision@5, and MRR; unanswerable cases are reported separately.

Every v2 expected narrative record resolves once in the admitted evidence artifacts with its document ID, source SHA-256, and source locator. Each document/ticker/form-type/reporting-period filter is consistent with the registration manifest. The audit added explicit validation of that last condition. Its first implementation compared a Python `date` to a manifest ISO string; tests exposed that implementation error before it reached a CLI run. The guard now compares canonical string values. No dataset judgment or retrieval behavior was changed.

The live persistent-corpus v2 evaluation was reproduced with unchanged dataset hash `d79de57f251a10de5797276e42b7d4fc6236124b9c268badc8477c538a6f1c9f`:

| Measure | Result |
| --- | ---: |
| Answerable / unanswerable cases | 20 / 3 |
| Recall@5 | 0.0500 |
| Recall@10 | 0.0500 |
| Precision@5 | 0.0100 |
| MRR | 0.0500 |

The case results explain the low score: 17 answerable questions returned no candidates, two returned candidates but not a judged relevant chunk, and one retrieved a judged chunk at rank one (Microsoft cloud gross margin). This is not a denominator, provenance, or metadata-filter defect. The current retriever uses `websearch_to_tsquery('english', question)` against only narrative chunk text. Its all-terms lexical matching is brittle for long natural-language questions and does not index document metadata, table structure, or semantic equivalents. This is a fair diagnostic of the current baseline, not a quality claim.

## Table contract and judgments

The complete contract is [`docs/TABLE_EVIDENCE_RETRIEVAL_CONTRACT.md`](../TABLE_EVIDENCE_RETRIEVAL_CONTRACT.md). It distinguishes actual persisted/artifact fields from future requirements and requires only admitted `financial_table` evidence with registered source-hash provenance. Rows, cells, spans, raw display text, period header strings, unit hints, warnings, and locator semantics remain structured. Quarantine records are never trusted evidence.

`data/evaluation/table_retrieval_judgments.v1.json` is a separate validation-only benchmark. It contains 10 manually reviewed cases: 8 answerable cases grounded in admitted QA-mapped Apple/Microsoft annual or quarterly statement tables; 2 unanswerable cases (standalone Apple Vision Pro and Microsoft Copilot revenue tables); and one multi-relevant annual-income-statement case. Every answerable reference has stable table/document/source identity, table location, metadata filters, and a manual rationale. The validator checks these against actual artifacts and the manifest. It cannot report table-retrieval performance until a table retriever exists.

## Changes

- Added manifest/filter consistency validation to the narrative evaluation guard and CLI.
- Added `app.evaluation.retrieval.table_judgments`, unit tests, and the separate versioned table-judgment dataset.
- Added the table-evidence retrieval contract.
- Preserved Task 07/09 narrative datasets and all source/evidence artifacts.

## Validation

Executed:

```powershell
python -m pytest tests/unit/test_table_judgments.py tests/unit/test_keyword_evaluation.py -q
python -m ruff check app scripts tests
python -m compileall -q app scripts tests
```

The focused unit command passed **15 tests**; Ruff and compileall passed. The
live v2 evaluation was run through the guarded WSL `financial_rag_dev`
workflow. Additional executed checks were:

- Windows `python -m pytest -q` — **75 passed, 1 skipped**, with the existing
  Starlette warning; the skip is the PostgreSQL integration module because the
  Windows interpreter does not have the storage driver.
- WSL `/tmp/financial-rag-pgtest-venv/bin/python -m pytest tests/unit -q` —
  **75 passed**, with the existing Starlette warning.
- WSL isolated live PostgreSQL
  `test_versioned_keyword_evaluation_runs_against_persisted_evidence` —
  **1 passed** against `financial_rag_test`; post-run inspection found **0**
  `evidence_test_%` schemas.
- `python scripts/validate_sec_registration_manifest.py` — **10 VALID**
  registered sources.

## Deferred work and next milestone

There is no table search projection/index, table ranking algorithm, or table-retrieval result object. `header_association_status` is currently `NOT_ESTABLISHED`, so a future implementation must not infer normalized row/column/value meaning. The next milestone should implement a narrow, structure-preserving table keyword-retrieval baseline against this contract and then execute this separate table benchmark. It should not add semantic retrieval or answer generation in the same task.
