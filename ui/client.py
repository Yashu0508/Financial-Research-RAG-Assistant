"""HTTP-only client for the Phase 9 UI; no retrieval or generation imports."""

from __future__ import annotations

import httpx


def submit(api_url: str, question: str) -> dict[str, object]:
    try:
        response = httpx.post(
            f"{api_url.rstrip('/')}/query", json={"question": question}, timeout=35
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("status") not in {"answered", "abstained"}:
            raise ValueError
        return payload
    except Exception:
        return {"status": "error", "message": "The query service is unavailable."}
