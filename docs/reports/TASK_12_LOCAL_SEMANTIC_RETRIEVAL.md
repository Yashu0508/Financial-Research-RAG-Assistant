# Phase 6 — Local Semantic Narrative Retrieval

## Scope and design

This implementation completes Phase 6 over admitted narrative evidence only. It does not
alter SEC sources, parsed/evidence artifacts, either narrative benchmark, table
retrieval, hybrid fusion, reranking, generation, or UI behavior.

Migration `004_semantic_narrative_retrieval.sql` adds model-configuration
records and source-preserving narrative embedding segments. It uses
`public.vector(384)` and a qualified `public.vector_cosine_ops` HNSW index;
application tables remain in the non-public guarded schema. Because connections
use `<app schema>, pg_catalog`, retrieval uses `OPERATOR(public.<=>)` rather
than adding `public` to the search path.

The model is `sentence-transformers/all-MiniLM-L6-v2` at revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, 384 dimensions, normalized cosine
vectors. Tested libraries are Sentence Transformers 6.1.0, Transformers 5.20.1,
PyTorch 2.14.1+cpu, NumPy 2.5.4, psycopg 3.2.10, PostgreSQL 16.15, and pgvector
0.6.0. The loader requires the exact external cached snapshot and loads its path
with `local_files_only=True`; it never resolves/downloads a model or switches
revisions.

The original 938 chunks remain unchanged. The 256-token model limit is handled
by tokenizer offset mappings and stable, non-overlapping 254-content-token
windows. Every child segment maps to its parent chunk and measured character
span and records its input hash, model configuration hash, document ID, and
source SHA-256. Retrieval scores child segments but returns the best parent
chunk deterministically. A fixed `hnsw.ef_search=1000` is set per search so
filtered queries are repeatable in this small corpus.

## Live corpus and benchmark

Guarded backfill against `financial_rag_dev` as `yatharth` applied migration
`004` and created configuration
`a92cf01525bc94b752c001f242a107eb9a774c5d168f8cf9e72e649d1095294e` with
**1,810** vectors for **938** admitted chunks. The preserved corpus remains 10
documents, 938 narrative chunks, 833 table records, and 425 quarantines.

The preserved v2 dataset SHA-256 is
`d79de57f251a10de5797276e42b7d4fc6236124b9c268badc8477c538a6f1c9f`.
Mode `postgres_pgvector_cosine_narrative_semantic_v1` measured 20 answerable
and 3 unanswerable cases: Recall@5 **0.65**, Recall@10 **0.90**, Precision@5
**0.14**, and MRR **0.5904166666666667**. Unanswerable returned candidates are
reported diagnostically but excluded from all metric denominators.

The recorded keyword v2 baseline is Recall@5/10 0.05, Precision@5 0.01, MRR
0.05. This small manually judged benchmark indicates improvement for this exact
configuration; it is not representative or a production-quality guarantee.

## Validation

Executed checks include the focused semantic unit/evaluator set (**16 passed**),
the WSL unit suite (**84 passed**, one pre-existing Starlette deprecation
warning), the Windows suite (**84 passed, 1 skipped** because native Python has
no psycopg driver), Ruff, compileall, and immutable manifest validation (**10
VALID**). The complete isolated PostgreSQL suite ran against only
`financial_rag_test` with generated schemas (**10 passed in 102.27s**). Each
completed cleanup check found zero `evidence_test_%` schemas. The focused
pgvector/idempotency and source-hash-mismatch cases also passed independently
(**2 passed**).

## Limitations and next milestone

Child windows are non-overlapping, context across a boundary may be weaker, and
there is no latency study. The benchmark remains small; table semantic retrieval
and numeric interpretation are absent. The next milestone is Phase 7 hybrid
fusion and bounded reranking, after defining a fair comparison against preserved
keyword and semantic baselines.
