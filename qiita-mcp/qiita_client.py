"""Thin async wrapper around the Qiita API v2.

Docs: https://qiita.com/api/v2/docs

- Base URL: https://qiita.com/api/v2
- Auth: Bearer token via the Authorization header (optional for public reads).
- Rate limit: 60 req/h unauthenticated per IP, 1000 req/h authenticated.

The access token is read from the QIITA_API_TOKEN environment variable. When it is
not set, only public read endpoints work; anything requiring authentication raises
``QiitaAuthError`` with a clear message.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

QIITA_API_BASE = os.environ.get("QIITA_API_BASE", "https://qiita.com/api/v2")
DEFAULT_TIMEOUT = float(os.environ.get("QIITA_HTTP_TIMEOUT", "30"))


class QiitaAuthError(RuntimeError):
    """Raised when an operation needs a token but QIITA_API_TOKEN is not set."""


class QiitaAPIError(RuntimeError):
    """Raised when the Qiita API returns a non-2xx response."""

    def __init__(self, status_code: int, message: str, body: Any = None):
        self.status_code = status_code
        self.body = body
        super().__init__(f"Qiita API error {status_code}: {message}")


def get_token() -> str | None:
    """Return the configured Qiita token, or None if unset/blank."""
    token = os.environ.get("QIITA_API_TOKEN", "").strip()
    return token or None


def has_token() -> bool:
    return get_token() is not None


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    token = get_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
    require_auth: bool = False,
) -> Any:
    """Perform a request against the Qiita API and return parsed JSON.

    For 204 No Content (e.g. stock checks) returns the raw ``httpx.Response`` so
    callers can inspect the status code.
    """
    if require_auth and not has_token():
        raise QiitaAuthError(
            "This operation requires a Qiita access token. Set the QIITA_API_TOKEN "
            "environment variable (Databricks App env var or secret) and redeploy/restart."
        )

    url = f"{QIITA_API_BASE}{path}"
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        resp = await client.request(
            method, url, params=params, json=json, headers=_headers()
        )

    if resp.status_code >= 400:
        try:
            body = resp.json()
            message = body.get("message", resp.text)
        except Exception:
            body = resp.text
            message = resp.text
        raise QiitaAPIError(resp.status_code, message, body)

    if resp.status_code == 204 or not resp.content:
        return {"status_code": resp.status_code}

    return resp.json()
