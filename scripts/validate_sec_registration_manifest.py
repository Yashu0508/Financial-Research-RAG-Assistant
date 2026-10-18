"""Validate the versioned SEC registration manifest and immutable local source bytes."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(DEFAULT_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(DEFAULT_PROJECT_ROOT))


def main(argv: list[str] | None = None) -> int:
    """Return nonzero for invalid manifest data or non-matching registered sources."""

    from app.ingestion.loaders.sec_manifest import (
        ManifestValidationError,
        check_registered_sources,
        load_registration_manifest,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/manifests/sec_documents.v1.json"),
        help="Project-relative manifest path unless absolute.",
    )
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest
    try:
        manifest = load_registration_manifest(manifest_path)
    except ManifestValidationError as exc:
        print(f"Manifest validation failed: {exc}", file=sys.stderr)
        return 2
    checks = check_registered_sources(root, manifest)
    counts = Counter(check.status for check in checks)
    print(
        f"Manifest {manifest.manifest_id} (schema {manifest.schema_version}): "
        f"{len(manifest.documents)} registered document(s)."
    )
    print(f"Source status counts: {dict(sorted(counts.items()))}")
    for check in checks:
        if not check.is_valid:
            print(
                f"{check.document_id}: {check.status} — {' '.join(check.diagnostics)}",
                file=sys.stderr,
            )
    return 0 if all(check.is_valid for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
