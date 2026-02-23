import sqlite3
import uuid
from datetime import datetime


class SessionManager:
    """Manages named sessions backed by the SQLite chat history database."""

    def __init__(self, db_path: str = "sidekick_chat_history.db"):
        self._db_path = db_path
        self._ensure_table()

    def _connect(self):
        return sqlite3.connect(self._db_path)

    def _ensure_table(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id         TEXT PRIMARY KEY,
                    name       TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

    def create_session(self, name: str = None) -> str:
        session_id = str(uuid.uuid4())
        if not name:
            name = f"Session – {datetime.now().strftime('%b %d, %H:%M')}"
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions (id, name, created_at) VALUES (?, ?, ?)",
                (session_id, name, datetime.now().isoformat()),
            )
        return session_id

    def rename_session(self, session_id: str, name: str):
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET name = ? WHERE id = ?",
                (name.strip(), session_id),
            )

    def list_sessions(self) -> list[tuple]:
        """Returns [(id, name, created_at)] ordered newest first."""
        with self._connect() as conn:
            return conn.execute(
                "SELECT id, name, created_at FROM sessions ORDER BY created_at DESC"
            ).fetchall()

    def get_session(self, session_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, name, created_at FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        return {"id": row[0], "name": row[1], "created_at": row[2]} if row else None

    def get_or_create_latest(self) -> str:
        """Return the most recent session ID, creating one if none exist."""
        sessions = self.list_sessions()
        if sessions:
            return sessions[0][0]
        return self.create_session("Default Session")