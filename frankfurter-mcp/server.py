"""Frankfurter MCP server (FastMCP, streamable HTTP).

A custom Model Context Protocol server that exposes the Frankfurter currency
exchange-rate API (https://frankfurter.dev) as MCP tools, designed to run on the
Databricks Apps platform.

- Transport: streamable HTTP, mounted at ``/mcp``.
- Port/host: binds ``0.0.0.0:$DATABRICKS_APP_PORT`` (8000 fallback for local dev).
- No authentication required (public API).

Docs: https://frankfurter.dev
"""

from __future__ import annotations

import os
from typing import Any

from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

import frankfurter_client as frankfurter

mcp = FastMCP(
    name="frankfurter-mcp",
    instructions=(
        "Tools for the Frankfurter currency exchange-rate API (https://frankfurter.dev). "
        "Get the latest reference rates, historical rates for a date, time series over a "
        "date range, convert an amount between currencies, and list supported currencies. "
        "Rates are published by central banks (ECB by default), updated ~16:00 CET on "
        "working days. No API key required."
    ),
)


# --------------------------------------------------------------------------- #
# Response shaping helpers
# --------------------------------------------------------------------------- #
def _rates_to_map(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Collapse a flat [{date, base, quote, rate}] array into a compact structure.

    Single date  -> {"date", "base", "rates": {quote: rate}}
    Multiple dates -> {"base", "start_date", "end_date", "rates": {date: {quote: rate}}}
    """
    if not rows:
        return {"rates": {}}
    base = rows[0].get("base")
    by_date: dict[str, dict[str, float]] = {}
    for row in rows:
        by_date.setdefault(row["date"], {})[row["quote"]] = row["rate"]
    dates = sorted(by_date)
    if len(dates) == 1:
        return {"date": dates[0], "base": base, "rates": by_date[dates[0]]}
    return {
        "base": base,
        "start_date": dates[0],
        "end_date": dates[-1],
        "rates": {d: by_date[d] for d in dates},
    }


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
@mcp.tool
async def get_latest_rates(
    base: str = "EUR", quotes: list[str] | None = None
) -> dict[str, Any]:
    """Get the latest exchange rates.

    Args:
        base: Base currency ISO code (e.g. "USD", "EUR", "JPY").
        quotes: Optional list of target currency codes to limit the response
            (e.g. ["USD", "GBP"]). Omit for all available currencies.
    """
    rows = await frankfurter.get("/rates", params={"base": base, "quotes": quotes})
    return _rates_to_map(rows)


@mcp.tool
async def get_historical_rates(
    date: str, base: str = "EUR", quotes: list[str] | None = None
) -> dict[str, Any]:
    """Get exchange rates for a specific past date.

    Args:
        date: Date in YYYY-MM-DD format (data available from 1999-01-04).
        base: Base currency ISO code.
        quotes: Optional list of target currency codes.
    """
    rows = await frankfurter.get(
        "/rates", params={"date": date, "base": base, "quotes": quotes}
    )
    return _rates_to_map(rows)


@mcp.tool
async def get_time_series(
    start_date: str,
    end_date: str,
    base: str = "EUR",
    quotes: list[str] | None = None,
) -> dict[str, Any]:
    """Get a time series of exchange rates across a date range.

    Args:
        start_date: Range start (YYYY-MM-DD).
        end_date: Range end (YYYY-MM-DD).
        base: Base currency ISO code.
        quotes: Optional list of target currency codes (recommended to keep the
            response small over long ranges).
    """
    rows = await frankfurter.get(
        "/rates",
        params={"from": start_date, "to": end_date, "base": base, "quotes": quotes},
    )
    return _rates_to_map(rows)


@mcp.tool
async def get_rate(base: str, quote: str, date: str | None = None) -> dict[str, Any]:
    """Get a single currency pair rate (optionally for a past date).

    Args:
        base: Base currency ISO code (e.g. "EUR").
        quote: Quote currency ISO code (e.g. "USD").
        date: Optional date in YYYY-MM-DD format; omit for the latest rate.
    """
    return await frankfurter.get(
        f"/rate/{base}/{quote}", params={"date": date} if date else None
    )


@mcp.tool
async def convert(
    amount: float,
    from_currency: str,
    to_currency: str,
    date: str | None = None,
) -> dict[str, Any]:
    """Convert an amount from one currency to another.

    Args:
        amount: The amount to convert.
        from_currency: Source currency ISO code.
        to_currency: Target currency ISO code.
        date: Optional date (YYYY-MM-DD) to use a historical rate; omit for latest.
    """
    if from_currency.upper() == to_currency.upper():
        return {
            "amount": amount,
            "from": from_currency.upper(),
            "to": to_currency.upper(),
            "rate": 1.0,
            "result": amount,
            "date": date,
        }
    pair = await frankfurter.get(
        f"/rate/{from_currency}/{to_currency}",
        params={"date": date} if date else None,
    )
    rate = pair["rate"]
    return {
        "amount": amount,
        "from": pair["base"],
        "to": pair["quote"],
        "rate": rate,
        "result": round(amount * rate, 6),
        "date": pair["date"],
    }


@mcp.tool
async def list_currencies() -> list[dict[str, Any]]:
    """List all supported currencies with their ISO code, name and symbol."""
    data = await frankfurter.get("/currencies")
    return [
        {
            "code": c.get("iso_code"),
            "name": c.get("name"),
            "symbol": c.get("symbol"),
        }
        for c in data
    ]


@mcp.tool
async def get_currency(code: str) -> dict[str, Any]:
    """Get details for a single currency by ISO code (e.g. "USD")."""
    return await frankfurter.get(f"/currency/{code}")


@mcp.tool
async def list_providers() -> Any:
    """List the available rate data providers (central banks / sources)."""
    return await frankfurter.get("/providers")


# --------------------------------------------------------------------------- #
# ASGI app: MCP at /mcp plus a plain health/landing route at /
# --------------------------------------------------------------------------- #
mcp_app = mcp.http_app(path="/mcp")


async def health(_request) -> JSONResponse:
    return JSONResponse(
        {"status": "ok", "service": "frankfurter-mcp", "mcp_endpoint": "/mcp"}
    )


app = Starlette(
    routes=[Route("/", health), Mount("/", app=mcp_app)],
    lifespan=mcp_app.lifespan,
)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("DATABRICKS_APP_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
