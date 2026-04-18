"""Scheduled task listing and cancellation."""

from fastapi import APIRouter, HTTPException

import scheduler
from api.schemas import ScheduledTaskInfo

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[ScheduledTaskInfo])
async def list_tasks() -> list[ScheduledTaskInfo]:
    return [
        ScheduledTaskInfo(
            id=t["id"],
            description=t["description"],
            cron_expr=t["cron_expr"],
            created_at=t["created_at"],
            enabled=bool(t["enabled"]),
            last_run=t["last_run"],
            last_result=t["last_result"],
            notify=bool(t["notify"]),
        )
        for t in scheduler._list_tasks()
    ]


@router.delete("/{task_id}")
async def cancel_task(task_id: str) -> dict:
    """Delete a task and detach it from the live scheduler.

    The Gradio app had a bug where the in-memory scheduler kept firing after
    a row was deleted from SQLite. Notifying ``scheduler._runner`` here closes
    that gap.
    """
    if not scheduler._remove_task(task_id):
        raise HTTPException(404, "task not found")
    if scheduler._runner:
        scheduler._runner.remove(task_id)
    return {"cancelled": True}
