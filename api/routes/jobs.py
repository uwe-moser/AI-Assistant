"""Job pipeline: list, status update, profile read."""

from fastapi import APIRouter, HTTPException, Query

import jobs as jobs_db
from api.schemas import (
    JobInfo,
    JobStatusUpdateIn,
    CandidateProfile,
)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _to_info(row: dict) -> JobInfo:
    return JobInfo(
        id=row["id"],
        title=row["title"],
        company=row.get("company"),
        location=row.get("location"),
        salary=row.get("salary"),
        status=row["status"],
        match_score=row.get("match_score"),
        match_rationale=row.get("match_rationale"),
        apply_url=row.get("apply_url"),
        posted_at=row.get("posted_at"),
        discovered_at=row["discovered_at"],
        updated_at=row["updated_at"],
        notes=row.get("notes"),
        source=row["source"],
    )


@router.get("/statuses", response_model=list[str])
async def statuses() -> list[str]:
    return list(jobs_db.PIPELINE_STATUSES)


@router.get("", response_model=list[JobInfo])
async def list_jobs(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[JobInfo]:
    if status and status not in jobs_db.PIPELINE_STATUSES:
        raise HTTPException(400, f"invalid status; allowed: {jobs_db.PIPELINE_STATUSES}")
    return [_to_info(r) for r in jobs_db.list_jobs(status=status, limit=limit)]


@router.get("/profile", response_model=CandidateProfile)
async def get_profile() -> CandidateProfile:
    return CandidateProfile(profile=jobs_db.get_profile())


@router.get("/{job_id}", response_model=JobInfo)
async def get_job(job_id: str) -> JobInfo:
    row = jobs_db.get_job(job_id)
    if not row:
        raise HTTPException(404, "job not found")
    return _to_info(row)


@router.patch("/{job_id}/status", response_model=JobInfo)
async def update_status(job_id: str, payload: JobStatusUpdateIn) -> JobInfo:
    if payload.status not in jobs_db.PIPELINE_STATUSES:
        raise HTTPException(400, f"invalid status; allowed: {jobs_db.PIPELINE_STATUSES}")
    if not jobs_db.set_status(job_id, payload.status, payload.notes):
        raise HTTPException(404, "job not found")
    return _to_info(jobs_db.get_job(job_id))
