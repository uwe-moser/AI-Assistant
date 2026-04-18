"""Session CRUD + history retrieval."""

from fastapi import APIRouter, HTTPException

from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage

from config import DB_PATH
from session_manager import SessionManager

from api.deps import sidekick_registry
from api.schemas import (
    SessionInfo,
    SessionCreateIn,
    SessionRenameIn,
    HistoryMessage,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

_session_manager = SessionManager()


def _to_info(row: tuple) -> SessionInfo:
    return SessionInfo(id=row[0], name=row[1], created_at=row[2])


@router.get("", response_model=list[SessionInfo])
async def list_sessions() -> list[SessionInfo]:
    return [_to_info(r) for r in _session_manager.list_sessions()]


@router.post("", response_model=SessionInfo)
async def create_session(payload: SessionCreateIn) -> SessionInfo:
    session_id = _session_manager.create_session(payload.name)
    info = _session_manager.get_session(session_id)
    return SessionInfo(**info)


@router.get("/latest", response_model=SessionInfo)
async def get_or_create_latest() -> SessionInfo:
    session_id = _session_manager.get_or_create_latest()
    info = _session_manager.get_session(session_id)
    return SessionInfo(**info)


@router.patch("/{session_id}", response_model=SessionInfo)
async def rename_session(session_id: str, payload: SessionRenameIn) -> SessionInfo:
    if not payload.name.strip():
        raise HTTPException(400, "name cannot be empty")
    if not _session_manager.get_session(session_id):
        raise HTTPException(404, "session not found")
    _session_manager.rename_session(session_id, payload.name)
    return SessionInfo(**_session_manager.get_session(session_id))


@router.delete("/{session_id}")
async def delete_session(session_id: str) -> dict:
    deleted = _session_manager.delete_session(session_id)
    if not deleted:
        raise HTTPException(404, "session not found")
    await sidekick_registry.evict(session_id)
    return {"deleted": True}


@router.get("/{session_id}/history", response_model=list[HistoryMessage])
async def get_history(session_id: str) -> list[HistoryMessage]:
    if not _session_manager.get_session(session_id):
        raise HTTPException(404, "session not found")

    hist = SQLChatMessageHistory(
        session_id=session_id,
        connection=f"sqlite:///{DB_PATH}",
    )
    out: list[HistoryMessage] = []
    for msg in hist.messages:
        if isinstance(msg, HumanMessage):
            out.append(HistoryMessage(role="user", content=msg.content))
        elif isinstance(msg, AIMessage):
            out.append(HistoryMessage(role="assistant", content=msg.content))
    return out
