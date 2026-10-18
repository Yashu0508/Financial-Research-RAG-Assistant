"""Deterministic, section-aware evidence preparation from approved SEC parser artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from app.ingestion.loaders.sec_manifest import (
    RegistrationManifest,
    check_registered_source,
    load_registration_manifest,
)
from app.ingestion.parsers.sec_html_parser import (
    PARSER_VERSION,
    ReviewedTableExpectation,
    load_reviewed_table_expectations,
)

CHUNKING_VERSION: Final = "1.0"
DEFAULT_PARSER_RELATIVE_DIR: Final = Path("data/processed/sec_parsed/v1")
DEFAULT_EVIDENCE_RELATIVE_DIR: Final = Path("data/processed/sec_evidence/v1")


@dataclass(frozen=True)
class ChunkingConfig:
    """Versioned parameters for deterministic narrative segmentation in Unicode characters."""

    version: str = CHUNKING_VERSION
    target_characters: int = 1_800
    maximum_characters: int = 2_400
    minimum_characters: int = 300
    overlap_characters: int = 0
    heading_boundary_policy: str = "never_cross_heading"
    long_block_policy: str = "split_at_whitespace_without_overlap"
    low_information_minimum_alphanumeric_characters: int = 3

    def digest(self) -> str:
        """Hash only the deterministic configuration that changes substantive evidence output."""

        return hashlib.sha256(_canonical_json(asdict(self)).encode("utf-8")).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _stable_id(*parts: object) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode("utf-8")).hexdigest()[:24]


def _nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _normalized_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()


def _section_key(block: dict[str, Any]) -> tuple[str | None, str | None]:
    context = block.get("heading_context")
    if not isinstance(context, dict):
        return None, None
    return context.get("locator"), context.get("text")


def _split_long_text(text: str, maximum: int) -> list[str]:
    """Split normalized parser text at whitespace, retaining every source character in order."""

    if len(text) <= maximum:
        return [text]
    pieces: list[str] = []
    remaining = text
    while len(remaining) > maximum:
        split_at = remaining.rfind(" ", 0, maximum + 1)
        if split_at <= 0:
            split_at = maximum
        pieces.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        pieces.append(remaining)
    return pieces


def _block_fragments(block: dict[str, Any], config: ChunkingConfig) -> list[dict[str, Any]]:
    text = str(block["text"])
    pieces = _split_long_text(text, config.maximum_characters)
    return [
        {
            "text": piece,
            "source_element_id": block["block_id"],
            "source_locator": block["source_locator"],
            "source_dom_tag": block["source_dom_tag"],
            "source_order": block["source_order"],
            "fragment_index": index,
            "fragment_count": len(pieces),
        }
        for index, piece in enumerate(pieces, start=1)
    ]


def _chunk_section(
    document_id: str,
    source_sha256: str,
    parser_version: str,
    parser_config_hash: str,
    section: tuple[str | None, str | None],
    blocks: list[dict[str, Any]],
    start_sequence: int,
    config: ChunkingConfig,
    inherited_warnings: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Create chunks within one heading section without cross-section merging or overlap."""

    admitted: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    sequence = start_sequence

    def flush() -> None:
        nonlocal pending, sequence
        if not pending:
            return
        text = "\n\n".join(fragment["text"] for fragment in pending)
        references = [
            {
                key: fragment[key]
                for key in (
                    "source_element_id",
                    "source_locator",
                    "source_dom_tag",
                    "source_order",
                    "fragment_index",
                    "fragment_count",
                )
            }
            for fragment in pending
        ]
        chunk_id = _stable_id(
            document_id,
            source_sha256,
            parser_version,
            parser_config_hash,
            config.digest(),
            "narrative",
            sequence,
            text,
        )
        admitted.append(
            {
                "evidence_type": "narrative_chunk",
                "validation_status": "ADMITTED",
                "chunk_id": chunk_id,
                "document_id": document_id,
                "source_sha256": source_sha256,
                "parser_version": parser_version,
                "parser_configuration_hash": parser_config_hash,
                "chunking_version": config.version,
                "chunking_configuration_hash": config.digest(),
                "chunk_sequence": sequence,
                "text": text,
                "character_count": len(text),
                "section_heading": {"locator": section[0], "text": section[1]},
                "source_elements": references,
                "inherited_source_warnings": inherited_warnings,
            }
        )
        pending = []
        sequence += 1

    for block in blocks:
        alphanumeric = len(re.findall(r"[\w]", str(block.get("text", "")), re.UNICODE))
        if alphanumeric < config.low_information_minimum_alphanumeric_characters:
            quarantined.append(
                {
                    "evidence_type": "quarantined_narrative",
                    "validation_status": "QUARANTINED",
                    "document_id": document_id,
                    "source_sha256": source_sha256,
                    "source_element_id": block.get("block_id"),
                    "source_locator": block.get("source_locator"),
                    "reason_code": "LOW_INFORMATION_BLOCK",
                    "diagnostic": (
                        "Narrative block did not meet the configured alphanumeric-content floor."
                    ),
                }
            )
            continue
        for fragment in _block_fragments(block, config):
            candidate_size = len(
                "\n\n".join([*(item["text"] for item in pending), fragment["text"]])
            )
            if pending and candidate_size > config.maximum_characters:
                flush()
            pending.append(fragment)
            if len("\n\n".join(item["text"] for item in pending)) >= config.target_characters:
                flush()
    flush()
    if len(admitted) >= 2 and admitted[-1]["character_count"] < config.minimum_characters:
        previous = admitted[-2]
        final = admitted[-1]
        merged_size = previous["character_count"] + 2 + final["character_count"]
        if merged_size <= config.maximum_characters:
            previous["text"] = f"{previous['text']}\n\n{final['text']}"
            previous["character_count"] = len(previous["text"])
            previous["source_elements"].extend(final["source_elements"])
            previous["chunk_id"] = _stable_id(
                document_id,
                source_sha256,
                parser_version,
                parser_config_hash,
                config.digest(),
                "narrative",
                previous["chunk_sequence"],
                previous["text"],
            )
            admitted.pop()
            sequence -= 1
    return admitted, quarantined, sequence


def _validate_table(table: dict[str, Any]) -> str | None:
    required = ("table_id", "source_locator", "original_html_table_index", "rows")
    if any(key not in table for key in required):
        return "MISSING_TABLE_PROVENANCE"
    if not isinstance(table["rows"], list) or not table["rows"]:
        return "MISSING_TABLE_ROWS"
    previous_row = 0
    for row in table["rows"]:
        if not isinstance(row, dict) or row.get("row_index", 0) <= previous_row:
            return "INVALID_ROW_ORDER"
        previous_row = row["row_index"]
        previous_cell = 0
        for cell in row.get("cells", []):
            if not isinstance(cell, dict) or cell.get("cell_index", 0) <= previous_cell:
                return "INVALID_CELL_ORDER"
            previous_cell = cell["cell_index"]
            if cell.get("cell_kind") not in {"header", "data"}:
                return "INVALID_CELL_KIND"
            if cell.get("rowspan", 0) < 1 or cell.get("colspan", 0) < 1:
                return "INVALID_CELL_SPAN"
            if not _nonempty_text(cell.get("source_locator")):
                return "MISSING_CELL_LOCATOR"
    return None


def _validate_reviewed_tables(
    tables: list[dict[str, Any]],
    expectations: tuple[ReviewedTableExpectation, ...],
) -> list[str]:
    by_index = {table["original_html_table_index"]: table for table in tables}
    failures: list[str] = []
    for expectation in expectations:
        table = by_index.get(expectation.table_index)
        if table is None:
            failures.append(f"QA_TABLE_MISSING:{expectation.category}:{expectation.table_index}")
            continue
        actual_rows = [
            row
            for row in table["rows"]
            if any(_nonempty_text(cell.get("text")) for cell in row["cells"])
        ][: len(expectation.preview_rows)]
        actual_text = {
            _normalized_text(cell.get("text", ""))
            for row in actual_rows
            for cell in row["cells"]
            if _nonempty_text(cell.get("text"))
        }
        expected_text = {
            _normalized_text(text)
            for row in expectation.preview_rows
            for text in row
            if _normalized_text(text)
        }
        if not expected_text.issubset(actual_text):
            failures.append(
                f"QA_TABLE_TEXT_MISMATCH:{expectation.category}:{expectation.table_index}"
            )
    return failures


def build_evidence_document(
    parser_artifact: dict[str, Any],
    config: ChunkingConfig = ChunkingConfig(),
    expectations: tuple[ReviewedTableExpectation, ...] = (),
) -> dict[str, Any]:
    """Transform one admitted parser artifact into distinct narrative and table evidence."""

    document_id = str(parser_artifact["document_id"])
    source_sha256 = str(parser_artifact["source_sha256"])
    parser_version = str(parser_artifact["parser_version"])
    parser_config_hash = str(parser_artifact["configuration_hash"])
    blocks = parser_artifact.get("narrative_blocks")
    tables = parser_artifact.get("tables")
    if not isinstance(blocks, list) or not isinstance(tables, list):
        return _document_quarantine(document_id, source_sha256, "MALFORMED_PARSER_ARTIFACT")
    block_ids = [block.get("block_id") for block in blocks]
    if len(block_ids) != len(set(block_ids)) or None in block_ids:
        return _document_quarantine(document_id, source_sha256, "DUPLICATE_OR_MISSING_BLOCK_ID")
    orders = [block.get("source_order") for block in blocks]
    if orders != sorted(orders) or len(orders) != len(set(orders)):
        return _document_quarantine(document_id, source_sha256, "INVALID_NARRATIVE_ORDER")
    inherited_warnings = list(parser_artifact.get("warnings", []))
    sections: list[tuple[tuple[str | None, str | None], list[dict[str, Any]]]] = []
    current_section: tuple[str | None, str | None] | None = None
    for block in blocks:
        if not _nonempty_text(block.get("text")):
            continue
        section = _section_key(block)
        if block.get("block_type") == "heading":
            section = (block.get("source_locator"), block.get("text"))
        if section != current_section:
            sections.append((section, []))
            current_section = section
        sections[-1][1].append(block)
    narrative_chunks: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    sequence = 0
    for section, section_blocks in sections:
        chunks, excluded, sequence = _chunk_section(
            document_id,
            source_sha256,
            parser_version,
            parser_config_hash,
            section,
            section_blocks,
            sequence,
            config,
            inherited_warnings,
        )
        narrative_chunks.extend(chunks)
        quarantined.extend(excluded)
    table_evidence: list[dict[str, Any]] = []
    table_ids: set[str] = set()
    for table in tables:
        reason = _validate_table(table)
        table_evidence_id = _stable_id(
            document_id,
            source_sha256,
            parser_version,
            parser_config_hash,
            config.digest(),
            "table",
            table.get("original_html_table_index"),
            table.get("table_id"),
        )
        if reason or table_evidence_id in table_ids:
            quarantined.append(
                {
                    "evidence_type": "quarantined_table_evidence",
                    "validation_status": "QUARANTINED",
                    "document_id": document_id,
                    "source_sha256": source_sha256,
                    "parser_table_id": table.get("table_id"),
                    "source_locator": table.get("source_locator"),
                    "reason_code": reason or "DUPLICATE_TABLE_EVIDENCE_ID",
                }
            )
            continue
        table_ids.add(table_evidence_id)
        table_evidence.append(
            {
                "evidence_type": "financial_table",
                "validation_status": "ADMITTED",
                "table_evidence_id": table_evidence_id,
                "document_id": document_id,
                "source_sha256": source_sha256,
                "parser_version": parser_version,
                "parser_configuration_hash": parser_config_hash,
                "chunking_version": config.version,
                "chunking_configuration_hash": config.digest(),
                "parser_table_id": table["table_id"],
                "original_html_table_index": table["original_html_table_index"],
                "source_locator": table["source_locator"],
                "caption": table.get("caption"),
                "preceding_heading": table.get("preceding_heading"),
                "unit_hints": table.get("unit_hints", []),
                "period_header_text": table.get("period_header_text", []),
                "header_association_status": "NOT_ESTABLISHED",
                "table_warnings": table.get("warnings", []),
                "inherited_source_warnings": inherited_warnings,
                "rows": table["rows"],
            }
        )
    qa_failures = _validate_reviewed_tables(table_evidence, expectations)
    if qa_failures:
        return _document_quarantine(
            document_id, source_sha256, "QA_REGRESSION_FAILURE", qa_failures
        )
    if not narrative_chunks and not table_evidence:
        return _document_quarantine(
            document_id,
            source_sha256,
            "NO_ADMITTED_EVIDENCE",
            quarantined_records=quarantined,
        )
    return {
        "record_type": "evidence_document",
        "admission_status": "ADMITTED_WITH_QUARANTINED_RECORDS" if quarantined else "ADMITTED",
        "document_id": document_id,
        "source_sha256": source_sha256,
        "parser_version": parser_version,
        "parser_configuration_hash": parser_config_hash,
        "chunking_version": config.version,
        "chunking_configuration_hash": config.digest(),
        "narrative_chunks": narrative_chunks,
        "table_evidence": table_evidence,
        "quarantined_evidence": quarantined,
        "warnings": inherited_warnings,
    }


def _document_quarantine(
    document_id: str,
    source_sha256: str,
    reason_code: str,
    details: list[str] | None = None,
    quarantined_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "record_type": "evidence_document_quarantine",
        "admission_status": "QUARANTINED",
        "document_id": document_id,
        "source_sha256": source_sha256,
        "reason_code": reason_code,
        "diagnostics": details or [],
        "quarantined_evidence": quarantined_records or [],
    }


def ensure_evidence_output_path(project_root: Path, candidate: Path) -> Path:
    """Reject output locations outside the repository's processed-data root."""

    processed_root = (project_root.resolve() / "data" / "processed").resolve()
    resolved = candidate.resolve()
    if resolved != processed_root and processed_root not in resolved.parents:
        raise ValueError(f"Evidence output must remain under {processed_root}")
    return resolved


def ensure_parser_artifact_path(project_root: Path, candidate: Path) -> Path:
    """Accept only parser-artifact directories under project-local processed data."""

    processed_root = (project_root.resolve() / "data" / "processed").resolve()
    resolved = candidate.resolve()
    if resolved != processed_root and processed_root not in resolved.parents:
        raise ValueError(f"Parser artifact input must remain under {processed_root}")
    return resolved


def _write_if_changed(path: Path, content: str) -> str:
    digest = _digest(content)
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return digest
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    os.replace(temporary, path)
    return digest


def _load_parser_artifact(
    parser_dir: Path,
    document_id: str,
    expected_hash: str,
) -> tuple[dict[str, Any] | None, str | None]:
    path = parser_dir / f"{document_id}.json"
    try:
        content = path.read_text(encoding="utf-8")
        artifact = json.loads(content)
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"PARSER_ARTIFACT_UNREADABLE:{type(exc).__name__}"
    if _digest(content) != expected_hash:
        return None, "PARSER_ARTIFACT_HASH_MISMATCH"
    return artifact, None


def run_evidence_preparation(
    project_root: Path,
    manifest_path: Path,
    parser_dir: Path | None = None,
    output_dir: Path | None = None,
    config: ChunkingConfig = ChunkingConfig(),
) -> tuple[list[dict[str, Any]], dict[str, Any], Path]:
    """Admit compatible parser artifacts and write deterministic evidence artifacts safely."""

    root = project_root.resolve()
    manifest: RegistrationManifest = load_registration_manifest(manifest_path)
    input_dir = ensure_parser_artifact_path(root, parser_dir or root / DEFAULT_PARSER_RELATIVE_DIR)
    destination = ensure_evidence_output_path(
        root, output_dir or root / DEFAULT_EVIDENCE_RELATIVE_DIR
    )
    destination.mkdir(parents=True, exist_ok=True)
    try:
        parser_metadata = json.loads((input_dir / "run_metadata.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Parser run metadata is unreadable: {type(exc).__name__}") from exc
    if parser_metadata.get("parser_version") != PARSER_VERSION:
        raise ValueError("Parser artifact version is incompatible with the evidence chunker.")
    parser_hashes = parser_metadata.get("artifact_sha256")
    if not isinstance(parser_hashes, dict):
        raise ValueError("Parser run metadata lacks an artifact hash inventory.")
    expectations = load_reviewed_table_expectations(root)
    artifacts: list[dict[str, Any]] = []
    output_hashes: dict[str, str] = {}
    for document in manifest.documents:
        source_check = check_registered_source(root, document)
        if not source_check.is_valid:
            evidence = _document_quarantine(
                document.document_id,
                document.source_sha256,
                f"SOURCE_{source_check.status}",
                list(source_check.diagnostics),
            )
        else:
            expected_hash = parser_hashes.get(document.document_id)
            artifact, failure = _load_parser_artifact(
                input_dir, document.document_id, str(expected_hash)
            )
            if failure or artifact is None:
                evidence = _document_quarantine(
                    document.document_id,
                    document.source_sha256,
                    failure or "PARSER_ARTIFACT_MISSING",
                )
            elif (
                artifact.get("record_type") != "parsed_document"
                or artifact.get("parse_status") != "PARSED"
                or artifact.get("document_id") != document.document_id
                or artifact.get("source_sha256") != document.source_sha256
                or artifact.get("parser_version") != parser_metadata.get("parser_version")
                or artifact.get("configuration_hash") != parser_metadata.get("configuration_hash")
            ):
                evidence = _document_quarantine(
                    document.document_id, document.source_sha256, "INCOMPATIBLE_PARSER_ARTIFACT"
                )
            else:
                evidence = build_evidence_document(
                    artifact, config, expectations.get(document.document_id, ())
                )
        artifacts.append(evidence)
        content = _canonical_json(evidence) + "\n"
        output_hashes[document.document_id] = _write_if_changed(
            destination / f"{document.document_id}.json", content
        )
    admission_counts: dict[str, int] = {}
    for evidence in artifacts:
        status = evidence["admission_status"]
        admission_counts[status] = admission_counts.get(status, 0) + 1
    metadata = {
        "record_type": "evidence_run_metadata",
        "chunking_version": config.version,
        "configuration": asdict(config),
        "configuration_hash": config.digest(),
        "manifest_id": manifest.manifest_id,
        "manifest_schema_version": manifest.schema_version,
        "parser_version": parser_metadata["parser_version"],
        "parser_configuration_hash": parser_metadata["configuration_hash"],
        "admission_status_counts": dict(sorted(admission_counts.items())),
        "artifact_sha256": dict(sorted(output_hashes.items())),
        "operational_timestamp_utc": datetime.now(UTC).isoformat(),
        "note": "Evidence hashes cover deterministic document JSON only; timestamp is operational.",
    }
    _write_if_changed(destination / "run_metadata.json", _canonical_json(metadata) + "\n")
    return artifacts, metadata, destination
