import json
from typing import Optional

from .bluesky_api import BlueskyAPI


def register_bluesky_tools(mcp, manager):
    """Register Bluesky-related MCP tools on the provided FastMCP instance."""

    @mcp.tool()
    async def bsky_login(handle: Optional[str] = None, password: Optional[str] = None) -> str:
        """Blueskyにログインしてセッションを開始します。

        既存のセッションがある場合は一度ログアウトしてから再ログインします。

        handle/password が未指定(None)の場合は、環境変数から補完します。

        - BSKY_HANDLE: ユーザーのハンドル名 (例: yourname.bsky.social)
        - BSKY_APP_PASSWORD: アプリパスワード
        """

        import os

        if handle is None:
            handle = os.getenv("BSKY_HANDLE")
        if password is None:
            password = os.getenv("BSKY_APP_PASSWORD")

        if not handle:
            return "Error: handle is required. Provide 'handle' argument or set env var BSKY_HANDLE."
        if not password:
            return "Error: password is required. Provide 'password' argument or set env var BSKY_APP_PASSWORD."

        # 既存セッションがあれば削除(ログアウト)
        if handle in manager.sessions:
            manager.remove_session(handle)

        new_session = manager.get_api().session.__class__(pds_url="https://bsky.social")
        api = BlueskyAPI(new_session, manager.http_get_json, manager.http_post_json)
        result = api.login(handle, password)
        if "successful" in result:
            manager.add_session(handle, api)
        return result

    @mcp.tool()
    async def bsky_logout(handle: str) -> str:
        """指定したハンドルのログインセッションを破棄（ログアウト）します。"""
        if manager.remove_session(handle):
            return f"Successfully logged out: {handle}"
        return f"Handle not found in sessions: {handle}"

    @mcp.tool()
    async def bsky_refresh_session(acting_handle: Optional[str] = None) -> str:
        """セッションを更新します。"""
        return manager.get_api(acting_handle).refresh_session()

    @mcp.tool()
    async def bsky_get_profile(handle: str, acting_handle: Optional[str] = None) -> str:
        """Blueskyのプロフィールを取得します。"""
        return manager.get_api(acting_handle).get_profile(handle)

    @mcp.tool()
    async def bsky_get_author_feed(
        handle: str,
        limit: int = 10,
        cursor: Optional[str] = None,
        acting_handle: Optional[str] = None,
    ) -> str:
        """指定したユーザーの最新投稿フィードを取得します。"""
        return manager.get_api(acting_handle).get_author_feed(
            handle=handle, limit=limit, cursor=cursor
        )

    @mcp.tool()
    async def bsky_get_actor_feeds(handle: str, acting_handle: Optional[str] = None) -> str:
        """指定したユーザーのカスタムフィード一覧を取得します。"""
        return manager.get_api(acting_handle).get_actor_feeds(handle)

    @mcp.tool()
    async def bsky_get_timeline(
        limit: int = 20, cursor: Optional[str] = None, acting_handle: Optional[str] = None
    ) -> str:
        """ログインユーザーのホームタイムラインを取得します（要認証）。"""
        return manager.get_api(acting_handle).get_timeline(limit=limit, cursor=cursor)

    @mcp.tool()
    async def bsky_get_timeline_page(
        limit: int = 50,
        cursor: Optional[str] = None,
        summary: bool = True,
        text_max_len: int = 120,
        acting_handle: Optional[str] = None,
    ) -> str:
        """ホームタイムラインを要約または全文で取得します（要認証）。"""
        return manager.get_api(acting_handle).get_timeline_page(
            limit=limit,
            cursor=cursor,
            summary=summary,
            text_max_len=text_max_len,
        )

    @mcp.tool()
    async def bsky_get_post_thread(
        uri: str, depth: int = 6, acting_handle: Optional[str] = None
    ) -> str:
        """特定投稿のスレッド（返信ツリー）を取得します。"""
        return manager.get_api(acting_handle).get_post_thread(uri=uri, depth=depth)

    @mcp.tool()
    async def bsky_get_follows(
        handle: str,
        limit: int = 50,
        cursor: Optional[str] = None,
        acting_handle: Optional[str] = None,
    ) -> str:
        """指定ユーザーのフォロー一覧を取得します。"""
        return manager.get_api(acting_handle).get_follows(
            handle=handle, limit=limit, cursor=cursor
        )

    @mcp.tool()
    async def bsky_get_followers(
        handle: str,
        limit: int = 50,
        cursor: Optional[str] = None,
        acting_handle: Optional[str] = None,
    ) -> str:
        """指定ユーザーのフォロワー一覧を取得します。"""
        return manager.get_api(acting_handle).get_followers(
            handle=handle, limit=limit, cursor=cursor
        )

    @mcp.tool()
    async def bsky_get_notifications(
        limit: int = 20, cursor: Optional[str] = None, acting_handle: Optional[str] = None
    ) -> str:
        """ログインユーザーの通知一覧を取得します（要認証）。"""
        return manager.get_api(acting_handle).get_notifications(limit=limit, cursor=cursor)

    @mcp.tool()
    async def bsky_resolve_handle(handle: str, acting_handle: Optional[str] = None) -> str:
        """ハンドル名をDIDに変換します。"""
        return manager.get_api(acting_handle).resolve_handle(handle)

    @mcp.tool()
    async def bsky_post(text: str, acting_handle: Optional[str] = None) -> str:
        """新規投稿を作成します（要認証）。"""
        return manager.get_api(acting_handle).post(text)

    @mcp.tool()
    async def bsky_reply(
        text: str,
        parent_uri: str,
        parent_cid: str,
        root_uri: str,
        root_cid: str,
        acting_handle: Optional[str] = None,
    ) -> str:
        """特定投稿へ返信します（要認証）。"""
        return manager.get_api(acting_handle).reply(
            text=text,
            parent_uri=parent_uri,
            parent_cid=parent_cid,
            root_uri=root_uri,
            root_cid=root_cid,
        )

    @mcp.tool()
    async def bsky_like(uri: str, cid: str, acting_handle: Optional[str] = None) -> str:
        """特定投稿にいいねします（要認証）。"""
        return manager.get_api(acting_handle).like(uri=uri, cid=cid)

    @mcp.tool()
    async def bsky_repost(uri: str, cid: str, acting_handle: Optional[str] = None) -> str:
        """特定投稿をリポストします（要認証）。"""
        return manager.get_api(acting_handle).repost(uri=uri, cid=cid)

    @mcp.tool()
    async def bsky_search_posts(
        query: str,
        limit: int = 10,
        cursor: Optional[str] = None,
        acting_handle: Optional[str] = None,
    ) -> str:
        """公開投稿を検索します。"""
        return manager.get_api(acting_handle).search_posts(
            query=query, limit=limit, cursor=cursor
        )

    @mcp.tool()
    async def bsky_get_likes(uri: str, acting_handle: Optional[str] = None) -> str:
        """指定投稿のいいね一覧を取得します。"""
        return manager.get_api(acting_handle).get_likes(uri)

    @mcp.tool()
    async def bsky_get_lists(
        handle: str,
        limit: int = 50,
        cursor: Optional[str] = None,
        acting_handle: Optional[str] = None,
    ) -> str:
        """指定ユーザーのリスト一覧を取得します。"""
        return manager.get_api(acting_handle).get_lists(handle=handle, limit=limit, cursor=cursor)

    @mcp.tool()
    async def bsky_get_list(
        list_uri: str,
        limit: int = 50,
        cursor: Optional[str] = None,
        acting_handle: Optional[str] = None,
    ) -> str:
        """指定リストの詳細を取得します。"""
        return manager.get_api(acting_handle).get_list(list_uri=list_uri, limit=limit, cursor=cursor)

    @mcp.tool()
    async def bsky_delete_post(post_uri: str, acting_handle: Optional[str] = None) -> str:
        """投稿を削除します（要認証）。"""
        return manager.get_api(acting_handle).delete_post(post_uri)

    @mcp.tool()
    async def bsky_follow(subject_did: str, acting_handle: Optional[str] = None) -> str:
        """指定DIDをフォローします（要認証）。"""
        return manager.get_api(acting_handle).follow(subject_did)

    @mcp.tool()
    async def bsky_unfollow(follow_uri: str, acting_handle: Optional[str] = None) -> str:
        """フォローを解除します（要認証）。"""
        return manager.get_api(acting_handle).unfollow(follow_uri)

    @mcp.tool()
    async def bsky_block(subject_did: str, acting_handle: Optional[str] = None) -> str:
        """指定DIDをブロックします（要認証）。"""
        return manager.get_api(acting_handle).block(subject_did)

    @mcp.tool()
    async def bsky_unblock(block_uri: str, acting_handle: Optional[str] = None) -> str:
        """ブロックを解除します（要認証）。"""
        return manager.get_api(acting_handle).unblock(block_uri)

    @mcp.tool()
    async def bsky_create_list(
        name: str,
        purpose: str = "app.bsky.graph.defs#curatormodlist",
        description: str = "",
        acting_handle: Optional[str] = None,
    ) -> str:
        """新しいリストを作成します（要認証）。"""
        return manager.get_api(acting_handle).create_list(
            name=name, purpose=purpose, description=description
        )

    @mcp.tool()
    async def bsky_delete_list(list_uri: str, acting_handle: Optional[str] = None) -> str:
        """リストを削除します（要認証）。"""
        return manager.get_api(acting_handle).delete_list(list_uri)

    @mcp.tool()
    async def bsky_add_to_list(
        subject_did: str, list_uri: str, acting_handle: Optional[str] = None
    ) -> str:
        """ユーザーをリストに追加します（要認証）。"""
        return manager.get_api(acting_handle).add_to_list(
            subject_did=subject_did, list_uri=list_uri
        )

    @mcp.tool()
    async def bsky_remove_from_list(
        listitem_uri: str, acting_handle: Optional[str] = None
    ) -> str:
        """ユーザーをリストから削除します（要認証）。"""
        return manager.get_api(acting_handle).remove_from_list(listitem_uri)

    @mcp.tool()
    async def bsky_search_users(
        term: str,
        limit: int = 10,
        cursor: Optional[str] = None,
        acting_handle: Optional[str] = None,
    ) -> str:
        """ユーザーをキーワードで検索します。"""
        return manager.get_api(acting_handle).search_users(
            term=term, limit=limit, cursor=cursor
        )

    @mcp.tool()
    async def bsky_mute(handle: str, acting_handle: Optional[str] = None) -> str:
        """指定ユーザーをミュートします（要認証）。"""
        return manager.get_api(acting_handle).mute(handle)

    @mcp.tool()
    async def bsky_unmute(handle: str, acting_handle: Optional[str] = None) -> str:
        """ミュートを解除します（要認証）。"""
        return manager.get_api(acting_handle).unmute(handle)

    @mcp.tool()
    async def bsky_update_profile(
        displayName: Optional[str] = None,
        description: Optional[str] = None,
        acting_handle: Optional[str] = None,
    ) -> str:
        """自分のプロフィールを更新します（要認証）。"""
        return manager.get_api(acting_handle).update_profile(
            displayName=displayName, description=description
        )

    @mcp.tool()
    async def bsky_set_threadgate(
        post_uri: str,
        allow_mentions: bool = True,
        allow_following: bool = False,
        acting_handle: Optional[str] = None,
    ) -> str:
        """投稿に対する返信制限を設定します（要認証）。"""
        return manager.get_api(acting_handle).set_threadgate(
            post_uri=post_uri,
            allow_mentions=allow_mentions,
            allow_following=allow_following,
        )

    return True
