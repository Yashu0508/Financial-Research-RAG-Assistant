"""Versioned, reproducible metrics for the PostgreSQL keyword baseline."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

from app.ingestion.loaders.sec_manifest import load_registration_manifest
from app.retrieval.keyword import KeywordSearchFilters, KeywordSearchResult


class EvaluationDataError(ValueError):
    """Raised when a versioned retrieval-evaluation dataset is malformed."""


class KeywordRetriever(Protocol):
    def search(
        self, query: str, filters: KeywordSearchFilters, limit: int
    ) -> list[KeywordSearchResult]: ...


ANSWERABLE = "answerable"
UNANSWERABLE = "unanswerable"
NARRATIVE_EVIDENCE_TYPE = "narrative"
NARRATIVE_KEYWORD_MODE = "postgres_english_narrative_keyword"


@dataclass(frozen=True)
class ExpectedNarrativeEvidence:
    """A manually reviewed narrative reference, not a table or generated answer."""

    chunk_id: str
    document_id: str | None
    source_locator: str | None
    source_sha256: str | None


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    question: str
    filters: KeywordSearchFilters
    status: str
    expected_chunk_ids: frozenset[str]
    expected_evidence: tuple[ExpectedNarrativeEvidence, ...]


@dataclass(frozen=True)
class CaseEvaluation:
    case_id: str
    status: str
    returned_chunk_ids: tuple[str, ...]
    first_relevant_rank: int | None
    relevant_at_5: int
    relevant_at_10: int


@dataclass(frozen=True)
class KeywordEvaluationReport:
    dataset_id: str
    dataset_version: str
    dataset_sha256: str
    evaluated_retrieval_mode: str
    answerable_case_count: int
    unanswerable_case_count: int
    case_results: tuple[CaseEvaluation, ...]
    recall_at_5: float
    recall_at_10: float
    precision_at_5: float
    mrr: float
    empty_result_case_count: int
    answerable_empty_result_case_count: int
    answerable_no_relevant_at_10_case_count: int


def _required_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvaluationDataError(f"{name} must be a non-empty string.")
    return value.strip()


def _optional_string(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _required_string(value, name)


def _case_status(raw_case: dict[str, object]) -> str:
    """Keep v1 compatible: omitted status means an answerable retrieval case."""

    status = raw_case.get("status", ANSWERABLE)
    if status not in (ANSWERABLE, UNANSWERABLE):
        raise EvaluationDataError("status must be 'answerable' or 'unanswerable'.")
    return status


def load_keyword_evaluation_dataset(path: Path) -> tuple[str, str, tuple[EvaluationCase, ...]]:
    """Load labels that reference stable evidence IDs without rewriting them."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationDataError(
            f"Evaluation dataset is unreadable: {type(exc).__name__}."
        ) from exc
    if not isinstance(payload, dict):
        raise EvaluationDataError("Evaluation dataset root must be an object.")
    dataset_id = _required_string(payload.get("dataset_id"), "dataset_id")
    version = _required_string(payload.get("dataset_version"), "dataset_version")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise EvaluationDataError("cases must be a non-empty list.")
    cases: list[EvaluationCase] = []
    require_source_hash = version == "2.0"
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            raise EvaluationDataError("Each case must be an object.")
        raw_filters = raw_case.get("filters")
        if not isinstance(raw_filters, dict):
            raise EvaluationDataError("Each case requires a filters object.")
        period = raw_filters.get("reporting_period_end")
        try:
            parsed_period = date.fromisoformat(period) if isinstance(period, str) else None
        except ValueError as exc:
            raise EvaluationDataError("reporting_period_end must be an ISO date.") from exc
        status = _case_status(raw_case)
        raw_evidence = raw_case.get("expected_relevant_evidence")
        if not isinstance(raw_evidence, list):
            raise EvaluationDataError("Each case needs an expected_relevant_evidence list.")
        if status == ANSWERABLE and not raw_evidence:
            raise EvaluationDataError("Answerable cases need expected_relevant_evidence.")
        if status == UNANSWERABLE and raw_evidence:
            raise EvaluationDataError("Unanswerable cases must not name relevant evidence.")
        if not all(isinstance(item, dict) for item in raw_evidence):
            raise EvaluationDataError("Expected evidence must contain objects.")
        evidence: list[ExpectedNarrativeEvidence] = []
        for item in raw_evidence:
            if item.get("evidence_type", NARRATIVE_EVIDENCE_TYPE) != NARRATIVE_EVIDENCE_TYPE:
                raise EvaluationDataError(
                    "Narrative keyword evaluation cannot contain table or other evidence types."
                )
            source_sha256 = _optional_string(item.get("source_sha256"), "source_sha256")
            if require_source_hash and source_sha256 is None:
                raise EvaluationDataError("Version 2.0 evidence requires source_sha256.")
            document_id = _optional_string(item.get("document_id"), "expected evidence document_id")
            source_locator = _optional_string(
                item.get("source_locator"), "expected evidence source_locator"
            )
            if require_source_hash and (document_id is None or source_locator is None):
                raise EvaluationDataError(
                    "Version 2.0 evidence requires document_id and source_locator."
                )
            evidence.append(
                ExpectedNarrativeEvidence(
                    _required_string(item.get("chunk_id"), "expected evidence chunk_id"),
                    document_id,
                    source_locator,
                    source_sha256,
                )
            )
        expected_ids = frozenset(item.chunk_id for item in evidence)
        if len(expected_ids) != len(raw_evidence):
            raise EvaluationDataError("Expected evidence chunk IDs must be unique.")
        cases.append(
            EvaluationCase(
                _required_string(raw_case.get("case_id"), "case_id"),
                _required_string(raw_case.get("question"), "question"),
                KeywordSearchFilters(
                    ticker=raw_filters.get("ticker"),
                    form_type=raw_filters.get("form_type"),
                    reporting_period_end=parsed_period,
                ),
                status,
                expected_ids,
                tuple(evidence),
            )
        )
    if len({case.case_id for case in cases}) != len(cases):
        raise EvaluationDataError("case_id values must be unique.")
    return dataset_id, version, tuple(cases)


def validate_keyword_evaluation_references(dataset_path: Path, evidence_directory: Path) -> None:
    """Require all answerable narrative labels to resolve to admitted artifact provenance."""

    _, _, cases = load_keyword_evaluation_dataset(dataset_path)
    artifacts: dict[str, dict[str, object]] = {}
    for case in cases:
        for expected in case.expected_evidence:
            if expected.document_id is None or expected.source_locator is None:
                raise EvaluationDataError(
                    "Evidence-reference validation requires document_id and source_locator."
                )
            if expected.document_id not in artifacts:
                try:
                    artifacts[expected.document_id] = json.loads(
                        (evidence_directory / f"{expected.document_id}.json").read_text(
                            encoding="utf-8"
                        )
                    )
                except (OSError, json.JSONDecodeError) as exc:
                    raise EvaluationDataError(
                        f"Expected evidence document is unavailable: {expected.document_id}."
                    ) from exc
            artifact = artifacts[expected.document_id]
            if artifact.get("document_id") != expected.document_id:
                raise EvaluationDataError("Evidence artifact document identity is inconsistent.")
            if expected.source_sha256 and artifact.get("source_sha256") != expected.source_sha256:
                raise EvaluationDataError("Expected evidence source hash is inconsistent.")
            chunks = artifact.get("narrative_chunks")
            if not isinstance(chunks, list):
                raise EvaluationDataError("Evidence artifact lacks narrative_chunks.")
            matches = [chunk for chunk in chunks if chunk.get("chunk_id") == expected.chunk_id]
            if len(matches) != 1:
                raise EvaluationDataError("Expected narrative chunk does not resolve exactly once.")
            chunk = matches[0]
            if chunk.get("document_id") != expected.document_id:
                raise EvaluationDataError(
                    "Expected narrative chunk document identity is inconsistent."
                )
            elements = chunk.get("source_elements")
            locators = (
                {element.get("source_locator") for element in elements if isinstance(element, dict)}
                if isinstance(elements, list)
                else set()
            )
            if expected.source_locator not in locators:
                raise EvaluationDataError(
                    "Expected narrative chunk source locator is inconsistent."
                )


def validate_keyword_evaluation_filters(dataset_path: Path, manifest_path: Path) -> None:
    """Ensure every answerable label can be reached by its documented filters."""

    _, _, cases = load_keyword_evaluation_dataset(dataset_path)
    try:
        manifest = load_registration_manifest(manifest_path)
    except (OSError, ValueError) as exc:
        raise EvaluationDataError(
            "Registration manifest is unavailable for filter validation."
        ) from exc
    documents = {document.document_id: document for document in manifest.documents}
    for case in cases:
        for expected in case.expected_evidence:
            if expected.document_id not in documents:
                raise EvaluationDataError("Expected evidence document is not registered.")
            document = documents[expected.document_id]
            filters = case.filters
            if filters.ticker is not None and filters.ticker.upper() != document.ticker:
                raise EvaluationDataError("Expected evidence ticker does not match case filters.")
            if filters.form_type is not None and filters.form_type != document.form_type:
                raise EvaluationDataError(
                    "Expected evidence form type does not match case filters."
                )
            if filters.reporting_period_end is not None and str(
                filters.reporting_period_end
            ) != str(document.reporting_period_end):
                raise EvaluationDataError(
                    "Expected evidence reporting period does not match case filters."
                )


def evaluate_keyword_retriever(
    retriever: KeywordRetriever,
    dataset_path: Path,
    *,
    retrieval_mode: str = NARRATIVE_KEYWORD_MODE,
) -> KeywordEvaluationReport:
    """Evaluate fixed labels using Recall@5/@10, Precision@5, and reciprocal rank."""
    dataset_id, version, cases = load_keyword_evaluation_dataset(dataset_path)
    dataset_sha256 = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    evaluated: list[CaseEvaluation] = []
    for case in cases:
        ids = tuple(
            result.chunk_id for result in retriever.search(case.question, case.filters, limit=10)
        )
        first_rank = next(
            (
                index
                for index, chunk_id in enumerate(ids, start=1)
                if chunk_id in case.expected_chunk_ids
            ),
            None,
        )
        evaluated.append(
            CaseEvaluation(
                case.case_id,
                case.status,
                ids,
                first_rank,
                sum(chunk_id in case.expected_chunk_ids for chunk_id in ids[:5]),
                sum(chunk_id in case.expected_chunk_ids for chunk_id in ids[:10]),
            )
        )
    answerable = tuple(item for item in evaluated if item.status == ANSWERABLE)
    count = len(answerable)
    if not count:
        raise EvaluationDataError("At least one answerable case is required for retrieval metrics.")
    return KeywordEvaluationReport(
        dataset_id,
        version,
        dataset_sha256,
        retrieval_mode,
        count,
        len(evaluated) - count,
        tuple(evaluated),
        sum(item.relevant_at_5 > 0 for item in answerable) / count,
        sum(item.relevant_at_10 > 0 for item in answerable) / count,
        sum(item.relevant_at_5 / 5 for item in answerable) / count,
        sum(1 / item.first_relevant_rank if item.first_relevant_rank else 0 for item in answerable)
        / count,
        sum(not item.returned_chunk_ids for item in evaluated),
        sum(not item.returned_chunk_ids for item in answerable),
        sum(item.relevant_at_10 == 0 for item in answerable),
    )
