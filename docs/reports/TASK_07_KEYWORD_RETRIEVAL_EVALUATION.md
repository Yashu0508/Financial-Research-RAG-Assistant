# Task 07 — Keyword Retrieval Evaluation

## Scope and numbering

Task 06 implemented the roadmap’s Phase 5 keyword baseline. The next unused task number is **Task 07**; this milestone evaluates that existing baseline without renumbering the roadmap’s later semantic-retrieval phase. No embedding, vector, LLM, generation, API, or UI functionality was added.

## Dataset and labels

`data/evaluation/keyword_retrieval.v1.json` is a versioned three-case diagnostic dataset. It contains two Microsoft 2024 10-K questions and one Apple 2024 10-K question. Every expected target records a stable narrative `chunk_id`, `document_id`, and source locator:

- Microsoft cash from operations — `1a637f5ad8f15028f954c0f7`, `msft-2024-10k`, `element:652:p`.
- Microsoft Cloud gross margin — `781b962ce0fc9d395f307b25`, `msft-2024-10k`, `element:564:div`.
- Apple product/services gross margins — `169484d0561050734c7855ac`, `aapl-2024-10k`, `element:219:div`.

Labels were made by manually reviewing these retained narrative chunks, not inferred from filenames or generated answers. A unit test resolves each label against the unchanged admitted evidence artifact and checks document identity and source locator.

## Metrics and implementation

`app/evaluation/retrieval/keyword_evaluation.py` loads and validates the dataset, runs the existing retriever at ten results, and calculates:

- Recall@5 and Recall@10: fraction of cases with at least one expected chunk in the cutoff.
- Precision@5: mean relevant retrieved chunks divided by the fixed cutoff of five.
- MRR: mean reciprocal rank of the first expected chunk.

`scripts/evaluate_keyword_retrieval.py` is read-only and emits deterministic JSON for a configured, already populated database. It does not create corpus data or alter labels.

## Measured result

The evaluation was executed in a generated schema in the dedicated WSL PostgreSQL 16 test database. The schema was migrated, populated using the unchanged Phase 3 evidence artifacts, evaluated, and dropped in the same run.

| Metric | Result |
| --- | ---: |
| Recall@5 | 0.3333 |
| Recall@10 | 0.3333 |
| Precision@5 | 0.0667 |
| MRR | 0.3333 |

The Microsoft Cloud gross-margin label ranked first. The cash-from-operations and Apple product/services-margin labels were not returned in the top ten. These are measured baseline results, not quality claims; they demonstrate that lexical phrasing and the small narrative-only scope need further work.

## Commands and validation

- `python -m pytest tests/unit/test_keyword_evaluation.py -q` — **4 passed**.
- WSL `python -m pytest tests/unit -q` — **54 passed**, with one existing non-failing FastAPI/Starlette deprecation warning.
- `TEST_POSTGRES_DSN='dbname=financial_rag_test user=yatharth' /tmp/financial-rag-pgtest-venv/bin/python -m pytest tests/integration/test_postgres_evidence_storage.py::test_versioned_keyword_evaluation_runs_against_persisted_evidence -q` — **1 passed** against live PostgreSQL 16.
- WSL `python -m ruff check app scripts tests` and `python -m compileall -q app scripts tests` — passed.
- WSL `python scripts/validate_sec_registration_manifest.py` — **10 `VALID`**.
- Post-test schema check for `evidence_test_*` and `evidence_eval_*` — **0** remaining schemas.
- `python scripts/evaluate_keyword_retrieval.py` — run against an already populated database with `DATABASE_URL` set in the active shell. The persistent CLI corpus was not created by this task; measured values above came from the generated-schema integration execution.

## Limitations and next step

This has only three manually reviewed, single-target narrative cases. It does not judge every relevant chunk, financial tables, numeric interpretation, answer correctness, user-query variety, or latency. The isolated integration database is cleaned after tests, so the evaluation CLI needs a separately persisted development database. The next step is to expand the versioned judged retrieval set—especially table-aware and multi-relevant cases—before using it to compare a future semantic retriever.
