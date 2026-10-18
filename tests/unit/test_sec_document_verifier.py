"""Focused tests for offline SEC filing verification."""

import csv
from pathlib import Path

from app.ingestion.validation.sec_document_verifier import (
    MANIFEST_COLUMNS,
    DocumentSpec,
    detect_financial_sections,
    manifest_field_names,
    verify_document,
    write_manifest,
)


def _spec(relative_path: str = "sample.html") -> DocumentSpec:
    return DocumentSpec(
        document_id="msft-sample-10k",
        company="Microsoft",
        expected_form_type="10-K",
        expected_reporting_period="2024-06-30",
        relative_source_path=relative_path,
    )


def _valid_html() -> str:
    narrative = "Business operations and financial discussion. " * 300
    return f"""
    <html><body>
      <ix:nonNumeric name="dei:EntityRegistrantName">Microsoft Corporation</ix:nonNumeric>
      <ix:nonNumeric name="dei:DocumentType">10-K</ix:nonNumeric>
      <ix:nonNumeric name="dei:DocumentPeriodEndDate">2024-06-30</ix:nonNumeric>
      <h1>FORM 10-K</h1><p>{narrative}</p>
      <h2>Risk Factors</h2>
      <h2>Management's Discussion and Analysis</h2>
      <table><tr><th>Consolidated Statements of Operations</th></tr>
        <tr><td>Net revenue</td><td>100</td><td>90</td><td>80</td><td>70</td><td>60</td></tr>
      </table>
      <table><tr><th>Consolidated Balance Sheets</th></tr>
        <tr><td>Total assets</td><td>500</td><td>450</td><td>400</td><td>350</td><td>300</td></tr>
      </table>
      <h2>Consolidated Statements of Cash Flows</h2>
    </body></html>
    """


def test_identifies_company_form_and_period(tmp_path: Path) -> None:
    (tmp_path / "sample.html").write_text(_valid_html(), encoding="utf-8")

    result = verify_document(tmp_path, _spec())

    assert result.detected_company == "Microsoft"
    assert result.detected_form_type == "10-K"
    assert result.detected_reporting_period == "2024-06-30"
    assert result.identity_check == "PASS"


def test_missing_file_is_a_graceful_failure(tmp_path: Path) -> None:
    result = verify_document(tmp_path, _spec("missing.html"))

    assert result.file_exists is False
    assert result.overall_status == "FAIL"
    assert "missing" in result.warnings.lower()


def test_sec_error_page_is_not_treated_as_a_report(tmp_path: Path) -> None:
    (tmp_path / "sample.html").write_text(
        "<html><body><h1>SEC.gov | Your Request</h1>"
        "<p>Your request originates from an undeclared automated tool.</p></body></html>",
        encoding="utf-8",
    )

    result = verify_document(tmp_path, _spec())

    assert result.extraction_check == "FAIL"
    assert result.overall_status == "FAIL"
    assert "error content" in result.warnings.lower()


def test_detects_financial_statement_headings() -> None:
    sections = detect_financial_sections(
        "Consolidated Statements of Operations. Consolidated Balance Sheets. "
        "Consolidated Statements of Cash Flows. Risk Factors. "
        "Management's Discussion and Analysis."
    )

    assert set(sections) == {
        "income_statement",
        "balance_sheet",
        "cash_flow_statement",
        "risk_factors",
        "management_discussion_and_analysis",
    }


def test_manifest_schema_is_stable(tmp_path: Path) -> None:
    (tmp_path / "sample.html").write_text(_valid_html(), encoding="utf-8")
    result = verify_document(tmp_path, _spec())
    output = tmp_path / "manifest.csv"

    write_manifest(output, [result])

    with output.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    assert tuple(reader.fieldnames or ()) == MANIFEST_COLUMNS == manifest_field_names()
    assert len(rows) == 1
    assert set(rows[0]) == set(MANIFEST_COLUMNS)
