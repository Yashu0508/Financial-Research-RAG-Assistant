"""Service health route."""

from fastapi import APIRouter

from app.api.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Confirm that the API can be imported and served."""

    return HealthResponse(
        status="ok",
        detail="Application is running; query delivery is available at POST /query.",
    )
