"""Explicit provider construction from environment-backed application settings."""

from __future__ import annotations

from app.core.config import Settings
from app.generation.providers import GeminiProvider, OpenAIResponsesProvider
from app.generation.service import GenerationConfiguration, GroundedGenerationService


class GenerationConfigurationError(ValueError):
    """Generation is not configured; callers must not silently select a fallback."""


def build_generation_service(settings: Settings, trusted_source_hashes: dict[str, str]):
    if settings.llm_provider == "openai":
        if not settings.llm_api_key:
            raise GenerationConfigurationError("OPENAI_API_KEY and LLM_MODEL must be configured.")
        provider = OpenAIResponsesProvider(settings.llm_api_key.get_secret_value())
    elif settings.llm_provider == "gemini":
        if not settings.gemini_api_key:
            raise GenerationConfigurationError("GEMINI_API_KEY and LLM_MODEL must be configured.")
        provider = GeminiProvider(settings.gemini_api_key.get_secret_value())
    else:
        raise GenerationConfigurationError("LLM_PROVIDER must be exactly 'openai' or 'gemini'.")
    if not settings.llm_model:
        raise GenerationConfigurationError("Selected provider requires LLM_MODEL.")
    configuration = GenerationConfiguration(
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_output_tokens=settings.llm_max_output_tokens,
    )
    return GroundedGenerationService(
        provider,
        configuration,
        trusted_source_hashes,
    )
