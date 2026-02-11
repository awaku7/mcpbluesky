# mcpbluesky

このリポジトリは、**Bluesky の API を操作するための MCP（Model Context Protocol）サーバー**（FastMCP）と、動作確認用の簡易クライアントを提供します。

Python パッケージは `src/mcpbluesky/` 配下にあり、サーバーは `mcpbluesky.server` をエントリポイントとして起動します。

`pyproject.toml` は Hatchling（PEP 517/518）でビルドする構成で、インストールすると `mcpbluesky` という **コンソールスクリプト**（`mcpbluesky = mcpbluesky.server:main`）が導入されます。

---

## 何ができるか

- **MCP サーバーとして Bluesky API をツール化**
  - 読み取り（プロフィール取得、タイムライン取得、検索など）
  - 書き込み（投稿、返信、いいね、リポスト、フォロー/ブロック、リスト操作など）
- **複数アカウントのセッション管理（永続化）**
  - `sessions.json` にアクセストークン/リフレッシュトークン等を保存
  - `acting_handle` 引数の省略時に使う **デフォルトハンドル**を保持
- （任意）**Jetstream を購読して日本語投稿をローカル SQLite に保存**し、検索可能

---

## ディレクトリ構成

主要ファイルは `src/mcpbluesky/` にあります。

- `src/mcpbluesky/server.py`
  - FastMCP サーバー本体
  - `SessionManager`（複数ユーザーセッションのロード/セーブ/選択）
  - Jetstream 購読（オプション）と DB 保存
  - ローカルDB検索ツール `bsky_search_local_posts` の提供
- `src/mcpbluesky/tools_bluesky.py`
  - MCP ツール（`bsky_*`）の登録
  - `acting_handle` による「どのログインセッションで実行するか」の切替
- `src/mcpbluesky/bluesky_api.py`
  - `BlueskyAPI`（HTTP 呼び出しの薄いラッパ）
  - `BlueskySession`（`accessJwt`/`refreshJwt`/`did`/`handle`/`pds_url`）
  - 投稿テキストのバリデーション（grapheme 300 / bytes 3000）
  - URL/ハッシュタグを facets に変換（UTF-8 バイトオフセットで index 設定）
- `src/mcpbluesky/common_http.py`
  - `urllib.request` ベースの HTTP 実装（requests 非依存）
  - スロットリング（最小間隔 0.2 秒）
  - リトライ（429/403/5xx 等）
  - （環境によっては）Zscaler continue 画面の検知と迂回
- `src/mcpbluesky/bluesky_db.py`
  - Jetstream から受信した投稿を SQLite へ保存・検索
  - 日本語判定（`langs` に `ja`、または ひらがな/カタカナ正規表現）
- `src/mcpbluesky/client.py`
  - HTTP transport（streamable-http）でサーバーに接続し、
    `list_tools()` と `bsky_get_profile` を呼ぶ動作確認用サンプル

---

## MCP サーバー（`server.py`）の挙動

### セッション管理（`SessionManager`）

- セッションは `sessions.json` に永続化されます。
- `SessionManager.default_handle` を保持し、各ツールの `acting_handle` が省略された場合に **そのデフォルトのセッション**を使います。
- `SessionManager.get_api(handle=None)`
  - 対象セッションが存在すればその `BlueskyAPI` を返す
  - 存在しなければ **未ログイン状態の `BlueskyAPI`** を返します（この場合 `auth_params()` により `https://public.api.bsky.app` を使用）

### Jetstream（オプション）

- **起動時デフォルトでは Jetstream は有効になりません。**
- `--jetstream` を付けた場合のみ Jetstream を別スレッドで起動し、
  `wss://jetstream1.us-east.bsky.network/subscribe?wantedCollections=app.bsky.feed.post` を購読します。
- `kind == "commit"` かつ `operation == "create"` の投稿のみを対象にし、
  `BlueskyDB.is_japanese(text, langs)` が True のものだけ DB に保存します。

---

## 提供ツール（MCP tools）

`src/mcpbluesky/tools_bluesky.py` と `src/mcpbluesky/server.py` により、少なくとも以下のツールが登録されます。

### セッション系

- `bsky_login(handle: Optional[str] = None, password: Optional[str] = None)`
  - `handle/password` が省略された場合は環境変数から補完
    - `BSKY_HANDLE`
    - `BSKY_APP_PASSWORD`
  - 既に同一 handle のセッションが存在する場合は `manager.remove_session(handle)` で削除してから再ログインします。
- `bsky_logout(handle: str)`
- `bsky_refresh_session(acting_handle: Optional[str] = None)`

### 読み取り系

- `bsky_get_profile(handle: str, acting_handle: Optional[str] = None)`
- `bsky_get_author_feed(handle: str, limit: int = 10, cursor: Optional[str] = None, acting_handle: Optional[str] = None)`
- `bsky_get_actor_feeds(handle: str, acting_handle: Optional[str] = None)`
- `bsky_get_timeline(limit: int = 20, cursor: Optional[str] = None, acting_handle: Optional[str] = None)`（要認証）
- `bsky_get_timeline_page(limit: int = 50, cursor: Optional[str] = None, summary: bool = True, text_max_len: int = 120, acting_handle: Optional[str] = None)`（要認証）
- `bsky_get_post_thread(uri: str, depth: int = 6, acting_handle: Optional[str] = None)`
- `bsky_get_follows(handle: str, limit: int = 50, cursor: Optional[str] = None, acting_handle: Optional[str] = None)`
- `bsky_get_followers(handle: str, limit: int = 50, cursor: Optional[str] = None, acting_handle: Optional[str] = None)`
- `bsky_get_notifications(limit: int = 20, cursor: Optional[str] = None, acting_handle: Optional[str] = None)`（要認証）
- `bsky_resolve_handle(handle: str, acting_handle: Optional[str] = None)`
- `bsky_search_posts(query: str, limit: int = 10, cursor: Optional[str] = None, acting_handle: Optional[str] = None)`
- `bsky_get_likes(uri: str, acting_handle: Optional[str] = None)`
- `bsky_get_lists(handle: str, limit: int = 50, cursor: Optional[str] = None, acting_handle: Optional[str] = None)`
- `bsky_get_list(list_uri: str, limit: int = 50, cursor: Optional[str] = None, acting_handle: Optional[str] = None)`
- `bsky_search_users(term: str, limit: int = 10, cursor: Optional[str] = None, acting_handle: Optional[str] = None)`

### 書き込み系（要認証）

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

### ローカルDB検索（`server.py` で定義）

- `bsky_search_local_posts(keyword: Optional[str] = None, limit: int = 50)`

---

## セットアップ / インストール

このプロジェクトは `pyproject.toml` を持つ **PEP 517/518** のパッケージで、ビルドバックエンドは **hatchling** です。

- プロジェクト名: `mcpbluesky`
- バージョン: `0.1.2`
- 対象 Python: `>= 3.10`
- 依存:
  - `fastmcp`
  - `grapheme`
  - `websockets`

### 依存関係だけ入れて手元で実行したい場合（開発・検証）

`requirements.txt` があるので、まずこれを入れて `python -m ...` で動かすこともできます。

```bash
pip install -r requirements.txt
```

ただし、この方法は「パッケージとしてインストールされる状態」を作りません。
コンソールスクリプト `mcpbluesky` も入りません。

### editable install（開発用インストール）

リポジトリを編集しながら、通常の import や `mcpbluesky` コマンドで動作させたい場合は editable install を使います。

```bash
pip install -e .
```

この形でインストールすると:

- `import mcpbluesky` が有効になります
- `mcpbluesky` コマンド（`mcpbluesky = mcpbluesky.server:main`）が導入されます

### ビルドしてインストール（配布物の作成）

#### 1) wheel/sdist をビルド

PEP 517 の標準ツール `build` を使うのが簡単です。

```bash
python -m pip install --upgrade build
python -m build
```

成功すると `dist/` 配下に成果物ができます（例）:

- `dist/mcpbluesky-0.1.2-py3-none-any.whl`
- `dist/mcpbluesky-0.1.2.tar.gz`

#### 2) wheel をインストール

```bash
python -m pip install dist/mcpbluesky-0.1.2-py3-none-any.whl
```

（バージョンは `pyproject.toml` の `version` に合わせてください）

#### 3) インストール確認

```bash
mcpbluesky --help
python -c "import mcpbluesky; print(mcpbluesky.__all__)"
```

---

## 起動方法

### 1) インストール済みの場合（推奨）

`pyproject.toml` の `[project.scripts]` により、インストールすると `mcpbluesky` コマンドが使えます。

#### stdio

```bash
mcpbluesky --transport stdio
```

#### HTTP: streamable-http

```bash
mcpbluesky --transport streamable-http --host 127.0.0.1 --port 8000 --mount-path /mcp
```

#### HTTP: sse

```bash
mcpbluesky --transport sse --host 127.0.0.1 --port 8000 --mount-path /mcp
```

#### Jetstream を有効化

```bash
mcpbluesky --transport stdio --jetstream
```

### 2) リポジトリから直接起動する場合

```bash
python -m mcpbluesky.server --transport stdio
```

---

## クライアントサンプル（動作確認）

`src/mcpbluesky/client.py` は、streamable-http で `http://127.0.0.1:8000/mcp` に接続するサンプルです。

```bash
python -m mcpbluesky.client
```

このスクリプトは:

- `list_tools()` を実行してツール一覧を表示
- `bsky_get_profile` を呼び出して `bsky.app` のプロフィールを取得

を行います。

---

## LLM エージェントからの利用（`mcp_servers.json` の例）

HTTP transport の例（`mount-path /mcp` の場合）:

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

- `transport=stdio` で使う場合は、エージェント側の stdio 起動設定（command/args 等）に合わせてください。
- HTTP transport を使う場合、URL は FastMCP の `mount_path` と一致させてください。

---

## 認証情報について

- `bsky_login` は **Bluesky のアプリパスワード**を使います（通常のログインパスワードは使わないでください）。
- 引数で渡すか、環境変数で設定します。
  - `BSKY_HANDLE`
  - `BSKY_APP_PASSWORD`

---

## ローカルDB（Jetstream保存）について

- DB ファイル（デフォルト）: `~/.mcpbluesky/bluesky_posts.db`
- `--jetstream` で Jetstream を購読している間、
  日本語と判定できた投稿が `posts` テーブルに保存されます。
- `bsky_search_local_posts` で保存済み投稿をキーワード検索できます。

---

## 注意事項 / セキュリティ

- `sessions.json` にはアクセストークン/リフレッシュトークン等が保存されます。取り扱いに注意してください。
- Jetstream を有効にした場合、Jetstream の受信処理は別スレッドで動きます。
- `common_http.py` には短時間大量アクセスを抑えるためのスロットリングと、
  429/5xx 等の簡易リトライが入っていますが、過剰なリクエストは避けてください。
