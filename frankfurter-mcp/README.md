# Frankfurter MCP (Databricks Apps)

A custom [Model Context Protocol](https://modelcontextprotocol.io) server that exposes the
[Frankfurter API](https://frankfurter.dev) — free currency exchange rates published by
central banks (ECB by default) — as MCP tools. Built with
[FastMCP](https://github.com/jlowin/fastmcp) (Python) and deployed on the **Databricks
Apps** platform using the streamable-HTTP transport.

- **MCP endpoint:** `https://<app-url>/mcp`
- **Health / landing:** `GET https://<app-url>/` → JSON status
- **Transport:** streamable HTTP (FastMCP)
- **Auth to Frankfurter:** none required (public API, no key)

## Tools

| Tool | Description |
|------|-------------|
| `get_latest_rates` | Latest rates for a `base` currency (optionally limited to `quotes`) |
| `get_historical_rates` | Rates for a specific `date` (data from 1999-01-04) |
| `get_time_series` | Rates across a date range (`start_date`..`end_date`) |
| `get_rate` | A single currency pair rate (optionally for a past date) |
| `convert` | Convert an `amount` between two currencies (latest or historical) |
| `list_currencies` | All supported currencies (code, name, symbol) |
| `get_currency` | Details for one currency by ISO code |
| `list_providers` | Available rate data providers (central banks / sources) |

Responses collapse Frankfurter's flat `[{date, base, quote, rate}]` arrays into a compact
`{date, base, rates: {quote: rate}}` (single date) or `{base, start_date, end_date,
rates: {date: {quote: rate}}}` (time series) shape to keep payloads small.

## Project layout

```
frankfurter-mcp/
├── server.py             # FastMCP server + Starlette app (health route + /mcp mount)
├── frankfurter_client.py # async Frankfurter API v2 wrapper
├── requirements.txt      # fastmcp, httpx, uvicorn
├── app.yaml              # Databricks Apps runtime config (command)
├── databricks.yml        # DAB bundle definition
├── test_local.py         # in-memory + live smoke test
└── README.md
```

## Local development

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# In-memory + live API smoke test
.venv/bin/python test_local.py

# Run the HTTP server locally (defaults to port 8000)
DATABRICKS_APP_PORT=8000 .venv/bin/python server.py
# → health:  curl http://localhost:8000/
# → MCP:     http://localhost:8000/mcp
```

## Deploy to Databricks Apps

```bash
databricks bundle validate -t dev --profile <PROFILE>
databricks bundle deploy   -t dev --profile <PROFILE>          # uploads code, creates the app
databricks bundle run frankfurter-mcp -t dev --profile <PROFILE>   # deploys + starts, prints URL
```

Verify:

```bash
databricks apps get frankfurter-mcp --profile <PROFILE> -o json   # app_status.state == RUNNING
curl https://<app-url>/                                           # health JSON
```

## Connecting an MCP client

The app sits behind Databricks OAuth, so clients must authenticate to the workspace.
Point your MCP client at `https://<app-url>/mcp` with a Databricks OAuth/bearer token,
e.g. from `databricks auth token --profile <PROFILE>`.
