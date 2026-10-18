"""FastAPI application entry point for guarded evidence-grounded queries."""

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.query import router as query_router

app = FastAPI(
    title="Financial Research RAG Assistant",
    description="Typed delivery of server-ranked evidence through grounded generation.",
    version="0.1.0",
)
app.include_router(health_router)
app.include_router(query_router)
