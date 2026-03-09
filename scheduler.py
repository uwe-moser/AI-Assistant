"""
Task Scheduling & Background Jobs for ApexFlow.

Persists scheduled tasks to SQLite and runs them via APScheduler.
Each task stores a natural-language description, a cron expression,
and an optional callback (e.g. push notification with results).
"""

import sqlite3
import uuid
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

DB_PATH = "sidekick_scheduled_tasks.db"

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_connection(db_path: str = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_tasks (
            id          TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            cron_expr   TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            enabled     INTEGER NOT NULL DEFAULT 1,
            last_run    TEXT,
            last_result TEXT,
            notify      INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    return conn


def _add_task(description: str, cron_expr: str, notify: bool = False,
              db_path: str = None) -> str:
    """Insert a new task and return its ID."""
    task_id = str(uuid.uuid4())[:8]
    conn = _get_connection(db_path or DB_PATH)
    conn.execute(
        "INSERT INTO scheduled_tasks (id, description, cron_expr, created_at, notify) "
        "VALUES (?, ?, ?, ?, ?)",
        (task_id, description, cron_expr, datetime.now().isoformat(), int(notify)),
    )
    conn.commit()
    conn.close()
    return task_id


def _remove_task(task_id: str, db_path: str = None) -> bool:
    """Delete a task by ID. Returns True if a row was deleted."""
    conn = _get_connection(db_path or DB_PATH)
    cursor = conn.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


def _list_tasks(db_path: str = None) -> list[dict]:
    """Return all tasks as a list of dicts."""
    conn = _get_connection(db_path or DB_PATH)
    rows = conn.execute(
        "SELECT id, description, cron_expr, created_at, enabled, last_run, last_result, notify "
        "FROM scheduled_tasks ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _get_task(task_id: str, db_path: str = None) -> Optional[dict]:
    """Return a single task dict or None."""
    conn = _get_connection(db_path or DB_PATH)
    row = conn.execute(
        "SELECT id, description, cron_expr, created_at, enabled, last_run, last_result, notify "
        "FROM scheduled_tasks WHERE id = ?", (task_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _update_task_result(task_id: str, result: str, db_path: str = None):
    """Update the last_run timestamp and last_result for a task."""
    conn = _get_connection(db_path or DB_PATH)
    conn.execute(
        "UPDATE scheduled_tasks SET last_run = ?, last_result = ? WHERE id = ?",
        (datetime.now().isoformat(), result[:2000], task_id),
    )
    conn.commit()
    conn.close()


def _set_task_enabled(task_id: str, enabled: bool, db_path: str = None) -> bool:
    """Enable or disable a task. Returns True if the task exists."""
    conn = _get_connection(db_path or DB_PATH)
    cursor = conn.execute(
        "UPDATE scheduled_tasks SET enabled = ? WHERE id = ?",
        (int(enabled), task_id),
    )
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated


# ---------------------------------------------------------------------------
# Cron expression validation
# ---------------------------------------------------------------------------

def validate_cron(cron_expr: str) -> tuple[bool, str]:
    """Validate a cron expression. Returns (is_valid, error_message)."""
    try:
        CronTrigger.from_crontab(cron_expr)
        return True, ""
    except ValueError as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# Tool-facing functions (called by LangChain tools)
# ---------------------------------------------------------------------------

def schedule_task(description: str, cron: str, notify: bool = False) -> str:
    """Schedule a recurring background task.

    Args:
        description: What the task should do, e.g. 'Check BBC News for tech headlines'
        cron: A cron expression, e.g. '0 8 * * *' (daily at 8 AM), '*/30 * * * *' (every 30 min)
        notify: Whether to send a push notification with results (default False)
    """
    description = description.strip()
    cron = cron.strip()

    if not description:
        return "Error: 'description' is required."
    if not cron:
        return "Error: 'cron' expression is required."

    valid, err = validate_cron(cron)
    if not valid:
        return f"Error: invalid cron expression '{cron}'. {err}"

    task_id = _add_task(description, cron, notify=notify)
    return (
        f"Task scheduled successfully.\n"
        f"  ID: {task_id}\n"
        f"  Schedule: {cron}\n"
        f"  Description: {description}\n"
        f"  Notifications: {'on' if notify else 'off'}"
    )


def list_scheduled_tasks() -> str:
    """List all scheduled tasks with their status and last results."""
    tasks = _list_tasks()
    if not tasks:
        return "No scheduled tasks found."

    lines = [f"Found {len(tasks)} scheduled task(s):\n"]
    for t in tasks:
        status = "enabled" if t["enabled"] else "disabled"
        last = t["last_run"] or "never"
        lines.append(
            f"  [{t['id']}] {t['description']}\n"
            f"    Schedule: {t['cron_expr']}  |  Status: {status}  |  Last run: {last}\n"
            f"    Notify: {'yes' if t['notify'] else 'no'}"
        )
        if t["last_result"]:
            preview = t["last_result"][:200]
            lines.append(f"    Last result: {preview}")
        lines.append("")
    return "\n".join(lines)


def cancel_scheduled_task(task_id: str) -> str:
    """Cancel (delete) a scheduled task by its ID."""
    task_id = task_id.strip()
    if not task_id:
        return "Error: task ID is required."
    if _remove_task(task_id):
        return f"Task '{task_id}' has been cancelled and removed."
    return f"Error: no task found with ID '{task_id}'."
