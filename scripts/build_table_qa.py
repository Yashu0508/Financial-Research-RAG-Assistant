"""Build the offline financial-table QA review package from verified local filings."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(DEFAULT_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(DEFAULT_PROJECT_ROOT))


def main() -> int:
    from app.ingestion.validation.financial_table_qa import build_review_package

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=DEFAULT_PROJECT_ROOT,
        help="Repository root (defaults to the parent of scripts/).",
    )
    args = parser.parse_args()
    checks, paths = build_review_package(args.project_root)
    counts = Counter(check.source_table_status for check in checks)
    print(f"Prepared {len(checks)} pending human checks: {dict(sorted(counts.items()))}")
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
