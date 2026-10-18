"""Tests for the versioned SEC registration contract and immutable source loader."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.ingestion.loaders.sec_manifest import (
    MANIFEST_SCHEMA_VERSION,
    ManifestValidationError,
    check_registered_sources,
    load_registration_manifest,
)


def _entry(
    path: str = "data/raw/sec_filings/Example/sample.html",
    content: bytes = b"source",
) -> dict:
    return {
        "document_id": "example-2024-10k",
        "company": "Example Corporation",
        "ticker": "EXMP",
        "form_type": "10-K",
        "filing_date": None,
        "reporting_period_end": "2024-12-31",
        "fiscal_year": None,
        "fiscal_quarter": None,
        "official_sec_source_url": None,
        "local_source_path": path,
        "source_sha256": hashlib.sha256(content).hexdigest(),
        "source_byte_size": len(content),
        "registration": {
            "registered_at": "2026-10-17T00:00:00Z",
            "acquisition_timestamp": None,
            "notes": "Synthetic unit-test registration.",
        },
        "processing_status": "registered",
        "validation_warnings": [
            "Official source URL is intentionally unavailable in this fixture."
        ],
    }


def _write_manifest(
    tmp_path: Path,
    entries: list[dict] | None = None,
    version: str = "1.0",
) -> Path:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": version,
                "manifest_id": "test-manifest",
                "documents": entries if entries is not None else [_entry()],
            }
        ),
        encoding="utf-8",
    )
    return manifest


def _write_source(tmp_path: Path, content: bytes = b"source") -> Path:
    source = tmp_path / "data/raw/sec_filings/Example/sample.html"
    source.parent.mkdir(parents=True)
    source.write_bytes(content)
    return source


def test_loads_valid_manifest_and_checks_matching_source(tmp_path: Path) -> None:
    _write_source(tmp_path)
    manifest = load_registration_manifest(_write_manifest(tmp_path))

    checks = check_registered_sources(tmp_path, manifest)

    assert manifest.schema_version == MANIFEST_SCHEMA_VERSION
    assert checks[0].status == "VALID"
    assert checks[0].actual_byte_size == len(b"source")


def test_rejects_unsupported_schema_version(tmp_path: Path) -> None:
    with pytest.raises(ManifestValidationError, match="Unsupported manifest schema version"):
        load_registration_manifest(_write_manifest(tmp_path, version="9.9"))


def test_rejects_duplicate_document_ids(tmp_path: Path) -> None:
    entry = _entry()
    with pytest.raises(ManifestValidationError, match="Duplicate document_id"):
        load_registration_manifest(_write_manifest(tmp_path, [entry, entry.copy()]))


def test_missing_and_changed_sources_are_explicit_without_manifest_repair(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path)
    manifest = load_registration_manifest(manifest_path)

    assert check_registered_sources(tmp_path, manifest)[0].status == "MISSING"

    source = _write_source(tmp_path, b"changed")
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    check = check_registered_sources(tmp_path, manifest)[0]

    assert check.status == "CHANGED"
    assert check.expected_sha256 != check.actual_sha256
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    registered_hash = json.loads(manifest_path.read_text(encoding="utf-8"))["documents"][0][
        "source_sha256"
    ]
    assert registered_hash != before


@pytest.mark.parametrize(
    "unsafe_path",
    ["../outside.html", "data/raw/sec_filings/Example/../../outside.html", "C:/outside.html"],
)
def test_rejects_unsafe_source_paths(tmp_path: Path, unsafe_path: str) -> None:
    with pytest.raises(ManifestValidationError, match="local_source_path"):
        load_registration_manifest(_write_manifest(tmp_path, [_entry(path=unsafe_path)]))


def test_repeated_checks_are_idempotent_and_do_not_mutate_source(tmp_path: Path) -> None:
    source = _write_source(tmp_path)
    manifest = load_registration_manifest(_write_manifest(tmp_path))
    before = source.read_bytes()

    first = check_registered_sources(tmp_path, manifest)
    second = check_registered_sources(tmp_path, manifest)

    assert first == second
    assert source.read_bytes() == before


def test_cli_exit_codes_and_diagnostics(tmp_path: Path) -> None:
    source = _write_source(tmp_path)
    manifest_path = _write_manifest(tmp_path)
    script = Path(__file__).resolve().parents[2] / "scripts/validate_sec_registration_manifest.py"
    command = [
        sys.executable,
        str(script),
        "--project-root",
        str(tmp_path),
        "--manifest",
        str(manifest_path),
    ]

    valid = subprocess.run(command, capture_output=True, text=True, check=False)
    assert valid.returncode == 0
    assert "VALID" in valid.stdout

    source.write_bytes(b"modified")
    changed = subprocess.run(command, capture_output=True, text=True, check=False)
    assert changed.returncode == 1
    assert "CHANGED" in changed.stderr

    manifest_path.write_text("{}", encoding="utf-8")
    invalid = subprocess.run(command, capture_output=True, text=True, check=False)
    assert invalid.returncode == 2
    assert "Manifest validation failed" in invalid.stderr
