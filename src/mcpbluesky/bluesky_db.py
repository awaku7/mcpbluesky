import sqlite3
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class BlueskyDB:
    """Jetstream から受信した投稿を保存・検索するための SQLite ラッパ。"""

    def __init__(self, db_path: str = "~/.mcpbluesky/bluesky_posts.db"):
        self.db_path = self._expand_db_path(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def _expand_db_path(self, path: str) -> str:
        import os

        return os.path.expandvars(os.path.expanduser(path))

    def init_db(self) -> None:
        """データベースとテーブルの初期化"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS posts (
                uri TEXT PRIMARY KEY,
                cid TEXT,
                author_did TEXT,
                author_handle TEXT,
                text TEXT,
                created_at TEXT,
                reply_parent TEXT,
                reply_root TEXT,
                indexed_at REAL
            )
            """
        )

        conn.commit()
        conn.close()

    def is_japanese(self, text: str, langs: Optional[List[str]] = None) -> bool:
        """投稿が日本語かどうかを判定する。

        1. langs タグに 'ja' が含まれていれば日本語とみなす。
        2. テキストにひらがな・カタカナが含まれていれば日本語とみなす。
        """

        if langs and "ja" in langs:
            return True

        if not text:
            return False

        japanese_pattern = re.compile(r"[\u3040-\u309F\u30A0-\u30FF]")
        if japanese_pattern.search(text):
            return True

        return False

    def insert_post(self, post_data: Dict[str, Any]) -> None:
        """投稿データをDBに保存する"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT OR IGNORE INTO posts (
                    uri, cid, author_did, author_handle, text,
                    created_at, reply_parent, reply_root, indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    post_data.get("uri"),
                    post_data.get("cid"),
                    post_data.get("author_did"),
                    post_data.get("author_handle"),
                    post_data.get("text"),
                    post_data.get("created_at"),
                    post_data.get("reply_parent"),
                    post_data.get("reply_root"),
                    time.time(),
                ),
            )
            conn.commit()
        except Exception as e:
            print(f"DB Insert Error: {e}")
        finally:
            conn.close()

    def search_posts(self, keyword: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """保存された投稿を検索する"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM posts"
        params: list[Any] = []

        if keyword:
            query += " WHERE text LIKE ?"
            params.append(f"%{keyword}%")

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            results.append(dict(row))

        conn.close()
        return results
