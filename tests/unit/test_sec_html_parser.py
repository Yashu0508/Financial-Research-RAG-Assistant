"""Focused tests for structure-preserving registered SEC HTML parsing."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.ingestion.loaders.sec_manifest import RegisteredDocument, RegistrationMetadata
from app.ingestion.parsers.sec_html_parser import (
    ParserConfig,
    ensure_parser_output_path,
    load_reviewed_table_expectations,
    parse_registered_document,
)


def _document(
    content: bytes = b"<html><body><p>default content " * 20 + b"</p></body></html>",
) -> RegisteredDocument:
    return RegisteredDocument(
        document_id="example-2024-10k",
        company="Example",
        ticker="EXMP",
        form_type="10-K",
        filing_date=None,
        reporting_period_end="2024-12-31",
        fiscal_year=None,
        fiscal_quarter=None,
        official_sec_source_url=None,
        local_source_path="data/raw/sec_filings/Example/sample.html",
        source_sha256=hashlib.sha256(content).hexdigest(),
        source_byte_size=len(content),
        registration=RegistrationMetadata("2026-10-17T00:00:00Z", None, "test registration"),
        processing_status="registered",
        validation_warnings=(),
    )


def _write_source(tmp_path: Path, content: bytes) -> RegisteredDocument:
    document = _document(content)
    source = tmp_path / document.local_source_path
    source.parent.mkdir(parents=True)
    source.write_bytes(content)
    return document


def test_preserves_visible_order_and_excludes_hidden_script_and_style(tmp_path: Path) -> None:
    content = b"""<html><body><h1>First heading</h1><p>First paragraph</p>
    <p hidden>Hidden paragraph</p><script>secret()</script><style>.x{}</style>
    <ul><li>First item</li></ul><h2>Second heading</h2><p>Second paragraph</p></body></html>"""
    artifact = parse_registered_document(
        tmp_path, _write_source(tmp_path, content), config=ParserConfig(1)
    )

    assert [block["text"] for block in artifact["narrative_blocks"]] == [
        "First heading",
        "First paragraph",
        "First item",
        "Second heading",
        "Second paragraph",
    ]
    assert artifact["narrative_blocks"][1]["heading_context"]["text"] == "First heading"
    assert all("Hidden" not in block["text"] for block in artifact["narrative_blocks"])


def test_preserves_table_indices_spans_empty_cells_and_numeric_display(tmp_path: Path) -> None:
    content = b"""<html><body><p>narrative sufficient for parser output</p>
    <table><tr><td>first</td></tr></table><h2>Statement</h2>
    <table id='statement'><caption>In millions</caption>
    <tr><th colspan='2'>Year ended 2024</th></tr>
    <tr><td>Net income</td><td rowspan='2'>(1,234)</td></tr>
    <tr><td></td></tr></table></body></html>"""
    artifact = parse_registered_document(
        tmp_path, _write_source(tmp_path, content), config=ParserConfig(1)
    )

    assert [table["original_html_table_index"] for table in artifact["tables"]] == [1, 2]
    table = artifact["tables"][1]
    assert table["caption"] == "In millions"
    assert table["rows"][0]["cells"][0]["colspan"] == 2
    assert table["rows"][1]["cells"][1]["rowspan"] == 2
    assert table["rows"][1]["cells"][1]["text"] == "(1,234)"
    assert table["rows"][2]["cells"][0]["text"] == ""
    assert "Year ended 2024" in table["period_header_text"]
    assert "In millions" in table["unit_hints"]


def test_malformed_and_nested_table_warnings_are_not_silently_trusted(tmp_path: Path) -> None:
    content = b"""<html><body><p>narrative sufficient for parser output</p><table>
    <tr><td>outer<table><tr><td>inner</td></tr></table></td></tr><tr></tr></table></body></html>"""
    artifact = parse_registered_document(
        tmp_path, _write_source(tmp_path, content), config=ParserConfig(1)
    )

    assert artifact["parse_status"] == "PARSED_WITH_WARNINGS"
    assert any("Nested table" in warning for warning in artifact["tables"][0]["warnings"])
    assert any("no direct table cells" in warning for warning in artifact["tables"][0]["warnings"])
    assert [table["original_html_table_index"] for table in artifact["tables"]] == [1, 2]


def test_invalid_span_quarantines_table_separately_from_trusted_tables(tmp_path: Path) -> None:
    content = (
        b"<html><body><p>visible narrative</p><table><tr><td colspan='0'>bad</td>"
        b"</tr></table></body></html>"
    )
    artifact = parse_registered_document(
        tmp_path, _write_source(tmp_path, content), config=ParserConfig(1)
    )

    assert artifact["parse_status"] == "PARSED_WITH_WARNINGS"
    assert artifact["tables"] == []
    assert artifact["quarantined_tables"][0]["parse_status"] == "QUARANTINED"
    assert artifact["quarantined_tables"][0]["reason_code"] == "INVALID_SPAN"


def test_malformed_html_is_recovered_with_an_explicit_warning(tmp_path: Path) -> None:
    content = b"<html><body><h1>Unclosed heading<p>Visible text"
    artifact = parse_registered_document(
        tmp_path, _write_source(tmp_path, content), config=ParserConfig(1)
    )

    assert artifact["parse_status"] == "PARSED_WITH_WARNINGS"
    assert any("Closing HTML marker" in warning for warning in artifact["warnings"])


def test_source_hash_mismatch_and_missing_source_never_parse(tmp_path: Path) -> None:
    content = b"<html><body><p>original</p></body></html>"
    document = _write_source(tmp_path, content)
    source = tmp_path / document.local_source_path
    source.write_bytes(b"<html><body><p>changed</p></body></html>")

    changed = parse_registered_document(tmp_path, document, config=ParserConfig(1))
    assert changed["record_type"] == "source_validation_failure"
    assert changed["parse_status"] == "CHANGED"

    source.unlink()
    missing = parse_registered_document(tmp_path, document, config=ParserConfig(1))
    assert missing["parse_status"] == "MISSING"


def test_stable_ids_and_artifact_content_are_deterministic(tmp_path: Path) -> None:
    content = (
        b"<html><body><h1>Heading</h1><p>Text</p><table><tr><td>Value</td></tr>"
        b"</table></body></html>"
    )
    document = _write_source(tmp_path, content)
    first = parse_registered_document(tmp_path, document, config=ParserConfig(1))
    second = parse_registered_document(tmp_path, document, config=ParserConfig(1))

    assert first == second
    assert first["narrative_blocks"][0]["source_locator"] == "element:1:h1"
    assert first["tables"][0]["rows"][0]["cells"][0]["source_locator"] == "table:1/row:1/cell:1"


def test_rejects_output_paths_outside_processed_data(tmp_path: Path) -> None:
    assert (
        ensure_parser_output_path(tmp_path, tmp_path / "data/processed/sec_parsed/v1").name == "v1"
    )
    with pytest.raises(ValueError, match="processed"):
        ensure_parser_output_path(tmp_path, tmp_path / "elsewhere")


def test_reviewed_qa_mapping_contains_all_30_candidates(project_root: Path) -> None:
    expectations = load_reviewed_table_expectations(project_root)

    assert len(expectations) == 10
    assert sum(len(value) for value in expectations.values()) == 30
    assert all(len(value) == 3 for value in expectations.values())


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]
