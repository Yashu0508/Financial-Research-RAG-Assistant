"""Typed public contract for trusted server-side financial research queries."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=1000)
    ticker: str | None = Field(default=None, pattern=r"^[A-Za-z]{1,8}$")
    form_type: Literal["10-K", "10-Q"] | None = None
    reporting_period_end: date | None = None

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None


class CitationResponse(BaseModel):
    evidence_id: str
    document_id: str
    source_url: str | None
    source_sha256: str
    section_heading: dict[str, object]


class QueryResponse(BaseModel):
    status: Literal["answered", "abstained"]
    answer: str
    citations: list[CitationResponse]
    warnings: list[str]
    abstention_reason: str | None
