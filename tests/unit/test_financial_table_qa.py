"""Focused synthetic tests for financial-table selection and safe QA rendering."""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from app.ingestion.validation.financial_table_qa import (
    CATEGORIES,
    ManifestDocument,
    TableCell,
    ensure_qa_output_path,
    expected_check_keys,
    extract_table_grid,
    render_review_html,
    select_financial_table,
)


def _income_table(label: str = "Consolidated Statements of Operations") -> str:
    return f"""
    <h2>{label}</h2>
    <table id="income"><tr><th>Year ended</th><th>2024</th><th>2023</th></tr>
      <tr><td>Revenue</td><td>100</td><td>90</td></tr>
      <tr><td>Gross margin</td><td>60</td><td>55</td></tr>
      <tr><td>Operating income</td><td>30</td><td>25</td></tr>
      <tr><td>Net income</td><td>(20)</td><td>18</td></tr>
      <tr><td>Earnings per share</td><td>2.00</td><td>1.80</td></tr>
      <tr><td>Extra values</td><td>3</td><td>4</td></tr>
      <tr><td>More values</td><td>5</td><td>6</td></tr>
    </table>
    """


def test_locates_labelled_financial_table() -> None:
    soup = BeautifulSoup(f"<html><body>{_income_table()}</body></html>", "lxml")

    status, candidate, _ = select_financial_table(soup, CATEGORIES[0])

    assert status == "FOUND"
    assert candidate is not None
    assert candidate.table.get("id") == "income"


def test_preserves_headers_row_labels_and_spans() -> None:
    soup = BeautifulSoup(
        "<table><tr><th colspan='2'>Year ended 2024</th></tr>"
        "<tr><td>Net income</td><td>(20)</td></tr></table>",
        "lxml",
    )

    rows, columns, truncated = extract_table_grid(soup.table)

    assert rows[0][0] == TableCell("Year ended 2024", "th", colspan=2)
    assert rows[1][0].text == "Net income"
    assert rows[1][1].text == "(20)"
    assert columns == 2
    assert truncated is False


def test_missing_and_ambiguous_tables_are_explicit() -> None:
    missing = BeautifulSoup("<html><body><p>No statements here.</p></body></html>", "lxml")
    status, candidate, _ = select_financial_table(missing, CATEGORIES[0])
    assert status == "NOT FOUND"
    assert candidate is None

    repeated = BeautifulSoup(
        f"<html><body>{_income_table('Summary')}{_income_table('Summary')}</body></html>",
        "lxml",
    )
    status, candidate, _ = select_financial_table(repeated, CATEGORIES[0])
    assert status == "AMBIGUOUS"
    assert candidate is not None


def test_review_html_escapes_cell_and_metadata_content(tmp_path: Path) -> None:
    from app.ingestion.validation.financial_table_qa import TableCheck

    check = TableCheck(
        document_id="unsafe<script>",
        source_filename="sample.html",
        company="A&B",
        form_type="10-K",
        reporting_period="2024-01-01",
        relative_source_path="sample.html",
        category="income_statement",
        category_label="Income <statement>",
        anchor="safe-anchor",
        source_table_status="FOUND",
        review_status="PENDING HUMAN REVIEW",
        heading_or_context="<img src=x onerror=alert(1)>",
        source_reference="HTML table 1",
        table_index=1,
        selection_score=30,
        runner_up_score=None,
        row_count=1,
        column_count=1,
        original_rows=[[TableCell("<script>alert(1)</script> & value", "td")]],
        extracted_representation="<b>not markup</b>",
        extraction_risks=["Risk & review"],
        render_truncated=False,
        extracted_truncated=False,
    )

    rendered = render_review_html([check], tmp_path)

    assert "<script>alert(1)</script>" not in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; value" in rendered
    assert "&lt;img src=x onerror=alert(1)&gt;" in rendered
    assert "&lt;b&gt;not markup&lt;/b&gt;" in rendered


def test_check_matrix_contains_all_ten_documents_and_categories() -> None:
    documents = [
        ManifestDocument(
            document_id=f"document-{index}",
            company="Example",
            form_type="10-K",
            reporting_period="2024-01-01",
            relative_source_path=f"document-{index}.html",
            sha256="0" * 64,
        )
        for index in range(10)
    ]

    keys = expected_check_keys(documents)

    assert len(keys) == 30
    assert len(set(keys)) == 30
    assert {category for _, category in keys} == {item.key for item in CATEGORIES}


def test_output_path_cannot_escape_designated_directory(tmp_path: Path) -> None:
    allowed = tmp_path / "data/processed/document_verification/table_qa/review.html"
    assert ensure_qa_output_path(tmp_path, allowed) == allowed.resolve()

    with pytest.raises(ValueError, match="Output must remain"):
        ensure_qa_output_path(tmp_path, tmp_path / "outside.html")
