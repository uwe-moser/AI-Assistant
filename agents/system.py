"""System agent: task scheduling, notifications, code execution."""

from agents.base import BaseAgent


class SystemAgent(BaseAgent):
    system_prompt = (
        "You are a system utilities specialist. Schedule recurring background "
        "tasks with cron expressions, send push notifications, and run Python "
        "code for calculations or data processing."
    )
