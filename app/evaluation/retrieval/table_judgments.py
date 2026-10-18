"""Validation-only contract for manually judged structured-table retrieval labels.

No table retriever or table metric execution is implemented here.  This module
keeps future table judgments separate from narrative keyword evaluation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.ingestion.loaders.sec_manifest import load_registration_manifest
from app.retrieval.keyword import KeywordSearchFilters

ANSWERABLE = "answerable"
UNANSWERABLE = "unanswerable"
TABLE_EVIDENCE_TYPE = "table"


class TableJudgmentDataError(ValueError):
    """Raised when table-retrieval labels do not match admitted table evidence."""


@dataclass(frozen=True)
class ExpectedTableEvidence:
    table_evidence_id: str
    document_id: str
    source_sha256: str
    source_locator: str
    original_html_table_index: int
    parser_table_id: str


@dataclass(frozen=True)
class TableJudgmentCase:
    case_id: str
    status: str
    question: str
    filters: KeywordSearchFilters
    expected_tables: tuple[ExpectedTableEvidence, ...]


def _required_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TableJudgmentDataError(f"{name} must be a non-empty string.")
    return value.strip()


def _filters(value: object) -> KeywordSearchFilters:
    if not isinstance(value, dict):
        raise TableJudgmentDataError("Each case requires a filters object.")
    period = value.get("reporting_period_end")
    try:
        parsed_period = date.fromisoformat(period) if isinstance(period, str) else None
    except ValueError as exc:
        raise TableJudgmentDataError("reporting_period_end must be an ISO date.") from exc
    return KeywordSearchFilters(
        ticker=value.get("ticker"),
        form_type=value.get("form_type"),
        reporting_period_end=parsed_period,
    )


def load_table_judgments(path: Path) -> tuple[str, str, tuple[TableJudgmentCase, ...]]:
    """Load a non-executable table-judgment dataset with strict stable references."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TableJudgmentDataError("Table judgment dataset is unreadable.") from exc
    if not isinstance(payload, dict):
        raise TableJudgmentDataError("Table judgment dataset root must be an object.")
    dataset_id = _required_string(payload.get("dataset_id"), "dataset_id")
    version = _required_string(payload.get("dataset_version"), "dataset_version")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise TableJudgmentDataError("cases must be a non-empty list.")
    cases: list[TableJudgmentCase] = []
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            raise TableJudgmentDataError("Each table judgment case must be an object.")
        status = raw_case.get("status")
        if status not in (ANSWERABLE, UNANSWERABLE):
            raise TableJudgmentDataError("status must be 'answerable' or 'unanswerable'.")
        raw_tables = raw_case.get("expected_relevant_evidence")
        if not isinstance(raw_tables, list):
            raise TableJudgmentDataError("Each case needs an expected_relevant_evidence list.")
        if status == ANSWERABLE and not raw_tables:
            raise TableJudgmentDataError("Answerable table cases need relevant table evidence.")
        if status == UNANSWERABLE and raw_tables:
            raise TableJudgmentDataError("Unanswerable table cases must not name table evidence.")
        tables: list[ExpectedTableEvidence] = []
        for table in raw_tables:
            if not isinstance(table, dict) or table.get("evidence_type") != TABLE_EVIDENCE_TYPE:
                raise TableJudgmentDataError("Table labels must have evidence_type 'table'.")
            index = table.get("original_html_table_index")
            if isinstance(index, bool) or not isinstance(index, int) or index < 1:
                raise TableJudgmentDataError(
                    "original_html_table_index must be a positive integer."
                )
            tables.append(
                ExpectedTableEvidence(
                    _required_string(table.get("table_evidence_id"), "table_evidence_id"),
                    _required_string(table.get("document_id"), "document_id"),
                    _required_string(table.get("source_sha256"), "source_sha256"),
                    _required_string(table.get("source_locator"), "source_locator"),
                    index,
                    _required_string(table.get("parser_table_id"), "parser_table_id"),
                )
            )
        if len({table.table_evidence_id for table in tables}) != len(tables):
            raise TableJudgmentDataError("Table evidence IDs must be unique within a case.")
        cases.append(
            TableJudgmentCase(
                _required_string(raw_case.get("case_id"), "case_id"),
                status,
                _required_string(raw_case.get("question"), "question"),
                _filters(raw_case.get("filters")),
                tuple(tables),
            )
        )
    if len({case.case_id for case in cases}) != len(cases):
        raise TableJudgmentDataError("case_id values must be unique.")
    return dataset_id, version, tuple(cases)


def validate_table_judgment_references(
    dataset_path: Path, evidence_directory: Path, manifest_path: Path
) -> None:
    """Validate table provenance and metadata filters without executing retrieval."""

    _, _, cases = load_table_judgments(dataset_path)
    manifest = load_registration_manifest(manifest_path)
    documents = {document.document_id: document for document in manifest.documents}
    artifacts: dict[str, dict[str, object]] = {}
    for case in cases:
        for expected in case.expected_tables:
            document = documents.get(expected.document_id)
            if document is None:
                raise TableJudgmentDataError("Expected table document is not registered.")
            if document.source_sha256 != expected.source_sha256:
                raise TableJudgmentDataError("Expected table source hash is inconsistent.")
            if case.filters.ticker and case.filters.ticker.upper() != document.ticker:
                raise TableJudgmentDataError("Expected table ticker does not match case filters.")
            if case.filters.form_type and case.filters.form_type != document.form_type:
                raise TableJudgmentDataError(
                    "Expected table form type does not match case filters."
                )
            if case.filters.reporting_period_end and str(case.filters.reporting_period_end) != str(
                document.reporting_period_end
            ):
                raise TableJudgmentDataError(
                    "Expected table reporting period does not match case filters."
                )
            if expected.document_id not in artifacts:
                try:
                    artifacts[expected.document_id] = json.loads(
                        (evidence_directory / f"{expected.document_id}.json").read_text(
                            encoding="utf-8"
                        )
                    )
                except (OSError, json.JSONDecodeError) as exc:
                    raise TableJudgmentDataError("Expected table artifact is unavailable.") from exc
            artifact = artifacts[expected.document_id]
            matches = [
                table
                for table in artifact.get("table_evidence", [])
                if table.get("table_evidence_id") == expected.table_evidence_id
            ]
            if len(matches) != 1:
                raise TableJudgmentDataError(
                    "Expected table evidence does not resolve exactly once."
                )
            table = matches[0]
            if (
                table.get("evidence_type") != "financial_table"
                or artifact.get("document_id") != expected.document_id
                or table.get("document_id") != expected.document_id
                or table.get("source_sha256") != expected.source_sha256
                or table.get("source_locator") != expected.source_locator
                or table.get("original_html_table_index") != expected.original_html_table_index
                or table.get("parser_table_id") != expected.parser_table_id
            ):
                raise TableJudgmentDataError("Expected table provenance is inconsistent.")
            if not table.get("rows") or table.get("validation_status") != "ADMITTED":
                raise TableJudgmentDataError("Expected table is not admitted structured evidence.")
