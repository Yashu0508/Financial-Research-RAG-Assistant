"""Deterministic identifier/provenance validation, not claim entailment."""

from __future__ import annotations

from dataclasses import dataclass

from app.generation.contracts import Citation, NarrativeEvidence, ValidationResult


@dataclass(frozen=True)
class CitationValidation:
    citations: tuple[Citation, ...]
    result: ValidationResult


def validate_citation_ids(
    citation_ids: object, evidence: tuple[NarrativeEvidence, ...]
) -> CitationValidation:
    """Resolve unique IDs only from application-side admitted evidence records."""

    if not isinstance(citation_ids, list) or not all(
        isinstance(item, str) for item in citation_ids
    ):
        return CitationValidation((), ValidationResult(False, errors=("CITATIONS_MALFORMED",)))
    index = {item.evidence_id: item for item in evidence}
    unknown = [item for item in citation_ids if item not in index]
    if unknown:
        return CitationValidation((), ValidationResult(False, errors=("CITATION_UNKNOWN",)))
    ids = tuple(dict.fromkeys(citation_ids))
    warnings = ("DUPLICATE_CITATIONS_REMOVED",) if len(ids) != len(citation_ids) else ()
    citations = tuple(
        Citation(
            evidence_id=item.evidence_id,
            document_id=item.document_id,
            source_sha256=item.source_sha256,
            source_url=item.source_url,
            section_heading=item.section_heading,
            source_elements=item.source_elements,
            parent_chunk_id=item.parent_chunk_id,
        )
        for evidence_id in ids
        for item in (index[evidence_id],)
    )
    return CitationValidation(citations, ValidationResult(True, warnings=warnings))
