# Phase 8 Readiness Audit — Grounded Generation, Citations, and Abstention

> **Status update:** This readiness audit predates the Phase 8 implementation.
> Grounded generation, identifier/provenance citation validation, and explicit
> abstention are now implemented; see
> [PHASE_8_GROUNDED_GENERATION.md](PHASE_8_GROUNDED_GENERATION.md).

## Scope decision

The authoritative roadmap defines Phase 8 as **grounded generation, citations,
and abstention**. Final documentation/portfolio work is Phase 11. This audit
does not implement a provider, citation resolver, abstention policy, query API,
or UI: no provider/adapter decision or answer-level evaluation set is admitted.
Therefore, **Phase 8 is not complete**.

This run corrects stale documentation and records rechecks only. It did not
alter raw SEC sources, processed artifacts, benchmark labels, schemas, corpus
rows, or model caches.

Files modified or created in this audit: `README.md`, `docs/ARCHITECTURE.md`,
`docs/DEVELOPMENT_PLAN.md`, `scripts/README.md`,
`docs/reports/PHASE_7_HYBRID_RETRIEVAL.md`, this report, and `CODEX_REPORT.md`.
No Python, SQL, source-data, processed-artifact, benchmark, or configuration
file was changed.

## Status matrix

| Area | Classification | Evidence / boundary |
| --- | --- | --- |
| SEC registration and integrity | Verified complete | Manifest CLI revalidated all 10 registered sources as `VALID`. |
| Parsing and provenance | Verified complete | Parser/chunker contracts and unit coverage preserve source/document hashes and locators; quarantines are explicit. |
| PostgreSQL persistence/safety | Verified complete | Migrations `001`–`004`, guarded development workflow, and generated-schema integration fixture exist. |
| Narrative keyword retrieval | Verified complete | Parameterized PostgreSQL English FTS and v1/v2 evaluator exist. |
| Local semantic narrative retrieval | Verified complete | Pinned local embeddings, pgvector retrieval, source-consistent segments, and v2 evaluator exist; tables are excluded. |
| Structured table keyword retrieval | Verified complete | Separate result/evaluation contracts preserve raw rows/cells/provenance. Header association remains `NOT_ESTABLISHED`. |
| RRF hybrid retrieval | Verified complete | Narrative-only RRF keeps branch ranks, RRF score, and deterministic ties. |
| Pinned bounded reranking | Partially complete | Exact local loading and fresh v2 evaluation work, but only focused unit coverage exists; no isolated PostgreSQL reranker assertion or ablation/latency study is recorded. |
| Generation, citations, abstention | Not implemented / blocked | `app/generation/*` has package boundaries only. Protocol, adapter, prompts, resolver/validator, policy, and answer-level judged cases are absent. |
| API and UI | Not implemented | Only `GET /health` exists; `ui/` has no runnable application. |
| Reproducibility docs | Partially complete | Guards, scripts, and pinned cache loading exist; README/architecture/runbook are corrected here, while Phase 11 fresh-machine/demo work remains. |

## Protected artifacts and offline models

The narrative benchmark is unchanged:

```text
data/evaluation/keyword_retrieval.v2.json
SHA-256 d79de57f251a10de5797276e42b7d4fc6236124b9c268badc8477c538a6f1c9f
```

The manifest CLI reported 10 registered documents and `{'VALID': 10}`.

In the WSL virtual environment (Python 3.12.3), local-only loaders succeeded
for `sentence-transformers/all-MiniLM-L6-v2@1110a243fdf4706b3f48f1d95db1a4f5529b4d41`
and `cross-encoder/ms-marco-MiniLM-L6-v2@233902d25c440f23af6f7d6e94d2946bac0bee0a`.
Both use exact snapshots under the configured external cache with
`local_files_only=True`; this check downloaded no model and used no alternate
revision.

## Fresh retrieval reproduction

These measurements are fresh runs against the guarded persistent development
corpus and unchanged v2 dataset. They are small-benchmark retrieval diagnostics,
not answer-quality, production-quality, or financial-correctness claims.

| Mode | Recall@5 | Recall@10 | Precision@5 | MRR | Other |
| --- | ---: | ---: | ---: | ---: | --- |
| Semantic | 0.65 | 0.90 | 0.14 | 0.5904166667 | 20 answerable / 3 unanswerable |
| RRF (`k=60`) | 0.65 | 0.90 | 0.14 | 0.5892261905 | branch depth 50; 20 / 3 |
| RRF + cross-encoder | 0.75 | 0.90 | 0.15 | 0.6972222222 | depths 50/20; 20 / 3; 27.78 s including local loads |

The keyword evaluator also ran without `--dataset`, so it correctly selected
the older v1 diagnostic data: Recall@5/10 0.3333333333, Precision@5
0.0666666667, MRR 0.3333333333 over three answerable cases. It is not comparable
to v2 results. The canonical README now requires the explicit v2 argument for
cross-mode comparison.

Unanswerable cases are excluded from retrieval metric denominators. This is not
an answer-level abstention implementation.

## Commands and observed results

```powershell
(Get-FileHash data/evaluation/keyword_retrieval.v2.json -Algorithm SHA256).Hash.ToLower()
python scripts/validate_sec_registration_manifest.py
python -m ruff check app scripts tests
python -m compileall -q app scripts tests
```

```bash
/tmp/financial-rag-pgtest-venv/bin/python -m pytest tests/unit -q
/tmp/financial-rag-pgtest-venv/bin/python scripts/evaluate_keyword_retrieval.py
/tmp/financial-rag-pgtest-venv/bin/python scripts/evaluate_semantic_retrieval.py
/tmp/financial-rag-pgtest-venv/bin/python scripts/evaluate_hybrid_retrieval.py --branch-depth 50
/tmp/financial-rag-pgtest-venv/bin/python scripts/evaluate_hybrid_reranking.py --candidate-depth 50 --rerank-depth 20
```

Ruff passed; `compileall` exited 0; WSL units passed **89** with one existing
Starlette/httpx deprecation warning. The reranking command completed with the
reported values. The first isolated integration run skipped because
`TEST_POSTGRES_DSN` was not exported into that shell. The live rerun used
`TEST_POSTGRES_DSN="dbname=financial_rag_test user=yatharth"` and passed
**10 tests in 137.29 seconds**. A post-run query found **0** remaining
`evidence_test_*` schemas. An in-process FastAPI smoke check returned HTTP 200
and the expected explicit health-only payload. The fixture was inspected first:
it creates and drops a random `evidence_test_*` schema only.

## Next bounded implementation

Phase 8 needs a provider-independent grounded-generation contract: typed
supplied-evidence and response/citation structures, credential-free imports,
deterministic citation-ID resolution against the supplied result set, explicit
abstention types/policy, and tests. It also requires a user-approved choice of
one separately configured provider adapter before provider calls are added.

Keep API/UI work, new retrieval methods, corpus rebuilds, model downloads,
database migrations, numeric interpretation, and source-controlled API keys
out of that task. Before Phase 9, add an isolated reranker integration assertion
and a bounded latency/ablation measurement.
