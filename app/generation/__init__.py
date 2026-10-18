"""Bounded, evidence-grounded generation contracts and orchestration."""

from .contracts import Citation, GenerationRequest, GenerationResponse, NarrativeEvidence
from .service import (
    GenerationConfiguration,
    GroundedGenerationService,
    narrative_evidence_from_result,
)

__all__ = [
    "Citation",
    "GenerationConfiguration",
    "GenerationRequest",
    "GenerationResponse",
    "GroundedGenerationService",
    "NarrativeEvidence",
    "narrative_evidence_from_result",
]
