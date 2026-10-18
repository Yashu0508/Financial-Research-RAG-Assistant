"""Provider-neutral contracts for bounded, evidence-grounded generation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_EVIDENCE_ITEMS = 10
MAX_EVIDENCE_CHARS = 12_000
MAX_OUTPUT_CHARS = 4_000


class GenerationContractError(ValueError):
    """Raised when an application-side generation contract is invalid."""


@dataclass(frozen=True)
class NarrativeEvidence:
    """One trusted, admitted narrative item supplied to a provider."""

    evidence_id: str
    document_id: str
    source_sha256: str
    text: str
    ticker: str
    company: str
    form_type: str
    reporting_period_end: date | None
    source_url: str | None
    section_heading: dict[str, object]
    source_elements: list[dict[str, object]]
    chunk_sequence: int
    parent_chunk_id: str | None = None
    retrieval_score: float | None = None
    reranker_score: float | None = None
    admission_status: str = "ADMITTED"

    def validate(self) -> None:
        if not self.evidence_id or not self.document_id or not self.text.strip():
            raise GenerationContractError("Evidence requires non-empty identity and text.")
        if not _SHA256.fullmatch(self.source_sha256):
            raise GenerationContractError("Evidence requires a lowercase SHA-256 source hash.")
        if self.admission_status != "ADMITTED":
            raise GenerationContractError("Only ADMITTED narrative evidence may be generated from.")
        if not isinstance(self.source_elements, list) or not self.source_elements:
            raise GenerationContractError("Evidence requires source-element provenance.")
        if self.parent_chunk_id is not None and not self.parent_chunk_id.strip():
            raise GenerationContractError("parent_chunk_id must be non-empty when present.")


@dataclass(frozen=True)
class GenerationRequest:
    question: str
    evidence: tuple[NarrativeEvidence, ...]

    def validate(self) -> None:
        if not isinstance(self.question, str) or not self.question.strip():
            raise GenerationContractError("Question must be non-empty text.")
        if len(self.evidence) > MAX_EVIDENCE_ITEMS:
            raise GenerationContractError(
                f"At most {MAX_EVIDENCE_ITEMS} evidence items are allowed."
            )
        if len({item.evidence_id for item in self.evidence}) != len(self.evidence):
            raise GenerationContractError("Evidence identifiers must be unique.")
        for item in self.evidence:
            item.validate()
        if sum(len(item.text) for item in self.evidence) > MAX_EVIDENCE_CHARS:
            raise GenerationContractError(f"Evidence exceeds {MAX_EVIDENCE_CHARS} characters.")


@dataclass(frozen=True)
class Citation:
    evidence_id: str
    document_id: str
    source_sha256: str
    source_url: str | None
    section_heading: dict[str, object]
    source_elements: list[dict[str, object]]
    parent_chunk_id: str | None


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class GenerationResponse:
    status: Literal["answered", "abstained"]
    answer: str
    citations: tuple[Citation, ...] = ()
    validation: ValidationResult = field(default_factory=lambda: ValidationResult(False))
    abstention_reason: str | None = None
