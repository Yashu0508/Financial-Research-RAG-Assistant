"""Prepare offline, human-review-only QA artifacts for selected financial tables."""

from __future__ import annotations

import csv
import hashlib
import html
import json
import os
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final
from urllib.parse import quote

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString

from app.ingestion.validation.sec_document_verifier import extract_visible_text

QA_RELATIVE_DIR: Final[Path] = Path("data/processed/document_verification/table_qa")
REVIEW_STATUS: Final[str] = "PENDING HUMAN REVIEW"
MAX_RENDER_ROWS: Final[int] = 80
MAX_RENDER_COLUMNS: Final[int] = 14
MAX_EXTRACTED_TEXT: Final[int] = 12_000


@dataclass(frozen=True)
class TableCategory:
    """Signals used to locate one financial statement category."""

    key: str
    label: str
    heading_patterns: tuple[str, ...]
    row_label_patterns: tuple[str, ...]


CATEGORIES: Final[tuple[TableCategory, ...]] = (
    TableCategory(
        key="income_statement",
        label="Income statement / statement of operations",
        heading_patterns=(
            r"(?:condensed\s+)?(?:consolidated\s+)?statements?\s+of\s+operations",
            r"(?:consolidated\s+)?in\s*c\s*ome\s+sta\s*tements?",
            r"statements?\s+of\s+(?:income|earnings)",
        ),
        row_label_patterns=(
            r"\b(?:net\s+sales|revenue)\b",
            r"\b(?:gross\s+margin|gross\s+profit)\b",
            r"\boperating\s+(?:income|loss)\b",
            r"\bnet\s+(?:income|loss)\b",
            r"\bearnings\s+per\s+share\b",
        ),
    ),
    TableCategory(
        key="balance_sheet",
        label="Balance sheet / statement of financial position",
        heading_patterns=(
            r"(?:condensed\s+)?(?:consolidated\s+)?balance\s+sheets?",
            r"statements?\s+of\s+financial\s+position",
        ),
        row_label_patterns=(
            r"\bcurrent\s+assets\b",
            r"\btotal\s+assets\b",
            r"\bcurrent\s+liabilities\b",
            r"\btotal\s+liabilities\b",
            r"\b(?:stockholders|shareholders)[’'`s\s]+equity\b",
        ),
    ),
    TableCategory(
        key="cash_flow_statement",
        label="Cash-flow statement / statement of cash flows",
        heading_patterns=(
            r"(?:condensed\s+)?(?:consolidated\s+)?statements?\s+of\s+cash\s+flows?",
            r"(?:consolidated\s+)?cash\s+flo\s*ws?\s+s\s*ta\s*tements?",
        ),
        row_label_patterns=(
            r"\boperating\s+activities\b",
            r"\binvesting\s+activities\b",
            r"\bfinancing\s+activities\b",
            r"\bdepreciation\b",
            r"\bcash\s+and\s+cash\s+equivalents\b",
        ),
    ),
)


@dataclass(frozen=True)
class ManifestDocument:
    document_id: str
    company: str
    form_type: str
    reporting_period: str
    relative_source_path: str
    sha256: str


@dataclass(frozen=True)
class TableCell:
    text: str
    kind: str
    colspan: int = 1
    rowspan: int = 1


@dataclass
class TableCheck:
    document_id: str
    source_filename: str
    company: str
    form_type: str
    reporting_period: str
    relative_source_path: str
    category: str
    category_label: str
    anchor: str
    source_table_status: str
    review_status: str
    heading_or_context: str
    source_reference: str
    table_index: int | None
    selection_score: int | None
    runner_up_score: int | None
    row_count: int
    column_count: int
    original_rows: list[list[TableCell]]
    extracted_representation: str
    extraction_risks: list[str]
    render_truncated: bool
    extracted_truncated: bool

    def inventory_record(self) -> dict[str, object]:
        """Return a compact machine-readable inventory without embedded table markup."""

        return {
            "document_id": self.document_id,
            "source_filename": self.source_filename,
            "company": self.company,
            "form_type": self.form_type,
            "reporting_period": self.reporting_period,
            "relative_source_path": self.relative_source_path,
            "category": self.category,
            "category_label": self.category_label,
            "anchor": self.anchor,
            "source_table_status": self.source_table_status,
            "review_status": self.review_status,
            "heading_or_context": self.heading_or_context,
            "source_reference": self.source_reference,
            "table_index": self.table_index,
            "selection_score": self.selection_score,
            "runner_up_score": self.runner_up_score,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "render_truncated": self.render_truncated,
            "extracted_truncated": self.extracted_truncated,
            "extraction_risks": self.extraction_risks,
            "original_rows_preview": [
                [asdict(cell) for cell in row]
                for row in self.original_rows[:5]
            ],
            "extracted_representation_preview": self.extracted_representation[:500],
        }


@dataclass(frozen=True)
class _Candidate:
    table: Tag
    index: int
    text: str
    context: str
    score: int
    heading_match: str
    heading_in_table: bool
    row_signal_count: int
    numeric_count: int
    row_count: int


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def load_manifest(path: Path) -> list[ManifestDocument]:
    """Load the existing verification manifest without changing its schema or contents."""

    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        ManifestDocument(
            document_id=row["document_id"],
            company=row["company"],
            form_type=row["detected_form_type"] or row["expected_form_type"],
            reporting_period=(
                row["detected_reporting_period"] or row["expected_reporting_period"]
            ),
            relative_source_path=row["relative_source_path"],
            sha256=row["sha256"],
        )
        for row in rows
    ]


def expected_check_keys(documents: Iterable[ManifestDocument]) -> list[tuple[str, str]]:
    """Return the complete document/category matrix in stable order."""

    return [
        (document.document_id, category.key)
        for document in documents
        for category in CATEGORIES
    ]


def _visible_table_copy(table: Tag) -> tuple[BeautifulSoup, Tag | None, str]:
    copy = BeautifulSoup(str(table), "lxml")
    extracted, _ = extract_visible_text(copy)
    return copy, copy.find("table"), extracted


def _preceding_context(table: Tag, limit: int = 1_800) -> str:
    parts: list[str] = []
    length = 0
    node: Tag | None = table
    while node is not None and len(parts) < 14 and length < limit:
        sibling = node.find_previous_sibling()
        while sibling is not None and len(parts) < 14 and length < limit:
            if isinstance(sibling, NavigableString):
                value = _normalize(str(sibling))
            else:
                value = _normalize(sibling.get_text(" ", strip=True))
            if value:
                compact = value[-300:]
                parts.append(compact)
                length += len(compact) + 1
            sibling = sibling.find_previous_sibling()
        parent = node.parent
        node = parent if isinstance(parent, Tag) else None
    return _normalize(" ".join(reversed(parts)))[-limit:]


def _first_match(patterns: Iterable[str], value: str) -> str:
    matches: list[tuple[int, str]] = []
    for pattern in patterns:
        match = re.search(pattern, value, re.IGNORECASE)
        if match:
            matches.append((match.start(), _normalize(match.group(0))))
    return min(matches, default=(0, ""), key=lambda item: item[0])[1]


def _candidate(table: Tag, index: int, category: TableCategory) -> _Candidate:
    _, visible_table, text = _visible_table_copy(table)
    context = _preceding_context(table)
    heading_in_table = bool(_first_match(category.heading_patterns, text))
    heading_match = _first_match(category.heading_patterns, text)
    if not heading_match:
        heading_match = _first_match(category.heading_patterns, context)
    row_signal_count = sum(
        bool(re.search(pattern, text, re.IGNORECASE)) for pattern in category.row_label_patterns
    )
    numeric_count = len(re.findall(r"(?:\$\s*)?\(?\d[\d,]*(?:\.\d+)?\)?%?", text))
    row_count = len(visible_table.find_all("tr")) if visible_table else 0
    score = (20 if heading_in_table else 10 if heading_match else 0) + row_signal_count * 4
    score += 4 if numeric_count >= 10 else 2 if numeric_count >= 5 else 0
    score += 3 if row_count >= 8 else 1 if row_count >= 4 else 0
    if row_count > 150:
        score -= 4
    return _Candidate(
        table=table,
        index=index,
        text=text,
        context=context,
        score=score,
        heading_match=heading_match,
        heading_in_table=heading_in_table,
        row_signal_count=row_signal_count,
        numeric_count=numeric_count,
        row_count=row_count,
    )


def select_financial_table(
    soup: BeautifulSoup,
    category: TableCategory,
) -> tuple[str, _Candidate | None, int | None]:
    """Select the strongest table candidate while surfacing uncertainty explicitly."""

    candidates = [
        _candidate(table, index, category)
        for index, table in enumerate(soup.find_all("table"), start=1)
    ]
    plausible = [
        candidate
        for candidate in candidates
        if candidate.row_signal_count >= 2
        and candidate.numeric_count >= 5
        and candidate.row_count >= 4
    ]
    plausible.sort(key=lambda candidate: (-candidate.score, candidate.index))
    if not plausible or plausible[0].score < 15:
        return "NOT FOUND", None, plausible[0].score if plausible else None
    selected = plausible[0]
    runner_up = plausible[1].score if len(plausible) > 1 else None
    if not selected.heading_match or (
        runner_up is not None
        and selected.score - runner_up < 3
        and not selected.heading_in_table
        and selected.row_signal_count < 4
    ):
        return "AMBIGUOUS", selected, runner_up
    return "FOUND", selected, runner_up


def extract_table_grid(table: Tag) -> tuple[list[list[TableCell]], int, bool]:
    """Extract escaped-at-render-time cell text while retaining basic table spans."""

    rows: list[list[TableCell]] = []
    max_columns = 0
    truncated = False
    _, visible_table, _ = _visible_table_copy(table)
    if visible_table is None:
        return rows, 0, False
    all_rows = visible_table.find_all("tr")
    if len(all_rows) > MAX_RENDER_ROWS:
        truncated = True
    for row in all_rows[:MAX_RENDER_ROWS]:
        cells = row.find_all(["th", "td"], recursive=False)
        if not cells:
            cells = row.find_all(["th", "td"])
        if len(cells) > MAX_RENDER_COLUMNS:
            truncated = True
        extracted_row = [
            TableCell(
                text=_normalize(cell.get_text(" ", strip=True)),
                kind="th" if cell.name == "th" else "td",
                colspan=_safe_span(cell.get("colspan")),
                rowspan=_safe_span(cell.get("rowspan")),
            )
            for cell in cells[:MAX_RENDER_COLUMNS]
        ]
        if any(cell.text for cell in extracted_row):
            rows.append(extracted_row)
            max_columns = max(
                max_columns,
                sum(cell.colspan for cell in extracted_row),
            )
    return rows, max_columns, truncated


def _safe_span(value: object) -> int:
    try:
        return max(1, min(int(str(value)), 20))
    except (TypeError, ValueError):
        return 1


def _heading_context(candidate: _Candidate, category: TableCategory) -> str:
    if candidate.heading_match:
        source = candidate.text if candidate.heading_in_table else candidate.context
        match = next(
            (
                re.search(pattern, source, re.IGNORECASE)
                for pattern in category.heading_patterns
                if re.search(pattern, source, re.IGNORECASE)
            ),
            None,
        )
        if match:
            start = max(0, match.start() - 100)
            end = min(len(source), match.end() + 180)
            return _normalize(source[start:end])
    return "No category heading was confidently associated with this candidate."


def _risks(
    status: str,
    rows: list[list[TableCell]],
    extracted: str,
    render_truncated: bool,
    extracted_truncated: bool,
) -> list[str]:
    if status == "NOT FOUND":
        return ["No table met the minimum heading, row-label, numeric, and row-count signals."]
    risks = [
        "The current extraction flattens cells into one whitespace-normalized sequence; "
        "explicit row and column boundaries are not retained."
    ]
    cells = [cell for row in rows for cell in row]
    if cells and not any(cell.kind == "th" for cell in cells):
        risks.append(
            "The source uses data cells rather than semantic <th> headers; header roles depend "
            "on visual styling and position."
        )
    if any(cell.colspan > 1 or cell.rowspan > 1 for cell in cells):
        risks.append("Merged cells can make flattened date/header-to-value alignment ambiguous.")
    if re.search(r"\(\s*\d[\d,]*(?:\.\d+)?\s*\)", extracted):
        risks.append("Parenthesized values are present; confirm negative/sign meaning manually.")
    if render_truncated:
        risks.append(
            f"The review grid is capped at {MAX_RENDER_ROWS} rows and "
            f"{MAX_RENDER_COLUMNS} source cells per row."
        )
    if extracted_truncated:
        risks.append(f"The flattened text preview is capped at {MAX_EXTRACTED_TEXT:,} characters.")
    if status == "AMBIGUOUS":
        risks.append("Automated scoring could not distinguish this candidate confidently.")
    return risks


def build_checks_for_document(project_root: Path, document: ManifestDocument) -> list[TableCheck]:
    """Build three pending checks for one manifest document."""

    source = project_root / document.relative_source_path
    if not source.is_file():
        return [
            _empty_check(document, category, "NOT FOUND", "Source file is missing.")
            for category in CATEGORIES
        ]
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != document.sha256:
        return [
            _empty_check(
                document,
                category,
                "AMBIGUOUS",
                "Source SHA-256 does not match the existing verification manifest.",
            )
            for category in CATEGORIES
        ]
    soup = BeautifulSoup(raw, "lxml")
    checks: list[TableCheck] = []
    for category in CATEGORIES:
        status, selected, runner_up = select_financial_table(soup, category)
        if selected is None:
            checks.append(
                _empty_check(
                    document,
                    category,
                    status,
                    "No qualifying table candidate was selected.",
                )
            )
            continue
        rows, column_count, render_truncated = extract_table_grid(selected.table)
        extracted = selected.text
        extracted_truncated = len(extracted) > MAX_EXTRACTED_TEXT
        compact_extracted = extracted[:MAX_EXTRACTED_TEXT]
        if extracted_truncated:
            compact_extracted += " … [preview truncated]"
        anchor = f"{document.document_id}-{category.key}"
        checks.append(
            TableCheck(
                document_id=document.document_id,
                source_filename=source.name,
                company=document.company,
                form_type=document.form_type,
                reporting_period=document.reporting_period,
                relative_source_path=document.relative_source_path,
                category=category.key,
                category_label=category.label,
                anchor=anchor,
                source_table_status=status,
                review_status=REVIEW_STATUS,
                heading_or_context=_heading_context(selected, category),
                source_reference=f"HTML table {selected.index}",
                table_index=selected.index,
                selection_score=selected.score,
                runner_up_score=runner_up,
                row_count=selected.row_count,
                column_count=column_count,
                original_rows=rows,
                extracted_representation=compact_extracted,
                extraction_risks=_risks(
                    status,
                    rows,
                    extracted,
                    render_truncated,
                    extracted_truncated,
                ),
                render_truncated=render_truncated,
                extracted_truncated=extracted_truncated,
            )
        )
    return checks


def _empty_check(
    document: ManifestDocument,
    category: TableCategory,
    status: str,
    reason: str,
) -> TableCheck:
    return TableCheck(
        document_id=document.document_id,
        source_filename=Path(document.relative_source_path).name,
        company=document.company,
        form_type=document.form_type,
        reporting_period=document.reporting_period,
        relative_source_path=document.relative_source_path,
        category=category.key,
        category_label=category.label,
        anchor=f"{document.document_id}-{category.key}",
        source_table_status=status,
        review_status=REVIEW_STATUS,
        heading_or_context="Not available.",
        source_reference="Not available.",
        table_index=None,
        selection_score=None,
        runner_up_score=None,
        row_count=0,
        column_count=0,
        original_rows=[],
        extracted_representation="Not available.",
        extraction_risks=[reason],
        render_truncated=False,
        extracted_truncated=False,
    )


def _render_grid(rows: list[list[TableCell]]) -> str:
    if not rows:
        return '<p class="not-found">No source table representation is available.</p>'
    rendered_rows: list[str] = []
    for row in rows:
        cells: list[str] = []
        for cell in row:
            tag = "th" if cell.kind == "th" else "td"
            attrs = ""
            if cell.colspan > 1:
                attrs += f' colspan="{cell.colspan}"'
            if cell.rowspan > 1:
                attrs += f' rowspan="{cell.rowspan}"'
            cells.append(f"<{tag}{attrs}>{html.escape(cell.text)}</{tag}>")
        rendered_rows.append(f"<tr>{''.join(cells)}</tr>")
    return f'<div class="table-scroll"><table>{"".join(rendered_rows)}</table></div>'


def render_review_html(
    checks: list[TableCheck],
    output_dir: Path,
    project_root: Path | None = None,
) -> str:
    """Render a self-contained, offline review page from escaped values only."""

    grouped: dict[str, list[TableCheck]] = {}
    for check in checks:
        grouped.setdefault(check.document_id, []).append(check)
    nav = "".join(
        f'<li><a href="#{html.escape(check.anchor, quote=True)}">'
        f"{html.escape(check.document_id)} — {html.escape(check.category_label)}</a></li>"
        for check in checks
    )
    sections: list[str] = []
    source_root = (project_root or output_dir).resolve()
    for document_id, document_checks in grouped.items():
        first = document_checks[0]
        sections.append(
            f'<section class="document"><h2>{html.escape(document_id)}</h2>'
            f'<p>{html.escape(first.company)} · {html.escape(first.form_type)} · '
            f'period ended {html.escape(first.reporting_period)}</p>'
        )
        for check in document_checks:
            source_link = quote(
                os.path.relpath(
                    (source_root / check.relative_source_path).resolve(),
                    output_dir.resolve(),
                ).replace("\\", "/"),
                safe="/._-",
            )
            risks = "".join(f"<li>{html.escape(risk)}</li>" for risk in check.extraction_risks)
            status_class = check.source_table_status.lower().replace(" ", "-")
            sections.append(
                f'<a class="anchor" id="{html.escape(check.anchor, quote=True)}"></a>'
                f'<details class="check" data-status="{status_class}">'
                f"<summary>{html.escape(check.category_label)} — "
                f'<span class="status {status_class}">'
                f"{html.escape(check.source_table_status)}</span>"
                f' — <span class="pending">{REVIEW_STATUS}</span></summary>'
                '<div class="metadata">'
                f"<p><strong>Source:</strong> <a href=\"{source_link}\">"
                f"{html.escape(check.source_filename)}</a> · "
                f"{html.escape(check.source_reference)}</p>"
                f"<p><strong>Heading/context:</strong> "
                f"{html.escape(check.heading_or_context)}</p>"
                f"<p><strong>Dimensions:</strong> {check.row_count} HTML rows; "
                f"approximately {check.column_count} structural columns. "
                "Spans and visually styled headers require human interpretation.</p></div>"
                '<div class="comparison"><article><h3>Reconstructed source table</h3>'
                "<p>Escaped cell text with source row order and basic row/column spans "
                "retained.</p>"
                f"{_render_grid(check.original_rows)}</article>"
                '<article><h3>Current normalized text representation</h3>'
                "<p>This is the selected table passed through the existing visible-text "
                "normalization logic.</p>"
                f'<pre>{html.escape(check.extracted_representation)}</pre></article></div>'
                f'<div class="risks"><h3>Extraction risks</h3><ul>{risks}</ul></div>'
                '<div class="review"><h3>Human review checklist</h3><ul>'
                "<li>☐ Correct statement/table selected</li>"
                "<li>☐ Row labels preserved and ordered</li>"
                "<li>☐ Column dates/periods align with values</li>"
                "<li>☐ Units and scale are clear</li>"
                "<li>☐ Parentheses/signs and totals are preserved</li>"
                "<li>☐ Record finding in the Markdown checklist; do not edit raw HTML</li>"
                "</ul></div></details>"
            )
        sections.append("</section>")
    css = """
    :root { color-scheme: light; font-family: Segoe UI, Arial, sans-serif; }
    body { margin: 0 auto; max-width: 1800px; padding: 1.5rem;
           color: #172033; background: #f4f6fa; }
    h1, h2, h3 { color: #12213d; }
    .notice { border-left: 5px solid #c27803; background: #fff5d6; padding: 1rem; }
    nav { columns: 2; background: white; padding: 1rem 2rem; border-radius: .5rem; }
    nav li { break-inside: avoid; margin: .35rem 0; }
    .document { margin: 2rem 0; }
    .anchor { display: block; scroll-margin-top: 1rem; }
    details { background: white; border: 1px solid #ccd3df; border-radius: .5rem; margin: .8rem 0; }
    summary { cursor: pointer; padding: 1rem; font-weight: 650; }
    details[open] summary { border-bottom: 1px solid #dde2ea; }
    .metadata, .risks, .review { padding: .25rem 1rem; }
    .comparison { display: grid;
                  grid-template-columns: minmax(0, 1.25fr) minmax(0, .75fr);
                  gap: 1rem; padding: 1rem; }
    article { min-width: 0; border: 1px solid #e0e4eb; border-radius: .4rem; padding: .75rem; }
    .table-scroll { overflow: auto; max-height: 70vh; }
    table { border-collapse: collapse; min-width: 100%; font-size: .82rem; background: white; }
    th, td { border: 1px solid #bfc7d4; padding: .28rem .42rem;
             text-align: right; vertical-align: top; white-space: nowrap; }
    th, td:first-child { text-align: left; }
    th { background: #e9eef7; }
    pre { white-space: pre-wrap; overflow-wrap: anywhere; max-height: 70vh; overflow: auto;
          background: #111827; color: #f3f4f6; padding: .8rem; border-radius: .35rem; }
    .status, .pending { border-radius: 999px; padding: .15rem .5rem; font-size: .78rem; }
    .found { background: #d9f7e5; color: #126238; }
    .ambiguous { background: #fff0c2; color: #744c00; }
    .not-found { background: #fee2e2; color: #8d2020; }
    .pending { background: #e7e9ee; color: #343a46; }
    @media (max-width: 1000px) { .comparison { grid-template-columns: 1fr; } nav { columns: 1; } }
    """
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Financial Table Extraction QA Review</title>"
        f"<style>{css}</style></head><body>"
        "<h1>Financial Table Extraction QA Review</h1>"
        '<div class="notice"><strong>No table is manually verified.</strong> '
        "Every check remains PENDING HUMAN REVIEW. FOUND means only that automated selection "
        "identified a likely source table. Compare structure, dates, units, signs, labels, and "
        "values before recording a human result.</div>"
        "<h2>How to use this page</h2><ol>"
        "<li>Select a check below and expand it.</li>"
        "<li>Compare the reconstructed source grid on the left with flattened text on the "
        "right.</li>"
        "<li>Use the local source link when visual context is unclear.</li>"
        "<li>Record the human conclusion in <code>table_qa_checklist.md</code>; do not edit "
        "raw files.</li>"
        f"</ol><nav><h2>All 30 checks</h2><ul>{nav}</ul></nav>{''.join(sections)}"
        "</body></html>"
    )


def render_checklist(checks: list[TableCheck]) -> str:
    """Render one explicit pending checklist entry per document/category pair."""

    lines = [
        "# Financial Table Extraction QA Checklist",
        "",
        "> No financial table has been manually verified. Every review status starts as "
        "`PENDING HUMAN REVIEW`.",
        "",
        "For each item, open the linked review section, compare both representations, then "
        "record notes without changing the raw source. Check row labels, date/period columns, "
        "units, signs/parentheses, totals, and value alignment.",
        "",
    ]
    current_document = ""
    for check in checks:
        if check.document_id != current_document:
            current_document = check.document_id
            lines.extend([f"## {current_document}", ""])
        lines.extend(
            [
                f"- [ ] [{check.category_label}](table_qa_review.html#{check.anchor})",
                f"  - Automated source-table status: `{check.source_table_status}`",
                f"  - Human review status: `{check.review_status}`",
                f"  - Source reference: `{check.source_reference}`",
                "  - Reviewer finding: _Not entered_",
                "",
            ]
        )
    return "\n".join(lines)


def ensure_qa_output_path(project_root: Path, candidate: Path) -> Path:
    """Reject any generated-artifact path outside the fixed table-QA directory."""

    allowed = (project_root.resolve() / QA_RELATIVE_DIR).resolve()
    resolved = candidate.resolve()
    if resolved != allowed and allowed not in resolved.parents:
        raise ValueError(f"Output must remain under {allowed}")
    return resolved


def write_review_package(
    project_root: Path,
    checks: list[TableCheck],
) -> tuple[Path, Path, Path]:
    """Write exactly the three requested artifacts inside the designated directory."""

    output_dir = ensure_qa_output_path(project_root, project_root / QA_RELATIVE_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = ensure_qa_output_path(project_root, output_dir / "table_qa_review.html")
    checklist_path = ensure_qa_output_path(project_root, output_dir / "table_qa_checklist.md")
    summary_path = ensure_qa_output_path(project_root, output_dir / "table_qa_summary.json")
    html_path.write_text(
        render_review_html(checks, output_dir, project_root),
        encoding="utf-8",
        newline="\n",
    )
    checklist_path.write_text(render_checklist(checks), encoding="utf-8", newline="\n")
    summary = {
        "review_status_policy": REVIEW_STATUS,
        "human_review_completed": False,
        "check_count": len(checks),
        "counts_by_source_table_status": {
            status: sum(check.source_table_status == status for check in checks)
            for status in ("FOUND", "AMBIGUOUS", "NOT FOUND")
        },
        "checks": [check.inventory_record() for check in checks],
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return html_path, checklist_path, summary_path


def build_review_package(project_root: Path) -> tuple[list[TableCheck], tuple[Path, Path, Path]]:
    """Load the existing manifest, select tables, and write the fixed QA package."""

    root = project_root.resolve()
    manifest = root / "data/processed/document_verification/document_manifest.csv"
    documents = load_manifest(manifest)
    checks = [
        check
        for document in documents
        for check in build_checks_for_document(root, document)
    ]
    expected = expected_check_keys(documents)
    actual = [(check.document_id, check.category) for check in checks]
    if len(documents) != 10 or actual != expected:
        raise ValueError("QA package must contain the stable 10-document × 3-category matrix.")
    return checks, write_review_package(root, checks)
