import json

try:
    from .bluesky_api import BlueskyAPI
except ImportError:
    # `python server.py` 直実行時のフォールバック
    from bluesky_api import BlueskyAPI


def register_bluesky_tools(mcp, api: BlueskyAPI):
    """Register Bluesky-related MCP tools on the provided FastMCP instance."""

    @mcp.tool()
    async def bsky_login(handle: str, password: str) -> str:
        """Blueskyにログインしてセッションを開始します。
        :param handle: ユーザーのハンドル名 (例: yourname.bsky.social)
        :param password: アプリパスワード
        """
        return api.login(handle, password)

    @mcp.tool()
    async def bsky_refresh_session() -> str:
        """リフレッシュトークンを使用してセッションを更新します（認証済みである必要があります）。"""
        return api.refresh_session()

    @mcp.tool()
    async def bsky_get_profile(handle: str) -> str:
        """Blueskyのプロフィールを取得します。"""
        return api.get_profile(handle)

    @mcp.tool()
    async def bsky_get_author_feed(handle: str, limit: int = 10, cursor: str = None) -> str:
        """指定したユーザーの最新の投稿フィードを取得します。"""
        return api.get_author_feed(handle=handle, limit=limit, cursor=cursor)

    @mcp.tool()
    async def bsky_get_actor_feeds(handle: str) -> str:
        """指定したユーザーが作成・公開しているカスタムフィードの一覧を取得します。"""
        return api.get_actor_feeds(handle)

    @mcp.tool()
    async def bsky_get_timeline(limit: int = 20, cursor: str = None) -> str:
        """ログインユーザーのホームタイムラインを取得します（認証必須）。"""
        return api.get_timeline(limit=limit, cursor=cursor)

    @mcp.tool()
    async def bsky_get_timeline_page(
        limit: int = 50,
        cursor: str = None,
        summary: bool = True,
        text_max_len: int = 120,
    ) -> str:
        """ログインユーザーのホームタイムラインを取得します（認証必須）。

        目的:
          - チャット等の出力サイズ制限に引っかからずにページング(cursor)を運用できるよう、
            summary=True では「必要最小限の情報＋次ページcursor」を返します。

        :param limit: 取得件数（Bluesky APIの上限により100程度まで推奨）
        :param cursor: 次ページ取得用cursor（未指定なら先頭ページ）
        :param summary: True の場合は要約形式、False の場合はAPIレスポンス全文
        :param text_max_len: summary=True のとき本文を何文字で切るか
        """
        return api.get_timeline_page(
            limit=limit,
            cursor=cursor,
            summary=summary,
            text_max_len=text_max_len,
        )

    @mcp.tool()
    async def bsky_get_post_thread(uri: str, depth: int = 6) -> str:
        """特定の投稿のスレッド（返信ツリー）を取得します。"""
        return api.get_post_thread(uri=uri, depth=depth)

    @mcp.tool()
    async def bsky_get_follows(handle: str, limit: int = 50, cursor: str = None) -> str:
        """指定したユーザーのフォロー一覧を取得します。"""
        return api.get_follows(handle=handle, limit=limit, cursor=cursor)

    @mcp.tool()
    async def bsky_get_followers(handle: str, limit: int = 50, cursor: str = None) -> str:
        """指定したユーザーのフォロワー一覧を取得します。"""
        return api.get_followers(handle=handle, limit=limit, cursor=cursor)

    @mcp.tool()
    async def bsky_get_notifications(limit: int = 20, cursor: str = None) -> str:
        """ログインユーザーの通知一覧を取得します（認証必須）。"""
        return api.get_notifications(limit=limit, cursor=cursor)

    @mcp.tool()
    async def bsky_resolve_handle(handle: str) -> str:
        """ハンドル名をDIDに変換します。"""
        return api.resolve_handle(handle)

    @mcp.tool()
    async def bsky_post(text: str) -> str:
        """新規投稿を作成します（認証必須）。"""
        return api.post(text)

    @mcp.tool()
    async def bsky_reply(text: str, parent_uri: str, parent_cid: str, root_uri: str, root_cid: str) -> str:
        """特定の投稿に対して返信します（認証必須）。"""
        return api.reply(
            text=text,
            parent_uri=parent_uri,
            parent_cid=parent_cid,
            root_uri=root_uri,
            root_cid=root_cid,
        )

    @mcp.tool()
    async def bsky_like(uri: str, cid: str) -> str:
        """特定の投稿に「いいね」をします（認証必須）。"""
        return api.like(uri=uri, cid=cid)

    @mcp.tool()
    async def bsky_repost(uri: str, cid: str) -> str:
        """特定の投稿をリポストします（認証必須）。"""
        return api.repost(uri=uri, cid=cid)

    @mcp.tool()
    async def bsky_search_posts(query: str, limit: int = 10, cursor: str = None) -> str:
        """Blueskyの公開投稿を検索します。"""
        return api.search_posts(query=query, limit=limit, cursor=cursor)

    @mcp.tool()
    async def bsky_get_likes(uri: str) -> str:
        """指定した投稿のライク（いいね）一覧を取得します。"""
        return api.get_likes(uri)

    @mcp.tool()
    async def bsky_get_lists(handle: str, limit: int = 50, cursor: str = None) -> str:
        """指定したユーザーが作成・公開しているリスト（Curated Lists）の一覧を取得します。"""
        return api.get_lists(handle=handle, limit=limit, cursor=cursor)

    @mcp.tool()
    async def bsky_get_list(list_uri: str, limit: int = 50, cursor: str = None) -> str:
        """指定したリストの詳細（メンバー一覧など）を取得します。"""
        return api.get_list(list_uri=list_uri, limit=limit, cursor=cursor)

    @mcp.tool()
    async def bsky_delete_post(post_uri: str) -> str:
        """投稿を削除します（認証必須）。
        :param post_uri: 削除する投稿のURI (at://did:plc:xxx/app.bsky.feed.post/rkey)
        """
        return api.delete_post(post_uri)

    @mcp.tool()
    async def bsky_follow(subject_did: str) -> str:
        """指定したユーザー（DID）をフォローします（認証必須）。
        :param subject_did: フォローするユーザーのDID
        """
        return api.follow(subject_did)

    @mcp.tool()
    async def bsky_unfollow(follow_uri: str) -> str:
        """フォローを解除します（認証必須）。
        :param follow_uri: 解除するフォローレコードのURI (at://did:plc:xxx/app.bsky.graph.follow/rkey)
        """
        return api.unfollow(follow_uri)

    @mcp.tool()
    async def bsky_block(subject_did: str) -> str:
        """指定したユーザー（DID）をブロックします（認証必須）。
        :param subject_did: ブロックするユーザーのDID
        """
        return api.block(subject_did)

    @mcp.tool()
    async def bsky_unblock(block_uri: str) -> str:
        """ブロックを解除します（認証必須）。
        :param block_uri: 解除するブロックレコードのURI (at://did:plc:xxx/app.bsky.graph.block/rkey)
        """
        return api.unblock(block_uri)

    @mcp.tool()
    async def bsky_create_list(
        name: str,
        purpose: str = "app.bsky.graph.defs#curatormodlist",
        description: str = "",
    ) -> str:
        """新しいリストを作成します（認証必須）。
        :param name: リスト名
        :param purpose: リストの目的（デフォルトはキュレーションリスト: app.bsky.graph.defs#curatormodlist。モデレーション用は #modlist）
        :param description: リストの説明
        """
        return api.create_list(name=name, purpose=purpose, description=description)

    @mcp.tool()
    async def bsky_delete_list(list_uri: str) -> str:
        """リストを削除します（認証必須）。
        :param list_uri: 削除するリストのURI (at://did:plc:xxx/app.bsky.graph.list/rkey)
        """
        return api.delete_list(list_uri)

    @mcp.tool()
    async def bsky_add_to_list(subject_did: str, list_uri: str) -> str:
        """ユーザーをリストに追加します（認証必須）。
        :param subject_did: 追加するユーザーのDID
        :param list_uri: 対象リストのURI
        """
        return api.add_to_list(subject_did=subject_did, list_uri=list_uri)

    @mcp.tool()
    async def bsky_remove_from_list(listitem_uri: str) -> str:
        """ユーザーをリストから削除します（認証必須）。
        :param listitem_uri: 削除するリストアイテム（登録レコード）のURI (at://.../app.bsky.graph.listitem/rkey)
        """
        return api.remove_from_list(listitem_uri)

    @mcp.tool()
    async def bsky_search_users(term: str, limit: int = 10, cursor: str = None) -> str:
        """ユーザーをキーワードで検索します。"""
        return api.search_users(term=term, limit=limit, cursor=cursor)

    @mcp.tool()
    async def bsky_mute(handle: str) -> str:
        """指定したユーザーをミュートします（認証必須）。"""
        return api.mute(handle)

    @mcp.tool()
    async def bsky_unmute(handle: str) -> str:
        """ユーザーのミュートを解除します（認証必須）。"""
        return api.unmute(handle)

    @mcp.tool()
    async def bsky_update_profile(displayName: str = None, description: str = None) -> str:
        """自分のプロフィール（表示名や自己紹介）を更新します（認証必須）。
        指定しなかった項目は現在の値が保持されます。
        """
        return api.update_profile(displayName=displayName, description=description)

    @mcp.tool()
    async def bsky_set_threadgate(
        post_uri: str, allow_mentions: bool = True, allow_following: bool = False
    ) -> str:
        """投稿に対する返信制限（スレッドゲート）を設定します（認証必須）。
        :param post_uri: 対象投稿のURI
        :param allow_mentions: メンションされた人の返信を許可するか
        :param allow_following: フォローしている人の返信を許可するか
        """
        return api.set_threadgate(
            post_uri=post_uri,
            allow_mentions=allow_mentions,
            allow_following=allow_following,
        )

    return True
