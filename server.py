import json
import os
import sys
import asyncio
import argparse
import websockets
from typing import Dict, Optional

from mcp.server.fastmcp import FastMCP
from bluesky_db import BlueskyDB

# common_http をインポート
try:
    from common_http import http_get_json, http_post_json
except ImportError:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    from common_http import http_get_json, http_post_json

try:
    from bluesky_api import BlueskyAPI, BlueskySession
    from tools_bluesky import register_bluesky_tools
except ImportError:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    from bluesky_api import BlueskyAPI, BlueskySession
    from tools_bluesky import register_bluesky_tools



class SessionManager:
    """複数ユーザーのセッションを管理するクラス（永続化対応）"""

    def __init__(self, get_json, post_json, storage_file="sessions.json"):
        self.sessions: Dict[str, BlueskyAPI] = {}
        self.http_get_json = get_json
        self.http_post_json = post_json
        self.storage_file = storage_file
        self.default_handle: Optional[str] = None
        self.load_sessions()

    def load_sessions(self):
        """ファイルからセッション情報を読み込む"""
        if not os.path.exists(self.storage_file):
            return
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for handle, s_data in data.items():
                    session = BlueskySession(**s_data)
                    api = BlueskyAPI(session, self.http_get_json, self.http_post_json)
                    self.sessions[handle] = api
                self.default_handle = list(self.sessions.keys())[-1] if self.sessions else None
                print(f"Loaded {len(self.sessions)} sessions from {self.storage_file}")
        except Exception as e:
            print(f"Failed to load sessions: {e}")

    def save_sessions(self):
        """セッション情報をファイルに保存する"""
        try:
            data = {}
            for handle, api in self.sessions.items():
                # dataclass を辞書変換
                s = api.session
                data[handle] = {
                    "accessJwt": s.accessJwt,
                    "refreshJwt": s.refreshJwt,
                    "did": s.did,
                    "handle": s.handle,
                    "pds_url": s.pds_url
                }
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save sessions: {e}")

    def get_api(self, handle: Optional[str] = None) -> BlueskyAPI:
        target = handle or self.default_handle
        if target and target in self.sessions:
            # 必要に応じてここで有効期限チェックや refresh_session を呼ぶロジックも追加可能
            return self.sessions[target]
        return BlueskyAPI(
            session=BlueskySession(pds_url="https://bsky.social"),
            http_get_json=self.http_get_json,
            http_post_json=self.http_post_json,
        )

    def add_session(self, handle: str, api: BlueskyAPI):
        self.sessions[handle] = api
        self.default_handle = handle
        self.save_sessions()

    def remove_session(self, handle: str) -> bool:
        """セッションを削除し、ファイルからも除去する"""
        if handle in self.sessions:
            del self.sessions[handle]
            # デフォルトハンドルの調整
            if self.default_handle == handle:
                self.default_handle = list(self.sessions.keys())[-1] if self.sessions else None
            self.save_sessions()
            return True
        return False



# FastMCPインスタンスを作成
# transport により host/port が必要な場合と不要な場合があるため、ここでは名前のみ指定し、
# 実際の待受設定は起動時引数で選択する。
mcp = FastMCP(
    "mcpbluesky-multi-user",
)

# データベースとセッションマネージャーの初期化
db = BlueskyDB()
manager = SessionManager(http_get_json, http_post_json)

# Jetstream listener control (set in __main__)
JETSTREAM_ENABLED = True


# MCPツール登録 (managerを渡す)
register_bluesky_tools(mcp, manager)

@mcp.tool()
async def bsky_search_local_posts(keyword: Optional[str] = None, limit: int = 50) -> str:
    """ローカルDBに保存された日本語投稿を検索します。"""
    results = db.search_posts(keyword, limit)
    return json.dumps(results, ensure_ascii=False, indent=2)

async def jetstream_listener():
    """Jetstreamを受信して日本語投稿をDBに保存するバックグラウンドタスク"""
    if not JETSTREAM_ENABLED:
        return
    uri = "wss://jetstream1.us-east.bsky.network/subscribe?wantedCollections=app.bsky.feed.post"
    print(f"Connecting to Jetstream: {uri}")
    
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                async for message in websocket:
                    data = json.loads(message)
                    # 投稿イベント(commit)かつ作成(create)のみ対象
                    if data.get("kind") == "commit" and data.get("commit", {}).get("operation") == "create":
                        commit = data["commit"]
                        record = commit.get("record", {})
                        text = record.get("text", "")
                        langs = record.get("langs", [])
                        
                        if db.is_japanese(text, langs):
                            post_data = {
                                "uri": f"at://{data['did']}/{commit['collection']}/{commit['rkey']}",
                                "cid": commit.get("cid"),
                                "author_did": data["did"],
                                "author_handle": None, # Jetstreamからはハンドルが直接取れないためDIDのみ
                                "text": text,
                                "created_at": record.get("createdAt"),
                                "reply_parent": record.get("reply", {}).get("parent", {}).get("uri"),
                                "reply_root": record.get("reply", {}).get("root", {}).get("uri"),
                            }
                            db.insert_post(post_data)
        except Exception as e:
            print(f"Jetstream Error: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    # NOTE:
    # - transport=stdio は Claude Desktop 等のローカルMCPクライアント向け（ポート待受なし）
    # - transport=streamable-http / sse はHTTP待受を行う
    # - stdio運用では stdout がプロトコル出力に使われるため、ログは stderr に出すのが安全

    parser = argparse.ArgumentParser(description="mcpbluesky server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="MCP transport (default: stdio)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind host for HTTP transports")
    parser.add_argument("--port", type=int, default=8000, help="Bind port for HTTP transports")
    parser.add_argument(
        "--mount-path",
        default=None,
        help="Mount path for HTTP transports (FastMCP mount_path)",
    )
    parser.add_argument(
        "--no-jetstream",
        action="store_true",
        help="Disable Jetstream background listener",
    )

    args = parser.parse_args()

    print(
        f"Starting mcpbluesky (Multi-user support) transport={args.transport}...",
        file=sys.stderr,
    )

    # HTTP transports では host/port を反映させるため、FastMCPの属性を書き換える
    # （FastMCPの実装が host/port を参照する前提）
    if args.transport in ("sse", "streamable-http"):
        mcp.host = args.host
        mcp.port = args.port

    # Jetstreamの起動方法:
    # - stdio: stdoutがMCPプロトコルに使われるため、Jetstreamのログ出力混入を避けたい場合は --no-jetstream を使う。
    #         Jetstreamを動かす場合は、FastMCPが内部でanyio.run()でイベントループを管理するため、
    #         ここから安全に create_task できない。別スレッドで asyncio.run() して常駐させる。
    # - HTTP transports: 同様に別スレッドで常駐させる（MCPサーバー側のループを汚さない）

    JETSTREAM_ENABLED = not args.no_jetstream

    if JETSTREAM_ENABLED:
        import threading

        def _jetstream_thread_main():
            asyncio.run(jetstream_listener())

        t = threading.Thread(target=_jetstream_thread_main, name="jetstream", daemon=True)
        t.start()

    mcp.run(transport=args.transport, mount_path=args.mount_path)
