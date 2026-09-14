"""Local smoke test for the Qiita MCP server.

Runs the server in-memory (no network transport) via the FastMCP client and calls
the public read tools against the real Qiita API. Write/authenticated tools are only
checked for their "token required" behavior when no token is configured.

Usage:  python test_local.py
"""

import asyncio
import json

from fastmcp import Client

import qiita_client as qiita
from server import mcp


def plain(result):
    """Extract a JSON-able Python object from a FastMCP CallToolResult.

    FastMCP returns structured_content as a JSON dict; list-returning tools are
    wrapped under a single "result" key.
    """
    sc = result.structured_content
    if isinstance(sc, dict) and set(sc.keys()) == {"result"}:
        return sc["result"]
    return sc


def show(label, value):
    print(f"\n=== {label} ===")
    print(json.dumps(value, ensure_ascii=False, indent=2)[:1500])


async def main():
    async with Client(mcp) as client:
        tools = await client.list_tools()
        print(f"Registered tools ({len(tools)}):")
        for t in tools:
            print(f"  - {t.name}")

        # --- public read tools ---
        res = await client.call_tool("search_items", {"query": "Databricks", "per_page": 3})
        items = plain(res)
        show("search_items(query=Databricks, per_page=3)", items)
        assert isinstance(items, list) and len(items) >= 1, "expected search results"
        assert items[0].get("id"), "item missing id"

        first_id = items[0]["id"]
        res = await client.call_tool("get_item", {"item_id": first_id})
        item = plain(res)
        show(f"get_item({first_id})", {k: item.get(k) for k in ("id", "title", "url", "tags")})
        assert item.get("id") == first_id
        assert item.get("body") is not None, "expected markdown body"

        res = await client.call_tool("list_tags", {"per_page": 3, "sort": "count"})
        tags = plain(res)
        show("list_tags(per_page=3)", tags)
        assert isinstance(tags, list) and tags, "expected tags"

        res = await client.call_tool("list_tag_items", {"tag_id": "Python", "per_page": 2})
        tag_items = plain(res)
        show("list_tag_items(Python, per_page=2)", tag_items)
        assert isinstance(tag_items, list)

        res = await client.call_tool("get_user", {"user_id": items[0]["user_id"]})
        show("get_user(...)", plain(res))
        assert plain(res).get("id") == items[0]["user_id"]

        # --- authenticated behavior ---
        if qiita.has_token():
            res = await client.call_tool("get_authenticated_user", {})
            show("get_authenticated_user()", plain(res))
            assert plain(res).get("id"), "expected authenticated user id"
            print("\n[token configured] authenticated read OK")
        else:
            # Write tool should fail cleanly with a token-required error.
            errored = False
            try:
                await client.call_tool("get_authenticated_user", {})
            except Exception as e:
                errored = True
                print(f"\n[no token] get_authenticated_user correctly refused: {e}")
            assert errored, "expected token-required error without QIITA_API_TOKEN"

    print("\nALL LOCAL TESTS PASSED ✅")


if __name__ == "__main__":
    asyncio.run(main())
