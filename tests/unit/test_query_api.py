"""Tests for the public query boundary without a database, model, or provider."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.query_pipeline import (
    PipelineUnavailable,
    RankedEvidencePipeline,
    get_query_pipeline,
)
from app.api.schemas.query import QueryRequest
from app.core.config import Settings
from app.generation import GenerationConfiguration
from app.generation.contracts import Citation, GenerationResponse, ValidationResult
from app.generation.service import GroundedGenerationService
from app.main import app


def _citation() -> Citation:
    return Citation(
        evidence_id="chunk-1",
        document_id="aapl-2024-10k",
        source_sha256="a" * 64,
        source_url="https://www.sec.gov/Archives/example",
        section_heading={"text": "Net sales"},
        source_elements=[{"element_id": "element-1"}],
        parent_chunk_id="chunk-1",
    )


class _Pipeline:
    def __init__(self, result: GenerationResponse | Exception) -> None:
        self.result = result

    def answer(self, request: QueryRequest) -> GenerationResponse:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture(autouse=True)
def _clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def _client(result: GenerationResponse | Exception) -> TestClient:
    app.dependency_overrides[get_query_pipeline] = lambda: _Pipeline(result)
    return TestClient(app)


def test_query_returns_only_server_pipeline_answer_and_trusted_citations():
    response = _client(
        GenerationResponse("answered", "Supported.", (_citation(),), ValidationResult(True), None)
    ).post("/query", json={"question": "What were net sales?", "ticker": "aapl"})

    assert response.status_code == 200
    assert response.json()["citations"] == [
        {
            "evidence_id": "chunk-1",
            "document_id": "aapl-2024-10k",
            "source_url": "https://www.sec.gov/Archives/example",
            "source_sha256": "a" * 64,
            "section_heading": {"text": "Net sales"},
        }
    ]
    assert response.json()["status"] == "answered"


@pytest.mark.parametrize("question", ["", "   ", "x" * 1001])
def test_query_rejects_empty_whitespace_and_overlong_questions(question):
    assert (
        _client(GenerationResponse("answered", "unused"))
        .post("/query", json={"question": question})
        .status_code
        == 422
    )


@pytest.mark.parametrize("field", ["evidence", "citations", "source_url", "retrieval_score"])
def test_query_rejects_client_supplied_trust_metadata(field):
    assert (
        _client(GenerationResponse("answered", "unused"))
        .post("/query", json={"question": "q", field: []})
        .status_code
        == 422
    )


def test_query_preserves_machine_readable_abstentions():
    for reason in ("NO_ELIGIBLE_EVIDENCE", "PROVIDER_FAILURE", "CITATION_UNKNOWN"):
        response = _client(
            GenerationResponse(
                "abstained",
                "I cannot provide a supported answer from the available filing evidence.",
                validation=ValidationResult(False),
                abstention_reason=reason,
            )
        ).post("/query", json={"question": "q"})
        assert response.status_code == 200
        assert response.json()["status"] == "abstained"
        assert response.json()["abstention_reason"] == reason
        assert response.json()["citations"] == []


@pytest.mark.parametrize(
    "failure", [PipelineUnavailable("db password=secret"), RuntimeError("trace")]
)
def test_query_failures_are_generic_503s_without_internal_details(failure):
    response = _client(failure).post("/query", json={"question": "q"})

    assert response.status_code == 503
    assert response.json()["detail"] in {
        "Query service is unavailable.",
        "Query service failed safely.",
    }
    assert "secret" not in response.text
    assert "trace" not in response.text


def test_missing_configuration_fails_closed_from_dependency(monkeypatch):
    import app.core.config as config

    monkeypatch.setattr(config, "get_settings", lambda: Settings(_env_file=None))
    with pytest.raises(HTTPException) as error:
        get_query_pipeline()
    assert error.value.status_code == 503
    assert error.value.detail == "Query service is unavailable."


class _Retriever:
    def __init__(self, result):
        self.result, self.calls = result, []

    def search(self, query, filters, limit):
        self.calls.append((query, filters, limit))
        return self.result


class _Generator:
    def __init__(self):
        self.request = None

    def generate(self, request):
        self.request = request
        return GenerationResponse(
            "abstained", "No evidence.", abstention_reason="NO_ELIGIBLE_EVIDENCE"
        )


class _Connection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def _retrieval_result(source_sha256="a" * 64):
    return SimpleNamespace(
        candidate=SimpleNamespace(
            chunk_id="chunk-1",
            document_id="aapl-2024-10k",
            source_sha256=source_sha256,
            text="Net sales were reported.",
            ticker="AAPL",
            company="Apple Inc.",
            form_type="10-K",
            reporting_period_end=date(2024, 9, 28),
            section_heading={"text": "Net sales"},
            source_elements=[{"element_id": "element-1"}],
            chunk_sequence=1,
            rrf_score=0.1,
        ),
        reranker_score=1.0,
    )


def test_ranked_pipeline_uses_server_filters_bound_and_manifest_url_then_closes_connection():
    retriever, generator, connection = (
        _Retriever([_retrieval_result()]),
        _Generator(),
        _Connection(),
    )
    pipeline = RankedEvidencePipeline(
        retriever,
        generator,
        {"aapl-2024-10k": "https://www.sec.gov/Archives/trusted"},
        connection=connection,
    )
    pipeline.answer(QueryRequest(question="sales", ticker="aapl", form_type="10-K"))

    assert retriever.calls[0][2] == 5
    assert retriever.calls[0][1].ticker == "AAPL"
    assert generator.request.evidence[0].source_url == "https://www.sec.gov/Archives/trusted"
    assert connection.closed


def test_ranked_pipeline_source_hash_mismatch_abstains_before_provider_use():
    class _Provider:
        def complete(self, request):
            raise AssertionError("a mismatched source must not reach the provider")

    pipeline = RankedEvidencePipeline(
        _Retriever([_retrieval_result("b" * 64)]),
        GroundedGenerationService(
            _Provider(), GenerationConfiguration("test"), {"aapl-2024-10k": "a" * 64}
        ),
        {},
    )
    assert pipeline.answer(QueryRequest(question="sales")).abstention_reason == "INVALID_PROVENANCE"
