"""The Streamlit boundary is exercised through its HTTP-only client."""

from __future__ import annotations

import httpx
import pytest

from ui.client import submit


class _Response:
    def __init__(self, payload, status_code=200):
        self.payload, self.status_code = payload, status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("bad", request=None, response=None)

    def json(self):
        return self.payload


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "answered", "answer": "Supported.", "citations": []},
        {
            "status": "abstained",
            "answer": "No evidence.",
            "abstention_reason": "NO_ELIGIBLE_EVIDENCE",
        },
    ],
)
def test_ui_client_returns_only_valid_api_answer_or_abstention(monkeypatch, payload):
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: _Response(payload))
    assert submit("http://api/", "q") == payload


@pytest.mark.parametrize("response", [_Response({}, 503), _Response({"status": "unknown"})])
def test_ui_client_hides_http_and_malformed_response_details(monkeypatch, response):
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: response)
    assert submit("http://api", "q") == {
        "status": "error",
        "message": "The query service is unavailable.",
    }


def test_ui_client_hides_transport_failures(monkeypatch):
    monkeypatch.setattr(
        httpx, "post", lambda *args, **kwargs: (_ for _ in ()).throw(httpx.TimeoutException("x"))
    )
    assert submit("http://api", "q")["status"] == "error"
