"""Offline, read-only verification of the expected SEC filing HTML corpus."""

from __future__ import annotations

import csv
import hashlib
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Final

from bs4 import BeautifulSoup, Tag

MANIFEST_COLUMNS: Final[tuple[str, ...]] = (
    "document_id",
    "company",
    "expected_form_type",
    "expected_reporting_period",
    "relative_source_path",
    "file_exists",
    "file_size_bytes",
    "sha256",
    "detected_company",
    "detected_form_type",
    "detected_reporting_period",
    "extracted_character_count",
    "extracted_word_count",
    "detected_financial_sections",
    "identity_check",
    "extraction_check",
    "table_quality_check",
    "overall_status",
    "warnings",
)

ERROR_PATTERNS: Final[tuple[str, ...]] = (
    "your request originates from an undeclared automated tool",
    "access denied",
    "document not found",
    "page not found",
    "request rate threshold exceeded",
    "sec.gov | your request",
)

SECTION_PATTERNS: Final[dict[str, tuple[str, ...]]] = {
    "income_statement": (
        r"(?:consolidated\s+)?statements?\s+of\s+(?:operations|income|earnings)",
        r"income\s+statements?",
    ),
    "balance_sheet": (
        r"(?:consolidated\s+)?balance\s+sheets?",
        r"statements?\s+of\s+financial\s+position",
    ),
    "cash_flow_statement": (
        r"(?:consolidated\s+)?statements?\s+of\s+cash\s+flows?",
        r"cash\s+flow\s+statements?",
        r"cash\s+flows\s+statements?",
    ),
    "risk_factors": (r"risk\s+factors",),
    "management_discussion_and_analysis": (
        r"management[’'`s\s]+discussion\s+and\s+analysis",
        r"management discussion and analysis",
    ),
}


@dataclass(frozen=True)
class DocumentSpec:
    """Expected identity and location of one source filing."""

    document_id: str
    company: str
    expected_form_type: str
    expected_reporting_period: str
    relative_source_path: str


@dataclass
class VerificationResult:
    """Manifest fields plus short report-only excerpts."""

    document_id: str
    company: str
    expected_form_type: str
    expected_reporting_period: str
    relative_source_path: str
    file_exists: bool
    file_size_bytes: int
    sha256: str
    detected_company: str
    detected_form_type: str
    detected_reporting_period: str
    extracted_character_count: int
    extracted_word_count: int
    detected_financial_sections: str
    identity_check: str
    extraction_check: str
    table_quality_check: str
    overall_status: str
    warnings: str
    identity_excerpt: str = ""
    financial_excerpt: str = ""

    def manifest_row(self) -> dict[str, object]:
        """Return exactly the stable public CSV schema."""

        values = asdict(self)
        return {column: values[column] for column in MANIFEST_COLUMNS}


EXPECTED_DOCUMENTS: Final[tuple[DocumentSpec, ...]] = (
    DocumentSpec(
        "msft-2022-10k",
        "Microsoft",
        "10-K",
        "2022-06-30",
        "data/raw/sec_filings/Microsoft/MSFT_2022_10K.html",
    ),
    DocumentSpec(
        "msft-2023-10k",
        "Microsoft",
        "10-K",
        "2023-06-30",
        "data/raw/sec_filings/Microsoft/MSFT_2023_10K.html",
    ),
    DocumentSpec(
        "msft-2024-10k",
        "Microsoft",
        "10-K",
        "2024-06-30",
        "data/raw/sec_filings/Microsoft/MSFT_2024_10K.html",
    ),
    DocumentSpec(
        "msft-fy2024-q1-10q",
        "Microsoft",
        "10-Q",
        "2023-09-30",
        "data/raw/sec_filings/Microsoft/MSFT_FY2024_Q1_10Q.html",
    ),
    DocumentSpec(
        "msft-fy2024-q2-10q",
        "Microsoft",
        "10-Q",
        "2023-12-31",
        "data/raw/sec_filings/Microsoft/MSFT_FY2024_Q2_10Q.html",
    ),
    DocumentSpec(
        "aapl-2022-10k",
        "Apple",
        "10-K",
        "2022-09-24",
        "data/raw/sec_filings/Apple/AAPL_2022_10K.html",
    ),
    DocumentSpec(
        "aapl-2023-10k",
        "Apple",
        "10-K",
        "2023-09-30",
        "data/raw/sec_filings/Apple/AAPL_2023_10K.html",
    ),
    DocumentSpec(
        "aapl-2024-10k",
        "Apple",
        "10-K",
        "2024-09-28",
        "data/raw/sec_filings/Apple/AAPL_2024_10K.html",
    ),
    DocumentSpec(
        "aapl-fy2024-q1-10q",
        "Apple",
        "10-Q",
        "2023-12-30",
        "data/raw/sec_filings/Apple/AAPL_FY2024_Q1_10Q.html",
    ),
    DocumentSpec(
        "aapl-fy2024-q2-10q",
        "Apple",
        "10-Q",
        "2024-03-30",
        "data/raw/sec_filings/Apple/AAPL_FY2024_Q2_10Q.html",
    ),
)


def _normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def _xbrl_value(soup: BeautifulSoup, concept: str) -> str:
    target = concept.lower()
    for tag in soup.find_all(attrs={"name": True}):
        name = str(tag.get("name", "")).lower()
        if name == target or name.endswith(f":{target}"):
            return _normalize_text(tag.get_text(" ", strip=True))
    return ""


def _detect_company(soup: BeautifulSoup, text: str) -> str:
    xbrl_name = _xbrl_value(soup, "entityregistrantname")
    candidate = xbrl_name or text[:50_000]
    if re.search(r"\bMicrosoft Corporation\b", candidate, re.IGNORECASE):
        return "Microsoft"
    if re.search(r"\bApple Inc\.?\b", candidate, re.IGNORECASE):
        return "Apple"
    return _normalize_text(xbrl_name)[:100]


def _detect_form_type(soup: BeautifulSoup, text: str) -> str:
    candidate = _xbrl_value(soup, "documenttype")
    match = re.search(r"10\s*[-–]\s*([KQ])", candidate or text[:30_000], re.IGNORECASE)
    return f"10-{match.group(1).upper()}" if match else ""


def _normalize_date(value: str) -> str:
    cleaned = _normalize_text(value).replace("Sept.", "Sep").replace("Sept ", "Sep ")
    for pattern in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(cleaned, pattern).date().isoformat()
        except ValueError:
            continue
    match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", cleaned)
    return match.group(1) if match else ""


def _detect_reporting_period(soup: BeautifulSoup, text: str) -> str:
    xbrl_period = _xbrl_value(soup, "documentperiodenddate")
    normalized = _normalize_date(xbrl_period)
    if normalized:
        return normalized
    match = re.search(
        r"(?:fiscal year|quarter|three months|six months)\s+ended\s+"
        r"([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})",
        text[:50_000],
        re.IGNORECASE,
    )
    return _normalize_date(match.group(1)) if match else ""


def _is_hidden(tag: Tag) -> bool:
    name = (tag.name or "").lower()
    style = str(tag.get("style", "")).lower().replace(" ", "")
    return (
        name in {"script", "style", "noscript", "template", "head", "ix:hidden"}
        or tag.has_attr("hidden")
        or str(tag.get("aria-hidden", "")).lower() == "true"
        or "display:none" in style
        or "visibility:hidden" in style
    )


def extract_visible_text(soup: BeautifulSoup) -> tuple[str, list[str]]:
    """Remove non-visible nodes and return normalized text plus original text blocks."""

    for tag in list(soup.find_all(True)):
        if tag.parent is not None and _is_hidden(tag):
            tag.decompose()
    blocks = [_normalize_text(value) for value in soup.stripped_strings]
    blocks = [value for value in blocks if value]
    return _normalize_text(" ".join(blocks)), blocks


def detect_financial_sections(text: str) -> list[str]:
    """Return canonical section labels detected through conservative heading patterns."""

    return [
        name
        for name, patterns in SECTION_PATTERNS.items()
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)
    ]


def _assess_tables(soup: BeautifulSoup) -> tuple[str, int, str]:
    useful = 0
    candidates: list[str] = []
    label_pattern = re.compile(
        r"(net (?:sales|revenue|income)|total assets|total liabilities|"
        r"cash (?:and cash |)equivalents|"
        r"operating activities|statements? of (?:operations|income|cash flows))",
        re.IGNORECASE,
    )
    numeric_pattern = re.compile(r"(?:\$\s*)?\(?\d[\d,]*(?:\.\d+)?\)?%?")
    for table in soup.find_all("table"):
        table_text = _normalize_text(table.get_text(" ", strip=True))
        if label_pattern.search(table_text) and len(numeric_pattern.findall(table_text)) >= 5:
            useful += 1
            candidates.append(table_text)
    statement_heading = re.compile(
        r"(?:consolidated\s+)?statements?\s+of\s+(?:operations|income|cash\s+flows?)|"
        r"(?:income|cash\s+flows?)\s+statements?|balance\s+sheets?",
        re.IGNORECASE,
    )
    best_candidate = next(
        (candidate for candidate in candidates if statement_heading.search(candidate)),
        candidates[0] if candidates else "",
    )
    excerpt = f"{best_candidate[:360]}…" if len(best_candidate) > 360 else best_candidate
    if useful >= 2:
        return "PASS", useful, excerpt
    if useful == 1:
        return "REVIEW", useful, excerpt
    return "FAIL", 0, "Not detected."


def _duplicate_ratio(blocks: Iterable[str]) -> float:
    long_blocks = [block for block in blocks if len(block) >= 120]
    if not long_blocks:
        return 0.0
    counts = Counter(long_blocks)
    duplicate_chars = sum((count - 1) * len(block) for block, count in counts.items() if count > 1)
    return duplicate_chars / sum(len(block) for block in long_blocks)


def _excerpt(text: str, pattern: str, radius: int = 180) -> str:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return "Not detected."
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    prefix = "…" if start else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{_normalize_text(text[start:end])}{suffix}"


def _missing_result(spec: DocumentSpec, warning: str) -> VerificationResult:
    return VerificationResult(
        **asdict(spec),
        file_exists=False,
        file_size_bytes=0,
        sha256="",
        detected_company="",
        detected_form_type="",
        detected_reporting_period="",
        extracted_character_count=0,
        extracted_word_count=0,
        detected_financial_sections="",
        identity_check="FAIL",
        extraction_check="FAIL",
        table_quality_check="FAIL",
        overall_status="FAIL",
        warnings=warning,
    )


def verify_document(project_root: Path, spec: DocumentSpec) -> VerificationResult:
    """Verify one expected source without modifying it or its companion directory."""

    source = project_root / Path(spec.relative_source_path)
    if not source.is_file():
        return _missing_result(spec, "Source file is missing.")
    size = source.stat().st_size
    if size == 0:
        return _missing_result(spec, "Source file exists but is empty.")

    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    warnings: list[str] = []
    try:
        soup = BeautifulSoup(raw, "lxml")
        metadata_soup = BeautifulSoup(raw, "lxml")
        text, blocks = extract_visible_text(soup)
    except Exception as exc:  # parser errors must become a row, not abort the batch
        result = _missing_result(spec, f"HTML parsing failed: {type(exc).__name__}: {exc}")
        result.file_exists = True
        result.file_size_bytes = size
        result.sha256 = digest
        return result

    company = _detect_company(metadata_soup, text)
    form_type = _detect_form_type(metadata_soup, text)
    period = _detect_reporting_period(metadata_soup, text)
    sections = detect_financial_sections(text)
    table_check, useful_tables, financial_excerpt = _assess_tables(soup)
    word_count = len(re.findall(r"\b[\w’'-]+\b", text, re.UNICODE))
    replacement_count = text.count("�")
    duplicate_ratio = _duplicate_ratio(blocks)
    first_text = text[:20_000].lower()
    error_messages = [message for message in ERROR_PATTERNS if message in first_text]

    if error_messages:
        warnings.append(f"SEC viewer/error content detected: {error_messages[0]}.")
    if len(text) < 10_000:
        warnings.append("Extracted text is unusually short for an SEC filing.")
    if word_count and len(text) / word_count < 2.5:
        warnings.append("Extracted text has an unusually low character-to-word ratio.")
    if replacement_count:
        warnings.append(f"Extracted text contains {replacement_count} replacement character(s).")
    if b"</html" not in raw[-20_000:].lower():
        warnings.append("Closing HTML marker was not found near the end; truncation needs review.")
    if duplicate_ratio >= 0.10:
        warnings.append(
            f"Repeated long text blocks are suspicious ({duplicate_ratio:.1%} duplicate ratio)."
        )
    if len(sections) < len(SECTION_PATTERNS):
        missing = sorted(set(SECTION_PATTERNS) - set(sections))
        warnings.append(f"Expected section heading(s) not detected: {', '.join(missing)}.")
    if useful_tables == 0:
        warnings.append(
            "No financial table with both expected labels and multiple numeric values found."
        )
    elif useful_tables == 1:
        warnings.append("Only one financial table candidate passed automated label/numeric checks.")

    company_match = company == spec.company
    form_match = form_type == spec.expected_form_type
    period_match = period == spec.expected_reporting_period
    if company and not company_match:
        warnings.append(f"Detected company {company!r} does not match expected {spec.company!r}.")
    if form_type and not form_match:
        warnings.append(
            f"Detected form type {form_type!r} does not match expected {spec.expected_form_type!r}."
        )
    if period and not period_match:
        warnings.append(
            f"Detected period {period!r} does not match expected "
            f"{spec.expected_reporting_period!r}."
        )

    has_identity_mismatch = (
        (company and not company_match)
        or (form_type and not form_match)
        or (period and not period_match)
    )
    if has_identity_mismatch:
        identity_check = "FAIL"
    elif company_match and form_match and period_match:
        identity_check = "PASS"
    else:
        identity_check = "REVIEW"
        missing_identity = [
            label
            for label, value in (("company", company), ("form type", form_type), ("period", period))
            if not value
        ]
        warnings.append(f"Identity value(s) not detected: {', '.join(missing_identity)}.")

    if error_messages or len(text) < 1_000:
        extraction_check = "FAIL"
    elif (
        len(text) < 50_000
        or len(sections) < 4
        or replacement_count > 10
        or duplicate_ratio >= 0.10
    ):
        extraction_check = "REVIEW"
    else:
        extraction_check = "PASS"

    checks = (identity_check, extraction_check, table_check)
    if "FAIL" in checks:
        overall = "FAIL"
    elif "REVIEW" in checks:
        overall = "REVIEW"
    else:
        overall = "PASS"

    heading_excerpt = _excerpt(
        text,
        r"(?:index\s+to\s+(?:consolidated\s+)?financial\s+statements|"
        r"(?:consolidated\s+)?statements?\s+of\s+(?:operations|income|cash\s+flows?)|"
        r"balance\s+sheets?\s+\(in\s+millions)",
    )
    if heading_excerpt == "Not detected.":
        heading_excerpt = financial_excerpt

    return VerificationResult(
        **asdict(spec),
        file_exists=True,
        file_size_bytes=size,
        sha256=digest,
        detected_company=company,
        detected_form_type=form_type,
        detected_reporting_period=period,
        extracted_character_count=len(text),
        extracted_word_count=word_count,
        detected_financial_sections=";".join(sections),
        identity_check=identity_check,
        extraction_check=extraction_check,
        table_quality_check=table_check,
        overall_status=overall,
        warnings="; ".join(warnings),
        identity_excerpt=_excerpt(
            text,
            r"(?:FORM\s+10-[KQ]|ANNUAL REPORT|QUARTERLY REPORT)",
        ),
        financial_excerpt=heading_excerpt,
    )


def verify_corpus(
    project_root: Path,
    specs: Iterable[DocumentSpec] = EXPECTED_DOCUMENTS,
) -> list[VerificationResult]:
    """Verify every expected document, preserving input order even when files are missing."""

    return [verify_document(project_root, spec) for spec in specs]


def write_manifest(path: Path, results: Iterable[VerificationResult]) -> None:
    """Write the stable CSV schema."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(result.manifest_row() for result in results)


def _md(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_report(results: list[VerificationResult]) -> str:
    """Render a concise report that never includes full filing content."""

    counts = Counter(result.overall_status for result in results)
    lines = [
        "# SEC Document Verification Report",
        "",
        "## Method",
        "",
        "This offline check reads each expected HTML source as bytes, records its size and "
        "SHA-256, parses it with Beautiful Soup using lxml, removes non-visible/hidden nodes, "
        "and normalizes "
        "visible text. Filing identity is detected preferentially from inline-XBRL DEI facts and "
        "cross-checked against expected company, form, and period. Section, error-page, encoding, "
        "truncation, duplication, and table-label/numeric heuristics assess extraction quality.",
        "",
        "Automated checks do **not** prove that table rows, dates, columns, or every numeric value "
        "remain correctly associated. Those relationships require manual review before ingestion.",
        "",
        "## Summary",
        "",
        f"- PASS: {counts['PASS']}",
        f"- REVIEW: {counts['REVIEW']}",
        f"- FAIL: {counts['FAIL']}",
        "",
        "| Document | Exists | Identity | Extraction | Tables | Overall | Sections | Warnings |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in results:
        sections = result.detected_financial_sections.replace(";", ", ") or "None detected"
        warnings = result.warnings or "None from automated checks"
        lines.append(
            f"| `{_md(result.document_id)}` | {_md(result.file_exists)} | "
            f"{_md(result.identity_check)} | {_md(result.extraction_check)} | "
            f"{_md(result.table_quality_check)} | **{_md(result.overall_status)}** | "
            f"{_md(sections)} | {_md(warnings)} |"
        )

    lines.extend(["", "## Document findings", ""])
    for result in results:
        lines.extend(
            [
                f"### {result.document_id} — {result.overall_status}",
                "",
                f"- Source: `{result.relative_source_path}`",
                f"- Size / SHA-256: {result.file_size_bytes:,} bytes / "
                f"`{result.sha256 or 'not available'}`",
                f"- Expected identity: {result.company}, {result.expected_form_type}, "
                f"period ended {result.expected_reporting_period}",
                f"- Detected identity: {result.detected_company or 'not detected'}, "
                f"{result.detected_form_type or 'not detected'}, "
                f"{result.detected_reporting_period or 'not detected'}",
                f"- Extracted text: {result.extracted_character_count:,} characters; "
                f"{result.extracted_word_count:,} words",
                f"- Sections: {result.detected_financial_sections.replace(';', ', ') or 'none'}",
                f"- Warnings: {result.warnings or 'none from automated checks'}",
                f"- Identity excerpt: “{_md(result.identity_excerpt)}”",
                f"- Financial-heading excerpt: “{_md(result.financial_excerpt)}”",
                "",
            ]
        )

    failures = [result for result in results if result.overall_status == "FAIL"]
    reviews = [result for result in results if result.overall_status == "REVIEW"]
    if failures:
        recommendation = (
            "Not ready for ingestion: resolve all FAIL findings and rerun verification."
        )
    elif reviews:
        names = ", ".join(result.document_id for result in reviews)
        recommendation = f"Ready only after specific review/fixes for: {names}."
    else:
        recommendation = (
            "Automated checks indicate the corpus is ready for the next ingestion-design step, "
            "subject to manual spot-checking of financial table label/date/value relationships."
        )
    lines.extend(
        [
            "## Manual checks outstanding",
            "",
            "- Open each source locally and compare at least one income statement, balance sheet, "
            "and cash-flow table against the extracted ordering.",
            "- Confirm column headers, units, signs/parentheses, dates, and row/value alignment.",
            "- Confirm that browser-saved companion resources are not required for textual "
            "meaning.",
            "- Treat automated heading detection as evidence of presence, not completeness.",
            "",
            "## Recommendation",
            "",
            recommendation,
            "",
        ]
    )
    return "\n".join(lines)


def write_report(path: Path, results: list[VerificationResult]) -> None:
    """Write the Markdown verification report."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(results), encoding="utf-8", newline="\n")


def run_verification(project_root: Path) -> tuple[Path, Path, list[VerificationResult]]:
    """Regenerate both permitted verification artifacts and return their paths/results."""

    root = project_root.resolve()
    output_dir = root / "data" / "processed" / "document_verification"
    manifest_path = output_dir / "document_manifest.csv"
    report_path = output_dir / "document_verification_report.md"
    results = verify_corpus(root)
    write_manifest(manifest_path, results)
    write_report(report_path, results)
    return manifest_path, report_path, results


def manifest_field_names() -> tuple[str, ...]:
    """Expose the output contract for tests and downstream review."""

    dataclass_names = {field.name for field in fields(VerificationResult)}
    assert set(MANIFEST_COLUMNS) <= dataclass_names
    return MANIFEST_COLUMNS
