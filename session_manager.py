import sqlite3
import uuid
from datetime import datetime

from config import DB_PATH, CHECKPOINTS_DB_PATH
from langchain_community.chat_message_histories import SQLChatMessageHistory


class SessionManager:
    """Manages named sessions backed by the SQLite chat history database."""

    def __init__(self, db_path: str = DB_PATH, checkpoints_db_path: str = CHECKPOINTS_DB_PATH):
        self._db_path = db_path
        self._checkpoints_db_path = checkpoints_db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._ensure_table()

    def _ensure_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id         TEXT PRIMARY KEY,
                name       TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        self._conn.commit()

    def create_session(self, name: str = None) -> str:
        session_id = str(uuid.uuid4())
        if not name:
            name = f"Session – {datetime.now().strftime('%b %d, %H:%M')}"
        self._conn.execute(
            "INSERT INTO sessions (id, name, created_at) VALUES (?, ?, ?)",
            (session_id, name, datetime.now().isoformat()),
        )
        self._conn.commit()
        return session_id

    def rename_session(self, session_id: str, name: str):
        self._conn.execute(
            "UPDATE sessions SET name = ? WHERE id = ?",
            (name.strip(), session_id),
        )
        self._conn.commit()

    def list_sessions(self) -> list[tuple]:
        """Returns [(id, name, created_at)] ordered newest first."""
        return self._conn.execute(
            "SELECT id, name, created_at FROM sessions ORDER BY created_at DESC"
        ).fetchall()

    def get_session(self, session_id: str) -> dict | None:
        row = self._conn.execute(
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

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all associated data (chat history, checkpoints)."""
        session = self.get_session(session_id)
        if not session:
            return False

        # 1. Delete session record
        self._conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self._conn.commit()

        # 2. Clear chat history
        chat_history = SQLChatMessageHistory(
            session_id=session_id,
            connection=f"sqlite:///{self._db_path}",
        )
        chat_history.clear()

        # 3. Clear checkpoint data
        cp_conn = sqlite3.connect(self._checkpoints_db_path)
        try:
            cp_conn.execute(
                "DELETE FROM checkpoints WHERE thread_id = ?", (session_id,)
            )
            cp_conn.execute(
                "DELETE FROM writes WHERE thread_id = ?", (session_id,)
            )
            cp_conn.commit()
        except sqlite3.OperationalError:
            pass  # tables may not exist yet
        finally:
            cp_conn.close()

        return True

    def close(self):
        self._conn.close()
