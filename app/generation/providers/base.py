"""Provider-facing protocol; provider response text remains untrusted."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ProviderError(RuntimeError):
    """A provider request failed without an alternate-provider fallback."""


@dataclass(frozen=True)
class ProviderRequest:
    model: str
    instructions: str
    input_text: str
    max_output_tokens: int
    timeout_seconds: float


class GenerationProvider(Protocol):
    def complete(self, request: ProviderRequest) -> str: ...
