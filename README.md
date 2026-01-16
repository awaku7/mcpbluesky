# mcpbluesky

このリポジトリは、**Bluesky 公開 API を操作するための MCP（Model Context Protocol）サーバー** およびクライアントの実装です。
もともとは `sbcagentcli` リポジトリの一部でしたが、独立したリポジトリとして分離されました。

HTTP（Streamable HTTP）ベースで動作し、LLM エージェントから Bluesky の各種機能を呼び出すためのツール群を提供します。

---

## 内容物

- `server.py`
  - Python 実装の MCP サーバー（FastMCP を利用）
  - Bluesky 公開 API を叩くツール群を公開します。
- `bluesky_api.py` / `tools_bluesky.py`
  - Bluesky API との通信およびツール実装の本体。
- `client.py`
  - `server.py` に接続し、ツール一覧の取得や呼び出しをテストするための簡易クライアント。
- `common_http.py`
  - HTTP 通信の共通処理（リトライ、スロットリング、Zscaler 等のネットワーク環境回避処理など）。
- `requirements.txt`
  - 動作に必要な Python パッケージ。

---

## セットアップ

### 依存関係のインストール

```bash
pip install -r requirements.txt
```

---

## 実行方法

### 1. サーバーの起動

```bash
python server.py
```
デフォルトで `http://127.0.0.1:8000/mcp` で待受を開始します。

### 2. クライアントでの動作確認

```bash
python client.py
```
起動中のサーバーに接続し、ツール一覧とプロフィールの取得をテストします。

---

## 提供される主なツール

`server.py` は以下のツールをエージェントに公開します：

- `bsky_login`: Bluesky へのログイン（アプリパスワードを使用）。
- `bsky_get_profile`: 指定したハンドルのプロフィール取得。
- `bsky_get_author_feed`: 指定したハンドルの投稿フィード取得。
- `bsky_search_posts`: 投稿の検索。
- `bsky_post_text`: テキストの投稿。
- （その他、`tools_bluesky.py` で定義されている多数のツール）

---

## 利用環境の設定

LLM エージェント（sbcagentcli 等）から利用する場合は、各エージェントの `mcp_servers.json` に以下のような設定を追加してください。

```json
{
  "mcp_servers": [
    {
      "name": "mcpbluesky",
      "url": "http://127.0.0.1:8000/mcp",
      "transport": "streamable-http"
    }
  ]
}
```

---

## 注意事項

- **認証情報**: ログインには Bluesky の **アプリパスワード** を使用してください。通常のログインパスワードは使用しないでください。
- **ネットワーク**: 429 (Too Many Requests) や 5xx エラーに対する簡易的なリトライ処理が含まれていますが、短時間での大量リクエストには注意してください。
- **分離履歴**: このリポジトリは `sbcagentcli` の `src/scheck/mcp` ディレクトリから履歴を保持したまま抽出されました。
