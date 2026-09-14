# Qiita MCP (Databricks Apps)

A custom [Model Context Protocol](https://modelcontextprotocol.io) server that exposes the
[Qiita API v2](https://qiita.com/api/v2/docs) as MCP tools. Built with
[FastMCP](https://github.com/jlowin/fastmcp) (Python) and deployed on the
**Databricks Apps** platform using the streamable-HTTP transport.

- **MCP endpoint:** `https://<app-url>/mcp`
- **Health / landing:** `GET https://<app-url>/` → JSON status
- **Transport:** streamable HTTP (FastMCP)

## Tools

Read tools work without authentication (Qiita allows 60 req/h per IP unauthenticated).
Authenticated-user and write tools require a Qiita access token (see below); without a
token they return a clear "token required" error. All 17 tools:

| Tool | Auth | Description |
|------|------|-------------|
| `search_items` | – | Search articles (`query`, `page`, `per_page`) |
| `get_item` | – | Get one article (with Markdown body) |
| `get_item_comments` | – | List comments on an article |
| `list_user_items` | – | List a user's articles |
| `get_user` | – | Get a user's public profile |
| `list_tags` | – | List tags (sort by `count`/`name`) |
| `get_tag` | – | Get one tag |
| `list_tag_items` | – | List articles for a tag |
| `list_user_stocks` | – | List a user's stocked articles |
| `get_authenticated_user` | ✅ | Profile of the token owner |
| `list_my_items` | ✅ | Token owner's articles (incl. private) |
| `create_item` | ✅ | Post a new article |
| `update_item` | ✅ | Update an article |
| `delete_item` | ✅ | Delete an article (irreversible) |
| `stock_item` | ✅ | Stock (bookmark) an article |
| `unstock_item` | ✅ | Remove from stocks |
| `is_item_stocked` | ✅ | Check if the token owner stocked an article |

## Qiita access token

Create a token at **Qiita → Settings → Applications → Personal access tokens**
(scopes `read_qiita` / `write_qiita`). Provide it to the app as the `QIITA_API_TOKEN`
environment variable. Prefer a Databricks secret over a plaintext env value:

```bash
# Store the token as a secret
databricks secrets create-scope qiita --profile <PROFILE>
databricks secrets put-secret qiita api_token --profile <PROFILE>

# Reference it from app.yaml (replace the value: "" entry):
#   env:
#     - name: QIITA_API_TOKEN
#       valueFrom: qiita-token      # a declared secret resource
```

The deploying user needs **MANAGE** on the secret scope. After changing the token,
restart the app for it to take effect.

## Project layout

```
qiita-mcp/
├── server.py         # FastMCP server + Starlette app (health route + /mcp mount)
├── qiita_client.py   # async Qiita API v2 wrapper
├── requirements.txt  # fastmcp, httpx, uvicorn
├── app.yaml          # Databricks Apps runtime config (command + env)
├── databricks.yml    # DAB bundle definition
├── test_local.py     # in-memory + live smoke test
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
databricks bundle deploy   -t dev --profile <PROFILE>   # uploads code, creates the app
databricks bundle run qiita-mcp -t dev --profile <PROFILE>   # deploys + starts, prints URL
```

Verify:

```bash
databricks apps get qiita-mcp --profile <PROFILE> -o json   # app_status.state == RUNNING
curl https://<app-url>/                                      # health JSON
```

## Connecting an MCP client

The app sits behind Databricks OAuth, so clients must authenticate to the workspace.
Point your MCP client at `https://<app-url>/mcp` with a Databricks OAuth/bearer token,
e.g. from `databricks auth token --profile <PROFILE>`.
