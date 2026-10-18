"""Versioned SEC registration manifest validation and immutable local source checks."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Final

MANIFEST_SCHEMA_VERSION: Final = "1.0"
ALLOWED_PROCESSING_STATUSES: Final = frozenset({"registered"})
SHA256_PATTERN: Final = re.compile(r"^[0-9a-f]{64}$")
DOCUMENT_ID_PATTERN: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ManifestValidationError(ValueError):
    """Raised when a registration manifest cannot safely be used."""


@dataclass(frozen=True)
class RegistrationMetadata:
    """Registration facts without fabricating unavailable acquisition data."""

    registered_at: str | None
    acquisition_timestamp: str | None
    notes: str


@dataclass(frozen=True)
class RegisteredDocument:
    """One immutable local SEC source registration."""

    document_id: str
    company: str
    ticker: str
    form_type: str
    filing_date: str | None
    reporting_period_end: str
    fiscal_year: int | None
    fiscal_quarter: int | None
    official_sec_source_url: str | None
    local_source_path: str
    source_sha256: str
    source_byte_size: int
    registration: RegistrationMetadata
    processing_status: str
    validation_warnings: tuple[str, ...]


@dataclass(frozen=True)
class RegistrationManifest:
    """A validated, versioned collection of immutable source registrations."""

    schema_version: str
    manifest_id: str
    documents: tuple[RegisteredDocument, ...]


@dataclass(frozen=True)
class LocalSourceCheck:
    """Result of comparing one registered source with its registered bytes."""

    document_id: str
    local_source_path: str
    status: str
    expected_sha256: str
    actual_sha256: str | None
    expected_byte_size: int
    actual_byte_size: int | None
    diagnostics: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        """Return whether the local source still matches its registration."""

        return self.status == "VALID"


def _require_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ManifestValidationError(f"{key} must be a non-empty string.")
    return value.strip()


def _optional_date(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ManifestValidationError(f"{field_name} must be an ISO date or null.")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ManifestValidationError(f"{field_name} must be an ISO date or null.") from exc


def _safe_relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.parts[:3] != ("data", "raw", "sec_filings"):
        raise ManifestValidationError(
            "local_source_path must be a safe project-relative path under data/raw/sec_filings."
        )
    if "\\" in value or path.suffix.lower() not in {".html", ".htm"}:
        raise ManifestValidationError(
            "local_source_path must name an HTML file using forward slashes."
        )
    return path.as_posix()


def _registration_metadata(payload: object) -> RegistrationMetadata:
    if not isinstance(payload, dict):
        raise ManifestValidationError("registration must be an object.")
    notes = _require_string(payload, "notes")
    registered_at = payload.get("registered_at")
    acquisition_timestamp = payload.get("acquisition_timestamp")
    for key, value in (
        ("registered_at", registered_at),
        ("acquisition_timestamp", acquisition_timestamp),
    ):
        if value is not None and not isinstance(value, str):
            raise ManifestValidationError(f"registration.{key} must be a string or null.")
    return RegistrationMetadata(registered_at, acquisition_timestamp, notes)


def _document_from_payload(payload: object) -> RegisteredDocument:
    if not isinstance(payload, dict):
        raise ManifestValidationError("Each document entry must be an object.")
    document_id = _require_string(payload, "document_id")
    if not DOCUMENT_ID_PATTERN.fullmatch(document_id):
        raise ManifestValidationError("document_id must be lowercase kebab-case.")
    source_sha256 = _require_string(payload, "source_sha256").lower()
    if not SHA256_PATTERN.fullmatch(source_sha256):
        raise ManifestValidationError("source_sha256 must be a lowercase SHA-256 hex digest.")
    size = payload.get("source_byte_size")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise ManifestValidationError("source_byte_size must be a positive integer.")
    fiscal_year = payload.get("fiscal_year")
    if fiscal_year is not None and (
        not isinstance(fiscal_year, int) or isinstance(fiscal_year, bool)
    ):
        raise ManifestValidationError("fiscal_year must be an integer or null.")
    fiscal_quarter = payload.get("fiscal_quarter")
    if fiscal_quarter is not None and fiscal_quarter not in {1, 2, 3, 4}:
        raise ManifestValidationError("fiscal_quarter must be 1 through 4 or null.")
    source_url = payload.get("official_sec_source_url")
    if source_url is not None and (
        not isinstance(source_url, str) or not source_url.startswith("https://www.sec.gov/")
    ):
        raise ManifestValidationError("official_sec_source_url must be an SEC HTTPS URL or null.")
    warnings = payload.get("validation_warnings", [])
    if not isinstance(warnings, list) or not all(isinstance(item, str) for item in warnings):
        raise ManifestValidationError("validation_warnings must be a list of strings.")
    status = _require_string(payload, "processing_status")
    if status not in ALLOWED_PROCESSING_STATUSES:
        raise ManifestValidationError(f"Unsupported processing_status: {status!r}.")
    ticker = _require_string(payload, "ticker").upper()
    if not re.fullmatch(r"[A-Z]{1,8}", ticker):
        raise ManifestValidationError("ticker must contain one to eight uppercase letters.")
    return RegisteredDocument(
        document_id=document_id,
        company=_require_string(payload, "company"),
        ticker=ticker,
        form_type=_require_string(payload, "form_type"),
        filing_date=_optional_date(payload.get("filing_date"), "filing_date"),
        reporting_period_end=_optional_date(
            _require_string(payload, "reporting_period_end"), "reporting_period_end"
        ) or "",
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        official_sec_source_url=source_url,
        local_source_path=_safe_relative_path(_require_string(payload, "local_source_path")),
        source_sha256=source_sha256,
        source_byte_size=size,
        registration=_registration_metadata(payload.get("registration")),
        processing_status=status,
        validation_warnings=tuple(warnings),
    )


def load_registration_manifest(path: Path) -> RegistrationManifest:
    """Load and validate a manifest without reading any registered source file."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestValidationError(f"Manifest file is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestValidationError(f"Manifest is not valid JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ManifestValidationError("Manifest root must be an object.")
    version = _require_string(payload, "schema_version")
    if version != MANIFEST_SCHEMA_VERSION:
        raise ManifestValidationError(
            f"Unsupported manifest schema version {version!r}; "
            f"expected {MANIFEST_SCHEMA_VERSION!r}."
        )
    documents_payload = payload.get("documents")
    if not isinstance(documents_payload, list) or not documents_payload:
        raise ManifestValidationError("documents must be a non-empty list.")
    documents = tuple(_document_from_payload(item) for item in documents_payload)
    document_ids = [document.document_id for document in documents]
    paths = [document.local_source_path for document in documents]
    if len(document_ids) != len(set(document_ids)):
        raise ManifestValidationError("Duplicate document_id values are not allowed.")
    if len(paths) != len(set(paths)):
        raise ManifestValidationError("Duplicate local_source_path values are not allowed.")
    return RegistrationManifest(version, _require_string(payload, "manifest_id"), documents)


def check_registered_source(project_root: Path, document: RegisteredDocument) -> LocalSourceCheck:
    """Read a single approved local source and compare it to immutable registration facts."""

    root = project_root.resolve()
    source = (root / Path(document.local_source_path)).resolve()
    raw_root = (root / "data" / "raw" / "sec_filings").resolve()
    if raw_root not in source.parents:
        return LocalSourceCheck(
            document.document_id,
            document.local_source_path,
            "INVALID_PATH",
            document.source_sha256,
            None,
            document.source_byte_size,
            None,
            ("Registered source path escapes the approved raw SEC directory.",),
        )
    try:
        raw = source.read_bytes()
    except FileNotFoundError:
        return LocalSourceCheck(
            document.document_id, document.local_source_path, "MISSING", document.source_sha256,
            None, document.source_byte_size, None, ("Registered local source file is missing.",)
        )
    except OSError as exc:
        return LocalSourceCheck(
            document.document_id,
            document.local_source_path,
            "UNREADABLE",
            document.source_sha256,
            None,
            document.source_byte_size,
            None,
            (f"Registered local source is unreadable: {type(exc).__name__}.",),
        )
    actual_size = len(raw)
    actual_hash = hashlib.sha256(raw).hexdigest()
    diagnostics: list[str] = []
    if actual_size != document.source_byte_size:
        diagnostics.append("Byte size differs from the immutable registration.")
    if actual_hash != document.source_sha256:
        diagnostics.append("SHA-256 differs from the immutable registration.")
    status = "VALID" if not diagnostics else "CHANGED"
    return LocalSourceCheck(
        document.document_id,
        document.local_source_path,
        status,
        document.source_sha256,
        actual_hash,
        document.source_byte_size,
        actual_size,
        tuple(diagnostics),
    )


def check_registered_sources(
    project_root: Path,
    manifest: RegistrationManifest,
) -> tuple[LocalSourceCheck, ...]:
    """Check every registered source in manifest order without mutation or network access."""

    return tuple(check_registered_source(project_root, document) for document in manifest.documents)
