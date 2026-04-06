"""
Task Scheduling & Background Jobs for ApexFlow.

Persists scheduled tasks to SQLite and runs them via APScheduler.
Each task stores a natural-language description, a cron expression,
and an optional callback (e.g. push notification with results).
"""

import asyncio
import logging
import sqlite3
import uuid
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import TASKS_DB_PATH

log = logging.getLogger(__name__)

DB_PATH = TASKS_DB_PATH

# Global reference to the running TaskRunner (set by TaskRunner.start())
_runner: Optional["TaskRunner"] = None

# Module-level reusable connection (for production use)
_conn: Optional[sqlite3.Connection] = None
_conn_db_path: Optional[str] = None

_CREATE_TABLE_SQL = """
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
"""

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_connection(db_path: str = None) -> sqlite3.Connection:
    global _conn, _conn_db_path
    # Custom db_path (used by tests) — always create a fresh connection
    if db_path:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute(_CREATE_TABLE_SQL)
        conn.commit()
        return conn
    # Production — reuse the module-level connection (recreate if DB_PATH changed)
    if _conn is None or _conn_db_path != DB_PATH:
        if _conn is not None:
            _conn.close()
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute(_CREATE_TABLE_SQL)
        _conn.commit()
        _conn_db_path = DB_PATH
    return _conn


def close():
    """Close the module-level database connection."""
    global _conn, _conn_db_path
    if _conn:
        _conn.close()
        _conn = None
        _conn_db_path = None


def _add_task(description: str, cron_expr: str, notify: bool = False,
              db_path: str = None) -> str:
    """Insert a new task and return its ID."""
    task_id = str(uuid.uuid4())[:8]
    conn = _get_connection(db_path)
    conn.execute(
        "INSERT INTO scheduled_tasks (id, description, cron_expr, created_at, notify) "
        "VALUES (?, ?, ?, ?, ?)",
        (task_id, description, cron_expr, datetime.now().isoformat(), int(notify)),
    )
    conn.commit()
    if db_path:
        conn.close()
    return task_id


def _remove_task(task_id: str, db_path: str = None) -> bool:
    """Delete a task by ID. Returns True if a row was deleted."""
    conn = _get_connection(db_path)
    cursor = conn.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    if db_path:
        conn.close()
    return deleted


def _list_tasks(db_path: str = None) -> list[dict]:
    """Return all tasks as a list of dicts."""
    conn = _get_connection(db_path)
    rows = conn.execute(
        "SELECT id, description, cron_expr, created_at, enabled, last_run, last_result, notify "
        "FROM scheduled_tasks ORDER BY created_at DESC"
    ).fetchall()
    if db_path:
        conn.close()
    return [dict(r) for r in rows]


def _get_task(task_id: str, db_path: str = None) -> Optional[dict]:
    """Return a single task dict or None."""
    conn = _get_connection(db_path)
    row = conn.execute(
        "SELECT id, description, cron_expr, created_at, enabled, last_run, last_result, notify "
        "FROM scheduled_tasks WHERE id = ?", (task_id,)
    ).fetchone()
    if db_path:
        conn.close()
    return dict(row) if row else None


def _update_task_result(task_id: str, result: str, db_path: str = None):
    """Update the last_run timestamp and last_result for a task."""
    conn = _get_connection(db_path)
    conn.execute(
        "UPDATE scheduled_tasks SET last_run = ?, last_result = ? WHERE id = ?",
        (datetime.now().isoformat(), result[:2000], task_id),
    )
    conn.commit()
    if db_path:
        conn.close()


def _set_task_enabled(task_id: str, enabled: bool, db_path: str = None) -> bool:
    """Enable or disable a task. Returns True if the task exists."""
    conn = _get_connection(db_path)
    cursor = conn.execute(
        "UPDATE scheduled_tasks SET enabled = ? WHERE id = ?",
        (int(enabled), task_id),
    )
    conn.commit()
    updated = cursor.rowcount > 0
    if db_path:
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
# Task Runner – APScheduler runtime engine
# ---------------------------------------------------------------------------

class TaskRunner:
    """Manages the APScheduler instance that actually executes scheduled tasks."""

    def __init__(self):
        self._scheduler = AsyncIOScheduler()
        self._started = False

    # -- lifecycle -----------------------------------------------------------

    async def start(self):
        """Load all enabled tasks from the DB and start the scheduler."""
        if self._started:
            return
        global _runner
        _runner = self

        for task in _list_tasks():
            if task["enabled"]:
                self._register_job(task)

        self._scheduler.start()
        self._started = True
        log.info("TaskRunner started with %d job(s)", len(self._scheduler.get_jobs()))

    def stop(self):
        global _runner
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        _runner = None
        log.info("TaskRunner stopped")

    # -- job management ------------------------------------------------------

    def _register_job(self, task: dict):
        """Add a cron job for *task* (dict from DB) to the scheduler."""
        trigger = CronTrigger.from_crontab(task["cron_expr"])
        self._scheduler.add_job(
            _execute_task,
            trigger=trigger,
            id=task["id"],
            args=[task["id"]],
            replace_existing=True,
            misfire_grace_time=300,
        )

    def add(self, task_id: str):
        """Register a newly-created task in the live scheduler."""
        task = _get_task(task_id)
        if task and task["enabled"]:
            self._register_job(task)

    def remove(self, task_id: str):
        """Remove a task from the live scheduler (if present)."""
        try:
            self._scheduler.remove_job(task_id)
        except Exception:
            pass  # job may not exist if it was already disabled


async def _execute_task(task_id: str):
    """Run a single scheduled task through a temporary Sidekick instance."""
    task = _get_task(task_id)
    if not task or not task["enabled"]:
        return

    log.info("Executing scheduled task %s: %s", task_id, task["description"])

    # Import here to avoid circular imports (sidekick imports scheduler tools)
    from sidekick import Sidekick

    sidekick = None
    try:
        session_id = f"scheduled-{task_id}-{uuid.uuid4().hex[:6]}"
        sidekick = Sidekick(session_id=session_id)
        await sidekick.setup(include_browser=False)

        execution_prompt = (
            f"This is an automated scheduled task execution. "
            f"Do NOT schedule or reschedule anything — the task is already scheduled. "
            f"Your job is to EXECUTE the following task RIGHT NOW by using your tools "
            f"(web search, file writing, PDF creation, etc.):\n\n"
            f"{task['description']}"
        )
        success_criteria = (
            "The task must be fully executed — not planned, not scheduled, but actually done. "
            "All files mentioned must be created. Provide a concise summary of what was done."
        )

        result_text = ""
        async for _ in sidekick.run_superstep(
            execution_prompt,
            success_criteria,
            [],
        ):
            pass  # consume the generator; we only care about the final state

        # Grab the last AI message from chat history
        messages = sidekick.chat_history.messages
        if messages:
            result_text = messages[-1].content[:2000]
        else:
            result_text = "(no output)"

        _update_task_result(task_id, result_text)
        log.info("Task %s completed: %s", task_id, result_text[:120])

        # Optional push notification
        if task["notify"]:
            try:
                from tools.system import push
                push(f"Scheduled task completed: {task['description']}\n\n{result_text[:500]}")
            except Exception as e:
                log.warning("Push notification failed for task %s: %s", task_id, e)

    except Exception as e:
        error_msg = f"Error: {e}"
        _update_task_result(task_id, error_msg)
        log.exception("Task %s failed", task_id)
    finally:
        if sidekick:
            sidekick.cleanup()


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

    # Register in the live scheduler so it starts running immediately
    if _runner:
        _runner.add(task_id)

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
        # Remove from live scheduler
        if _runner:
            _runner.remove(task_id)
        return f"Task '{task_id}' has been cancelled and removed."
    return f"Error: no task found with ID '{task_id}'."
