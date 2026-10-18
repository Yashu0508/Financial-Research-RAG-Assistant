# Phase 8 — Grounded Generation, Citation Validation, and Abstention

## Implemented boundary

Phase 8 adds a provider-neutral generation boundary for **admitted narrative
evidence only**. It does not alter retrieval, ingestion, tables, corpus rows,
schema, API query routes, or UI behavior. The sole API route remains
`GET /health`; query/API integration is Phase 9.

The one configured adapter is OpenAI's Python SDK using the Responses API. It is
selected only when `LLM_PROVIDER=openai`; model selection is explicit through
`LLM_MODEL`. The adapter calls no fallback provider or model, uses `store=False`,
and imports the optional SDK only when a real request is made. The official SDK
documents the Responses API as its primary text-generation API and uses
`OPENAI_API_KEY`; see [the official Python SDK reference](https://developers.openai.com/api/reference/python).

No live provider call was made. `openai==3.34.0` is declared in the optional
`generation` dependency group, but routine tests inject a fake provider and
require neither the SDK nor a credential.

## Configuration

```text
LLM_PROVIDER=openai
OPENAI_API_KEY=<local secret only>
LLM_MODEL=gpt-5.4
LLM_TIMEOUT_SECONDS=30
LLM_MAX_OUTPUT_TOKENS=800
```

`gpt-5.4` is the single documented configured model; an unavailable model or
account access failure is a provider failure, never a silent substitution.
`OPENAI_API_KEY` is read as a secret and is never logged or serialized. Legacy
`LLM_API_KEY` is accepted only as a configuration alias. Importing application
or generation modules requires no key and does not import the SDK.

## Contracts and validation

`NarrativeEvidence` requires a stable evidence/document ID, lowercase source
SHA-256, exact text, filing metadata, source elements, and `ADMITTED` status.
`GenerationRequest` caps evidence at 10 items and 12,000 total characters.
`GenerationConfiguration` caps output at 800 tokens; provider text is capped at
4,000 characters before parsing.

The provider receives deterministic JSON with only supplied evidence and
separate retrieval/reranker scores. The prompt treats evidence as untrusted
material, directs the provider to ignore embedded instructions, and requires
JSON containing only `status`, `answer`, `citations`, and `reason`.

The provider text is untrusted. Citation IDs must resolve to supplied evidence;
duplicates are removed in first-seen order. Returned metadata, URLs, and
locators are constructed only from trusted application-side records. A
document-to-source-hash map must match every supplied item. Unknown IDs, missing
citations, invalid provenance, malformed output, output limits, provider errors,
empty evidence, and provider abstention produce explicit `abstained` results.

This is identifier/provenance validation, **not factual-entailment validation**.
The implementation cannot prove a cited passage supports every natural-language
claim; resolved citations do not independently establish financial truth.

## Tests and actual results

Focused fake-provider tests cover valid citations, injected evidence
instructions, unknown/missing/duplicate citations, malformed/oversized output,
provider errors, empty evidence, quarantined/source-inconsistent evidence,
configuration failure, and no silent provider/model fallback.

```text
python -m pytest tests/unit/test_grounded_generation.py tests/unit/test_config.py -q
15 passed

/tmp/financial-rag-pgtest-venv/bin/python -m pytest tests/unit -q
103 passed, 1 existing Starlette/httpx deprecation warning

TEST_POSTGRES_DSN="dbname=financial_rag_test user=yatharth" \
  /tmp/financial-rag-pgtest-venv/bin/python -m pytest -q
113 passed in 137.15 seconds, 1 existing Starlette/httpx deprecation warning
```

No live provider, persistent-corpus mutation, or benchmark evaluation was
needed. The protected narrative v2 SHA-256 remains
`d79de57f251a10de5797276e42b7d4fc6236124b9c268badc8477c538a6f1c9f`.
The integration fixture used only generated schemas in `financial_rag_test`; a
post-run query confirmed zero remaining `evidence_test_*` schemas.

`python -m ruff check app scripts tests` passed and `compileall` exited 0.
An additional repository-wide `ruff format --check app tests` reported nine
pre-existing files that would be reformatted outside the Phase 8 change set.
They were not rewritten; the Phase 8 files passed their targeted format check.

## Remaining limitation

The adapter contract is implemented, but a live OpenAI request remains
unverified because no paid-call authorization or credential was provided. Phase
9 may add a typed query endpoint/UI only after an approved ranked-evidence
source is wired into `GroundedGenerationService`.
