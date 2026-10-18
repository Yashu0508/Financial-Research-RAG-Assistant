"""Evaluate deterministic recorded fixtures for grounded-answer contracts.

This never loads a provider SDK, database, embedding model, or credential.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    from app.evaluation.answers.grounded_answer_evaluation import (
        evaluate_grounded_answers,
        load_grounded_answer_dataset,
        validate_grounded_answer_references,
    )
    from app.generation.contracts import Citation, GenerationResponse, ValidationResult

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=Path("data/evaluation/grounded_answer_quality.v1.json")
    )
    args = parser.parse_args(argv)
    dataset = args.dataset if args.dataset.is_absolute() else ROOT / args.dataset
    evidence_directory = ROOT / "data/processed/sec_evidence/v1"
    try:
        validate_grounded_answer_references(dataset, evidence_directory)
        _, _, cases = load_grounded_answer_dataset(dataset)
        payload = json.loads(dataset.read_text(encoding="utf-8"))
        raw = {item["case_id"]: item for item in payload["cases"]}
        artifacts: dict[str, dict[str, object]] = {}
        responses = {}
        for case in cases:
            if case.status == "unanswerable":
                responses[case.case_id] = GenerationResponse(
                    "abstained",
                    "I cannot provide a supported answer from the available filing evidence.",
                    abstention_reason="NO_ELIGIBLE_EVIDENCE",
                )
                continue
            citations = []
            for reference in raw[case.case_id]["supporting_evidence"]:
                document_id = reference["document_id"]
                if document_id not in artifacts:
                    artifacts[document_id] = json.loads(
                        (evidence_directory / f"{document_id}.json").read_text(encoding="utf-8")
                    )
                chunk = next(
                    item
                    for item in artifacts[document_id]["narrative_chunks"]
                    if item["chunk_id"] == reference["chunk_id"]
                )
                citations.append(
                    Citation(
                        chunk["chunk_id"],
                        document_id,
                        chunk["source_sha256"],
                        None,
                        chunk["section_heading"],
                        chunk["source_elements"],
                        chunk["chunk_id"],
                    )
                )
            responses[case.case_id] = GenerationResponse(
                "answered",
                " ".join(case.required_factual_points),
                tuple(citations),
                ValidationResult(True),
            )
        report = evaluate_grounded_answers(dataset, responses)
    except Exception as exc:
        print(
            f"Grounded-answer fixture evaluation failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    output = asdict(report)
    output["evaluation_mode"] = "deterministic_recorded_fixture_contract_v1"
    output["live_provider_used"] = False
    print(json.dumps(output, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
