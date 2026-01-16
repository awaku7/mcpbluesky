import os
import sys

from mcp.server.fastmcp import FastMCP

# common_http をインポート
try:
    from common_http import http_get_json, http_post_json
except ImportError:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    from common_http import http_get_json, http_post_json

# このファイルを `python server.py` として直接実行する運用を許容するため、
# 相対importに失敗した場合は同一ディレクトリを sys.path に入れて絶対importでフォールバックする。
try:
    from .bluesky_api import BlueskyAPI, BlueskySession
    from .tools_bluesky import register_bluesky_tools
except ImportError:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    from bluesky_api import BlueskyAPI, BlueskySession
    from tools_bluesky import register_bluesky_tools


# FastMCPインスタンスを作成
mcp = FastMCP(
    "bluesky-public-server",
    host="0.0.0.0",
    port=8000,
)


# セッション情報を保持するグローバル変数（互換のため「SESSION」という名前は維持）
SESSION = BlueskySession(
    accessJwt=None,
    refreshJwt=None,
    did=None,
    handle=None,
    pds_url="https://bsky.social",  # 基本的に bsky.social を使用
)


# APIクライアント（ビジネスロジック層）
API = BlueskyAPI(session=SESSION, http_get_json=http_get_json, http_post_json=http_post_json)


# MCPツール登録
register_bluesky_tools(mcp, API)


if __name__ == "__main__":
    print("Starting Bluesky Full-featured MCP Server (PDS-aware) on port 8000...")
    mcp.run(transport="streamable-http")
