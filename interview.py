"""
Interview practice persistence layer.

Stores interview sessions (tied to a job) and per-question turns with
scoring. Used by the InterviewCoachAgent.
"""

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Optional

from config import INTERVIEW_DB_PATH

DB_PATH = INTERVIEW_DB_PATH

SESSION_STATUSES = ("in_progress", "finished", "abandoned")

_CREATE_SESSIONS_SQL = """
    CREATE TABLE IF NOT EXISTS interview_sessions (
        id              TEXT PRIMARY KEY,
        job_id          TEXT,
        title           TEXT,
        plan_json       TEXT NOT NULL,
        current_index   INTEGER NOT NULL DEFAULT 0,
        status          TEXT NOT NULL DEFAULT 'in_progress',
        final_summary   TEXT,
        overall_score   REAL,
        created_at      TEXT NOT NULL,
        updated_at      TEXT NOT NULL
    )
"""

_CREATE_TURNS_SQL = """
    CREATE TABLE IF NOT EXISTS interview_turns (
        id          TEXT PRIMARY KEY,
        session_id  TEXT NOT NULL,
        idx         INTEGER NOT NULL,
        question    TEXT NOT NULL,
        category    TEXT,
        answer      TEXT,
        score       REAL,
        critique    TEXT,
        created_at  TEXT NOT NULL,
        FOREIGN KEY (session_id) REFERENCES interview_sessions(id) ON DELETE CASCADE
    )
"""


_conn: Optional[sqlite3.Connection] = None
_conn_db_path: Optional[str] = None


def _get_connection(db_path: str = None) -> sqlite3.Connection:
    global _conn, _conn_db_path
    if db_path:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute(_CREATE_SESSIONS_SQL)
        conn.execute(_CREATE_TURNS_SQL)
        conn.commit()
        return conn
    if _conn is None or _conn_db_path != DB_PATH:
        if _conn is not None:
            _conn.close()
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute(_CREATE_SESSIONS_SQL)
        _conn.execute(_CREATE_TURNS_SQL)
        _conn.commit()
        _conn_db_path = DB_PATH
    return _conn


def close():
    global _conn, _conn_db_path
    if _conn:
        _conn.close()
        _conn = None
        _conn_db_path = None


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def create_session(
    plan: list[dict],
    job_id: str = None,
    title: str = "",
    db_path: str = None,
) -> str:
    """Create a new interview session with a question plan. Returns session ID.

    ``plan`` is a list of {question, category} dicts.
    """
    session_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()
    conn = _get_connection(db_path)
    conn.execute(
        """
        INSERT INTO interview_sessions (id, job_id, title, plan_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (session_id, job_id, title, json.dumps(plan, ensure_ascii=False), now, now),
    )
    # Pre-seed turns for each planned question
    for i, q in enumerate(plan):
        conn.execute(
            """
            INSERT INTO interview_turns (id, session_id, idx, question, category, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4())[:8], session_id, i,
                q.get("question", ""), q.get("category", ""), now,
            ),
        )
    conn.commit()
    if db_path:
        conn.close()
    return session_id


def get_session(session_id: str, db_path: str = None) -> Optional[dict]:
    conn = _get_connection(db_path)
    row = conn.execute(
        "SELECT * FROM interview_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if db_path:
        conn.close()
    return dict(row) if row else None


def list_sessions(db_path: str = None) -> list[dict]:
    conn = _get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM interview_sessions ORDER BY created_at DESC"
    ).fetchall()
    if db_path:
        conn.close()
    return [dict(r) for r in rows]


def get_turns(session_id: str, db_path: str = None) -> list[dict]:
    conn = _get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM interview_turns WHERE session_id = ? ORDER BY idx",
        (session_id,),
    ).fetchall()
    if db_path:
        conn.close()
    return [dict(r) for r in rows]


def get_current_turn(session_id: str, db_path: str = None) -> Optional[dict]:
    """Return the next unanswered turn, or None if all are answered."""
    conn = _get_connection(db_path)
    row = conn.execute(
        "SELECT * FROM interview_turns WHERE session_id = ? AND answer IS NULL "
        "ORDER BY idx LIMIT 1",
        (session_id,),
    ).fetchone()
    if db_path:
        conn.close()
    return dict(row) if row else None


def save_answer(
    turn_id: str,
    answer: str,
    score: float,
    critique: str,
    db_path: str = None,
):
    conn = _get_connection(db_path)
    conn.execute(
        "UPDATE interview_turns SET answer = ?, score = ?, critique = ? WHERE id = ?",
        (answer, score, critique, turn_id),
    )
    conn.commit()
    if db_path:
        conn.close()


def advance_session(session_id: str, db_path: str = None):
    conn = _get_connection(db_path)
    conn.execute(
        "UPDATE interview_sessions SET current_index = current_index + 1, updated_at = ? "
        "WHERE id = ?",
        (datetime.now().isoformat(), session_id),
    )
    conn.commit()
    if db_path:
        conn.close()


def finish_session(
    session_id: str,
    overall_score: float,
    summary: str,
    db_path: str = None,
):
    conn = _get_connection(db_path)
    conn.execute(
        """
        UPDATE interview_sessions
        SET status = 'finished', overall_score = ?, final_summary = ?, updated_at = ?
        WHERE id = ?
        """,
        (overall_score, summary, datetime.now().isoformat(), session_id),
    )
    conn.commit()
    if db_path:
        conn.close()
