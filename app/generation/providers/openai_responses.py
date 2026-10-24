"""Lazy OpenAI Responses adapter; no SDK or credential is needed at import."""

from __future__ import annotations

from typing import Any

from .base import ProviderError, ProviderRequest

MAX_OPENAI_RETRIES = 2


class OpenAIResponsesProvider:
    """One explicitly configured provider; never falls back to another model."""

    def __init__(self, api_key: str, *, client: Any | None = None) -> None:
        if not api_key.strip():
            raise ProviderError("OPENAI_API_KEY is required for the OpenAI provider.")
        self._api_key = api_key
        self._client = client

    def complete(self, request: ProviderRequest) -> str:
        try:
            client = self._client
            if client is None:
                from openai import OpenAI

                # The pinned SDK applies bounded exponential backoff and honors
                # Retry-After for its retryable transport/status failures.
                client = OpenAI(
                    api_key=self._api_key,
                    timeout=request.timeout_seconds,
                    max_retries=MAX_OPENAI_RETRIES,
                )
            response = client.responses.create(
                model=request.model,
                instructions=request.instructions,
                input=request.input_text,
                max_output_tokens=request.max_output_tokens,
                store=False,
            )
            output = getattr(response, "output_text", None)
            if not isinstance(output, str) or not output.strip():
                raise ProviderError("OpenAI returned no text output.")
            return output
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError("OpenAI generation request failed.") from exc
