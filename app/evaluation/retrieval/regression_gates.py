"""Small-corpus regression gates for the preserved narrative v2 benchmark."""

from __future__ import annotations

from dataclasses import dataclass

V2_SHA256 = "d79de57f251a10de5797276e42b7d4fc6236124b9c268badc8477c538a6f1c9f"


class RegressionGateError(ValueError):
    """A measured result materially regressed from the documented baseline."""


@dataclass(frozen=True)
class NarrativeRerankingGate:
    """Conservative gates: one case is 0.05 on this 20-case benchmark."""

    recall_at_5: float = 0.70
    recall_at_10: float = 0.85
    precision_at_5: float = 0.14
    mrr: float = 0.65
    answerable_case_count: int = 20
    unanswerable_case_count: int = 3


def assert_reranking_v2_gate(
    report: object, gate: NarrativeRerankingGate = NarrativeRerankingGate()
) -> None:
    """Fail visibly on materially lower quality or changed denominator/dataset."""
    checks = {
        "dataset_sha256": (getattr(report, "dataset_sha256", None), V2_SHA256),
        "answerable_case_count": (
            getattr(report, "answerable_case_count", None),
            gate.answerable_case_count,
        ),
        "unanswerable_case_count": (
            getattr(report, "unanswerable_case_count", None),
            gate.unanswerable_case_count,
        ),
    }
    for name, (actual, expected) in checks.items():
        if actual != expected:
            raise RegressionGateError(f"{name} changed: {actual!r} != {expected!r}.")
    for name, minimum in (
        ("recall_at_5", gate.recall_at_5),
        ("recall_at_10", gate.recall_at_10),
        ("precision_at_5", gate.precision_at_5),
        ("mrr", gate.mrr),
    ):
        value = getattr(report, name, None)
        if not isinstance(value, (int, float)) or value < minimum:
            raise RegressionGateError(f"{name} regressed: {value!r} < {minimum}.")
