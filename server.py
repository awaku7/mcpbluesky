import os
import sys
from typing import Dict, Optional

from mcp.server.fastmcp import FastMCP

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
    """複数ユーザーのセッションを管理するクラス"""

    def __init__(self, get_json, post_json):
        self.sessions: Dict[str, BlueskyAPI] = {}
        self.http_get_json = get_json
        self.http_post_json = post_json
        self.default_handle: Optional[str] = None

    def get_api(self, handle: Optional[str] = None) -> BlueskyAPI:
        """指定されたハンドル、または最後にログインしたハンドルのAPIインスタンスを返す"""
        target = handle or self.default_handle
        if target and target in self.sessions:
            return self.sessions[target]

        # セッションがない場合は未認証の新規インスタンスを返す
        return BlueskyAPI(
            session=BlueskySession(pds_url="https://bsky.social"),
            http_get_json=self.http_get_json,
            http_post_json=self.http_post_json,
        )

    def add_session(self, handle: str, api: BlueskyAPI):
        self.sessions[handle] = api
        self.default_handle = handle


# FastMCPインスタンスを作成
mcp = FastMCP(
    "mcpbluesky-multi-user",
    host="0.0.0.0",
    port=8000,
)

# セッションマネージャーの初期化
manager = SessionManager(http_get_json, http_post_json)

# MCPツール登録 (managerを渡す)
register_bluesky_tools(mcp, manager)


if __name__ == "__main__":
    print("Starting mcpbluesky (Multi-user support) on port 8000...")
    mcp.run(transport="streamable-http")
