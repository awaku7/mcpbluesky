import json
import sys
import os
from datetime import datetime, timezone
from mcp.server.fastmcp import FastMCP

# common_http をインポート
try:
    from common_http import http_get_json, http_post_json
except ImportError:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    from common_http import http_get_json, http_post_json

# FastMCPインスタンスを作成
mcp = FastMCP(
    "bluesky-public-server",
    host="0.0.0.0",
    port=8000
)

# セッション情報を保持するグローバル変数
SESSION = {
    "accessJwt": None,
    "did": None,
    "handle": None,
    "pds_url": "https://bsky.social" # 基本的に bsky.social を使用
}

def get_auth_params():
    if SESSION["accessJwt"]:
        return {
            "extra_headers": {"Authorization": f"Bearer {SESSION['accessJwt']}"},
            "base_url": SESSION["pds_url"]
        }
    return {"base_url": "https://public.api.bsky.app"}

@mcp.tool()
async def bsky_login(handle: str, password: str) -> str:
    """
    Blueskyにログインしてセッションを開始します。
    :param handle: ユーザーのハンドル名 (例: yourname.bsky.social)
    :param password: アプリパスワード
    """
    if not handle or not password:
        return "Error: Handle and password are required."

    try:
        # ログイン時は認証が必要なため bsky.social を直接叩く
        result = http_post_json(
            "/xrpc/com.atproto.server.createSession",
            {"identifier": handle, "password": password},
            base_url="https://bsky.social"
        )
        
        SESSION["accessJwt"] = result.get("accessJwt")
        SESSION["did"] = result.get("did")
        SESSION["handle"] = result.get("handle")
        
        return f"Login successful as {SESSION['handle']} (DID: {SESSION['did']})"
    except Exception as e:
        return f"Login failed: {str(e)}"

@mcp.tool()
async def bsky_get_profile(handle: str) -> str:
    """Blueskyのプロフィールを取得します。"""
    params = get_auth_params()
    result = http_get_json("/xrpc/app.bsky.actor.getProfile", {"actor": handle}, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_get_author_feed(handle: str, limit: int = 10, cursor: str = None) -> str:
    """指定したユーザーの最新の投稿フィードを取得します。"""
    params = get_auth_params()
    query = {"actor": handle, "limit": limit}
    if cursor: query["cursor"] = cursor
    result = http_get_json("/xrpc/app.bsky.feed.getAuthorFeed", query, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_get_actor_feeds(handle: str) -> str:
    """指定したユーザーが作成・公開しているカスタムフィードの一覧を取得します。"""
    params = get_auth_params()
    result = http_get_json("/xrpc/app.bsky.feed.getActorFeeds", {"actor": handle}, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_get_timeline(limit: int = 20, cursor: str = None) -> str:
    """ログインユーザーのホームタイムラインを取得します（認証必須）。"""
    params = get_auth_params()
    if not SESSION["accessJwt"]: return "Error: Authentication required."
    query = {"limit": limit}
    if cursor: query["cursor"] = cursor
    result = http_get_json("/xrpc/app.bsky.feed.getTimeline", query, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_get_post_thread(uri: str, depth: int = 6) -> str:
    """特定の投稿のスレッド（返信ツリー）を取得します。"""
    params = get_auth_params()
    result = http_get_json("/xrpc/app.bsky.feed.getPostThread", {"uri": uri, "depth": depth}, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_get_follows(handle: str, limit: int = 50, cursor: str = None) -> str:
    """指定したユーザーのフォロー一覧を取得します。"""
    params = get_auth_params()
    query = {"actor": handle, "limit": limit}
    if cursor: query["cursor"] = cursor
    result = http_get_json("/xrpc/app.bsky.graph.getFollows", query, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_get_followers(handle: str, limit: int = 50, cursor: str = None) -> str:
    """指定したユーザーのフォロワー一覧を取得します。"""
    params = get_auth_params()
    query = {"actor": handle, "limit": limit}
    if cursor: query["cursor"] = cursor
    result = http_get_json("/xrpc/app.bsky.graph.getFollowers", query, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_get_notifications(limit: int = 20, cursor: str = None) -> str:
    """ログインユーザーの通知一覧を取得します（認証必須）。"""
    params = get_auth_params()
    if not SESSION["accessJwt"]: return "Error: Authentication required."
    query = {"limit": limit}
    if cursor: query["cursor"] = cursor
    result = http_get_json("/xrpc/app.bsky.notification.listNotifications", query, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_resolve_handle(handle: str) -> str:
    """ハンドル名をDIDに変換します。"""
    params = get_auth_params()
    result = http_get_json("/xrpc/com.atproto.identity.resolveHandle", {"handle": handle}, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_post(text: str) -> str:
    """新規投稿を作成します（認証必須）。"""
    params = get_auth_params()
    if not SESSION["accessJwt"]: return "Error: Authentication required."
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    data = {
        "repo": SESSION["did"],
        "collection": "app.bsky.feed.post",
        "record": {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": now
        }
    }
    result = http_post_json("/xrpc/com.atproto.repo.createRecord", data, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_reply(text: str, parent_uri: str, parent_cid: str, root_uri: str, root_cid: str) -> str:
    """特定の投稿に対して返信します（認証必須）。"""
    params = get_auth_params()
    if not SESSION["accessJwt"]: return "Error: Authentication required."
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    data = {
        "repo": SESSION["did"],
        "collection": "app.bsky.feed.post",
        "record": {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": now,
            "reply": {
                "parent": {"uri": parent_uri, "cid": parent_cid},
                "root": {"uri": root_uri, "cid": root_cid}
            }
        }
    }
    result = http_post_json("/xrpc/com.atproto.repo.createRecord", data, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_like(uri: str, cid: str) -> str:
    """特定の投稿に「いいね」をします（認証必須）。"""
    params = get_auth_params()
    if not SESSION["accessJwt"]: return "Error: Authentication required."
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    data = {
        "repo": SESSION["did"],
        "collection": "app.bsky.feed.like",
        "record": {
            "$type": "app.bsky.feed.like",
            "subject": {"uri": uri, "cid": cid},
            "createdAt": now
        }
    }
    result = http_post_json("/xrpc/com.atproto.repo.createRecord", data, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_repost(uri: str, cid: str) -> str:
    """特定の投稿をリポストします（認証必須）。"""
    params = get_auth_params()
    if not SESSION["accessJwt"]: return "Error: Authentication required."
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    data = {
        "repo": SESSION["did"],
        "collection": "app.bsky.feed.repost",
        "record": {
            "$type": "app.bsky.feed.repost",
            "subject": {"uri": uri, "cid": cid},
            "createdAt": now
        }
    }
    result = http_post_json("/xrpc/com.atproto.repo.createRecord", data, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_search_posts(query: str, limit: int = 10, cursor: str = None) -> str:
    """Blueskyの公開投稿を検索します。"""
    params = get_auth_params()
    q_params = {"q": query, "limit": limit}
    if cursor: q_params["cursor"] = cursor
    result = http_get_json("/xrpc/app.bsky.feed.searchPosts", q_params, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_get_likes(uri: str) -> str:
    """指定した投稿のライク（いいね）一覧を取得します。"""
    params = get_auth_params()
    result = http_get_json("/xrpc/app.bsky.feed.getLikes", {"uri": uri}, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_get_lists(handle: str, limit: int = 50, cursor: str = None) -> str:
    """指定したユーザーが作成・公開しているリスト（Curated Lists）の一覧を取得します。"""
    params = get_auth_params()
    query = {"actor": handle, "limit": limit}
    if cursor: query["cursor"] = cursor
    result = http_get_json("/xrpc/app.bsky.graph.getLists", query, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_get_list(list_uri: str, limit: int = 50, cursor: str = None) -> str:
    """指定したリストの詳細（メンバー一覧など）を取得します。"""
    params = get_auth_params()
    query = {"list": list_uri, "limit": limit}
    if cursor: query["cursor"] = cursor
    result = http_get_json("/xrpc/app.bsky.graph.getList", query, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_delete_post(post_uri: str) -> str:
    """
    投稿を削除します（認証必須）。
    :param post_uri: 削除する投稿のURI (at://did:plc:xxx/app.bsky.feed.post/rkey)
    """
    params = get_auth_params()
    if not SESSION["accessJwt"]: return "Error: Authentication required."
    
    # URIからcollectionとrkeyを抽出
    # at://did:plc:xxx/app.bsky.feed.post/rkey
    parts = post_uri.replace("at://", "").split("/")
    if len(parts) < 3:
        return f"Error: Invalid post URI format: {post_uri}"
    
    repo = parts[0]
    collection = parts[1]
    rkey = parts[2]
    
    data = {
        "repo": repo,
        "collection": collection,
        "rkey": rkey
    }
    
    result = http_post_json("/xrpc/com.atproto.repo.deleteRecord", data, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_follow(subject_did: str) -> str:
    """
    指定したユーザー（DID）をフォローします（認証必須）。
    :param subject_did: フォローするユーザーのDID
    """
    params = get_auth_params()
    if not SESSION["accessJwt"]: return "Error: Authentication required."
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    data = {
        "repo": SESSION["did"],
        "collection": "app.bsky.graph.follow",
        "record": {
            "$type": "app.bsky.graph.follow",
            "subject": subject_did,
            "createdAt": now
        }
    }
    result = http_post_json("/xrpc/com.atproto.repo.createRecord", data, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_unfollow(follow_uri: str) -> str:
    """
    フォローを解除します（認証必須）。
    :param follow_uri: 解除するフォローレコードのURI (at://did:plc:xxx/app.bsky.graph.follow/rkey)
    """
    params = get_auth_params()
    if not SESSION["accessJwt"]: return "Error: Authentication required."
    
    parts = follow_uri.replace("at://", "").split("/")
    if len(parts) < 3:
        return f"Error: Invalid follow URI format: {follow_uri}"
    
    repo = parts[0]
    collection = parts[1]
    rkey = parts[2]
    
    data = {
        "repo": repo,
        "collection": collection,
        "rkey": rkey
    }
    
    result = http_post_json("/xrpc/com.atproto.repo.deleteRecord", data, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_block(subject_did: str) -> str:
    """
    指定したユーザー（DID）をブロックします（認証必須）。
    :param subject_did: ブロックするユーザーのDID
    """
    params = get_auth_params()
    if not SESSION["accessJwt"]: return "Error: Authentication required."
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    data = {
        "repo": SESSION["did"],
        "collection": "app.bsky.graph.block",
        "record": {
            "$type": "app.bsky.graph.block",
            "subject": subject_did,
            "createdAt": now
        }
    }
    result = http_post_json("/xrpc/com.atproto.repo.createRecord", data, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_unblock(block_uri: str) -> str:
    """
    ブロックを解除します（認証必須）。
    :param block_uri: 解除するブロックレコードのURI (at://did:plc:xxx/app.bsky.graph.block/rkey)
    """
    params = get_auth_params()
    if not SESSION["accessJwt"]: return "Error: Authentication required."
    
    parts = block_uri.replace("at://", "").split("/")
    if len(parts) < 3:
        return f"Error: Invalid block URI format: {block_uri}"
    
    repo = parts[0]
    collection = parts[1]
    rkey = parts[2]
    
    data = {
        "repo": repo,
        "collection": collection,
        "rkey": rkey
    }
    
    result = http_post_json("/xrpc/com.atproto.repo.deleteRecord", data, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_create_list(name: str, purpose: str = "app.bsky.graph.defs#curatormodlist", description: str = "") -> str:
    """
    新しいリストを作成します（認証必須）。
    :param name: リスト名
    :param purpose: リストの目的（デフォルトはキュレーションリスト: app.bsky.graph.defs#curatormodlist。モデレーション用は #modlist）
    :param description: リストの説明
    """
    params = get_auth_params()
    if not SESSION["accessJwt"]: return "Error: Authentication required."
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    data = {
        "repo": SESSION["did"],
        "collection": "app.bsky.graph.list",
        "record": {
            "$type": "app.bsky.graph.list",
            "name": name,
            "purpose": purpose,
            "description": description,
            "createdAt": now
        }
    }
    result = http_post_json("/xrpc/com.atproto.repo.createRecord", data, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_delete_list(list_uri: str) -> str:
    """
    リストを削除します（認証必須）。
    :param list_uri: 削除するリストのURI (at://did:plc:xxx/app.bsky.graph.list/rkey)
    """
    params = get_auth_params()
    if not SESSION["accessJwt"]: return "Error: Authentication required."
    
    parts = list_uri.replace("at://", "").split("/")
    if len(parts) < 3:
        return f"Error: Invalid list URI format: {list_uri}"
    
    data = {
        "repo": parts[0],
        "collection": parts[1],
        "rkey": parts[2]
    }
    
    result = http_post_json("/xrpc/com.atproto.repo.deleteRecord", data, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_add_to_list(subject_did: str, list_uri: str) -> str:
    """
    ユーザーをリストに追加します（認証必須）。
    :param subject_did: 追加するユーザーのDID
    :param list_uri: 対象リストのURI
    """
    params = get_auth_params()
    if not SESSION["accessJwt"]: return "Error: Authentication required."
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    data = {
        "repo": SESSION["did"],
        "collection": "app.bsky.graph.listitem",
        "record": {
            "$type": "app.bsky.graph.listitem",
            "subject": subject_did,
            "list": list_uri,
            "createdAt": now
        }
    }
    result = http_post_json("/xrpc/com.atproto.repo.createRecord", data, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_remove_from_list(listitem_uri: str) -> str:
    """
    ユーザーをリストから削除します（認証必須）。
    :param listitem_uri: 削除するリストアイテム（登録レコード）のURI (at://.../app.bsky.graph.listitem/rkey)
    """
    params = get_auth_params()
    if not SESSION["accessJwt"]: return "Error: Authentication required."
    
    parts = listitem_uri.replace("at://", "").split("/")
    if len(parts) < 3:
        return f"Error: Invalid listitem URI format: {listitem_uri}"
    
    data = {
        "repo": parts[0],
        "collection": parts[1],
        "rkey": parts[2]
    }
    
    result = http_post_json("/xrpc/com.atproto.repo.deleteRecord", data, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_search_users(term: str, limit: int = 10, cursor: str = None) -> str:
    """ユーザーをキーワードで検索します。"""
    params = get_auth_params()
    query = {"q": term, "limit": limit}
    if cursor: query["cursor"] = cursor
    result = http_get_json("/xrpc/app.bsky.actor.searchActors", query, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_mute(handle: str) -> str:
    """指定したユーザーをミュートします（認証必須）。"""
    params = get_auth_params()
    if not SESSION["accessJwt"]: return "Error: Authentication required."
    result = http_post_json("/xrpc/app.bsky.graph.muteActor", {"actor": handle}, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_unmute(handle: str) -> str:
    """ユーザーのミュートを解除します（認証必須）。"""
    params = get_auth_params()
    if not SESSION["accessJwt"]: return "Error: Authentication required."
    result = http_post_json("/xrpc/app.bsky.graph.unmuteActor", {"actor": handle}, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_update_profile(displayName: str = None, description: str = None) -> str:
    """
    自分のプロフィール（表示名や自己紹介）を更新します（認証必須）。
    指定しなかった項目は現在の値が保持されます。
    """
    params = get_auth_params()
    if not SESSION["accessJwt"]: return "Error: Authentication required."
    
    # 現在のプロフィールを取得
    current = http_get_json("/xrpc/app.bsky.actor.getProfile", {"actor": SESSION["did"]}, **params)
    
    data = {
        "repo": SESSION["did"],
        "collection": "app.bsky.actor.profile",
        "rkey": "self",
        "record": {
            "$type": "app.bsky.actor.profile",
            "displayName": displayName if displayName is not None else current.get("displayName", ""),
            "description": description if description is not None else current.get("description", ""),
            "avatar": current.get("avatar"),
            "banner": current.get("banner")
        }
    }
    # putRecord を使用して更新
    result = http_post_json("/xrpc/com.atproto.repo.putRecord", data, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

@mcp.tool()
async def bsky_set_threadgate(post_uri: str, allow_mentions: bool = True, allow_following: bool = False) -> str:
    """
    投稿に対する返信制限（スレッドゲート）を設定します（認証必須）。
    :param post_uri: 対象投稿のURI
    :param allow_mentions: メンションされた人の返信を許可するか
    :param allow_following: フォローしている人の返信を許可するか
    """
    params = get_auth_params()
    if not SESSION["accessJwt"]: return "Error: Authentication required."
    
    rkey = post_uri.split("/")[-1]
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    allow_rules = []
    if allow_mentions: allow_rules.append({"$type": "app.bsky.feed.defs#mentionRule"})
    if allow_following: allow_rules.append({"$type": "app.bsky.feed.defs#followingRule"})
    
    data = {
        "repo": SESSION["did"],
        "collection": "app.bsky.feed.threadgate",
        "rkey": rkey,
        "record": {
            "$type": "app.bsky.feed.threadgate",
            "post": post_uri,
            "allow": allow_rules,
            "createdAt": now
        }
    }
    result = http_post_json("/xrpc/com.atproto.repo.putRecord", data, **params)
    return json.dumps(result, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    print("Starting Bluesky Full-featured MCP Server (PDS-aware) on port 8000...")
    mcp.run(transport="streamable-http")
