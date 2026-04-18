"""
FastAPI entry point for ApexFlow.

Wraps the existing Sidekick orchestrator, scheduler, knowledge base, jobs, and
interview modules so the new Next.js frontend can drive everything over HTTP +
WebSocket. The legacy Gradio app (`python app.py`) keeps working unchanged.

Run:
    uvicorn api.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import scheduler

from api.deps import sidekick_registry
from api.routes import sessions, chat, tasks, knowledge, jobs, interview

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Boot the scheduler and tear down Sidekick instances on shutdown."""
    runner = scheduler.TaskRunner()
    await runner.start()
    try:
        yield
    finally:
        runner.stop()
        await sidekick_registry.shutdown_all()


app = FastAPI(
    title="ApexFlow API",
    description="HTTP + WebSocket surface for the ApexFlow multi-agent assistant.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


app.include_router(sessions.router)
app.include_router(chat.router)
app.include_router(tasks.router)
app.include_router(knowledge.router)
app.include_router(jobs.router)
app.include_router(interview.router)
