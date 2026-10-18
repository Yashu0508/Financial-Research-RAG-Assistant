"""Typed query delivery; failures expose no internal diagnostics."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.query_pipeline import PipelineUnavailable, QueryPipeline, get_query_pipeline
from app.api.schemas.query import CitationResponse, QueryRequest, QueryResponse

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
def query(
    request: QueryRequest, pipeline: QueryPipeline = Depends(get_query_pipeline)
) -> QueryResponse:
    try:
        result = pipeline.answer(request)
    except PipelineUnavailable as exc:
        raise HTTPException(status_code=503, detail="Query service is unavailable.") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Query service failed safely.") from exc
    return QueryResponse(
        status=result.status,
        answer=result.answer,
        citations=[
            CitationResponse(
                evidence_id=c.evidence_id,
                document_id=c.document_id,
                source_url=c.source_url,
                source_sha256=c.source_sha256,
                section_heading=c.section_heading,
            )
            for c in result.citations
        ],
        warnings=list(result.validation.warnings),
        abstention_reason=result.abstention_reason,
    )
