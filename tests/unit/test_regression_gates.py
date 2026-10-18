from types import SimpleNamespace

import pytest

from app.evaluation.retrieval.regression_gates import (
    V2_SHA256,
    RegressionGateError,
    assert_reranking_v2_gate,
)


def _report(**changes):
    values = {
        "dataset_sha256": V2_SHA256,
        "answerable_case_count": 20,
        "unanswerable_case_count": 3,
        "recall_at_5": 0.75,
        "recall_at_10": 0.90,
        "precision_at_5": 0.15,
        "mrr": 0.6972,
    }
    return SimpleNamespace(**(values | changes))


def test_documented_reranking_baseline_passes_small_corpus_gate():
    assert_reranking_v2_gate(_report())


@pytest.mark.parametrize(
    "changes", [{"dataset_sha256": "x"}, {"answerable_case_count": 19}, {"mrr": 0.64}]
)
def test_changed_dataset_or_material_metric_regression_fails(changes):
    with pytest.raises(RegressionGateError):
        assert_reranking_v2_gate(_report(**changes))
