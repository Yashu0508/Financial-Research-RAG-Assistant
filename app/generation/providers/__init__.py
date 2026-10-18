"""Provider-neutral protocol and the explicit OpenAI adapter."""

from .base import GenerationProvider, ProviderError, ProviderRequest
from .gemini import GeminiProvider
from .openai_responses import OpenAIResponsesProvider

__all__ = [
    "GeminiProvider",
    "GenerationProvider",
    "OpenAIResponsesProvider",
    "ProviderError",
    "ProviderRequest",
]
