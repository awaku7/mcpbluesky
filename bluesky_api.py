import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class BlueskySession:
    accessJwt: str | None = None
    refreshJwt: str | None = None
    did: str | None = None
    handle: str | None = None
    pds_url: str = "https://bsky.social"


class BlueskyAPI:
    """Bluesky API client wrapper.

    - MCP tool 実装から HTTP 呼び出し・セッション管理・共通ロジックを分離するための薄い層。
    - http_get_json / http_post_json は外部から注入し、テストや差し替えを容易にする。
    """

    def __init__(self, session: BlueskySession, http_get_json, http_post_json):
        self.session = session
        self.http_get_json = http_get_json
        self.http_post_json = http_post_json

    # -------------------------
    # Common helpers
    # -------------------------
    @staticmethod
    def parse_facets(text: str):
        """テキストからURLを抽出してBlueskyのfacetsフォーマットに変換します。"""
        facets = []
        url_regex = re.compile(r"(https?://[^\s<>\"]+|www\.[^\s<>\"]+)")

        for match in url_regex.finditer(text):
            url = match.group(0)
            uri = url if url.startswith("http") else f"https://{url}"

            start_byte = len(text[: match.start()].encode("utf-8"))
            end_byte = len(text[: match.end()].encode("utf-8"))

            facets.append(
                {
                    "index": {"byteStart": start_byte, "byteEnd": end_byte},
                    "features": [
                        {
                            "$type": "app.bsky.richtext.facet#link",
                            "uri": uri,
                        }
                    ],
                }
            )
        return facets

    def _now_iso_z(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def auth_params(self) -> dict:
        if self.session.accessJwt:
            return {
                "extra_headers": {"Authorization": f"Bearer {self.session.accessJwt}"},
                "base_url": self.session.pds_url,
            }
        return {"base_url": "https://public.api.bsky.app"}

    def require_auth(self) -> str | None:
        if not self.session.accessJwt:
            return "Error: Authentication required."
        return None

    # -------------------------
    # Auth
    # -------------------------
    def login(self, handle: str, password: str) -> str:
        if not handle or not password:
            return "Error: Handle and password are required."

        if self.session.accessJwt and self.session.handle == handle:
            return f"Already logged in as {handle}."

        try:
            result = self.http_post_json(
                "/xrpc/com.atproto.server.createSession",
                {"identifier": handle, "password": password},
                base_url="https://bsky.social",
            )

            self.session.accessJwt = result.get("accessJwt")
            self.session.refreshJwt = result.get("refreshJwt")
            self.session.did = result.get("did")
            self.session.handle = result.get("handle")

            return f"Login successful as {self.session.handle} (DID: {self.session.did})"
        except Exception as e:
            return f"Login failed: {str(e)}"

    def refresh_session(self) -> str:
        if not self.session.refreshJwt:
            return "Error: No refresh token available. Please login first."

        try:
            result = self.http_post_json(
                "/xrpc/com.atproto.server.refreshSession",
                {},
                extra_headers={"Authorization": f"Bearer {self.session.refreshJwt}"},
                base_url=self.session.pds_url,
            )

            self.session.accessJwt = result.get("accessJwt")
            self.session.refreshJwt = result.get("refreshJwt")
            self.session.did = result.get("did")
            self.session.handle = result.get("handle")

            return f"Session refreshed successfully for {self.session.handle}"
        except Exception as e:
            return f"Refresh failed: {str(e)}"

    # -------------------------
    # Read APIs
    # -------------------------
    def get_profile(self, handle: str) -> str:
        params = self.auth_params()
        result = self.http_get_json("/xrpc/app.bsky.actor.getProfile", {"actor": handle}, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def get_author_feed(self, handle: str, limit: int = 10, cursor: str | None = None) -> str:
        params = self.auth_params()
        query = {"actor": handle, "limit": limit}
        if cursor:
            query["cursor"] = cursor
        result = self.http_get_json("/xrpc/app.bsky.feed.getAuthorFeed", query, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def get_actor_feeds(self, handle: str) -> str:
        params = self.auth_params()
        result = self.http_get_json("/xrpc/app.bsky.feed.getActorFeeds", {"actor": handle}, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def get_timeline(self, limit: int = 20, cursor: str | None = None) -> str:
        err = self.require_auth()
        if err:
            return err
        params = self.auth_params()
        query = {"limit": limit}
        if cursor:
            query["cursor"] = cursor
        result = self.http_get_json("/xrpc/app.bsky.feed.getTimeline", query, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def get_timeline_page(
        self,
        limit: int = 50,
        cursor: str | None = None,
        summary: bool = True,
        text_max_len: int = 120,
    ) -> str:
        err = self.require_auth()
        if err:
            return err

        params = self.auth_params()
        query = {"limit": limit}
        if cursor:
            query["cursor"] = cursor

        result = self.http_get_json("/xrpc/app.bsky.feed.getTimeline", query, **params)

        if not summary:
            return json.dumps(result, ensure_ascii=False, indent=2)

        feed = result.get("feed", [])
        next_cursor = result.get("cursor")

        def _pick_post_view(pv: dict) -> dict:
            author = pv.get("author") or {}
            record = pv.get("record") or {}
            text = record.get("text")
            if isinstance(text, str) and text_max_len is not None and text_max_len > 0:
                if len(text) > text_max_len:
                    text = text[:text_max_len] + "…"

            return {
                "uri": pv.get("uri"),
                "cid": pv.get("cid"),
                "createdAt": record.get("createdAt"),
                "author": {
                    "did": author.get("did"),
                    "handle": author.get("handle"),
                    "displayName": author.get("displayName"),
                },
                "text": text,
                "likeCount": pv.get("likeCount"),
                "replyCount": pv.get("replyCount"),
                "repostCount": pv.get("repostCount"),
                "quoteCount": pv.get("quoteCount"),
            }

        out_items = []
        for item in feed:
            post = item.get("post")
            if isinstance(post, dict):
                out_items.append({"post": _pick_post_view(post), "reason": item.get("reason")})
            else:
                out_items.append({"post": None, "reason": item.get("reason")})

        out = {
            "cursor": next_cursor,
            "limit": limit,
            "count": len(out_items),
            "items": out_items,
        }

        return json.dumps(out, ensure_ascii=False, indent=2)

    def get_post_thread(self, uri: str, depth: int = 6) -> str:
        params = self.auth_params()
        result = self.http_get_json(
            "/xrpc/app.bsky.feed.getPostThread", {"uri": uri, "depth": depth}, **params
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    def get_follows(self, handle: str, limit: int = 50, cursor: str | None = None) -> str:
        params = self.auth_params()
        query = {"actor": handle, "limit": limit}
        if cursor:
            query["cursor"] = cursor
        result = self.http_get_json("/xrpc/app.bsky.graph.getFollows", query, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def get_followers(self, handle: str, limit: int = 50, cursor: str | None = None) -> str:
        params = self.auth_params()
        query = {"actor": handle, "limit": limit}
        if cursor:
            query["cursor"] = cursor
        result = self.http_get_json("/xrpc/app.bsky.graph.getFollowers", query, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def get_notifications(self, limit: int = 20, cursor: str | None = None) -> str:
        err = self.require_auth()
        if err:
            return err
        params = self.auth_params()
        query = {"limit": limit}
        if cursor:
            query["cursor"] = cursor
        result = self.http_get_json(
            "/xrpc/app.bsky.notification.listNotifications", query, **params
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    def resolve_handle(self, handle: str) -> str:
        params = self.auth_params()
        result = self.http_get_json(
            "/xrpc/com.atproto.identity.resolveHandle", {"handle": handle}, **params
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    # -------------------------
    # Write APIs
    # -------------------------
    def post(self, text: str) -> str:
        err = self.require_auth()
        if err:
            return err
        params = self.auth_params()
        now = self._now_iso_z()
        facets = self.parse_facets(text)

        data = {
            "repo": self.session.did,
            "collection": "app.bsky.feed.post",
            "record": {
                "$type": "app.bsky.feed.post",
                "text": text,
                "createdAt": now,
            },
        }
        if facets:
            data["record"]["facets"] = facets

        result = self.http_post_json("/xrpc/com.atproto.repo.createRecord", data, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def reply(self, text: str, parent_uri: str, parent_cid: str, root_uri: str, root_cid: str) -> str:
        err = self.require_auth()
        if err:
            return err
        params = self.auth_params()
        now = self._now_iso_z()
        facets = self.parse_facets(text)

        data = {
            "repo": self.session.did,
            "collection": "app.bsky.feed.post",
            "record": {
                "$type": "app.bsky.feed.post",
                "text": text,
                "createdAt": now,
                "reply": {
                    "parent": {"uri": parent_uri, "cid": parent_cid},
                    "root": {"uri": root_uri, "cid": root_cid},
                },
            },
        }
        if facets:
            data["record"]["facets"] = facets

        result = self.http_post_json("/xrpc/com.atproto.repo.createRecord", data, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def like(self, uri: str, cid: str) -> str:
        err = self.require_auth()
        if err:
            return err
        params = self.auth_params()
        now = self._now_iso_z()
        data = {
            "repo": self.session.did,
            "collection": "app.bsky.feed.like",
            "record": {
                "$type": "app.bsky.feed.like",
                "subject": {"uri": uri, "cid": cid},
                "createdAt": now,
            },
        }
        result = self.http_post_json("/xrpc/com.atproto.repo.createRecord", data, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def repost(self, uri: str, cid: str) -> str:
        err = self.require_auth()
        if err:
            return err
        params = self.auth_params()
        now = self._now_iso_z()
        data = {
            "repo": self.session.did,
            "collection": "app.bsky.feed.repost",
            "record": {
                "$type": "app.bsky.feed.repost",
                "subject": {"uri": uri, "cid": cid},
                "createdAt": now,
            },
        }
        result = self.http_post_json("/xrpc/com.atproto.repo.createRecord", data, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def search_posts(self, query: str, limit: int = 10, cursor: str | None = None) -> str:
        params = self.auth_params()
        q_params = {"q": query, "limit": limit}
        if cursor:
            q_params["cursor"] = cursor
        result = self.http_get_json("/xrpc/app.bsky.feed.searchPosts", q_params, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def get_likes(self, uri: str) -> str:
        params = self.auth_params()
        result = self.http_get_json("/xrpc/app.bsky.feed.getLikes", {"uri": uri}, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def get_lists(self, handle: str, limit: int = 50, cursor: str | None = None) -> str:
        params = self.auth_params()
        query = {"actor": handle, "limit": limit}
        if cursor:
            query["cursor"] = cursor
        result = self.http_get_json("/xrpc/app.bsky.graph.getLists", query, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def get_list(self, list_uri: str, limit: int = 50, cursor: str | None = None) -> str:
        params = self.auth_params()
        query = {"list": list_uri, "limit": limit}
        if cursor:
            query["cursor"] = cursor
        result = self.http_get_json("/xrpc/app.bsky.graph.getList", query, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def delete_post(self, post_uri: str) -> str:
        err = self.require_auth()
        if err:
            return err
        params = self.auth_params()

        parts = post_uri.replace("at://", "").split("/")
        if len(parts) < 3:
            return f"Error: Invalid post URI format: {post_uri}"

        repo = parts[0]
        collection = parts[1]
        rkey = parts[2]

        data = {"repo": repo, "collection": collection, "rkey": rkey}
        result = self.http_post_json("/xrpc/com.atproto.repo.deleteRecord", data, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def follow(self, subject_did: str) -> str:
        err = self.require_auth()
        if err:
            return err
        params = self.auth_params()
        now = self._now_iso_z()
        data = {
            "repo": self.session.did,
            "collection": "app.bsky.graph.follow",
            "record": {
                "$type": "app.bsky.graph.follow",
                "subject": subject_did,
                "createdAt": now,
            },
        }
        result = self.http_post_json("/xrpc/com.atproto.repo.createRecord", data, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def unfollow(self, follow_uri: str) -> str:
        err = self.require_auth()
        if err:
            return err
        params = self.auth_params()

        parts = follow_uri.replace("at://", "").split("/")
        if len(parts) < 3:
            return f"Error: Invalid follow URI format: {follow_uri}"

        repo = parts[0]
        collection = parts[1]
        rkey = parts[2]

        data = {"repo": repo, "collection": collection, "rkey": rkey}
        result = self.http_post_json("/xrpc/com.atproto.repo.deleteRecord", data, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def block(self, subject_did: str) -> str:
        err = self.require_auth()
        if err:
            return err
        params = self.auth_params()
        now = self._now_iso_z()
        data = {
            "repo": self.session.did,
            "collection": "app.bsky.graph.block",
            "record": {
                "$type": "app.bsky.graph.block",
                "subject": subject_did,
                "createdAt": now,
            },
        }
        result = self.http_post_json("/xrpc/com.atproto.repo.createRecord", data, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def unblock(self, block_uri: str) -> str:
        err = self.require_auth()
        if err:
            return err
        params = self.auth_params()

        parts = block_uri.replace("at://", "").split("/")
        if len(parts) < 3:
            return f"Error: Invalid block URI format: {block_uri}"

        repo = parts[0]
        collection = parts[1]
        rkey = parts[2]

        data = {"repo": repo, "collection": collection, "rkey": rkey}
        result = self.http_post_json("/xrpc/com.atproto.repo.deleteRecord", data, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def create_list(
        self,
        name: str,
        purpose: str = "app.bsky.graph.defs#curatormodlist",
        description: str = "",
    ) -> str:
        err = self.require_auth()
        if err:
            return err
        params = self.auth_params()
        now = self._now_iso_z()
        data = {
            "repo": self.session.did,
            "collection": "app.bsky.graph.list",
            "record": {
                "$type": "app.bsky.graph.list",
                "name": name,
                "purpose": purpose,
                "description": description,
                "createdAt": now,
            },
        }
        result = self.http_post_json("/xrpc/com.atproto.repo.createRecord", data, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def delete_list(self, list_uri: str) -> str:
        err = self.require_auth()
        if err:
            return err
        params = self.auth_params()

        parts = list_uri.replace("at://", "").split("/")
        if len(parts) < 3:
            return f"Error: Invalid list URI format: {list_uri}"

        data = {"repo": parts[0], "collection": parts[1], "rkey": parts[2]}
        result = self.http_post_json("/xrpc/com.atproto.repo.deleteRecord", data, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def add_to_list(self, subject_did: str, list_uri: str) -> str:
        err = self.require_auth()
        if err:
            return err
        params = self.auth_params()
        now = self._now_iso_z()
        data = {
            "repo": self.session.did,
            "collection": "app.bsky.graph.listitem",
            "record": {
                "$type": "app.bsky.graph.listitem",
                "subject": subject_did,
                "list": list_uri,
                "createdAt": now,
            },
        }
        result = self.http_post_json("/xrpc/com.atproto.repo.createRecord", data, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def remove_from_list(self, listitem_uri: str) -> str:
        err = self.require_auth()
        if err:
            return err
        params = self.auth_params()

        parts = listitem_uri.replace("at://", "").split("/")
        if len(parts) < 3:
            return f"Error: Invalid listitem URI format: {listitem_uri}"

        data = {"repo": parts[0], "collection": parts[1], "rkey": parts[2]}
        result = self.http_post_json("/xrpc/com.atproto.repo.deleteRecord", data, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def search_users(self, term: str, limit: int = 10, cursor: str | None = None) -> str:
        params = self.auth_params()
        query = {"q": term, "limit": limit}
        if cursor:
            query["cursor"] = cursor
        result = self.http_get_json("/xrpc/app.bsky.actor.searchActors", query, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def mute(self, handle: str) -> str:
        err = self.require_auth()
        if err:
            return err
        params = self.auth_params()
        result = self.http_post_json("/xrpc/app.bsky.graph.muteActor", {"actor": handle}, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def unmute(self, handle: str) -> str:
        err = self.require_auth()
        if err:
            return err
        params = self.auth_params()
        result = self.http_post_json("/xrpc/app.bsky.graph.unmuteActor", {"actor": handle}, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def update_profile(self, displayName: str | None = None, description: str | None = None) -> str:
        err = self.require_auth()
        if err:
            return err
        params = self.auth_params()

        current = self.http_get_json(
            "/xrpc/app.bsky.actor.getProfile", {"actor": self.session.did}, **params
        )

        data = {
            "repo": self.session.did,
            "collection": "app.bsky.actor.profile",
            "rkey": "self",
            "record": {
                "$type": "app.bsky.actor.profile",
                "displayName": displayName
                if displayName is not None
                else current.get("displayName", ""),
                "description": description
                if description is not None
                else current.get("description", ""),
                "avatar": current.get("avatar"),
                "banner": current.get("banner"),
            },
        }
        result = self.http_post_json("/xrpc/com.atproto.repo.putRecord", data, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def set_threadgate(
        self, post_uri: str, allow_mentions: bool = True, allow_following: bool = False
    ) -> str:
        err = self.require_auth()
        if err:
            return err
        params = self.auth_params()

        rkey = post_uri.split("/")[-1]
        now = self._now_iso_z()

        allow_rules = []
        if allow_mentions:
            allow_rules.append({"$type": "app.bsky.feed.defs#mentionRule"})
        if allow_following:
            allow_rules.append({"$type": "app.bsky.feed.defs#followingRule"})

        data = {
            "repo": self.session.did,
            "collection": "app.bsky.feed.threadgate",
            "rkey": rkey,
            "record": {
                "$type": "app.bsky.feed.threadgate",
                "post": post_uri,
                "allow": allow_rules,
                "createdAt": now,
            },
        }
        result = self.http_post_json("/xrpc/com.atproto.repo.putRecord", data, **params)
        return json.dumps(result, ensure_ascii=False, indent=2)
