import sqlite3
from datetime import datetime

from config import DB_PATH


class UserProfile:
    """Persistent key-value store for user metadata, backed by SQLite."""

    def __init__(self, db_path: str = DB_PATH):
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._ensure_table()

    def _ensure_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        self._conn.commit()

    def upsert(self, key: str, value: str):
        """Insert or update a profile fact."""
        self._conn.execute(
            """
            INSERT INTO user_profile (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key.strip(), value.strip(), datetime.now().isoformat()),
        )
        self._conn.commit()

    def get_all(self) -> dict:
        """Return all profile facts as a dict."""
        rows = self._conn.execute(
            "SELECT key, value FROM user_profile ORDER BY key"
        ).fetchall()
        return {k: v for k, v in rows}

    def get_prompt_block(self) -> str:
        """Return a compact string block for injection into the system prompt."""
        facts = self.get_all()
        if not facts:
            return ""
        lines = "\n".join(f"  {k}: {v}" for k, v in facts.items())
        return f"\n\n    Known facts about this user:\n{lines}"

    def close(self):
        self._conn.close()
