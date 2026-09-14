"""Thin async wrapper around the Frankfurter API v2.

Docs: https://frankfurter.dev

- Base URL: https://api.frankfurter.dev/v2
- No authentication / API key required (public API).
- Requests are rate-limited to prevent abuse; no fixed daily/monthly quota.

Frankfurter serves reference exchange rates published by central banks (default: the
European Central Bank), updated around 16:00 CET on working days.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

FRANKFURTER_API_BASE = os.environ.get(
    "FRANKFURTER_API_BASE", "https://api.frankfurter.dev/v2"
)
DEFAULT_TIMEOUT = float(os.environ.get("FRANKFURTER_HTTP_TIMEOUT", "30"))


class FrankfurterAPIError(RuntimeError):
    """Raised when the Frankfurter API returns a non-2xx response."""

    def __init__(self, status_code: int, message: str, body: Any = None):
        self.status_code = status_code
        self.body = body
        super().__init__(f"Frankfurter API error {status_code}: {message}")


def _clean_params(params: dict[str, Any] | None) -> dict[str, Any]:
    """Drop None values; join list values into comma-separated strings."""
    cleaned: dict[str, Any] = {}
    for key, value in (params or {}).items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            if not value:
                continue
            value = ",".join(str(v) for v in value)
        cleaned[key] = value
    return cleaned


async def get(path: str, *, params: dict[str, Any] | None = None) -> Any:
    """GET a Frankfurter endpoint and return parsed JSON."""
    url = f"{FRANKFURTER_API_BASE}{path}"
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        resp = await client.get(url, params=_clean_params(params))

    if resp.status_code >= 400:
        try:
            body = resp.json()
            message = body.get("message", resp.text) if isinstance(body, dict) else resp.text
        except Exception:
            body = resp.text
            message = resp.text
        raise FrankfurterAPIError(resp.status_code, message, body)

    return resp.json()
