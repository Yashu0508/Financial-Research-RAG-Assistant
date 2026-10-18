from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.evaluation.answers.grounded_answer_evaluation import (
    AnswerEvaluationDataError,
    evaluate_grounded_answers,
    load_grounded_answer_dataset,
    validate_grounded_answer_references,
)
from app.generation.contracts import Citation, GenerationResponse, ValidationResult

ROOT = Path(__file__).resolve().parents[2]


def _citation(identifier="chunk"):
    return Citation(identifier, "doc", "a" * 64, None, {}, [{"source_locator": "x"}], identifier)


def test_grounded_answer_dataset_is_provenance_checked():
    path = ROOT / "data/evaluation/grounded_answer_quality.v1.json"
    assert load_grounded_answer_dataset(path)[0] == "sec-grounded-answer-quality-v1"
    validate_grounded_answer_references(path, ROOT / "data/processed/sec_evidence/v1")


def test_answer_and_abstention_metrics_remain_separate(tmp_path):
    dataset = {
        "dataset_id": "x",
        "dataset_version": "1",
        "cases": [
            {
                "case_id": "a",
                "status": "answerable",
                "question": "q",
                "supporting_evidence": [{"chunk_id": "chunk"}],
                "required_factual_points": ["fact"],
                "allowed_abstention_reasons": [],
            },
            {
                "case_id": "u",
                "status": "unanswerable",
                "question": "q",
                "supporting_evidence": [],
                "required_factual_points": [],
                "allowed_abstention_reasons": ["NO_ELIGIBLE_EVIDENCE"],
            },
        ],
    }
    path = tmp_path / "answers.json"
    path.write_text(json.dumps(dataset), encoding="utf-8")
    report = evaluate_grounded_answers(
        path,
        {
            "a": GenerationResponse("answered", "fact", (_citation(),), ValidationResult(True)),
            "u": GenerationResponse("abstained", "no", abstention_reason="NO_ELIGIBLE_EVIDENCE"),
        },
    )
    assert (report.answerable_pass_count, report.correct_abstention_count) == (1, 1)


def test_bad_fact_or_unknown_citation_does_not_pass(tmp_path):
    dataset = {
        "dataset_id": "x",
        "dataset_version": "1",
        "cases": [
            {
                "case_id": "a",
                "status": "answerable",
                "question": "q",
                "supporting_evidence": [{"chunk_id": "chunk"}],
                "required_factual_points": ["fact"],
                "allowed_abstention_reasons": [],
            }
        ],
    }
    path = tmp_path / "answers.json"
    path.write_text(json.dumps(dataset), encoding="utf-8")
    report = evaluate_grounded_answers(
        path,
        {
            "a": GenerationResponse(
                "answered", "wrong", (_citation("other"),), ValidationResult(True)
            )
        },
    )
    assert report.answerable_pass_count == 0


def test_invalid_answer_dataset_is_rejected(tmp_path):
    path = tmp_path / "answers.json"
    path.write_text('{"dataset_id":"x","dataset_version":"1","cases":[]}', encoding="utf-8")
    with pytest.raises(AnswerEvaluationDataError):
        load_grounded_answer_dataset(path)
