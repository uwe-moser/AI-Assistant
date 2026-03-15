"""Centralized configuration for ApexFlow."""

from dotenv import load_dotenv

load_dotenv(override=True)

DB_PATH = "sidekick_chat_history.db"
CHECKPOINTS_DB_PATH = "sidekick_checkpoints.db"
TASKS_DB_PATH = "sidekick_scheduled_tasks.db"
SANDBOX_DIR = "sandbox"
DEFAULT_MODEL = "gpt-5.2-chat-latest"
