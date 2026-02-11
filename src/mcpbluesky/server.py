import os
import sys
import json
import asyncio
import argparse
import websockets
from typing import Dict, Optional

from mcp.server.fastmcp import FastMCP

from .bluesky_db import BlueskyDB
from .common_http import http_get_json, http_post_json
from .bluesky_api import BlueskyAPI, BlueskySession
from .tools_bluesky import register_bluesky_tools


class SessionManager:
    """複数ユーザーのセッションを管理するクラス（永続化対応）"""

    def __init__(self, get_json, post_json, storage_file: str = "sessions.json"):
        self.sessions: Dict[str, BlueskyAPI] = {}
        self.http_get_json = get_json
        self.http_post_json = post_json
        self.storage_file = storage_file
        self.default_handle: Optional[str] = None
        self.load_sessions()

    def load_sessions(self) -> None:
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

    def save_sessions(self) -> None:
        """セッション情報をファイルに保存する"""
        try:
            data = {}
            for handle, api in self.sessions.items():
                s = api.session
                data[handle] = {
                    "accessJwt": s.accessJwt,
                    "refreshJwt": s.refreshJwt,
                    "did": s.did,
                    "handle": s.handle,
                    "pds_url": s.pds_url,
                }
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save sessions: {e}")

    def get_api(self, handle: Optional[str] = None) -> BlueskyAPI:
        target = handle or self.default_handle
        if target and target in self.sessions:
            return self.sessions[target]
        return BlueskyAPI(
            session=BlueskySession(pds_url="https://bsky.social"),
            http_get_json=self.http_get_json,
            http_post_json=self.http_post_json,
        )

    def add_session(self, handle: str, api: BlueskyAPI) -> None:
        self.sessions[handle] = api
        self.default_handle = handle
        self.save_sessions()

    def remove_session(self, handle: str) -> bool:
        """セッションを削除し、ファイルからも除去する"""
        if handle in self.sessions:
            del self.sessions[handle]
            if self.default_handle == handle:
                self.default_handle = list(self.sessions.keys())[-1] if self.sessions else None
            self.save_sessions()
            return True
        return False


mcp = FastMCP(
    "mcpbluesky-multi-user",
)

# database and session manager
db = BlueskyDB()
manager = SessionManager(http_get_json, http_post_json)

# Jetstream listener control (set in main)
# NOTE: 起動時デフォルトでは Jetstream を起動しない。必要な場合は --jetstream を指定する。
JETSTREAM_ENABLED = False

# MCP tool registration
register_bluesky_tools(mcp, manager)


@mcp.tool()
async def bsky_search_local_posts(keyword: Optional[str] = None, limit: int = 50) -> str:
    """ローカルDBに保存された日本語投稿を検索します。"""
    results = db.search_posts(keyword, limit)
    return json.dumps(results, ensure_ascii=False, indent=2)


async def jetstream_listener() -> None:
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
                                "author_handle": None,
                                "text": text,
                                "created_at": record.get("createdAt"),
                                "reply_parent": record.get("reply", {}).get("parent", {}).get("uri"),
                                "reply_root": record.get("reply", {}).get("root", {}).get("uri"),
                            }
                            db.insert_post(post_data)
        except Exception as e:
            print(f"Jetstream Error: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)


def main(argv: Optional[list[str]] = None) -> None:
    """Console script entry point."""

    global JETSTREAM_ENABLED

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
        "--jetstream",
        action="store_true",
        help="Enable Jetstream background listener",
    )

    args = parser.parse_args(argv)

    print(
        f"Starting mcpbluesky (Multi-user support) transport={args.transport}...",
        file=sys.stderr,
    )

    if args.transport in ("sse", "streamable-http"):
        mcp.host = args.host
        mcp.port = args.port

    JETSTREAM_ENABLED = bool(args.jetstream)

    if JETSTREAM_ENABLED:
        import threading

        def _jetstream_thread_main() -> None:
            asyncio.run(jetstream_listener())

        t = threading.Thread(target=_jetstream_thread_main, name="jetstream", daemon=True)
        t.start()

    mcp.run(transport=args.transport, mount_path=args.mount_path)


if __name__ == "__main__":
    main()
