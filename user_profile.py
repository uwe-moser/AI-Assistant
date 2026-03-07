import sqlite3
from datetime import datetime


class UserProfile:
    """Persistent key-value store for user metadata, backed by SQLite."""

    def __init__(self, db_path: str = "sidekick_chat_history.db"):
        self._db_path = db_path
        self._ensure_table()

    def _connect(self):
        return sqlite3.connect(self._db_path)

    def _ensure_table(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_profile (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

    def upsert(self, key: str, value: str):
        """Insert or update a profile fact."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_profile (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key.strip(), value.strip(), datetime.now().isoformat()),
            )

    def get_all(self) -> dict:
        """Return all profile facts as a dict."""
        with self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM user_profile ORDER BY key").fetchall()
        return {k: v for k, v in rows}

    def get_prompt_block(self) -> str:
        """Return a compact string block for injection into the system prompt."""
        facts = self.get_all()
        if not facts:
            return ""
        lines = "\n".join(f"  {k}: {v}" for k, v in facts.items())
        return f"\n\n    Known facts about this user:\n{lines}"