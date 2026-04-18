"""Pydantic schemas for ApexFlow's HTTP surface."""

from typing import Any, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

class SessionInfo(BaseModel):
    id: str
    name: str
    created_at: str


class SessionCreateIn(BaseModel):
    name: Optional[str] = None


class SessionRenameIn(BaseModel):
    name: str


class HistoryMessage(BaseModel):
    role: str
    content: str
    metadata: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Chat (WebSocket)
# ---------------------------------------------------------------------------

class ChatMessageIn(BaseModel):
    """Frame the client sends over the WebSocket to start a turn."""
    message: str
    success_criteria: Optional[str] = ""
    history: list[HistoryMessage] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Scheduled tasks
# ---------------------------------------------------------------------------

class ScheduledTaskInfo(BaseModel):
    id: str
    description: str
    cron_expr: str
    created_at: str
    enabled: bool
    last_run: Optional[str] = None
    last_result: Optional[str] = None
    notify: bool


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------

class KnowledgeDoc(BaseModel):
    filename: str
    chunks: int


class KnowledgeOverview(BaseModel):
    total_chunks: int
    documents: list[KnowledgeDoc]


class KnowledgeOpResult(BaseModel):
    message: str
    overview: KnowledgeOverview


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

class JobInfo(BaseModel):
    id: str
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    salary: Optional[str] = None
    status: str
    match_score: Optional[float] = None
    match_rationale: Optional[str] = None
    apply_url: Optional[str] = None
    posted_at: Optional[str] = None
    discovered_at: str
    updated_at: str
    notes: Optional[str] = None
    source: str


class JobStatusUpdateIn(BaseModel):
    status: str
    notes: Optional[str] = None


class CandidateProfile(BaseModel):
    profile: dict[str, Any]


# ---------------------------------------------------------------------------
# Interview
# ---------------------------------------------------------------------------

class InterviewSessionInfo(BaseModel):
    id: str
    job_id: Optional[str] = None
    title: Optional[str] = None
    status: str
    current_index: int
    overall_score: Optional[float] = None
    final_summary: Optional[str] = None
    created_at: str
    updated_at: str


class InterviewTurnInfo(BaseModel):
    id: str
    idx: int
    question: str
    category: Optional[str] = None
    answer: Optional[str] = None
    score: Optional[float] = None
    critique: Optional[str] = None


class InterviewSessionDetail(BaseModel):
    session: InterviewSessionInfo
    turns: list[InterviewTurnInfo]
