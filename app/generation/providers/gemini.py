"""Lazy Gemini GenerateContent adapter; imports no SDK at module import time."""

from __future__ import annotations

from typing import Any

from .base import ProviderError, ProviderRequest


class GeminiProvider:
    """One explicitly configured Gemini provider with no fallback behavior."""

    def __init__(self, api_key: str, *, client: Any | None = None) -> None:
        if not api_key.strip():
            raise ProviderError("GEMINI_API_KEY is required for the Gemini provider.")
        self._api_key = api_key
        self._client = client

    def complete(self, request: ProviderRequest) -> str:
        try:
            client = self._client
            if client is None:
                from google import genai

                client = genai.Client(api_key=self._api_key)
            if self._client is None:
                from google.genai import types

                config = types.GenerateContentConfig(
                    system_instruction=request.instructions,
                    max_output_tokens=request.max_output_tokens,
                )
            else:
                config = {
                    "system_instruction": request.instructions,
                    "max_output_tokens": request.max_output_tokens,
                }
            response = client.models.generate_content(
                model=request.model, contents=request.input_text, config=config
            )
            output = getattr(response, "text", None)
            if not isinstance(output, str) or not output.strip():
                raise ProviderError("Gemini returned no text output.")
            return output
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError("Gemini generation request failed.") from exc
