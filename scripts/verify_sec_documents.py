"""Regenerate local SEC source-verification artifacts without network access."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(DEFAULT_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(DEFAULT_PROJECT_ROOT))


def main() -> int:
    from app.ingestion.validation.sec_document_verifier import run_verification

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=DEFAULT_PROJECT_ROOT,
        help="Repository root (defaults to the parent of scripts/).",
    )
    args = parser.parse_args()

    manifest, report, results = run_verification(args.project_root)
    counts = Counter(result.overall_status for result in results)
    print(f"Verified {len(results)} expected documents: {dict(sorted(counts.items()))}")
    print(f"Manifest: {manifest}")
    print(f"Report: {report}")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
