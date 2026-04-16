"""
Unit tests for scheduler.py — task scheduling & background jobs.

Tests the SQLite persistence layer, cron validation, and the
tool-facing functions (schedule_task, list_scheduled_tasks, cancel_scheduled_task).

Run with:  pytest tests/test_scheduler.py -v --tb=short
"""

import os

import pytest


# ===================================================================
# Fixture: temporary database
# ===================================================================

@pytest.fixture
def db(tmp_path):
    """Return a path to a fresh temporary SQLite database."""
    return str(tmp_path / "tasks.db")


# ===================================================================
# Database helpers — _add_task, _list_tasks, _get_task, _remove_task
# ===================================================================

class TestDatabaseHelpers:
    """Tests for the low-level DB functions."""

    def test_add_and_get_task(self, db):
        from scheduler import _add_task, _get_task
        task_id = _add_task("Check news", "0 8 * * *", notify=True, db_path=db)
        assert len(task_id) == 8

        task = _get_task(task_id, db_path=db)
        assert task is not None
        assert task["description"] == "Check news"
        assert task["cron_expr"] == "0 8 * * *"
        assert task["enabled"] == 1
        assert task["notify"] == 1
        assert task["last_run"] is None
        assert task["last_result"] is None

    def test_list_tasks_empty(self, db):
        from scheduler import _list_tasks
        assert _list_tasks(db_path=db) == []

    def test_list_tasks_returns_all(self, db):
        from scheduler import _add_task, _list_tasks
        _add_task("Task A", "0 * * * *", db_path=db)
        _add_task("Task B", "*/5 * * * *", db_path=db)
        tasks = _list_tasks(db_path=db)
        assert len(tasks) == 2

    def test_remove_task_success(self, db):
        from scheduler import _add_task, _remove_task, _get_task
        task_id = _add_task("Temp task", "0 0 * * *", db_path=db)
        assert _remove_task(task_id, db_path=db) is True
        assert _get_task(task_id, db_path=db) is None

    def test_remove_nonexistent_returns_false(self, db):
        from scheduler import _remove_task
        assert _remove_task("nonexist", db_path=db) is False

    def test_update_task_result(self, db):
        from scheduler import _add_task, _update_task_result, _get_task
        task_id = _add_task("Run check", "0 9 * * *", db_path=db)
        _update_task_result(task_id, "All good!", db_path=db)
        task = _get_task(task_id, db_path=db)
        assert task["last_result"] == "All good!"
        assert task["last_run"] is not None

    def test_update_result_truncates_long_text(self, db):
        from scheduler import _add_task, _update_task_result, _get_task
        task_id = _add_task("Big result", "0 0 * * *", db_path=db)
        long_text = "x" * 5000
        _update_task_result(task_id, long_text, db_path=db)
        task = _get_task(task_id, db_path=db)
        assert len(task["last_result"]) == 2000

    def test_set_task_enabled(self, db):
        from scheduler import _add_task, _set_task_enabled, _get_task
        task_id = _add_task("Toggle me", "0 0 * * *", db_path=db)
        _set_task_enabled(task_id, False, db_path=db)
        assert _get_task(task_id, db_path=db)["enabled"] == 0
        _set_task_enabled(task_id, True, db_path=db)
        assert _get_task(task_id, db_path=db)["enabled"] == 1

    def test_set_enabled_nonexistent_returns_false(self, db):
        from scheduler import _set_task_enabled
        assert _set_task_enabled("nope", True, db_path=db) is False

    def test_get_nonexistent_task_returns_none(self, db):
        from scheduler import _get_task
        assert _get_task("nope", db_path=db) is None


# ===================================================================
# Cron validation
# ===================================================================

class TestCronValidation:
    """Tests for validate_cron()."""

    @pytest.mark.parametrize("expr", [
        "0 8 * * *",       # daily at 8 AM
        "*/5 * * * *",     # every 5 minutes
        "0 0 1 * *",       # first of every month
        "30 14 * * 1-5",   # weekdays at 2:30 PM
        "0 */2 * * *",     # every 2 hours
    ])
    def test_valid_expressions(self, expr):
        from scheduler import validate_cron
        valid, err = validate_cron(expr)
        assert valid is True
        assert err == ""

    @pytest.mark.parametrize("expr", [
        "",
        "not a cron",
        "60 * * * *",      # minute out of range
        "* * * *",         # too few fields
        "* * * * * * *",   # too many fields
    ])
    def test_invalid_expressions(self, expr):
        from scheduler import validate_cron
        valid, err = validate_cron(expr)
        assert valid is False
        assert err != ""


# ===================================================================
# Tool function — schedule_task
# ===================================================================

class TestScheduleTask:
    """Tests for the schedule_task tool function."""

    def test_schedules_valid_task(self, db, monkeypatch):
        from scheduler import schedule_task
        import scheduler
        monkeypatch.setattr(scheduler, "DB_PATH", db)

        result = schedule_task(
            description="Check BBC News",
            cron="0 8 * * *",
            notify=True,
        )
        assert "successfully" in result.lower()
        assert "0 8 * * *" in result
        assert "Check BBC News" in result

    def test_missing_description_returns_error(self, db, monkeypatch):
        from scheduler import schedule_task
        import scheduler
        monkeypatch.setattr(scheduler, "DB_PATH", db)

        result = schedule_task(description="", cron="0 * * * *")
        assert "Error" in result
        assert "description" in result.lower()

    def test_missing_cron_returns_error(self, db, monkeypatch):
        from scheduler import schedule_task
        import scheduler
        monkeypatch.setattr(scheduler, "DB_PATH", db)

        result = schedule_task(description="Do something", cron="")
        assert "Error" in result
        assert "cron" in result.lower()

    def test_invalid_cron_returns_error(self, db, monkeypatch):
        from scheduler import schedule_task
        import scheduler
        monkeypatch.setattr(scheduler, "DB_PATH", db)

        result = schedule_task(description="Bad cron", cron="not valid")
        assert "Error" in result
        assert "invalid cron" in result.lower()

    def test_notify_defaults_to_off(self, db, monkeypatch):
        from scheduler import schedule_task
        import scheduler
        monkeypatch.setattr(scheduler, "DB_PATH", db)

        result = schedule_task(description="No notify", cron="0 9 * * *")
        assert "Notifications: off" in result


# ===================================================================
# Tool function — list_scheduled_tasks
# ===================================================================

class TestListScheduledTasks:
    """Tests for the list_scheduled_tasks tool function."""

    def test_empty_list(self, db, monkeypatch):
        from scheduler import list_scheduled_tasks
        import scheduler
        monkeypatch.setattr(scheduler, "DB_PATH", db)

        result = list_scheduled_tasks()
        assert "no scheduled tasks" in result.lower()

    def test_lists_existing_tasks(self, db, monkeypatch):
        from scheduler import list_scheduled_tasks, _add_task
        import scheduler
        monkeypatch.setattr(scheduler, "DB_PATH", db)

        _add_task("Morning news", "0 8 * * *", db_path=db)
        _add_task("Weather check", "0 7 * * *", notify=True, db_path=db)

        result = list_scheduled_tasks()
        assert "2 scheduled task" in result
        assert "Morning news" in result
        assert "Weather check" in result

    def test_shows_last_result(self, db, monkeypatch):
        from scheduler import list_scheduled_tasks, _add_task, _update_task_result
        import scheduler
        monkeypatch.setattr(scheduler, "DB_PATH", db)

        task_id = _add_task("Check stock", "*/30 * * * *", db_path=db)
        _update_task_result(task_id, "AAPL: $185.50", db_path=db)

        result = list_scheduled_tasks()
        assert "AAPL: $185.50" in result


# ===================================================================
# Tool function — cancel_scheduled_task
# ===================================================================

class TestCancelScheduledTask:
    """Tests for the cancel_scheduled_task tool function."""

    def test_cancels_existing_task(self, db, monkeypatch):
        from scheduler import cancel_scheduled_task, _add_task, _get_task
        import scheduler
        monkeypatch.setattr(scheduler, "DB_PATH", db)

        task_id = _add_task("Delete me", "0 0 * * *", db_path=db)
        result = cancel_scheduled_task(task_id)
        assert "cancelled" in result.lower()
        assert _get_task(task_id, db_path=db) is None

    def test_cancel_nonexistent_returns_error(self, db, monkeypatch):
        from scheduler import cancel_scheduled_task
        import scheduler
        monkeypatch.setattr(scheduler, "DB_PATH", db)

        result = cancel_scheduled_task("nope1234")
        assert "Error" in result or "no task found" in result.lower()

    def test_cancel_empty_id_returns_error(self):
        from scheduler import cancel_scheduled_task
        result = cancel_scheduled_task("")
        assert "Error" in result

    def test_cancel_strips_whitespace(self, db, monkeypatch):
        from scheduler import cancel_scheduled_task, _add_task
        import scheduler
        monkeypatch.setattr(scheduler, "DB_PATH", db)

        task_id = _add_task("Padded ID", "0 0 * * *", db_path=db)
        result = cancel_scheduled_task(f"  {task_id}  ")
        assert "cancelled" in result.lower()


# ===================================================================
# Scheduler tools registered in tools/system.py
# ===================================================================

class TestSchedulerToolRegistration:
    """Verify scheduling tools are registered in the system tools module."""

    def test_contains_scheduler_tool_names(self):
        from tools.system import get_tools
        tools = get_tools()
        names = {t.name for t in tools}
        expected = {"schedule_task", "list_scheduled_tasks", "cancel_scheduled_task"}
        missing = expected - names
        assert not missing, f"Missing tools: {missing}"
