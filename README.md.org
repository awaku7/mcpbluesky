# MCP（Model Context Protocol）

このディレクトリには、サンプル用途の **MCP サーバー / クライアント** 実装が含まれます。

本リポジトリ本体（scheck）の「`tools/handle_mcp_v2`」「`tools/mcp_tools_list`」は、HTTP ベースの MCP サーバーに接続してツールを呼び出すための **クライアント側ツール**です。

---

## 内容物

- `server.py`
  - Python 実装の MCP サーバー（FastMCP を利用）
  - 本リポジトリでは **Bluesky 公開 API を叩くツール群**のサンプルとして実装されています。

- `client.py`
  - `streamable_http_client` を用いて `server.py` に接続し、`list_tools` やツール呼び出しを試す簡易クライアントです。

- `common_http.py`
  - Bluesky API 呼び出しの共通処理（GET/POST）
  - 簡易スロットリングや 429/5xx リトライ、ネットワーク環境（Zscaler の continue ページ等）向けの回避処理が含まれています。

---

## 前提（重要）

- `server.py` は **HTTP(Streamable HTTP) transport** で待受します。
- 接続先 URL は `http://127.0.0.1:8000/mcp` です。
- 現行の `tools/handle_mcp_v2` / `tools/mcp_tools_list` は、URL 末尾が `/mcp` でない場合に自動で補います。

---

## MCP サーバーリスト（mcp_servers.json）

`scheck` 側の `mcp_tools_list` ツールは、引数 `url` を省略した場合に **リポジトリ直下**の `mcp_servers.json` を参照します。

- `mcp_servers.json` が存在する場合:
  - `server_name` が指定されていれば、その `name` に一致するエントリの `url` を使用
  - `server_name` が未指定なら、先頭（`mcp_servers[0]`）の `url` を使用
- `mcp_servers.json` が存在しない（または読み込みに失敗）場合:
  - 最終的に `http://127.0.0.1:8000/mcp` がデフォルトとして使われます

### ファイル形式

```json
{
  "mcp_servers": [
    {
      "name": "bluesky-local",
      "url": "http://127.0.0.1:8000/mcp",
      "transport": "streamable-http"
    }
  ]
}
```

### 更新方法

1. リポジトリ直下の `mcp_servers.json` をテキストエディタで開く
2. `mcp_servers` 配列に、追加・変更したいサーバー定義を追記/編集する
   - `name`: `mcp_tools_list(server_name=...)` で参照する識別子
   - `url`: MCP の HTTP エンドポイント（例: `http://127.0.0.1:8000/mcp`）
   - `transport`: 参考情報（現状、`mcp_tools_list` / `handle_mcp_v2` は `streamable_http_client` を利用しており、ここで指定した transport による切替処理は行っていません）
3. `mcp_tools_list` を `url` 省略で呼び、反映されているか確認する
   - 例: `mcp_tools_list(server_name="bluesky-local")`

---

## 実行方法（例）

### サーバー

```bash
python mcp/server.py
```

起動すると 8000 番で待受します。

### クライアント

```bash
python mcp/client.py
```

`list_tools()` の結果表示と、`bsky_get_profile` の呼び出しを行います。

---

## サーバーが提供する主なツール

`server.py` は FastMCP の `@mcp.tool()` で複数ツールを公開しています（例）:

- `bsky_login(handle: str, password: str)`
- `bsky_get_profile(handle: str)`
- `bsky_get_author_feed(handle: str, limit: int = 10, cursor: str | None = None)`
- `bsky_search_posts(query: str, limit: int = 10, cursor: str | None = None)`
- ほか多数

提供ツールの一覧は、

- scheck 側: `mcp_tools_list` ツール
- もしくは `mcp/client.py` の `list_tools()`

で確認してください。

---

## 注意事項

- `bsky_login` は Bluesky の **アプリパスワード**を使用します（通常のパスワードは使わないでください）。
- 認証情報は Git 管理に含めないでください（`.env` 等で管理）。
- MCP SDK / FastMCP はバージョン差分の影響を受けることがあります。`server.py` が起動しない場合は、依存関係の更新・固定を検討してください。
