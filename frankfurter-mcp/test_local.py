"""Local smoke test for the Frankfurter MCP server.

Runs the server in-memory via the FastMCP client and calls each tool against the
real Frankfurter API (https://frankfurter.dev). No API key required.

Usage:  python test_local.py
"""

import asyncio
import json

from fastmcp import Client

from server import mcp


def plain(result):
    """Extract a JSON-able Python object from a FastMCP CallToolResult."""
    sc = result.structured_content
    if isinstance(sc, dict) and set(sc.keys()) == {"result"}:
        return sc["result"]
    return sc


def show(label, value):
    print(f"\n=== {label} ===")
    print(json.dumps(value, ensure_ascii=False, indent=2)[:1200])


async def main():
    async with Client(mcp) as client:
        tools = await client.list_tools()
        print(f"Registered tools ({len(tools)}):")
        for t in tools:
            print(f"  - {t.name}")

        res = await client.call_tool("get_latest_rates", {"base": "USD", "quotes": ["EUR", "JPY"]})
        latest = plain(res)
        show("get_latest_rates(USD -> EUR,JPY)", latest)
        assert latest["base"] == "USD" and "EUR" in latest["rates"], "expected USD rates"

        res = await client.call_tool(
            "get_historical_rates", {"date": "2020-01-02", "base": "EUR", "quotes": ["USD"]}
        )
        hist = plain(res)
        show("get_historical_rates(2020-01-02)", hist)
        assert hist["date"] == "2020-01-02" and "USD" in hist["rates"]

        res = await client.call_tool(
            "get_time_series",
            {"start_date": "2024-01-01", "end_date": "2024-01-05", "base": "USD", "quotes": ["EUR"]},
        )
        ts = plain(res)
        show("get_time_series(2024-01-01..05)", ts)
        assert ts["start_date"] and ts["end_date"] and len(ts["rates"]) >= 2

        res = await client.call_tool("convert", {"amount": 100, "from_currency": "USD", "to_currency": "JPY"})
        conv = plain(res)
        show("convert(100 USD -> JPY)", conv)
        assert conv["from"] == "USD" and conv["to"] == "JPY" and conv["result"] > 0

        res = await client.call_tool("get_rate", {"base": "EUR", "quote": "USD"})
        show("get_rate(EUR/USD)", plain(res))
        assert plain(res)["base"] == "EUR"

        res = await client.call_tool("list_currencies", {})
        currencies = plain(res)
        show("list_currencies (first 3)", currencies[:3])
        assert isinstance(currencies, list) and any(c["code"] == "USD" for c in currencies)

    print("\nALL LOCAL TESTS PASSED ✅")


if __name__ == "__main__":
    asyncio.run(main())
