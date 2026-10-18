# Phase 7 — Hybrid Retrieval and Bounded Reranking

> **Status update:** This report records the original RRF-only Phase 7 result.
> Its statements that reranking was deferred were superseded by Phase 7B's
> pinned local cross-encoder implementation. See
> [PHASE_7B_RERANKING.md](PHASE_7B_RERANKING.md) and
> [PHASE_8_READINESS_AUDIT.md](PHASE_8_READINESS_AUDIT.md) for current status.

## Implemented RRF baseline

Phase 7 adds deterministic narrative-only Reciprocal Rank Fusion over the
existing independent PostgreSQL keyword and local semantic retrievers. It does
not modify either source retriever, embeddings, database schema, raw data, or
judgments. Candidates deduplicate by stable `chunk_id`; conflicting immutable
document/source-hash/text provenance for one ID is an error, not a merge.

For each branch hit at one-based rank `r`, RRF contributes `1 / (60 + r)`. The
default branch depth is 50 (validated 1–100), result limits are validated 1–100,
and equal fusion scores sort by document ID, chunk sequence, and chunk ID. Both
branches receive the same existing ticker/form/reporting-period filters. Empty
branches are valid; malformed results and branch failures are explicit errors.

The hybrid result returns the original evidence provenance plus `keyword_rank`,
`semantic_rank`, and `rrf_score`. It remains narrative-only; table retrieval is
separate.

## Reranking status

Bounded reranking is **not implemented**. Inspection found only the pinned
embedding-model snapshot in the approved external model cache, no local
reranker snapshot. No model was downloaded, substituted, or called remotely.
This preserves the phase's offline/reproducibility guarantees. Reranker model
selection, exact revision, cache admission, CPU resource test, input-window
policy, bounded cap, fallback policy, and evaluation are deferred.

## Measurement

The preserved `keyword_retrieval.v2.json` SHA-256 remains
`d79de57f251a10de5797276e42b7d4fc6236124b9c268badc8477c538a6f1c9f` with 20
answerable and 3 unanswerable cases. `python scripts/evaluate_hybrid_retrieval.py
--branch-depth 50` measured mode `rrf_narrative_keyword_semantic_v1`:

| Mode | Recall@5 | Recall@10 | Precision@5 | MRR |
| --- | ---: | ---: | ---: | ---: |
| Keyword | 0.05 | 0.05 | 0.01 | 0.05 |
| Semantic | 0.65 | 0.90 | 0.14 | 0.5904166667 |
| RRF (`k=60`) | 0.65 | 0.90 | 0.14 | 0.5892261905 |

RRF matches the semantic Recall/Precision on this small benchmark but is
slightly lower in MRR. It is therefore not claimed to improve the semantic
baseline. Unanswerable cases retain returned-candidate diagnostics and remain
outside metric denominators.

## Limitations and next action

This benchmark is small and manually judged; it is not a production quality or
latency claim. Candidate-level rank diagnostics are available in hybrid results,
while the evaluation report preserves existing per-case returned-ID diagnostics.
The next Phase 7 action is to admit and test one pinned local CPU reranker, then
implement bounded reranking and rerun this same preserved benchmark. Phase 8 is
out of scope.

## Validation

Executed checks: focused hybrid/keyword/semantic/evaluation unit tests (**23
passed**); complete WSL unit suite (**87 passed**, one pre-existing Starlette
warning); Ruff; compileall; and source-manifest validation (**10 VALID**). The
complete isolated PostgreSQL suite ran only against `financial_rag_test` and
passed **10 tests in 104.15 seconds**. The final Windows suite passed **87**
with **1 expected integration skip** (no native psycopg). Post-run inspection
found **0** generated `evidence_test_%` schemas. Persistent-corpus readback
remained 10 documents, 938 narrative chunks, 833 tables, 425 quarantines, and
1,810 embeddings.
