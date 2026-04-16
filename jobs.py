"""
Job search persistence layer.

Backs the JobSearchAgent with SQLite-stored candidate profile, discovered
jobs, a pipeline status per job, and the per-posting application
requirements the agent collects from Browser/Documents agents.

No submission happens here — the agent is discover-only. "applied" in the
pipeline means the user confirmed they submitted manually using the
generated package.
"""

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Optional

from config import JOBS_DB_PATH

DB_PATH = JOBS_DB_PATH

PIPELINE_STATUSES = (
    "discovered",
    "shortlisted",
    "ready_to_apply",
    "applied",
    "interview",
    "offer",
    "rejected",
    "dismissed",
)

_CREATE_PROFILE_SQL = """
    CREATE TABLE IF NOT EXISTS candidate_profile (
        id         INTEGER PRIMARY KEY CHECK (id = 1),
        data_json  TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
"""

_CREATE_JOBS_SQL = """
    CREATE TABLE IF NOT EXISTS jobs (
        id              TEXT PRIMARY KEY,
        source          TEXT NOT NULL,
        source_id       TEXT,
        title           TEXT NOT NULL,
        company         TEXT,
        location        TEXT,
        salary          TEXT,
        description     TEXT,
        posted_at       TEXT,
        apply_url       TEXT,
        dedupe_key      TEXT UNIQUE,
        raw_json        TEXT,
        match_score     REAL,
        match_rationale TEXT,
        status          TEXT NOT NULL DEFAULT 'discovered',
        notes           TEXT,
        discovered_at   TEXT NOT NULL,
        updated_at      TEXT NOT NULL
    )
"""

_CREATE_REQUIREMENTS_SQL = """
    CREATE TABLE IF NOT EXISTS application_requirements (
        job_id       TEXT PRIMARY KEY,
        apply_method TEXT,
        fields_json  TEXT,
        attachments_json TEXT,
        contact_email TEXT,
        notes        TEXT,
        extracted_at TEXT NOT NULL,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
    )
"""


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

_conn: Optional[sqlite3.Connection] = None
_conn_db_path: Optional[str] = None


def _get_connection(db_path: str = None) -> sqlite3.Connection:
    """Return a SQLite connection with all tables created.

    Custom ``db_path`` (for tests) creates a fresh connection each time.
    Production reuses a module-level connection.
    """
    global _conn, _conn_db_path
    if db_path:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        _ensure_schema(conn)
        return conn
    if _conn is None or _conn_db_path != DB_PATH:
        if _conn is not None:
            _conn.close()
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _ensure_schema(_conn)
        _conn_db_path = DB_PATH
    return _conn


def _ensure_schema(conn: sqlite3.Connection):
    conn.execute(_CREATE_PROFILE_SQL)
    conn.execute(_CREATE_JOBS_SQL)
    conn.execute(_CREATE_REQUIREMENTS_SQL)
    conn.commit()


def close():
    """Close the module-level connection."""
    global _conn, _conn_db_path
    if _conn:
        _conn.close()
        _conn = None
        _conn_db_path = None


# ---------------------------------------------------------------------------
# Candidate profile (single-row JSON blob)
# ---------------------------------------------------------------------------

def get_profile(db_path: str = None) -> dict:
    """Return the stored candidate profile dict, or {} if none saved."""
    conn = _get_connection(db_path)
    row = conn.execute("SELECT data_json FROM candidate_profile WHERE id = 1").fetchone()
    if db_path:
        conn.close()
    if not row:
        return {}
    return json.loads(row["data_json"])


def save_profile(profile: dict, db_path: str = None):
    """Overwrite the candidate profile."""
    conn = _get_connection(db_path)
    conn.execute(
        """
        INSERT INTO candidate_profile (id, data_json, updated_at)
        VALUES (1, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            data_json = excluded.data_json,
            updated_at = excluded.updated_at
        """,
        (json.dumps(profile, ensure_ascii=False), datetime.now().isoformat()),
    )
    conn.commit()
    if db_path:
        conn.close()


def update_profile(patch: dict, db_path: str = None) -> dict:
    """Shallow-merge *patch* into the existing profile and persist."""
    current = get_profile(db_path)
    current.update(patch)
    save_profile(current, db_path)
    return current


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

def _make_dedupe_key(source: str, company: str, title: str, apply_url: str = "") -> str:
    """Normalize company+title (plus URL fallback) for duplicate detection."""
    if apply_url:
        return apply_url.strip().lower().rstrip("/")
    company_norm = (company or "").strip().lower()
    title_norm = (title or "").strip().lower()
    return f"{source}::{company_norm}::{title_norm}"


def upsert_job(
    *,
    source: str,
    title: str,
    company: str = "",
    location: str = "",
    salary: str = "",
    description: str = "",
    posted_at: str = "",
    apply_url: str = "",
    source_id: str = "",
    raw: dict = None,
    db_path: str = None,
) -> tuple[str, bool]:
    """Insert a new job or return the existing one's ID if already seen.

    Returns (job_id, created) where ``created`` is True for a fresh row.
    """
    dedupe_key = _make_dedupe_key(source, company, title, apply_url)
    conn = _get_connection(db_path)

    existing = conn.execute(
        "SELECT id FROM jobs WHERE dedupe_key = ?", (dedupe_key,)
    ).fetchone()
    if existing:
        if db_path:
            conn.close()
        return existing["id"], False

    job_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()
    conn.execute(
        """
        INSERT INTO jobs (
            id, source, source_id, title, company, location, salary, description,
            posted_at, apply_url, dedupe_key, raw_json,
            status, discovered_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'discovered', ?, ?)
        """,
        (
            job_id, source, source_id, title, company, location, salary, description,
            posted_at, apply_url, dedupe_key,
            json.dumps(raw, ensure_ascii=False) if raw else None,
            now, now,
        ),
    )
    conn.commit()
    if db_path:
        conn.close()
    return job_id, True


def get_job(job_id: str, db_path: str = None) -> Optional[dict]:
    conn = _get_connection(db_path)
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if db_path:
        conn.close()
    return dict(row) if row else None


def list_jobs(
    status: str = None,
    limit: int = 50,
    db_path: str = None,
) -> list[dict]:
    conn = _get_connection(db_path)
    if status:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE status = ? "
            "ORDER BY match_score DESC NULLS LAST, discovered_at DESC LIMIT ?",
            (status, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM jobs "
            "ORDER BY match_score DESC NULLS LAST, discovered_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    if db_path:
        conn.close()
    return [dict(r) for r in rows]


def set_status(job_id: str, status: str, notes: str = None, db_path: str = None) -> bool:
    if status not in PIPELINE_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Allowed: {PIPELINE_STATUSES}")
    conn = _get_connection(db_path)
    if notes is not None:
        cursor = conn.execute(
            "UPDATE jobs SET status = ?, notes = ?, updated_at = ? WHERE id = ?",
            (status, notes, datetime.now().isoformat(), job_id),
        )
    else:
        cursor = conn.execute(
            "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
            (status, datetime.now().isoformat(), job_id),
        )
    conn.commit()
    updated = cursor.rowcount > 0
    if db_path:
        conn.close()
    return updated


def set_match_score(
    job_id: str, score: float, rationale: str, db_path: str = None
) -> bool:
    conn = _get_connection(db_path)
    cursor = conn.execute(
        "UPDATE jobs SET match_score = ?, match_rationale = ?, updated_at = ? WHERE id = ?",
        (score, rationale, datetime.now().isoformat(), job_id),
    )
    conn.commit()
    updated = cursor.rowcount > 0
    if db_path:
        conn.close()
    return updated


# ---------------------------------------------------------------------------
# Application requirements (what needs to be entered on the website)
# ---------------------------------------------------------------------------

def save_requirements(
    job_id: str,
    apply_method: str,
    fields: list[dict],
    attachments: list[str] = None,
    contact_email: str = "",
    notes: str = "",
    db_path: str = None,
):
    """Store the extracted application form requirements for a job.

    ``fields`` is a list of dicts like {"label": "Full name", "type": "text", "required": true}.
    ``attachments`` is a list of strings like ["CV (PDF)", "Cover letter"].
    """
    conn = _get_connection(db_path)
    conn.execute(
        """
        INSERT INTO application_requirements (
            job_id, apply_method, fields_json, attachments_json,
            contact_email, notes, extracted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_id) DO UPDATE SET
            apply_method = excluded.apply_method,
            fields_json = excluded.fields_json,
            attachments_json = excluded.attachments_json,
            contact_email = excluded.contact_email,
            notes = excluded.notes,
            extracted_at = excluded.extracted_at
        """,
        (
            job_id, apply_method,
            json.dumps(fields, ensure_ascii=False),
            json.dumps(attachments or [], ensure_ascii=False),
            contact_email, notes, datetime.now().isoformat(),
        ),
    )
    conn.commit()
    if db_path:
        conn.close()


def get_requirements(job_id: str, db_path: str = None) -> Optional[dict]:
    conn = _get_connection(db_path)
    row = conn.execute(
        "SELECT * FROM application_requirements WHERE job_id = ?", (job_id,)
    ).fetchone()
    if db_path:
        conn.close()
    if not row:
        return None
    data = dict(row)
    data["fields"] = json.loads(data.pop("fields_json") or "[]")
    data["attachments"] = json.loads(data.pop("attachments_json") or "[]")
    return data
