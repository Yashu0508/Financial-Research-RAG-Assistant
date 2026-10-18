# Phase 10 — Evaluation, Regression Testing, and Hardening

## Scope and separation

Phase 10 measures retrieval separately from answer-contract behavior. The
immutable narrative v2 benchmark remains SHA-256
`d79de57f251a10de5797276e42b7d4fc6236124b9c268badc8477c538a6f1c9f` with 20
answerable and 3 unanswerable cases. No labels, raw filings, evidence artifacts,
or persistent corpus rows changed.

`grounded_answer_quality.v1.json` is a separate, provenance-checked dataset
with three answerable cases and one unanswerable case. It checks literal
required factual points, expected supplied-evidence citation IDs, and allowed
abstention reasons using recorded deterministic fixtures. Its SHA-256 is
`eef44ea5a9e8a0afc09a3bb3a3fd8243ffa6edf17bedf54548589c7050c98d1a`.
It is not a live-model score and does not prove semantic claim entailment.

## Measured guarded retrieval results

All modes used the preserved v2 labels and guarded `financial_rag_dev` corpus:

| Mode | R@5 | R@10 | P@5 | MRR | Empty results | Answerable no relevant @10 |
|---|---:|---:|---:|---:|---:|---:|
| Keyword | 0.05 | 0.05 | 0.01 | 0.05 | 17 | 19 |
| Semantic | 0.65 | 0.90 | 0.14 | 0.5904 | 0 | 2 |
| RRF | 0.65 | 0.90 | 0.14 | 0.5892 | 0 | 2 |
| RRF + reranking | 0.75 | 0.90 | 0.15 | 0.6972 | 0 | 2 |

The reranking run used branch/candidate depth 50 and rerank depth 20, the pinned
cross-encoder revision `233902d25c440f23af6f7d6e94d2946bac0bee0a`, completed
in 23.75 seconds, and passed the regression gate.

## Gates and commands

The reranking gate preserves the dataset hash and denominators and requires at
least R@5 0.70, R@10 0.85, P@5 0.14, and MRR 0.65. It is intentionally a
small-corpus regression alarm, not a production-quality threshold. A changed
dataset/denominator or lower result fails visibly.

```powershell
python scripts/evaluate_grounded_answers.py
python scripts/evaluate_keyword_retrieval.py --dataset data/evaluation/keyword_retrieval.v2.json
python scripts/evaluate_semantic_retrieval.py
python scripts/evaluate_hybrid_retrieval.py --branch-depth 50
python scripts/evaluate_hybrid_reranking.py --candidate-depth 50 --rerank-depth 20
```

The final command executes the gate. Routine evaluation makes no provider call;
live-provider evaluation remains deliberately unimplemented/opt-in.

## Results and limitations

The recorded-fixture run passed 3/3 answerable contract cases and 1/1 correct
abstention. Unit tests inject unknown citations, malformed output, quarantined
or source-hash-mismatched evidence, missing configuration, retrieval/database
failures, UI failures, and request/output bounds. These tests verify fail-closed
behavior and public-error secrecy; they do not evaluate a real provider or prove
financial-answer correctness/entailment.

Focused Phase 10 checks executed: Ruff, compileall, manifest validation (10
VALID sources), and 19 evaluation-focused unit tests passed. The prior Phase 9B
full WSL/integration runs predate these Phase 10 files; they must be rerun before
calling Phase 10 complete.

## Gemini provider addition

The provider-neutral generation boundary also supports `LLM_PROVIDER=gemini`.
It uses the official `google-genai` SDK's `Client(...).models.generate_content`
interface, reads only `GEMINI_API_KEY` through settings, and keeps `LLM_MODEL`
provider-selected (`gemini-2.5-flash` is the documented example). Install with
`python -m pip install -e ".[gemini]"`. Google documents the SDK and API
interface at [Google GenAI SDK](https://ai.google.dev/gemini-api/docs/libraries)
and [GenerateContent](https://ai.google.dev/api/generate-content). Google notes
availability and free-tier eligibility can change; do not assume a model is
available until a separately authorized manual smoke test. No Gemini request was
made in this work.
