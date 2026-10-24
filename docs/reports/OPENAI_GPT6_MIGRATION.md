# OpenAI GPT-6 Migration

## Decision and verified model

The active documented provider is OpenAI, using exact API model ID
`gpt-6-astra`. Official OpenAI documentation identifies it as GPT-6 Astra, the
flagship GPT-6 model, and lists `gpt-6-astra` as its API model ID. The model
catalog says current models are available through the Responses API and client
SDKs. The official pricing page lists Standard short-context rates of $10.00 per
million input tokens and $50.00 per million output tokens as of the inspection
date; pricing and account entitlements remain external conditions. See [OpenAI
Models](https://developers.openai.com/api/docs/models), [GPT-6
guidance](https://developers.openai.com/api/docs/guides/latest-model), and
[OpenAI pricing](https://developers.openai.com/api/docs/pricing).

The existing `OpenAIResponsesProvider` is compatible with this model because it
passes the configured model string directly to `client.responses.create`. The
pinned `openai==3.34.0` SDK was installed and inspected in the established WSL
environment; it exposes the Responses client, configurable timeout, and
`max_retries` parameter.

Account access, billing, and entitlement to `gpt-6-astra` are not locally
verifiable without an authorized live request. No substitute model is selected
automatically.

## Scoped implementation

`app/generation/providers/openai_responses.py` now passes the existing
`ProviderRequest.timeout_seconds` and an explicit bound of two SDK-managed
retries to `OpenAI`. The pinned SDK implements retry handling for retryable
transient failures, including rate limits and server errors, and considers
`Retry-After`; permanent authentication, permission, and invalid-model errors
remain provider errors rather than triggering any provider/model fallback.

The adapter continues to map:

- `model` to the configured `LLM_MODEL`;
- `instructions`, `input_text`, and `max_output_tokens` to the Responses API;
- non-empty `response.output_text` to provider output; and
- non-provider exceptions to a `ProviderError` with the SDK exception preserved
  as its exception cause for in-process sanitized diagnostics.

No retrieval, evidence, citation, abstention, API, UI, source-data, benchmark,
or database behavior changed. The existing Gemini adapter remains dormant code;
the documented configuration does not select it and there is no fallback to it.

## Required local configuration

Do not commit or print the local `.env` file. The developer must set these
variable names/values locally:

```text
LLM_PROVIDER=openai
OPENAI_API_KEY=<local secret>
LLM_MODEL=gpt-6-astra
LLM_TIMEOUT_SECONDS=30
LLM_MAX_OUTPUT_TOKENS=800
```

Install the already declared optional dependency in the established WSL
environment when needed:

```bash
cd "/mnt/d/Financial Research RAG Assistant"
/tmp/financial-rag-pgtest-venv/bin/python -m pip install -e ".[generation]"
```

## Validation performed

The following commands actually ran in WSL Ubuntu:

```bash
/tmp/financial-rag-pgtest-venv/bin/python -m pytest \
  tests/unit/test_grounded_generation.py tests/unit/test_config.py -q
# 25 passed

/tmp/financial-rag-pgtest-venv/bin/python -m pytest tests/unit -q
# 140 passed

/tmp/financial-rag-pgtest-venv/bin/python -m ruff check app tests
# All checks passed

/tmp/financial-rag-pgtest-venv/bin/python -m compileall -q app tests
# exited 0

/tmp/financial-rag-pgtest-venv/bin/python scripts/validate_sec_registration_manifest.py
# 10 registered sources, all VALID
```

The added mocks verify the GPT-6 Astra request payload, configured timeout and
two-retry SDK construction, empty output rejection, and cause preservation for
authentication, permission, invalid-model, rate-limit, server, and timeout-like
SDK failures. They make no network requests.

## Authorized live smoke test, not yet executed

Run only after deliberately authorizing one paid request. This makes one small
Responses API request through the project adapter and prints only a sanitized
category, optional numeric HTTP status, and response length.

```bash
cd "/mnt/d/Financial Research RAG Assistant"

/tmp/financial-rag-pgtest-venv/bin/python - <<'PY'
import openai

from app.core.config import get_settings
from app.generation.providers import OpenAIResponsesProvider, ProviderError, ProviderRequest


def classify(error: BaseException) -> tuple[str, int | None]:
    if not isinstance(error, ProviderError):
        return "UNCLASSIFIED_ERROR", None
    if str(error) == "OpenAI returned no text output.":
        return "EMPTY_RESPONSE", None

    cause = error.__cause__
    if isinstance(cause, (openai.AuthenticationError, openai.PermissionDeniedError)):
        return "AUTHENTICATION_OR_PERMISSION", cause.status_code
    if isinstance(cause, openai.NotFoundError):
        return "MODEL_NOT_FOUND", cause.status_code
    if isinstance(cause, openai.RateLimitError):
        return "RATE_LIMIT_OR_QUOTA", cause.status_code
    if isinstance(cause, openai.InternalServerError):
        return "PROVIDER_SERVICE_ERROR", cause.status_code
    if isinstance(cause, (openai.APITimeoutError, openai.APIConnectionError)):
        return "NETWORK_OR_TIMEOUT", None
    if isinstance(cause, openai.APIStatusError):
        code = cause.status_code if type(cause.status_code) is int else None
        return "SDK_REQUEST_ERROR", code
    return "UNCLASSIFIED_ERROR", None


settings = get_settings()
if (
    settings.llm_provider != "openai"
    or settings.llm_api_key is None
    or not settings.llm_model
):
    print("UNCLASSIFIED_ERROR")
    raise SystemExit(2)

try:
    text = OpenAIResponsesProvider(settings.llm_api_key.get_secret_value()).complete(
        ProviderRequest(
            model=settings.llm_model,
            instructions="Return exactly the word: OK",
            input_text="Reply with exactly: OK",
            max_output_tokens=8,
            timeout_seconds=30.0,
        )
    )
    print("SUCCESS")
    print(f"RESPONSE_LENGTH={len(text)}")
except Exception as error:
    category, status = classify(error)
    print(category)
    if status is not None:
        print(f"HTTP_STATUS={status}")
    raise SystemExit(1)
PY
```

No live OpenAI request or live RAG quality evaluation has been made. After a
successful smoke test, run the protected existing evaluation commands unchanged
and compare measured answer/citation/abstention behavior without modifying
benchmark labels or metrics.
