"""Deterministic evaluation of recorded grounded-answer fixtures.

This checks answer-contract behavior and required literal factual points.  It is
not semantic claim-entailment evaluation and never calls a model.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from app.evaluation.retrieval.keyword_evaluation import ANSWERABLE, UNANSWERABLE
from app.generation.contracts import GenerationResponse


class AnswerEvaluationDataError(ValueError):
    """Raised for malformed grounded-answer evaluation data."""


@dataclass(frozen=True)
class AnswerEvaluationCase:
    case_id: str
    question: str
    status: str
    evidence_ids: frozenset[str]
    required_factual_points: tuple[str, ...]
    allowed_abstention_reasons: frozenset[str]


@dataclass(frozen=True)
class AnswerCaseResult:
    case_id: str
    status: str
    passed: bool
    answer_factual_points_passed: bool | None
    citations_passed: bool | None
    abstention_passed: bool | None


@dataclass(frozen=True)
class GroundedAnswerEvaluationReport:
    dataset_id: str
    dataset_version: str
    dataset_sha256: str
    answerable_case_count: int
    unanswerable_case_count: int
    answerable_pass_count: int
    correct_abstention_count: int
    case_results: tuple[AnswerCaseResult, ...]


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AnswerEvaluationDataError(f"{field} must be a non-empty string.")
    return value.strip()


def load_grounded_answer_dataset(path: Path) -> tuple[str, str, tuple[AnswerEvaluationCase, ...]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AnswerEvaluationDataError("Answer evaluation dataset is unreadable.") from exc
    if not isinstance(payload, dict):
        raise AnswerEvaluationDataError("Answer evaluation dataset root must be an object.")
    dataset_id = _string(payload.get("dataset_id"), "dataset_id")
    version = _string(payload.get("dataset_version"), "dataset_version")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise AnswerEvaluationDataError("cases must be a non-empty list.")
    cases = []
    for raw in raw_cases:
        if not isinstance(raw, dict):
            raise AnswerEvaluationDataError("Each case must be an object.")
        status = raw.get("status")
        if status not in (ANSWERABLE, UNANSWERABLE):
            raise AnswerEvaluationDataError("status must be answerable or unanswerable.")
        evidence = raw.get("supporting_evidence", [])
        if not isinstance(evidence, list) or not all(isinstance(item, dict) for item in evidence):
            raise AnswerEvaluationDataError("supporting_evidence must be an object list.")
        ids = frozenset(_string(item.get("chunk_id"), "supporting chunk_id") for item in evidence)
        if len(ids) != len(evidence):
            raise AnswerEvaluationDataError("supporting chunk IDs must be unique.")
        facts = raw.get("required_factual_points", [])
        if not isinstance(facts, list) or not all(
            isinstance(item, str) and item.strip() for item in facts
        ):
            raise AnswerEvaluationDataError("required_factual_points must be a string list.")
        reasons = raw.get("allowed_abstention_reasons", [])
        if not isinstance(reasons, list) or not all(
            isinstance(item, str) and item for item in reasons
        ):
            raise AnswerEvaluationDataError("allowed_abstention_reasons must be a string list.")
        if status == ANSWERABLE and (not ids or not facts or reasons):
            raise AnswerEvaluationDataError(
                "Answerable cases require evidence/facts and no abstention reasons."
            )
        if status == UNANSWERABLE and (ids or facts or not reasons):
            raise AnswerEvaluationDataError("Unanswerable cases require only abstention reasons.")
        cases.append(
            AnswerEvaluationCase(
                _string(raw.get("case_id"), "case_id"),
                _string(raw.get("question"), "question"),
                status,
                ids,
                tuple(item.strip() for item in facts),
                frozenset(reasons),
            )
        )
    if len({case.case_id for case in cases}) != len(cases):
        raise AnswerEvaluationDataError("case_id values must be unique.")
    return dataset_id, version, tuple(cases)


def validate_grounded_answer_references(dataset_path: Path, evidence_directory: Path) -> None:
    """Require every answerable supporting reference to match admitted evidence."""
    try:
        payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AnswerEvaluationDataError("Answer evaluation dataset is unreadable.") from exc
    _, _, cases = load_grounded_answer_dataset(dataset_path)
    raw_cases = {item["case_id"]: item for item in payload["cases"]}
    artifacts: dict[str, dict[str, object]] = {}
    for case in cases:
        for reference in raw_cases[case.case_id].get("supporting_evidence", []):
            document_id = _string(reference.get("document_id"), "supporting document_id")
            source_hash = _string(reference.get("source_sha256"), "supporting source_sha256")
            locator = _string(reference.get("source_locator"), "supporting source_locator")
            if document_id not in artifacts:
                try:
                    artifacts[document_id] = json.loads(
                        (evidence_directory / f"{document_id}.json").read_text(encoding="utf-8")
                    )
                except (OSError, json.JSONDecodeError) as exc:
                    raise AnswerEvaluationDataError(
                        "Supporting evidence artifact is unavailable."
                    ) from exc
            artifact = artifacts[document_id]
            if (
                artifact.get("document_id") != document_id
                or artifact.get("source_sha256") != source_hash
            ):
                raise AnswerEvaluationDataError(
                    "Supporting evidence artifact provenance is inconsistent."
                )
            matches = [
                chunk
                for chunk in artifact.get("narrative_chunks", [])
                if isinstance(chunk, dict) and chunk.get("chunk_id") == reference.get("chunk_id")
            ]
            if len(matches) != 1 or matches[0].get("document_id") != document_id:
                raise AnswerEvaluationDataError(
                    "Supporting narrative chunk does not resolve exactly once."
                )
            locations = {
                element.get("source_locator")
                for element in matches[0].get("source_elements", [])
                if isinstance(element, dict)
            }
            if locator not in locations:
                raise AnswerEvaluationDataError(
                    "Supporting narrative source locator is inconsistent."
                )


def evaluate_grounded_answers(
    dataset_path: Path, responses: Mapping[str, GenerationResponse]
) -> GroundedAnswerEvaluationReport:
    """Score recorded answers without treating them as live model-quality results."""
    dataset_id, version, cases = load_grounded_answer_dataset(dataset_path)
    results = []
    for case in cases:
        if case.case_id not in responses:
            raise AnswerEvaluationDataError(f"Missing response for {case.case_id}.")
        response = responses[case.case_id]
        if case.status == ANSWERABLE:
            factual = response.status == "answered" and all(
                point.casefold() in response.answer.casefold()
                for point in case.required_factual_points
            )
            cited_ids = {citation.evidence_id for citation in response.citations}
            citations = response.status == "answered" and case.evidence_ids.issubset(cited_ids)
            results.append(
                AnswerCaseResult(
                    case.case_id, case.status, factual and citations, factual, citations, None
                )
            )
        else:
            abstained = (
                response.status == "abstained"
                and response.abstention_reason in case.allowed_abstention_reasons
            )
            results.append(
                AnswerCaseResult(case.case_id, case.status, abstained, None, None, abstained)
            )
    answerable = [result for result in results if result.status == ANSWERABLE]
    unanswerable = [result for result in results if result.status == UNANSWERABLE]
    return GroundedAnswerEvaluationReport(
        dataset_id,
        version,
        hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        len(answerable),
        len(unanswerable),
        sum(result.passed for result in answerable),
        sum(result.passed for result in unanswerable),
        tuple(results),
    )
