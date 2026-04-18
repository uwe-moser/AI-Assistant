"""Interview practice: list sessions, fetch a session with all turns."""

from fastapi import APIRouter, HTTPException

import interview as interview_db
from api.schemas import (
    InterviewSessionInfo,
    InterviewSessionDetail,
    InterviewTurnInfo,
)

router = APIRouter(prefix="/api/interviews", tags=["interviews"])


def _to_session(row: dict) -> InterviewSessionInfo:
    return InterviewSessionInfo(
        id=row["id"],
        job_id=row.get("job_id"),
        title=row.get("title"),
        status=row["status"],
        current_index=row["current_index"],
        overall_score=row.get("overall_score"),
        final_summary=row.get("final_summary"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _to_turn(row: dict) -> InterviewTurnInfo:
    return InterviewTurnInfo(
        id=row["id"],
        idx=row["idx"],
        question=row["question"],
        category=row.get("category"),
        answer=row.get("answer"),
        score=row.get("score"),
        critique=row.get("critique"),
    )


@router.get("", response_model=list[InterviewSessionInfo])
async def list_sessions() -> list[InterviewSessionInfo]:
    return [_to_session(r) for r in interview_db.list_sessions()]


@router.get("/{session_id}", response_model=InterviewSessionDetail)
async def get_session(session_id: str) -> InterviewSessionDetail:
    session = interview_db.get_session(session_id)
    if not session:
        raise HTTPException(404, "interview session not found")
    return InterviewSessionDetail(
        session=_to_session(session),
        turns=[_to_turn(t) for t in interview_db.get_turns(session_id)],
    )
