"""Bounded evidence-to-answer orchestration with deterministic validation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.generation.abstention import abstain
from app.generation.citations import validate_citation_ids
from app.generation.contracts import (
    MAX_OUTPUT_CHARS,
    GenerationContractError,
    GenerationRequest,
    GenerationResponse,
    NarrativeEvidence,
    ValidationResult,
)
from app.generation.prompts.grounded import INSTRUCTIONS, build_provider_input
from app.generation.providers import GenerationProvider, ProviderError, ProviderRequest

MAX_OUTPUT_TOKENS = 800


@dataclass(frozen=True)
class GenerationConfiguration:
    model: str
    timeout_seconds: float = 30.0
    max_output_tokens: int = MAX_OUTPUT_TOKENS

    def validate(self) -> None:
        if not self.model.strip():
            raise GenerationContractError("LLM_MODEL must be configured.")
        if not 1 <= self.max_output_tokens <= MAX_OUTPUT_TOKENS:
            raise GenerationContractError(
                f"max_output_tokens must be 1 through {MAX_OUTPUT_TOKENS}."
            )
        if not 1 <= self.timeout_seconds <= 120:
            raise GenerationContractError("timeout_seconds must be from 1 through 120.")


def narrative_evidence_from_result(result: Any, *, source_url: str | None) -> NarrativeEvidence:
    """Adapt an existing narrative result without changing retrieval contracts."""

    candidate = getattr(result, "candidate", result)
    required = (
        "chunk_id",
        "document_id",
        "source_sha256",
        "text",
        "ticker",
        "company",
        "form_type",
        "reporting_period_end",
        "section_heading",
        "source_elements",
        "chunk_sequence",
    )
    if any(not hasattr(candidate, name) for name in required):
        raise GenerationContractError("Result lacks required narrative evidence provenance.")
    retrieval_score = getattr(candidate, "rrf_score", None)
    if retrieval_score is None:
        retrieval_score = getattr(candidate, "similarity", getattr(candidate, "rank", None))
    return NarrativeEvidence(
        evidence_id=candidate.chunk_id,
        document_id=candidate.document_id,
        source_sha256=candidate.source_sha256,
        text=candidate.text,
        ticker=candidate.ticker,
        company=candidate.company,
        form_type=candidate.form_type,
        reporting_period_end=candidate.reporting_period_end,
        source_url=source_url,
        section_heading=candidate.section_heading,
        source_elements=candidate.source_elements,
        chunk_sequence=candidate.chunk_sequence,
        parent_chunk_id=getattr(candidate, "chunk_id", None),
        retrieval_score=retrieval_score,
        reranker_score=getattr(result, "reranker_score", None),
    )


class GroundedGenerationService:
    """Use one provider on an already bounded, application-validated request."""

    def __init__(
        self,
        provider: GenerationProvider,
        configuration: GenerationConfiguration,
        trusted_source_hashes: Mapping[str, str],
    ) -> None:
        configuration.validate()
        self.provider = provider
        self.configuration = configuration
        self.trusted_source_hashes = dict(trusted_source_hashes)

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        try:
            request.validate()
        except GenerationContractError:
            return abstain("INVALID_EVIDENCE")
        if not request.evidence:
            return abstain("NO_ELIGIBLE_EVIDENCE")
        if any(
            self.trusted_source_hashes.get(item.document_id) != item.source_sha256
            for item in request.evidence
        ):
            return abstain("INVALID_PROVENANCE")
        try:
            output = self.provider.complete(
                ProviderRequest(
                    model=self.configuration.model,
                    instructions=INSTRUCTIONS,
                    input_text=build_provider_input(request),
                    max_output_tokens=self.configuration.max_output_tokens,
                    timeout_seconds=self.configuration.timeout_seconds,
                )
            )
        except ProviderError:
            return abstain("PROVIDER_FAILURE")
        return self._validate_output(output, request)

    def _validate_output(self, output: object, request: GenerationRequest) -> GenerationResponse:
        if not isinstance(output, str) or len(output) > MAX_OUTPUT_CHARS:
            return abstain("OUTPUT_LIMIT_OR_MALFORMED")
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            return abstain("MALFORMED_PROVIDER_OUTPUT")
        if not isinstance(payload, dict) or set(payload) != {
            "status",
            "answer",
            "citations",
            "reason",
        }:
            return abstain("MALFORMED_PROVIDER_OUTPUT")
        status, answer, citation_ids, reason = (
            payload["status"],
            payload["answer"],
            payload["citations"],
            payload["reason"],
        )
        if status == "abstained" and isinstance(reason, str):
            return abstain("PROVIDER_ABSTAINED", warning="Provider reported insufficient evidence.")
        if status != "answered" or not isinstance(answer, str) or not answer.strip():
            return abstain("MALFORMED_PROVIDER_OUTPUT")
        if len(answer) > MAX_OUTPUT_CHARS:
            return abstain("OUTPUT_LIMIT_OR_MALFORMED")
        citations = validate_citation_ids(citation_ids, request.evidence)
        if not citations.result.valid:
            return abstain(citations.result.errors[0])
        if not citations.citations:
            return abstain("MISSING_CITATIONS")
        return GenerationResponse(
            status="answered",
            answer=answer.strip(),
            citations=citations.citations,
            validation=ValidationResult(True, warnings=citations.result.warnings),
        )
