"""Application boundary for ranked evidence then Phase 8 generation."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from fastapi import HTTPException

from app.api.schemas.query import QueryRequest
from app.generation import GenerationRequest, GenerationResponse, narrative_evidence_from_result


class QueryPipeline(Protocol):
    def answer(self, request: QueryRequest) -> GenerationResponse: ...


class PipelineUnavailable(RuntimeError):
    pass


def get_query_pipeline() -> QueryPipeline:
    """Build the approved guarded RRF+rereanking pipeline, or fail closed."""
    connection = None
    try:
        import psycopg

        from app.core.config import get_settings
        from app.generation.factory import build_generation_service
        from app.ingestion.loaders.sec_manifest import load_registration_manifest
        from app.retrieval.hybrid import ReciprocalRankFusionRetriever
        from app.retrieval.keyword import PostgresKeywordRetriever
        from app.retrieval.reranking import (
            BoundedCrossEncoderReranker,
            HybridRerankingRetriever,
            current_reranker_configuration,
            load_pinned_reranker,
        )
        from app.retrieval.semantic import (
            PostgresSemanticRetriever,
            current_embedding_configuration,
            load_pinned_model,
        )
        from app.storage.development import (
            development_target_from_settings,
            prepare_development_connection,
        )

        settings = get_settings()
        target = development_target_from_settings(settings)
        if not settings.semantic_model_cache_dir:
            raise PipelineUnavailable("Model cache is not configured.")
        manifest = load_registration_manifest(
            Path(__file__).resolve().parents[2] / "data/manifests/sec_documents.v1.json"
        )
        hashes = {d.document_id: d.source_sha256 for d in manifest.documents}
        urls = {d.document_id: d.official_sec_source_url for d in manifest.documents}
        connection = psycopg.connect(settings.database_url)
        prepare_development_connection(connection, target, create_schema=False)
        cache = Path(settings.semantic_model_cache_dir)
        ec = current_embedding_configuration()
        rc = current_reranker_configuration()
        hybrid = ReciprocalRankFusionRetriever(
            PostgresKeywordRetriever(connection),
            PostgresSemanticRetriever(connection, load_pinned_model(cache, ec), ec),
        )
        retriever = HybridRerankingRetriever(
            hybrid, BoundedCrossEncoderReranker(load_pinned_reranker(cache, rc))
        )
        return RankedEvidencePipeline(
            retriever,
            build_generation_service(settings, hashes),
            urls,
            connection=connection,
        )
    except Exception as exc:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
        # Dependencies execute before the route handler.  Convert failures here
        # so configuration/model/database diagnostics cannot become a public 500.
        raise HTTPException(status_code=503, detail="Query service is unavailable.") from exc


class RankedEvidencePipeline:
    """Thin adapter: retriever is server-owned; client evidence is never accepted."""

    def __init__(
        self, retriever, generator, source_urls: dict[str, str | None], *, connection=None
    ) -> None:
        self.retriever, self.generator, self.source_urls, self.connection = (
            retriever,
            generator,
            source_urls,
            connection,
        )

    def answer(self, request: QueryRequest) -> GenerationResponse:
        from app.retrieval.keyword import KeywordSearchFilters

        try:
            results = self.retriever.search(
                request.question,
                KeywordSearchFilters(
                    request.ticker, request.form_type, request.reporting_period_end
                ),
                5,
            )
            evidence = tuple(
                narrative_evidence_from_result(
                    result,
                    source_url=self.source_urls.get(
                        getattr(result, "candidate", result).document_id
                    ),
                )
                for result in results
            )
            return self.generator.generate(GenerationRequest(request.question, evidence))
        finally:
            if self.connection is not None:
                try:
                    self.connection.close()
                except Exception:
                    # A valid response must not fail merely because a read-only
                    # connection could not be closed cleanly.
                    pass
