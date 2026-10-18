"""Health endpoint schemas."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Public health response for the scaffold API."""

    status: str
    detail: str
