"""Unit tests for the only currently implemented API route."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_reports_query_delivery_state() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "detail": "Application is running; query delivery is available at POST /query.",
    }
