"""Centralized configuration for ApexFlow."""

from dotenv import load_dotenv

load_dotenv(override=True)

DB_PATH = "sidekick_chat_history.db"
CHECKPOINTS_DB_PATH = "sidekick_checkpoints.db"
TASKS_DB_PATH = "sidekick_scheduled_tasks.db"
JOBS_DB_PATH = "sidekick_jobs.db"
INTERVIEW_DB_PATH = "sidekick_interviews.db"
SANDBOX_DIR = "sandbox"
JOB_APPLICATIONS_DIR = "sandbox/job_applications"
DEFAULT_MODEL = "gpt-5.2-chat-latest"

# Adzuna country for job search (de, gb, us, fr, etc.)
ADZUNA_COUNTRY = "de"
