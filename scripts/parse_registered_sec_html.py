"""Parse only currently VALID registered SEC HTML sources into structured local artifacts."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(DEFAULT_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(DEFAULT_PROJECT_ROOT))


def main(argv: list[str] | None = None) -> int:
    """Run local parsing and return nonzero if any source is invalid or quarantined."""

    from app.ingestion.loaders.sec_manifest import ManifestValidationError
    from app.ingestion.parsers.sec_html_parser import run_parser

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument(
        "--manifest", type=Path, default=Path("data/manifests/sec_documents.v1.json")
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    manifest = args.manifest if args.manifest.is_absolute() else root / args.manifest
    output = (
        args.output_dir
        if args.output_dir is None or args.output_dir.is_absolute()
        else root / args.output_dir
    )
    try:
        artifacts, _, destination = run_parser(root, manifest, output)
    except (ManifestValidationError, ValueError, OSError) as exc:
        print(f"Parser setup failed: {exc}", file=sys.stderr)
        return 2
    counts = Counter(artifact["parse_status"] for artifact in artifacts)
    narrative = sum(len(artifact.get("narrative_blocks", [])) for artifact in artifacts)
    tables = sum(len(artifact.get("tables", [])) for artifact in artifacts)
    quarantined = sum(len(artifact.get("quarantined_tables", [])) for artifact in artifacts)
    warnings = sum(len(artifact.get("warnings", [])) for artifact in artifacts)
    print(f"Parsed {len(artifacts)} registered document(s): {dict(sorted(counts.items()))}")
    print(
        f"Narrative blocks: {narrative}; tables: {tables}; warnings: {warnings}; "
        f"quarantined tables: {quarantined}"
    )
    print(f"Output: {destination}")
    blocking = {"MISSING", "CHANGED", "UNREADABLE", "INVALID_PATH", "QUARANTINED"}
    return 1 if any(artifact["parse_status"] in blocking for artifact in artifacts) else 0


if __name__ == "__main__":
    raise SystemExit(main())
