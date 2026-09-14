# custom_mcp_with_databricks_apps

Databricks Apps を使って作成したカスタム MCP（Model Context Protocol）サーバー集です。
いずれも Python の [FastMCP](https://github.com/jlowin/fastmcp) で実装し、streamable-HTTP
トランスポートで Databricks Apps プラットフォーム上にデプロイしています。

## 収録している MCP

| ディレクトリ | 対象 API | 概要 | ツール数 |
|--------------|----------|------|:---:|
| [`qiita-mcp/`](qiita-mcp/) | [Qiita API v2](https://qiita.com/api/v2/docs) | 記事の検索・取得、ユーザー/タグ/コメント/ストックの参照、記事の投稿・更新・削除・ストックなど | 17 |
| [`frankfurter-mcp/`](frankfurter-mcp/) | [Frankfurter API](https://frankfurter.dev) | 中央銀行（ECB）公表の為替レート。最新/過去/期間レート、通貨換算、通貨一覧 | 8 |

各ディレクトリの `README.md` にツール一覧・ローカル実行・デプロイ手順をまとめています。

## 共通アーキテクチャ

- **実装**: `FastMCP` でツールを定義し、`mcp.http_app(path="/mcp")` を Starlette アプリに
  マウント。ルート `/` はヘルスチェック用の JSON を返す。
- **ランタイム**: `0.0.0.0:$DATABRICKS_APP_PORT` にバインド（Databricks Apps 仕様）。
- **MCP エンドポイント**: `https://<app-url>/mcp`
- **認証**: アプリ自体は Databricks OAuth の背後にあるため、MCP クライアントは
  ワークスペースのトークン（例: `databricks auth token`）で接続する。

## デプロイ（各ディレクトリ内で実行）

```bash
databricks bundle validate -t dev --profile <PROFILE>
databricks bundle deploy   -t dev --profile <PROFILE>
databricks bundle run <app-name> -t dev --profile <PROFILE>   # デプロイ＋起動、URL を表示
```

## ローカルテスト

```bash
cd <mcp-dir>
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python test_local.py    # 実 API に対する in-memory スモークテスト
```
