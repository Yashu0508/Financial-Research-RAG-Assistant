# Task 09 — Versioned Judged Retrieval Benchmark v2

## Scope

Task 09 is the next milestone after live Task 08 development-corpus validation.
It evaluates only the existing PostgreSQL English full-text retriever over
admitted **narrative** chunks. It does not implement semantic retrieval,
embeddings, hybrid fusion, reranking, table retrieval, answer generation, or a
UI. Task 07 v1 remains unchanged.

## Dataset and judgment method

`data/evaluation/keyword_retrieval.v2.json` contains 23 manually reviewed
questions: 20 answerable narrative-retrieval cases and 3 explicitly
unanswerable cases. It covers Apple and Microsoft, 10-K and 10-Q filings,
financial performance, business operations, capital return, and risks.

Every answerable v2 reference contains an evidence type, stable chunk ID,
document ID, document source SHA-256, and source locator. Labels were created
by reading the retained chunk and its provenance in the admitted artifact, not
from filename inference or lexical overlap. Artifact validation requires every
reference to resolve exactly once and rejects bad document IDs, hashes,
locators, missing chunks, duplicate chunk IDs within a case, and table evidence
in this narrative-only benchmark.

Two cases use multiple relevant narrative chunks:

- Apple 2024 supply-chain and component-sourcing risks — four chunks.
- Microsoft fiscal 2024 Q2 cloud execution and competitive risks — two chunks.

The three unanswerable cases contain an empty expected-evidence list because
the reviewed narrative corpus does not disclose the requested standalone amount:
Apple Vision Pro revenue, Microsoft Copilot revenue, and Apple India Q2 net
sales. They are reported separately, not treated as retrieval misses, and are
not an answer-generation abstention evaluation.

No table judgments were added in Task 09. The existing table QA provides a
structural/manual-review baseline but not a table-retrieval relevance contract.
The narrative evaluator explicitly rejects table evidence labels until that
contract and a table retriever exist.

## Metrics and reproducibility

For answerable cases only:

- Recall@5/@10 is the fraction with at least one judged chunk at the cutoff.
- Precision@5 is the mean number of judged chunks in the first five divided by
  five, including when fewer than five candidates are returned.
- MRR is the mean reciprocal rank of the first judged chunk.

The evaluator runs each query at a fixed limit of ten. It reports dataset ID,
version, SHA-256 of the dataset bytes, retrieval mode, and separate answerable
and unanswerable case counts. V1 omits `status`, which is interpreted as
`answerable` for backward compatibility; its prior metric interpretation is
unchanged.

## Live measured v2 baseline

Command run in WSL against the guarded persistent `financial_rag_dev` corpus:

```bash
/tmp/financial-rag-pgtest-venv/bin/python scripts/evaluate_keyword_retrieval.py \
  --dataset data/evaluation/keyword_retrieval.v2.json
```

| Field | Result |
| --- | --- |
| Dataset ID/version | `sec-keyword-retrieval-v2` / `2.0` |
| Dataset SHA-256 | `d79de57f251a10de5797276e42b7d4fc6236124b9c268badc8477c538a6f1c9f` |
| Retrieval mode | `postgres_english_narrative_keyword` |
| Answerable / unanswerable | 20 / 3 |
| Recall@5 | 0.0500 |
| Recall@10 | 0.0500 |
| Precision@5 | 0.0100 |
| MRR | 0.0500 |

These are diagnostic measurements of the unchanged keyword baseline, not a
statistically representative or production-quality evaluation.

## Commands and validation

```powershell
python -m pytest tests\unit\test_keyword_evaluation.py -q
python scripts\evaluate_keyword_retrieval.py --dataset data/evaluation/keyword_retrieval.v2.json
```

- WSL `python -m pytest tests/unit -q` — **70 passed**, with one existing
  Starlette deprecation warning.
- WSL `TEST_POSTGRES_DSN='dbname=financial_rag_test user=yatharth' ...
  test_versioned_keyword_evaluation_runs_against_persisted_evidence -q` —
  **1 passed**. The integration fixture used a generated schema and removed it.
- WSL manifest validation — **10 `VALID`** sources.
- Windows `python -m pytest -q` — **70 passed, 1 skipped** because its
  interpreter lacks `psycopg`, with the same existing warning.
- Ruff and compileall — passed in Windows and WSL checks.
- The default v1 CLI executed against `financial_rag_dev`; it reported 3
  answerable/0 unanswerable cases and retained Recall@5/10 `0.3333`,
  Precision@5 `0.0667`, and MRR `0.3333`.

## Next milestone

Define the table-evidence retrieval contract and separate table relevance labels
before implementing table retrieval or comparing any future semantic retriever.

## Task 10 audit note

Task 10 reproduced the v2 figures against the guarded persistent corpus and
verified that target chunk IDs, source hashes, locators, and document filters
resolve correctly. The low score is not a metric-denominator or filter-label
defect: 17 answerable queries returned no lexical candidates, two returned
non-relevant candidates, and one returned a judged result. The audit added a
date-normalized manifest-filter validation guard without changing v1 or v2
labels. See `docs/reports/TASK_10_TABLE_EVIDENCE_RETRIEVAL_CONTRACT.md` for
the audit and table-evidence preparation.
