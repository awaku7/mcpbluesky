# mcpbluesky

このリポジトリは、**Bluesky の API を操作するための MCP（Model Context Protocol）サーバー**（FastMCP）と、その簡易クライアントを提供します。

- `server.py` は **マルチユーザーのログインセッション管理**（永続化）に対応し、Bluesky の読み取り/書き込み系 API を MCP ツールとして公開します。
- `common_http.py` は `urllib` ベースの軽量 HTTP 実装で、**スロットリング**、**リトライ**、および（環境によっては）**Zscaler の continue 画面を迂回**するための処理を含みます。
- `bluesky_db.py` は Jetstream から受信した投稿のうち **日本語投稿をローカル SQLite に保存**し、簡易検索できるようにします。

---

## ファイル構成と役割

### `server.py`

FastMCP ベースの MCP サーバーです。

主な機能:

- `FastMCP("mcpbluesky-multi-user")` に対して Bluesky 関連ツールを登録
- `SessionManager` による **複数アカウントのセッション管理**
  - `sessions.json` へ永続化（アクセストークン/リフレッシュトークン/DID 等）
  - `default_handle` を保持し、`acting_handle` 省略時の操作対象を決定
- Jetstream（WebSocket）を購読し、受信した投稿のうち日本語と判定できたものを `bluesky_posts.db` に保存
  - `--no-jetstream` で Jetstream を無効化可能
- 起動時引数で transport を切り替え
  - `--transport stdio`（デフォルト）: ローカル MCP クライアント（Claude Desktop 等）向け
  - `--transport sse` / `--transport streamable-http`: HTTP 待受型
  - `--host` / `--port` / `--mount-path` で待受設定を調整

サーバーが登録するツール:

- `tools_bluesky.register_bluesky_tools(mcp, manager)` が定義する Bluesky API 操作ツール一式
- `bsky_search_local_posts`（`server.py` 定義）: ローカルDBに保存した投稿の検索

### `bluesky_api.py`

`BlueskyAPI`（API クライアントの薄いラッパ）と、`BlueskySession`（セッション情報 dataclass）を提供します。

特徴:

- HTTP 実装（`http_get_json` / `http_post_json`）を外部注入でき、テストや差し替えが容易
- `auth_params()` により、
  - ログイン済み: `Authorization: Bearer <accessJwt>` を付与し、`session.pds_url` を base_url に使用
  - 未ログイン: `https://public.api.bsky.app`（AppView / Public API）を base_url に使用
- 投稿本文のバリデーション
  - grapheme 数: 最大 300
  - UTF-8 バイト数: 最大 3000
- `parse_facets(text)`
  - URL とハッシュタグを検出し、Bluesky の richtext facets 形式へ変換
  - byte index（UTF-8 バイトオフセット）を計算して `facet.index.byteStart/byteEnd` を設定

提供メソッド（抜粋）:

- 認証
  - `login(handle, password)`
  - `refresh_session()`
- 読み取り系
  - `get_profile(handle)`
  - `get_author_feed(handle, limit=10, cursor=None)`
  - `get_actor_feeds(handle)`
  - `get_timeline(limit=20, cursor=None)`（要認証）
  - `get_timeline_page(limit=50, cursor=None, summary=True, text_max_len=120)`（要認証・要約出力も可）
  - `get_post_thread(uri, depth=6)`
  - `get_follows(handle, limit=50, cursor=None)`
  - `get_followers(handle, limit=50, cursor=None)`
  - `get_notifications(limit=20, cursor=None)`（要認証）
  - `resolve_handle(handle)`
  - `search_posts(query, limit=10, cursor=None)`
  - `get_likes(uri)`
  - `get_lists(handle, limit=50, cursor=None)`
  - `get_list(list_uri, limit=50, cursor=None)`
  - `search_users(term, limit=10, cursor=None)`
- 書き込み系（要認証）
  - `post(text)`
  - `reply(text, parent_uri, parent_cid, root_uri, root_cid)`
  - `like(uri, cid)`
  - `repost(uri, cid)`
  - `delete_post(post_uri)`
  - `follow(subject_did)` / `unfollow(follow_uri)`
  - `block(subject_did)` / `unblock(block_uri)`
  - `create_list(name, purpose=..., description="")` / `delete_list(list_uri)`
  - `add_to_list(subject_did, list_uri)` / `remove_from_list(listitem_uri)`
  - `mute(handle)` / `unmute(handle)`
  - `update_profile(displayName=None, description=None)`
  - `set_threadgate(post_uri, allow_mentions=True, allow_following=False)`

### `tools_bluesky.py`

`register_bluesky_tools(mcp, manager)` により、FastMCP に Bluesky 用ツールを登録します。

設計上のポイント:

- ほぼすべてのツールが `acting_handle: Optional[str] = None` を受け取り、
  - 指定があればそのハンドルのセッションで実行
  - 省略時は `SessionManager.default_handle` のセッションで実行
- 認証情報の受け渡し
  - `bsky_login` は引数未指定の場合、環境変数を参照
    - `BSKY_HANDLE`
    - `BSKY_APP_PASSWORD`
  - 既存セッションがある場合は `manager.remove_session(handle)` で一旦破棄してから再ログイン

登録されるツール（README 記載のため、名称を正確に列挙）:

- セッション
  - `bsky_login(handle: Optional[str], password: Optional[str])`
  - `bsky_logout(handle: str)`
  - `bsky_refresh_session(acting_handle: Optional[str])`
- 読み取り
  - `bsky_get_profile(handle: str, acting_handle: Optional[str])`
  - `bsky_get_author_feed(handle: str, limit: int = 10, cursor: Optional[str] = None, acting_handle: Optional[str] = None)`
  - `bsky_get_actor_feeds(handle: str, acting_handle: Optional[str] = None)`
  - `bsky_get_timeline(limit: int = 20, cursor: Optional[str] = None, acting_handle: Optional[str] = None)`
  - `bsky_get_timeline_page(limit: int = 50, cursor: Optional[str] = None, summary: bool = True, text_max_len: int = 120, acting_handle: Optional[str] = None)`
  - `bsky_get_post_thread(uri: str, depth: int = 6, acting_handle: Optional[str] = None)`
  - `bsky_get_follows(handle: str, limit: int = 50, cursor: Optional[str] = None, acting_handle: Optional[str] = None)`
  - `bsky_get_followers(handle: str, limit: int = 50, cursor: Optional[str] = None, acting_handle: Optional[str] = None)`
  - `bsky_get_notifications(limit: int = 20, cursor: Optional[str] = None, acting_handle: Optional[str] = None)`
  - `bsky_resolve_handle(handle: str, acting_handle: Optional[str] = None)`
  - `bsky_search_posts(query: str, limit: int = 10, cursor: Optional[str] = None, acting_handle: Optional[str] = None)`
  - `bsky_get_likes(uri: str, acting_handle: Optional[str] = None)`
  - `bsky_get_lists(handle: str, limit: int = 50, cursor: Optional[str] = None, acting_handle: Optional[str] = None)`
  - `bsky_get_list(list_uri: str, limit: int = 50, cursor: Optional[str] = None, acting_handle: Optional[str] = None)`
  - `bsky_search_users(term: str, limit: int = 10, cursor: Optional[str] = None, acting_handle: Optional[str] = None)`
- 書き込み
  - `bsky_post(text: str, acting_handle: Optional[str] = None)`
  - `bsky_reply(text: str, parent_uri: str, parent_cid: str, root_uri: str, root_cid: str, acting_handle: Optional[str] = None)`
  - `bsky_like(uri: str, cid: str, acting_handle: Optional[str] = None)`
  - `bsky_repost(uri: str, cid: str, acting_handle: Optional[str] = None)`
  - `bsky_delete_post(post_uri: str, acting_handle: Optional[str] = None)`
  - `bsky_follow(subject_did: str, acting_handle: Optional[str] = None)`
  - `bsky_unfollow(follow_uri: str, acting_handle: Optional[str] = None)`
  - `bsky_block(subject_did: str, acting_handle: Optional[str] = None)`
  - `bsky_unblock(block_uri: str, acting_handle: Optional[str] = None)`
  - `bsky_create_list(name: str, purpose: str = "app.bsky.graph.defs#curatormodlist", description: str = "", acting_handle: Optional[str] = None)`
  - `bsky_delete_list(list_uri: str, acting_handle: Optional[str] = None)`
  - `bsky_add_to_list(subject_did: str, list_uri: str, acting_handle: Optional[str] = None)`
  - `bsky_remove_from_list(listitem_uri: str, acting_handle: Optional[str] = None)`
  - `bsky_mute(handle: str, acting_handle: Optional[str] = None)`
  - `bsky_unmute(handle: str, acting_handle: Optional[str] = None)`
  - `bsky_update_profile(displayName: Optional[str] = None, description: Optional[str] = None, acting_handle: Optional[str] = None)`
  - `bsky_set_threadgate(post_uri: str, allow_mentions: bool = True, allow_following: bool = False, acting_handle: Optional[str] = None)`

### `common_http.py`

`urllib.request` ベースの HTTP クライアント実装です（requests 非依存）。

- `http_get_json(path, params, retries=3, extra_headers=None, base_url=APPVIEW)`
- `http_post_json(path, payload, retries=3, extra_headers=None, base_url=APPVIEW)`

特徴:

- `_throttle()`
  - プロセス内グローバルで最小リクエスト間隔 `_MIN_INTERVAL=0.2s` を保証
  - `threading.Lock` で並列呼び出しでも最低間隔を維持
- 簡易リトライ
  - 429: `Retry-After` を優先して待機
  - 403/5xx: 3秒待機してリトライ
  - その他例外: 2秒待機してリトライ
- `ZscalerContinueParser` / `try_zscaler_continue()`
  - HTML 内に `_sm_ctn` が含まれる場合、hidden input を集めて continue URL を復元
  - `_trigger_zscaler_continue()` で continue URL にアクセスし、続けて本来の API を再試行

### `bluesky_db.py`

Jetstream から受信した投稿を保存・検索するための SQLite ラッパです。

- DB ファイル: `~/.mcpbluesky/bluesky_posts.db`（デフォルト）
- テーブル: `posts`
  - `uri` (PRIMARY KEY)
  - `cid`
  - `author_did`
  - `author_handle`
  - `text`
  - `created_at`
  - `reply_parent`
  - `reply_root`
  - `indexed_at`（保存時刻の epoch 秒）

日本語判定:

- `langs` に `"ja"` があれば日本語とみなす
- それ以外は、正規表現 `[\u3040-\u309F\u30A0-\u30FF]` により、ひらがな/カタカナが含まれるかで判定

検索:

- `search_posts(keyword=None, limit=50)`
  - `keyword` があれば `text LIKE %keyword%`
  - `created_at DESC` で新しい順

### `client.py`

`mcp.client.streamable_http.streamable_http_client` を使って MCP サーバーに接続し、

- `list_tools()` で利用可能ツール一覧を取得
- `call_tool("bsky_get_profile", {"handle": "bsky.app"})` を実行

して、MCP サーバーが正しく動作しているかを確認するためのサンプルです。

---

## セットアップ

### 依存関係のインストール

```bash
pip install -r requirements.txt
```

---

## 実行方法

### サーバー起動（stdio）

```bash
python server.py
```

### サーバー起動（HTTP: streamable-http / SSE）

`--transport` を指定して起動します。

```bash
python server.py --transport streamable-http --host 127.0.0.1 --port 8000 --mount-path /mcp
```

SSE の場合:

```bash
python server.py --transport sse --host 127.0.0.1 --port 8000 --mount-path /mcp
```

### Jetstream を無効化して起動

```bash
python server.py --no-jetstream
```

---

## LLM エージェントからの利用（mcp_servers.json）

利用するエージェントの `mcp_servers.json` に、接続先を追加します（例）。

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

- `transport=stdio` で使う場合は、エージェント側の stdio 設定（起動コマンド）に合わせてください。
- HTTP 系 transport を使う場合、URL は FastMCP の `mount_path` と一致させてください。

---

## 認証情報について

- `bsky_login` は **Bluesky のアプリパスワード** を使用します。
- 引数で渡すか、環境変数で設定します。
  - `BSKY_HANDLE`
  - `BSKY_APP_PASSWORD`

---

## ローカルDB（Jetstream保存）について

- Jetstream購読で受信した投稿のうち、日本語と判定できた投稿を `bluesky_posts.db` に保存します。
- `bsky_search_local_posts` で、保存済み投稿をキーワード検索できます。

---

## 注意事項 / セキュリティ

- **アプリパスワードを使用**してください（通常のログインパスワードは使用しないでください）。
- `sessions.json` にはアクセストークン/リフレッシュトークン等が保存されます。取り扱いに注意してください。
- Jetstream を stdio transport で有効化すると、stdout を汚して MCP プロトコル出力に干渉する可能性があります。必要に応じて `--no-jetstream` を利用してください。
- レート制限（429）やネットワークエラー時は `common_http.py` 側のリトライ/スロットリングに従いますが、短時間の大量リクエストは避けてください。
