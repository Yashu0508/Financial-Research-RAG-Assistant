"""Tests for deterministic, section-aware SEC evidence preparation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.ingestion.chunking.sec_evidence_chunker import (
    ChunkingConfig,
    build_evidence_document,
    ensure_evidence_output_path,
    ensure_parser_artifact_path,
    run_evidence_preparation,
)
from app.ingestion.parsers.sec_html_parser import ReviewedTableExpectation


def _block(index: int, text: str, kind: str = "paragraph", heading: str | None = "Revenue") -> dict:
    locator = f"element:{index}:{'h2' if kind == 'heading' else 'p'}"
    return {
        "block_id": f"block-{index}",
        "block_type": kind,
        "source_locator": locator,
        "source_dom_tag": "h2" if kind == "heading" else "p",
        "source_order": index,
        "text": text,
        "heading_context": {"locator": "element:1:h2" if heading else None, "text": heading},
    }


def _table(index: int = 3) -> dict:
    return {
        "table_id": f"parser-table-{index}",
        "source_locator": f"table:{index}",
        "original_html_table_index": index,
        "caption": "In millions",
        "preceding_heading": {"text": "Statements", "source_html_id": None},
        "unit_hints": ["In millions"],
        "period_header_text": ["2024", "2023"],
        "warnings": [],
        "rows": [
            {
                "row_id": "row-1",
                "row_index": 1,
                "source_locator": f"table:{index}/row:1",
                "structural_column_span": 2,
                "cells": [
                    {
                        "cell_id": "cell-1",
                        "cell_index": 1,
                        "cell_kind": "header",
                        "text": "Year ended 2024",
                        "colspan": 2,
                        "rowspan": 1,
                        "source_locator": f"table:{index}/row:1/cell:1",
                    }
                ],
            },
            {
                "row_id": "row-2",
                "row_index": 2,
                "source_locator": f"table:{index}/row:2",
                "structural_column_span": 2,
                "cells": [
                    {
                        "cell_id": "cell-2",
                        "cell_index": 1,
                        "cell_kind": "data",
                        "text": "Net income",
                        "colspan": 1,
                        "rowspan": 1,
                        "source_locator": f"table:{index}/row:2/cell:1",
                    },
                    {
                        "cell_id": "cell-3",
                        "cell_index": 2,
                        "cell_kind": "data",
                        "text": "(1,234)",
                        "colspan": 1,
                        "rowspan": 1,
                        "source_locator": f"table:{index}/row:2/cell:2",
                    },
                ],
            },
        ],
    }


def _artifact(blocks: list[dict] | None = None, tables: list[dict] | None = None) -> dict:
    return {
        "record_type": "parsed_document",
        "parse_status": "PARSED",
        "document_id": "example-2024-10k",
        "source_sha256": "a" * 64,
        "parser_version": "1.0",
        "configuration_hash": "b" * 64,
        "narrative_blocks": blocks or [_block(1, "Revenue")],
        "tables": tables or [_table()],
        "warnings": [],
    }


def test_sections_lists_and_provenance_remain_separate() -> None:
    blocks = [
        _block(1, "Revenue", "heading", None),
        _block(2, "First paragraph."),
        _block(3, "First list item.", "list_item"),
        _block(4, "Risk Factors", "heading", "Revenue"),
        _block(5, "Second section paragraph.", "paragraph", "Risk Factors"),
    ]
    blocks[4]["heading_context"]["locator"] = "element:4:h2"
    artifact = _artifact(blocks)
    config = ChunkingConfig(target_characters=1_000, maximum_characters=1_200, minimum_characters=1)

    evidence = build_evidence_document(artifact, config)

    assert evidence["admission_status"] == "ADMITTED"
    assert len(evidence["narrative_chunks"]) == 2
    assert "First list item." in evidence["narrative_chunks"][0]["text"]
    assert evidence["narrative_chunks"][1]["section_heading"]["text"] == "Risk Factors"
    assert evidence["narrative_chunks"][0]["source_elements"][0]["source_element_id"] == "block-1"
    assert evidence["table_evidence"][0]["evidence_type"] == "financial_table"
    assert "rows" not in evidence["narrative_chunks"][0]


def test_long_blocks_split_deterministically_with_provenance() -> None:
    text = "word " * 30
    artifact = _artifact([_block(1, text)])
    config = ChunkingConfig(target_characters=30, maximum_characters=40, minimum_characters=1)

    first = build_evidence_document(artifact, config)
    second = build_evidence_document(artifact, config)

    chunks = first["narrative_chunks"]
    assert first == second
    assert len(chunks) > 1
    assert all(chunk["character_count"] <= 40 for chunk in chunks)
    assert chunks[0]["source_elements"][0]["fragment_count"] > 1


def test_ids_change_when_content_or_configuration_changes() -> None:
    base = _artifact([_block(1, "content one")])
    changed = _artifact([_block(1, "content two")])

    base_id = build_evidence_document(base)["narrative_chunks"][0]["chunk_id"]
    changed_id = build_evidence_document(changed)["narrative_chunks"][0]["chunk_id"]
    config_id = build_evidence_document(base, ChunkingConfig(target_characters=900))[
        "narrative_chunks"
    ][0]["chunk_id"]

    assert base_id != changed_id
    assert base_id != config_id


def test_low_information_and_invalid_table_are_quarantined() -> None:
    invalid_table = _table()
    invalid_table["rows"][1]["cells"][1]["rowspan"] = 0
    evidence = build_evidence_document(_artifact([_block(1, "--")], [invalid_table]))

    assert evidence["admission_status"] == "QUARANTINED"
    assert evidence["reason_code"] == "NO_ADMITTED_EVIDENCE"
    assert {item["reason_code"] for item in evidence["quarantined_evidence"]} == {
        "LOW_INFORMATION_BLOCK",
        "INVALID_CELL_SPAN",
    }


def test_table_preserves_raw_numeric_text_spans_and_no_header_inference() -> None:
    evidence = build_evidence_document(_artifact())
    table = evidence["table_evidence"][0]

    assert table["header_association_status"] == "NOT_ESTABLISHED"
    assert table["rows"][0]["cells"][0]["cell_kind"] == "header"
    assert table["rows"][0]["cells"][0]["colspan"] == 2
    assert table["rows"][1]["cells"][1]["text"] == "(1,234)"
    assert table["rows"][1]["cells"][1]["source_locator"] == "table:3/row:2/cell:2"


def test_qa_mismatch_quarantines_the_entire_document() -> None:
    expectation = ReviewedTableExpectation("income_statement", 3, (("missing",),))

    evidence = build_evidence_document(_artifact(), expectations=(expectation,))

    assert evidence["admission_status"] == "QUARANTINED"
    assert evidence["reason_code"] == "QA_REGRESSION_FAILURE"


def test_rejects_unsafe_output_path(tmp_path: Path) -> None:
    assert (
        ensure_evidence_output_path(tmp_path, tmp_path / "data/processed/sec_evidence/v1").name
        == "v1"
    )
    assert (
        ensure_parser_artifact_path(tmp_path, tmp_path / "data/processed/sec_parsed/v1").name
        == "v1"
    )
    with pytest.raises(ValueError, match="processed"):
        ensure_evidence_output_path(tmp_path, tmp_path / "not-processed")
    with pytest.raises(ValueError, match="processed"):
        ensure_parser_artifact_path(tmp_path, tmp_path / "not-processed")


def test_source_hash_mismatch_quarantines_before_artifact_admission(tmp_path: Path) -> None:
    root = tmp_path
    source = root / "data/raw/sec_filings/Example/sample.html"
    source.parent.mkdir(parents=True)
    source.write_text("original", encoding="utf-8")
    expected_hash = hashlib.sha256(b"original").hexdigest()
    manifest = {
        "schema_version": "1.0",
        "manifest_id": "test",
        "documents": [
            {
                "document_id": "example-2024-10k",
                "company": "Example",
                "ticker": "EXMP",
                "form_type": "10-K",
                "filing_date": None,
                "reporting_period_end": "2024-12-31",
                "fiscal_year": None,
                "fiscal_quarter": None,
                "official_sec_source_url": None,
                "local_source_path": "data/raw/sec_filings/Example/sample.html",
                "source_sha256": expected_hash,
                "source_byte_size": 8,
                "registration": {
                    "registered_at": None,
                    "acquisition_timestamp": None,
                    "notes": "test",
                },
                "processing_status": "registered",
                "validation_warnings": [],
            }
        ],
    }
    manifest_path = root / "data/manifests/manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    parser_dir = root / "data/processed/sec_parsed/v1"
    parser_dir.mkdir(parents=True)
    parser_artifact = _artifact()
    parser_content = json.dumps(parser_artifact, sort_keys=True, separators=(",", ":")) + "\n"
    (parser_dir / "example-2024-10k.json").write_text(parser_content, encoding="utf-8")
    (parser_dir / "run_metadata.json").write_text(
        json.dumps(
            {
                "parser_version": "1.0",
                "configuration_hash": "b" * 64,
                "artifact_sha256": {
                    "example-2024-10k": hashlib.sha256(parser_content.encode()).hexdigest()
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    qa_dir = root / "data/processed/document_verification/table_qa"
    qa_dir.mkdir(parents=True)
    qa_checks = [
        {
            "document_id": f"example-{index}",
            "source_table_status": "FOUND",
            "table_index": category + 1,
            "category": f"category-{category}",
            "original_rows_preview": [[{"text": "Year ended 2024"}]],
        }
        for index in range(10)
        for category in range(3)
    ]
    (qa_dir / "table_qa_summary.json").write_text(
        json.dumps({"checks": qa_checks}), encoding="utf-8"
    )
    (qa_dir / "table_qa_checklist.md").write_text(
        "Human review status: `PASS`\n" * 30, encoding="utf-8"
    )
    source.write_text("changed", encoding="utf-8")

    artifacts, _, _ = run_evidence_preparation(root, manifest_path, parser_dir)

    assert artifacts[0]["admission_status"] == "QUARANTINED"
    assert artifacts[0]["reason_code"] == "SOURCE_CHANGED"
