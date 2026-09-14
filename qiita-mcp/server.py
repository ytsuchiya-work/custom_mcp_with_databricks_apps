"""Qiita MCP server (FastMCP, streamable HTTP).

A custom Model Context Protocol server that exposes the Qiita API v2 as MCP tools,
designed to run on the Databricks Apps platform.

- Transport: streamable HTTP, mounted at ``/mcp``.
- Port/host: binds ``0.0.0.0:$DATABRICKS_APP_PORT`` (8000 fallback for local dev).
- Auth to Qiita: optional Bearer token from ``QIITA_API_TOKEN``. Public read tools
  work without it; write / authenticated-user tools require it.

Docs: https://qiita.com/api/v2/docs
"""

from __future__ import annotations

import os
from typing import Any

from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

import qiita_client as qiita

mcp = FastMCP(
    name="qiita-mcp",
    instructions=(
        "Tools for the Qiita API v2 (https://qiita.com). Search and read articles "
        "(items), users, tags, comments and stocks without authentication. Creating, "
        "updating, deleting articles and stocking require a Qiita access token "
        "configured on the server (QIITA_API_TOKEN)."
    ),
)


# --------------------------------------------------------------------------- #
# Response shaping helpers (keep payloads small for the LLM)
# --------------------------------------------------------------------------- #
def _slim_item(item: dict[str, Any]) -> dict[str, Any]:
    """Compact representation of an item for list results."""
    user = item.get("user") or {}
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "url": item.get("url"),
        "likes_count": item.get("likes_count"),
        "stocks_count": item.get("stocks_count"),
        "comments_count": item.get("comments_count"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "tags": [t.get("name") for t in item.get("tags", [])],
        "user_id": user.get("id"),
        "private": item.get("private"),
    }


def _full_item(item: dict[str, Any]) -> dict[str, Any]:
    """Item with the markdown body (drops the large rendered HTML body)."""
    slim = _slim_item(item)
    slim["body"] = item.get("body")
    return slim


def _tags_payload(tags: list[str] | None) -> list[dict[str, Any]]:
    """Convert a list of tag names to the {name, versions} shape Qiita expects."""
    return [{"name": t, "versions": []} for t in (tags or [])]


# --------------------------------------------------------------------------- #
# Read tools (work without a token, rate-limited to 60 req/h unauthenticated)
# --------------------------------------------------------------------------- #
@mcp.tool
async def search_items(
    query: str = "", page: int = 1, per_page: int = 20
) -> list[dict[str, Any]]:
    """Search Qiita articles (items).

    Args:
        query: Qiita search query, e.g. "Databricks", "tag:python", "user:foo stocks:>10".
        page: Page number (1-100).
        per_page: Items per page (1-100).
    """
    params = {"page": page, "per_page": per_page}
    if query:
        params["query"] = query
    data = await qiita.request("GET", "/items", params=params)
    return [_slim_item(i) for i in data]


@mcp.tool
async def get_item(item_id: str) -> dict[str, Any]:
    """Get a single Qiita article by its item id, including the markdown body."""
    data = await qiita.request("GET", f"/items/{item_id}")
    return _full_item(data)


@mcp.tool
async def get_item_comments(item_id: str) -> list[dict[str, Any]]:
    """List comments on a Qiita article."""
    data = await qiita.request("GET", f"/items/{item_id}/comments")
    return [
        {
            "id": c.get("id"),
            "body": c.get("body"),
            "user_id": (c.get("user") or {}).get("id"),
            "created_at": c.get("created_at"),
        }
        for c in data
    ]


@mcp.tool
async def list_user_items(
    user_id: str, page: int = 1, per_page: int = 20
) -> list[dict[str, Any]]:
    """List articles posted by a specific user."""
    params = {"page": page, "per_page": per_page}
    data = await qiita.request("GET", f"/users/{user_id}/items", params=params)
    return [_slim_item(i) for i in data]


@mcp.tool
async def get_user(user_id: str) -> dict[str, Any]:
    """Get a Qiita user's public profile."""
    u = await qiita.request("GET", f"/users/{user_id}")
    return {
        "id": u.get("id"),
        "name": u.get("name"),
        "description": u.get("description"),
        "items_count": u.get("items_count"),
        "followees_count": u.get("followees_count"),
        "followers_count": u.get("followers_count"),
        "organization": u.get("organization"),
        "location": u.get("location"),
        "github_login_name": u.get("github_login_name"),
        "twitter_screen_name": u.get("twitter_screen_name"),
    }


@mcp.tool
async def list_tags(
    page: int = 1, per_page: int = 20, sort: str = "count"
) -> list[dict[str, Any]]:
    """List Qiita tags.

    Args:
        page: Page number (1-100).
        per_page: Tags per page (1-100).
        sort: "count" (popularity) or "name".
    """
    params = {"page": page, "per_page": per_page, "sort": sort}
    data = await qiita.request("GET", "/tags", params=params)
    return [
        {
            "id": t.get("id"),
            "items_count": t.get("items_count"),
            "followers_count": t.get("followers_count"),
        }
        for t in data
    ]


@mcp.tool
async def get_tag(tag_id: str) -> dict[str, Any]:
    """Get a single tag by id."""
    return await qiita.request("GET", f"/tags/{tag_id}")


@mcp.tool
async def list_tag_items(
    tag_id: str, page: int = 1, per_page: int = 20
) -> list[dict[str, Any]]:
    """List articles that have a specific tag."""
    params = {"page": page, "per_page": per_page}
    data = await qiita.request("GET", f"/tags/{tag_id}/items", params=params)
    return [_slim_item(i) for i in data]


@mcp.tool
async def list_user_stocks(
    user_id: str, page: int = 1, per_page: int = 20
) -> list[dict[str, Any]]:
    """List articles stocked (bookmarked) by a specific user."""
    params = {"page": page, "per_page": per_page}
    data = await qiita.request("GET", f"/users/{user_id}/stocks", params=params)
    return [_slim_item(i) for i in data]


# --------------------------------------------------------------------------- #
# Authenticated read tools (require QIITA_API_TOKEN)
# --------------------------------------------------------------------------- #
@mcp.tool
async def get_authenticated_user() -> dict[str, Any]:
    """Get the profile of the user who owns the configured access token."""
    u = await qiita.request("GET", "/authenticated_user", require_auth=True)
    return {
        "id": u.get("id"),
        "name": u.get("name"),
        "items_count": u.get("items_count"),
        "followers_count": u.get("followers_count"),
        "followees_count": u.get("followees_count"),
        "permanent_id": u.get("permanent_id"),
    }


@mcp.tool
async def list_my_items(page: int = 1, per_page: int = 20) -> list[dict[str, Any]]:
    """List articles posted by the authenticated user (includes private items)."""
    params = {"page": page, "per_page": per_page}
    data = await qiita.request(
        "GET", "/authenticated_user/items", params=params, require_auth=True
    )
    return [_slim_item(i) for i in data]


# --------------------------------------------------------------------------- #
# Write tools (require QIITA_API_TOKEN) — mutate the token owner's account
# --------------------------------------------------------------------------- #
@mcp.tool
async def create_item(
    title: str,
    body: str,
    tags: list[str] | None = None,
    private: bool = True,
    tweet: bool = False,
) -> dict[str, Any]:
    """Create (post) a new Qiita article.

    Args:
        title: Article title.
        body: Article body in Markdown.
        tags: List of tag names (at least one recommended; Qiita requires >=1 for public).
        private: If True (default) the article is a private/limited-share post.
        tweet: If True, also tweet the article on post (only when linked to Twitter).
    """
    payload = {
        "title": title,
        "body": body,
        "tags": _tags_payload(tags),
        "private": private,
        "tweet": tweet,
    }
    data = await qiita.request("POST", "/items", json=payload, require_auth=True)
    return _full_item(data)


@mcp.tool
async def update_item(
    item_id: str,
    title: str | None = None,
    body: str | None = None,
    tags: list[str] | None = None,
    private: bool | None = None,
) -> dict[str, Any]:
    """Update an existing Qiita article. Only provided fields are changed."""
    payload: dict[str, Any] = {}
    if title is not None:
        payload["title"] = title
    if body is not None:
        payload["body"] = body
    if tags is not None:
        payload["tags"] = _tags_payload(tags)
    if private is not None:
        payload["private"] = private
    if not payload:
        raise ValueError("Provide at least one field to update.")
    data = await qiita.request(
        "PATCH", f"/items/{item_id}", json=payload, require_auth=True
    )
    return _full_item(data)


@mcp.tool
async def delete_item(item_id: str) -> dict[str, Any]:
    """Delete a Qiita article by its item id. This is irreversible."""
    await qiita.request("DELETE", f"/items/{item_id}", require_auth=True)
    return {"deleted": True, "item_id": item_id}


@mcp.tool
async def stock_item(item_id: str) -> dict[str, Any]:
    """Stock (bookmark) an article as the authenticated user."""
    await qiita.request("PUT", f"/items/{item_id}/stock", require_auth=True)
    return {"stocked": True, "item_id": item_id}


@mcp.tool
async def unstock_item(item_id: str) -> dict[str, Any]:
    """Remove an article from the authenticated user's stocks."""
    await qiita.request("DELETE", f"/items/{item_id}/stock", require_auth=True)
    return {"stocked": False, "item_id": item_id}


@mcp.tool
async def is_item_stocked(item_id: str) -> dict[str, Any]:
    """Check whether the authenticated user has stocked an article."""
    try:
        await qiita.request("GET", f"/items/{item_id}/stock", require_auth=True)
        return {"stocked": True, "item_id": item_id}
    except qiita.QiitaAPIError as e:
        if e.status_code == 404:
            return {"stocked": False, "item_id": item_id}
        raise


# --------------------------------------------------------------------------- #
# ASGI app: MCP at /mcp plus a plain health/landing route at /
# --------------------------------------------------------------------------- #
mcp_app = mcp.http_app(path="/mcp")


async def health(_request) -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "service": "qiita-mcp",
            "mcp_endpoint": "/mcp",
            "qiita_token_configured": qiita.has_token(),
        }
    )


app = Starlette(
    routes=[Route("/", health), Mount("/", app=mcp_app)],
    lifespan=mcp_app.lifespan,
)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("DATABRICKS_APP_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
