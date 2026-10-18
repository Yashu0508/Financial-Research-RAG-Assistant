"""Explicit, provider-independent abstention construction."""

from __future__ import annotations

from app.generation.contracts import GenerationResponse, ValidationResult


def abstain(reason: str, *, warning: str | None = None) -> GenerationResponse:
    """Return a safe user-facing abstention without provider diagnostics."""

    warnings = (warning,) if warning else ()
    return GenerationResponse(
        status="abstained",
        answer="I cannot provide a supported answer from the available filing evidence.",
        validation=ValidationResult(False, warnings=warnings, errors=(reason,)),
        abstention_reason=reason,
    )
