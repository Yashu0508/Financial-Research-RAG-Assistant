"""Deterministic, structure-preserving parsing for registered local SEC HTML files."""

from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from bs4 import BeautifulSoup, Tag

from app.ingestion.loaders.sec_manifest import (
    RegisteredDocument,
    check_registered_source,
    load_registration_manifest,
)

PARSER_VERSION: Final = "1.0"
DEFAULT_OUTPUT_RELATIVE_DIR: Final = Path("data/processed/sec_parsed/v1")
QA_SUMMARY_RELATIVE_PATH: Final = Path(
    "data/processed/document_verification/table_qa/table_qa_summary.json"
)
QA_CHECKLIST_RELATIVE_PATH: Final = Path(
    "data/processed/document_verification/table_qa/table_qa_checklist.md"
)


@dataclass(frozen=True)
class ParserConfig:
    """Explicit versioned rules that shape substantive parser output."""

    version: str = PARSER_VERSION
    visible_text_minimum_characters: int = 200
    narrative_tags: tuple[str, ...] = ("h1", "h2", "h3", "h4", "h5", "h6", "p", "li")

    def digest(self) -> str:
        """Return the stable hash of parser behavior that affects artifact content."""

        return hashlib.sha256(_canonical_json(asdict(self)).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ReviewedTableExpectation:
    """A reviewed QA candidate used only to regression-check structural preservation."""

    category: str
    table_index: int
    preview_rows: tuple[tuple[str, ...], ...]


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).replace("\xa0", " ")).strip()


def _stable_id(*parts: object) -> str:
    source = "|".join(str(part) for part in parts)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:24]


def _is_hidden(tag: Tag) -> bool:
    style = str(tag.get("style", "")).lower().replace(" ", "")
    return (
        (tag.name or "").lower() in {"script", "style", "noscript", "template", "head", "ix:hidden"}
        or tag.has_attr("hidden")
        or str(tag.get("aria-hidden", "")).lower() == "true"
        or "display:none" in style
        or "visibility:hidden" in style
    )


def _visible_soup(raw: bytes) -> BeautifulSoup:
    """Parse permissively and remove demonstrably non-visible content only."""

    soup = BeautifulSoup(raw, "lxml")
    for tag in list(soup.find_all(True)):
        if tag.parent is not None and _is_hidden(tag):
            tag.decompose()
    return soup


def _has_ancestor(tag: Tag, name: str) -> bool:
    return any(
        (parent.name or "").lower() == name for parent in tag.parents if isinstance(parent, Tag)
    )


def _nearest_table(tag: Tag) -> Tag | None:
    return tag.find_parent("table")


def _unit_hints(value: str) -> list[str]:
    return re.findall(r"\b(?:in|\$ in)\s+(?:thousands|millions|billions)\b", value, re.IGNORECASE)


def _period_hints(rows: list[dict[str, Any]]) -> list[str]:
    hints: list[str] = []
    pattern = re.compile(
        r"\b(?:19|20)\d{2}\b|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", re.I
    )
    for row in rows[:6]:
        for cell in row["cells"]:
            if pattern.search(cell["text"]):
                hints.append(cell["text"])
    return hints


def _preceding_heading(tag: Tag) -> tuple[str | None, str | None]:
    heading = tag.find_previous(["h1", "h2", "h3", "h4", "h5", "h6"])
    if heading is None:
        return None, None
    text = _normalize(heading.get_text(" ", strip=True))
    if not text:
        return None, None
    return text, str(heading.get("id")) if heading.has_attr("id") else None


def _parse_narrative(
    soup: BeautifulSoup,
    document: RegisteredDocument,
    config: ParserConfig,
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    current_heading: dict[str, str | None] = {"text": None, "locator": None}
    element_index = 0
    structural_tags = (*config.narrative_tags, "div")
    for tag in soup.find_all(structural_tags):
        if _has_ancestor(tag, "table"):
            continue
        text = _normalize(tag.get_text(" ", strip=True))
        if not text:
            continue
        element_index += 1
        tag_name = (tag.name or "").lower()
        if tag_name == "div" and tag.find([*config.narrative_tags, "table", "div"]) is not None:
            element_index -= 1
            continue
        locator = f"element:{element_index}:{tag_name}"
        block_type = (
            "heading"
            if tag_name.startswith("h")
            else "list_item"
            if tag_name == "li"
            else "paragraph"
        )
        block = {
            "block_id": _stable_id(
                document.document_id, document.source_sha256, "narrative", element_index
            ),
            "document_id": document.document_id,
            "source_sha256": document.source_sha256,
            "parser_version": config.version,
            "configuration_hash": config.digest(),
            "block_type": block_type,
            "source_dom_tag": tag_name,
            "source_locator": locator,
            "source_html_id": str(tag.get("id")) if tag.has_attr("id") else None,
            "source_order": element_index,
            "text": text,
            "heading_context": current_heading.copy(),
        }
        blocks.append(block)
        if block_type == "heading":
            current_heading = {"text": text, "locator": locator}
    return blocks


def _parse_table(
    table: Tag,
    table_index: int,
    document: RegisteredDocument,
    config: ParserConfig,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Preserve actual cells/spans; quarantine only structurally unusable tables."""

    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    table_text = _normalize(table.get_text(" ", strip=True))
    for row_index, row in enumerate(table.find_all("tr"), start=1):
        if _nearest_table(row) is not table:
            continue
        cells: list[dict[str, Any]] = []
        for cell_index, cell in enumerate(row.find_all(["th", "td"], recursive=False), start=1):
            try:
                colspan = int(cell.get("colspan", 1))
                rowspan = int(cell.get("rowspan", 1))
            except (TypeError, ValueError):
                return None, _quarantine_table(
                    table_index,
                    document,
                    config,
                    "INVALID_SPAN",
                    "Cell has a non-integer span attribute.",
                )
            if colspan < 1 or rowspan < 1:
                return None, _quarantine_table(
                    table_index, document, config, "INVALID_SPAN", "Cell span must be positive."
                )
            text = cell.get_text(" ", strip=True)
            cells.append(
                {
                    "cell_id": _stable_id(
                        document.document_id,
                        document.source_sha256,
                        "table",
                        table_index,
                        row_index,
                        cell_index,
                    ),
                    "source_locator": f"table:{table_index}/row:{row_index}/cell:{cell_index}",
                    "row_index": row_index,
                    "cell_index": cell_index,
                    "source_dom_tag": (cell.name or "").lower(),
                    "cell_kind": "header" if (cell.name or "").lower() == "th" else "data",
                    "text": text,
                    "colspan": colspan,
                    "rowspan": rowspan,
                    "unit_hints": _unit_hints(text),
                }
            )
        if not cells:
            warnings.append(f"Row {row_index} has no direct table cells.")
        rows.append(
            {
                "row_id": _stable_id(
                    document.document_id,
                    document.source_sha256,
                    "table",
                    table_index,
                    "row",
                    row_index,
                ),
                "source_locator": f"table:{table_index}/row:{row_index}",
                "row_index": row_index,
                "cells": cells,
                "structural_column_span": sum(cell["colspan"] for cell in cells),
            }
        )
    if not rows or not any(row["cells"] for row in rows):
        return None, _quarantine_table(
            table_index,
            document,
            config,
            "NO_CELLS",
            "Table has no usable direct row/cell structure.",
        )
    widths = {row["structural_column_span"] for row in rows if row["cells"]}
    if len(widths) > 1:
        warnings.append("Rows have inconsistent structural column spans; preserved for review.")
    if table.find("table") is not None:
        warnings.append(
            "Nested table markup is present; nested tables have independent table indices."
        )
    heading, heading_html_id = _preceding_heading(table)
    caption_tag = table.find("caption")
    caption = _normalize(caption_tag.get_text(" ", strip=True)) if caption_tag else None
    record = {
        "table_id": _stable_id(document.document_id, document.source_sha256, "table", table_index),
        "document_id": document.document_id,
        "source_sha256": document.source_sha256,
        "parser_version": config.version,
        "configuration_hash": config.digest(),
        "parse_status": "PARSED_WITH_WARNINGS" if warnings else "PARSED",
        "original_html_table_index": table_index,
        "source_locator": f"table:{table_index}",
        "source_html_id": str(table.get("id")) if table.has_attr("id") else None,
        "caption": caption,
        "preceding_heading": {"text": heading, "source_html_id": heading_html_id},
        "unit_hints": _unit_hints(" ".join(filter(None, [caption, heading, table_text[:1000]]))),
        "period_header_text": _period_hints(rows),
        "rows": rows,
        "warnings": warnings,
    }
    return record, None


def _quarantine_table(
    table_index: int,
    document: RegisteredDocument,
    config: ParserConfig,
    reason_code: str,
    detail: str,
) -> dict[str, Any]:
    return {
        "record_type": "quarantined_table",
        "table_id": _stable_id(document.document_id, document.source_sha256, "table", table_index),
        "document_id": document.document_id,
        "source_sha256": document.source_sha256,
        "parser_version": config.version,
        "configuration_hash": config.digest(),
        "parse_status": "QUARANTINED",
        "original_html_table_index": table_index,
        "source_locator": f"table:{table_index}",
        "reason_code": reason_code,
        "diagnostic": detail,
    }


def load_reviewed_table_expectations(
    project_root: Path,
) -> dict[str, tuple[ReviewedTableExpectation, ...]]:
    """Load the 30 reviewed QA candidates as structural regression expectations."""

    summary_path = project_root / QA_SUMMARY_RELATIVE_PATH
    checklist_path = project_root / QA_CHECKLIST_RELATIVE_PATH
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    checklist = checklist_path.read_text(encoding="utf-8")
    checks = payload.get("checks")
    if not isinstance(checks, list) or len(checks) != 30:
        raise ValueError("Reviewed QA summary must contain exactly 30 candidate checks.")
    if checklist.count("Human review status: `PASS`") != 30:
        raise ValueError("Reviewed QA checklist must contain 30 PASS entries.")
    result: dict[str, list[ReviewedTableExpectation]] = {}
    for check in checks:
        if check.get("source_table_status") != "FOUND" or not isinstance(
            check.get("table_index"), int
        ):
            raise ValueError("Reviewed QA candidates must have a selected source table index.")
        preview_rows = tuple(
            tuple(_normalize(str(cell.get("text", ""))) for cell in row)
            for row in check.get("original_rows_preview", [])
        )
        result.setdefault(str(check["document_id"]), []).append(
            ReviewedTableExpectation(str(check["category"]), check["table_index"], preview_rows)
        )
    if set(result) == set() or any(len(items) != 3 for items in result.values()):
        raise ValueError("Reviewed QA candidates must map three statement tables per document.")
    return {document_id: tuple(items) for document_id, items in result.items()}


def _validate_reviewed_tables(
    tables: list[dict[str, Any]],
    expectations: tuple[ReviewedTableExpectation, ...],
) -> list[str]:
    by_index = {table["original_html_table_index"]: table for table in tables}
    warnings: list[str] = []
    for expectation in expectations:
        table = by_index.get(expectation.table_index)
        if table is None:
            warnings.append(
                f"Reviewed {expectation.category} table index {expectation.table_index} is missing."
            )
            continue
        actual_rows = [
            row for row in table["rows"] if any(_normalize(cell["text"]) for cell in row["cells"])
        ][: len(expectation.preview_rows)]
        expected_text = [cell for row in expectation.preview_rows for cell in row if cell]
        actual_text = [
            _normalize(cell["text"])
            for row in actual_rows
            for cell in row["cells"]
            if _normalize(cell["text"])
        ]
        for text in expected_text:
            if text not in actual_text:
                warnings.append(
                    f"Reviewed {expectation.category} table index {expectation.table_index} "
                    f"does not preserve preview cell text {text!r}."
                )
                break
    return warnings


def parse_registered_document(
    project_root: Path,
    document: RegisteredDocument,
    expectations: tuple[ReviewedTableExpectation, ...] = (),
    config: ParserConfig = ParserConfig(),
) -> dict[str, Any]:
    """Parse one registered, currently valid source into separate structured evidence types."""

    check = check_registered_source(project_root, document)
    if not check.is_valid:
        return {
            "record_type": "source_validation_failure",
            "document_id": document.document_id,
            "source_sha256": document.source_sha256,
            "parse_status": check.status,
            "diagnostics": list(check.diagnostics),
        }
    source = project_root / document.local_source_path
    try:
        raw = source.read_bytes()
        soup = _visible_soup(raw)
    except Exception as exc:  # malformed source cannot leave trusted output
        return {
            "record_type": "document_quarantine",
            "document_id": document.document_id,
            "source_sha256": document.source_sha256,
            "parse_status": "QUARANTINED",
            "reason_code": "PARSER_EXCEPTION",
            "diagnostic": f"{type(exc).__name__}: {exc}",
        }
    narrative = _parse_narrative(soup, document, config)
    tables: list[dict[str, Any]] = []
    quarantined_tables: list[dict[str, Any]] = []
    for table_index, table in enumerate(soup.find_all("table"), start=1):
        record, quarantine = _parse_table(table, table_index, document, config)
        if record is not None:
            tables.append(record)
        if quarantine is not None:
            quarantined_tables.append(quarantine)
    visible_characters = sum(len(block["text"]) for block in narrative)
    warnings: list[str] = []
    if b"</html" not in raw[-20_000:].lower():
        warnings.append("Closing HTML marker was not found near the end; parser recovery was used.")
    if visible_characters < config.visible_text_minimum_characters:
        warnings.append(
            f"Visible narrative has {visible_characters} characters; "
            f"configured minimum is {config.visible_text_minimum_characters}."
        )
    warnings.extend(_validate_reviewed_tables(tables, expectations))
    if not narrative and not tables:
        return {
            "record_type": "document_quarantine",
            "document_id": document.document_id,
            "source_sha256": document.source_sha256,
            "parse_status": "QUARANTINED",
            "reason_code": "NO_VISIBLE_EVIDENCE",
            "diagnostic": "No visible narrative blocks or usable tables were parsed.",
            "quarantined_tables": quarantined_tables,
        }
    status = "PARSED_WITH_WARNINGS" if warnings or quarantined_tables else "PARSED"
    return {
        "record_type": "parsed_document",
        "document_id": document.document_id,
        "source_sha256": document.source_sha256,
        "parser_version": config.version,
        "configuration_hash": config.digest(),
        "parse_status": status,
        "source": {
            "local_source_path": document.local_source_path,
            "byte_size": document.source_byte_size,
            "source_validation_status": check.status,
        },
        "locator_semantics": {
            "narrative": (
                "element:<visible narrative ordinal>:<DOM tag>; ordinal is parser order, "
                "not a raw-byte offset."
            ),
            "table": (
                "table:<one-based visible DOM table order>/row:<one-based row>/"
                "cell:<one-based direct cell>."
            ),
        },
        "narrative_blocks": narrative,
        "tables": tables,
        "quarantined_tables": quarantined_tables,
        "warnings": warnings,
    }


def ensure_parser_output_path(project_root: Path, candidate: Path) -> Path:
    """Restrict parser output to a project-local processed-data subtree."""

    processed_root = (project_root.resolve() / "data" / "processed").resolve()
    resolved = candidate.resolve()
    if resolved != processed_root and processed_root not in resolved.parents:
        raise ValueError(f"Parser output must remain under {processed_root}")
    return resolved


def _write_if_changed(path: Path, content: str) -> str:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return digest
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    os.replace(temporary, path)
    return digest


def run_parser(
    project_root: Path,
    manifest_path: Path,
    output_dir: Path | None = None,
    config: ParserConfig = ParserConfig(),
) -> tuple[list[dict[str, Any]], dict[str, Any], Path]:
    """Validate sources, parse valid ones, and atomically write deterministic artifacts."""

    root = project_root.resolve()
    manifest = load_registration_manifest(manifest_path)
    destination = ensure_parser_output_path(root, output_dir or root / DEFAULT_OUTPUT_RELATIVE_DIR)
    destination.mkdir(parents=True, exist_ok=True)
    expectations = load_reviewed_table_expectations(root)
    artifacts: list[dict[str, Any]] = []
    hashes: dict[str, str] = {}
    for document in manifest.documents:
        artifact = parse_registered_document(
            root, document, expectations.get(document.document_id, ()), config
        )
        artifacts.append(artifact)
        content = _canonical_json(artifact) + "\n"
        hashes[document.document_id] = _write_if_changed(
            destination / f"{document.document_id}.json", content
        )
    status_counts: dict[str, int] = {}
    for artifact in artifacts:
        status = artifact["parse_status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    metadata = {
        "record_type": "parser_run_metadata",
        "parser_version": config.version,
        "configuration": asdict(config),
        "configuration_hash": config.digest(),
        "manifest_id": manifest.manifest_id,
        "manifest_schema_version": manifest.schema_version,
        "document_status_counts": dict(sorted(status_counts.items())),
        "artifact_sha256": dict(sorted(hashes.items())),
        "operational_timestamp_utc": datetime.now(UTC).isoformat(),
        "note": (
            "Artifact hashes cover deterministic document JSON only; "
            "operational timestamp is excluded."
        ),
    }
    _write_if_changed(destination / "run_metadata.json", _canonical_json(metadata) + "\n")
    return artifacts, metadata, destination
