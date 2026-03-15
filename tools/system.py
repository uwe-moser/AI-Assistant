"""System tools: push notifications, task scheduling, Python REPL."""

import os
import requests

from langchain_core.tools import Tool, StructuredTool
from langchain_experimental.tools import PythonREPLTool

from scheduler import schedule_task, list_scheduled_tasks, cancel_scheduled_task


PUSHOVER_URL = "https://api.pushover.net/1/messages.json"


def push(text: str) -> str:
    """Send a push notification to the user."""
    token = os.getenv("PUSHOVER_TOKEN")
    user = os.getenv("PUSHOVER_USER")
    requests.post(PUSHOVER_URL, data={"token": token, "user": user, "message": text})
    return "success"


def get_tools():
    """Return all system/utility tools."""
    push_tool = Tool(
        name="send_push_notification",
        func=push,
        description="Send a push notification to alert the user.",
    )

    python_repl = PythonREPLTool()

    schedule_task_tool = StructuredTool.from_function(
        func=schedule_task,
        name="schedule_task",
        description=(
            "Schedule a recurring background task with a cron expression. "
            "Example: description='Check BBC News for tech headlines', cron='0 8 * * *', notify=True"
        ),
    )

    list_tasks_tool = StructuredTool.from_function(
        func=list_scheduled_tasks,
        name="list_scheduled_tasks",
        description="List all scheduled background tasks with their status, schedule, and last results.",
    )

    cancel_task_tool = StructuredTool.from_function(
        func=cancel_scheduled_task,
        name="cancel_scheduled_task",
        description="Cancel and remove a scheduled task by its ID (e.g. 'a1b2c3d4').",
    )

    return [push_tool, python_repl, schedule_task_tool, list_tasks_tool, cancel_task_tool]
