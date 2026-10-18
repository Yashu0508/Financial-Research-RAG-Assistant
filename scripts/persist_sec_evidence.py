"""Persist existing approved Phase 3 evidence into configured PostgreSQL storage."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_approved_evidence() -> tuple[object, dict[str, object], list[dict[str, object]]]:
    """Load only manifest-approved sources and hash-verified evidence artifacts."""

    from app.ingestion.loaders.sec_manifest import (
        check_registered_sources,
        load_registration_manifest,
    )

    manifest = load_registration_manifest(ROOT / "data/manifests/sec_documents.v1.json")
    invalid = [check for check in check_registered_sources(ROOT, manifest) if not check.is_valid]
    if invalid:
        raise ValueError(
            "Registered source validation failed: "
            + ", ".join(item.document_id for item in invalid)
        )
    evidence_dir = ROOT / "data/processed/sec_evidence/v1"
    metadata = json.loads((evidence_dir / "run_metadata.json").read_text(encoding="utf-8"))
    artifacts: list[dict[str, object]] = []
    for document in manifest.documents:
        content = (evidence_dir / f"{document.document_id}.json").read_text(encoding="utf-8")
        if hashlib.sha256(content.encode()).hexdigest() != metadata["artifact_sha256"].get(
            document.document_id
        ):
            raise ValueError(f"Evidence artifact hash mismatch: {document.document_id}")
        artifacts.append(json.loads(content))
    return manifest, metadata, artifacts


def main() -> int:
    from app.core.config import get_settings
    from app.storage.development import (
        DevelopmentDatabaseError,
        development_target_from_settings,
        prepare_development_connection,
    )

    settings = get_settings()
    try:
        target = development_target_from_settings(settings)
    except DevelopmentDatabaseError as exc:
        print(f"Development target validation failed: {exc}", file=sys.stderr)
        return 2
    try:
        manifest, metadata, artifacts = load_approved_evidence()
    except (OSError, ValueError, KeyError) as exc:
        print(f"Evidence input validation failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    try:
        import psycopg
    except ImportError:
        print(
            "PostgreSQL driver is not installed; install the storage optional dependency.",
            file=sys.stderr,
        )
        return 2
    from app.storage.repositories.evidence_repository import (
        PostgresEvidenceRepository,
        StorageError,
    )

    try:
        with psycopg.connect(settings.database_url) as connection:
            prepare_development_connection(
                connection, target, create_schema=False
            )
            result = PostgresEvidenceRepository(connection).persist_run(
                manifest, metadata, artifacts
            )
    except (DevelopmentDatabaseError, OSError, ValueError, StorageError) as exc:
        print(f"Evidence persistence failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(
        f"Run {result.run_id}; inserted={result.inserted}; narratives={result.narrative_count}; tables={result.table_count}; quarantines={result.quarantine_count}"  # noqa: E501
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
