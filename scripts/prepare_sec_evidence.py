"""Prepare deterministic evidence from approved SEC parser artifacts."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(DEFAULT_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(DEFAULT_PROJECT_ROOT))


def main(argv: list[str] | None = None) -> int:
    """Return nonzero if an evidence document is quarantined or setup is invalid."""

    from app.ingestion.chunking.sec_evidence_chunker import run_evidence_preparation
    from app.ingestion.loaders.sec_manifest import ManifestValidationError

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument(
        "--manifest", type=Path, default=Path("data/manifests/sec_documents.v1.json")
    )
    parser.add_argument("--parser-dir", type=Path, default=Path("data/processed/sec_parsed/v1"))
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    manifest = args.manifest if args.manifest.is_absolute() else root / args.manifest
    parser_dir = args.parser_dir if args.parser_dir.is_absolute() else root / args.parser_dir
    output = (
        args.output_dir
        if args.output_dir is None or args.output_dir.is_absolute()
        else root / args.output_dir
    )
    try:
        artifacts, metadata, destination = run_evidence_preparation(
            root, manifest, parser_dir, output
        )
    except (ManifestValidationError, ValueError, OSError) as exc:
        print(f"Evidence preparation failed: {exc}", file=sys.stderr)
        return 2
    counts = Counter(artifact["admission_status"] for artifact in artifacts)
    narrative = sum(len(artifact.get("narrative_chunks", [])) for artifact in artifacts)
    tables = sum(len(artifact.get("table_evidence", [])) for artifact in artifacts)
    quarantined = sum(len(artifact.get("quarantined_evidence", [])) for artifact in artifacts)
    print(f"Evidence documents: {len(artifacts)}; admission: {dict(sorted(counts.items()))}")
    print(
        f"Narrative chunks: {narrative}; table evidence: {tables}; "
        f"quarantined records: {quarantined}"
    )
    print(
        f"Chunking configuration: {metadata['chunking_version']} / {metadata['configuration_hash']}"
    )
    print(f"Output: {destination}")
    blocking = {"QUARANTINED"}
    return 1 if any(artifact["admission_status"] in blocking for artifact in artifacts) else 0


if __name__ == "__main__":
    raise SystemExit(main())
