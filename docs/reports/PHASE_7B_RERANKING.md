# Phase 7B — Pinned Local Bounded Reranking

Selected `cross-encoder/ms-marco-MiniLM-L6-v2` revision
`233902d25c440f23af6f7d6e94d2946bac0bee0a`, Apache-2.0. The model card
documents passage-ranking use, 22.7M parameters, and CPU-appropriate MiniLM-L6
performance. Required assets were downloaded once into the existing external
cache `/home/yatharth/.cache/financial-rag-models`; normal loading uses the
exact snapshot path and `local_files_only=True`.

Reranking is narrative-only and read-only. It receives bounded RRF candidates,
uses original evidence text, creates deterministic candidate windows under a
512-token pair limit, scores windows with the cross-encoder, takes each
candidate's maximum raw score, and returns the sorted reranked window followed
by untouched trailing hybrid candidates. Scores are not probabilities. Default
candidate/rerank depths are 50/20 and are capped at 100/50.

The unchanged repository benchmark hash is
`d79de57f251a10de5797276e42b7d4fc6236124b9c268badc8477c538a6f1c9f`
(the prompt's `f2510` spelling conflicts with the actual file). Against 20
answerable and 3 unanswerable cases, `evaluate_hybrid_reranking.py` measured
Recall@5 0.75, Recall@10 0.90, Precision@5 0.15, MRR 0.6972222222; elapsed
wall time was 28.94 seconds including local model loading/evaluation. This
improves the recorded RRF baseline on this small benchmark only.

Source: [Hugging Face model card](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2).
