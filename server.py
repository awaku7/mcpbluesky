import json
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
