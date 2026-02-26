from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models import Evidence, IngestionJob, Mark
from app.schemas import (
    EvidenceOut,
    JobOut,
    MarkOut,
    ScoreFactor,
    ScoreOut,
    SearchRequest,
    SearchResultOut,
)
from app.scoring import compute_score

router = APIRouter(prefix="/api", tags=["search"])

SOURCES = ["dip_trademark", "dip_exclusive"]

JOB_TIMEOUT_MINUTES = 10


@router.post("/search", response_model=SearchResultOut)
async def create_search(req: SearchRequest, session: AsyncSession = Depends(get_session)):
    name_normalized = req.brand_name.strip().lower()
    if not name_normalized:
        raise HTTPException(status_code=400, detail="brand_name is required")

    # Upsert mark
    result = await session.execute(
        select(Mark).where(Mark.name_normalized == name_normalized)
    )
    mark = result.scalar_one_or_none()

    if not mark:
        mark = Mark(name=req.brand_name.strip(), name_normalized=name_normalized)
        session.add(mark)
        await session.flush()

    # Idempotent enqueue: reuse existing pending/running job per source
    jobs = []
    for source in SOURCES:
        existing = await session.execute(
            select(IngestionJob).where(
                IngestionJob.mark_id == mark.id,
                IngestionJob.source == source,
                IngestionJob.status.in_(["pending", "running"]),
            )
        )
        active_job = existing.scalar_one_or_none()
        if active_job:
            jobs.append(active_job)
        else:
            job = IngestionJob(mark_id=mark.id, source=source)
            session.add(job)
            jobs.append(job)

    await session.commit()

    for job in jobs:
        await session.refresh(job)
    await session.refresh(mark)

    return SearchResultOut(
        mark=MarkOut.model_validate(mark),
        jobs=[JobOut.model_validate(j) for j in jobs],
        score=ScoreOut(total=0, authoritative=0, secondary=0, label="none", factors=[]),
        evidence=[],
    )


def _latest_jobs(jobs: list[IngestionJob]) -> list[IngestionJob]:
    """Return only the most-recent job per source."""
    by_source: dict[str, IngestionJob] = {}
    for j in jobs:
        prev = by_source.get(j.source)
        if prev is None or j.created_at > prev.created_at:
            by_source[j.source] = j
    return list(by_source.values())


@router.get("/search/{mark_id}", response_model=SearchResultOut)
async def get_search(mark_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    # Lightweight reaper: fail jobs stuck running >10 min for this mark
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=JOB_TIMEOUT_MINUTES)
    await session.execute(
        update(IngestionJob)
        .where(
            IngestionJob.mark_id == mark_id,
            IngestionJob.status == "running",
            IngestionJob.started_at < cutoff,
        )
        .values(
            status="failed",
            error_message="timeout",
            completed_at=datetime.now(timezone.utc),
        )
    )

    result = await session.execute(
        select(Mark)
        .where(Mark.id == mark_id)
        .options(selectinload(Mark.evidence), selectinload(Mark.jobs))
    )
    mark = result.scalar_one_or_none()
    if not mark:
        raise HTTPException(status_code=404, detail="Mark not found")

    latest_jobs = _latest_jobs(mark.jobs)

    evidence_dicts = [
        {
            "source": e.source,
            "source_type": e.source_type,
            "detail": e.detail,
        }
        for e in mark.evidence
    ]
    score_breakdown = compute_score(evidence_dicts)

    return SearchResultOut(
        mark=MarkOut.model_validate(mark),
        jobs=[JobOut.model_validate(j) for j in latest_jobs],
        score=ScoreOut(
            total=score_breakdown.total,
            authoritative=score_breakdown.authoritative,
            secondary=score_breakdown.secondary,
            label=score_breakdown.label,
            factors=[ScoreFactor(**f) for f in score_breakdown.factors],
        ),
        evidence=[EvidenceOut.model_validate(e) for e in mark.evidence],
    )


@router.post("/search/{mark_id}/retry")
async def retry_failed_jobs(mark_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Mark).where(Mark.id == mark_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Mark not found")

    await session.execute(
        update(IngestionJob)
        .where(IngestionJob.mark_id == mark_id, IngestionJob.status == "failed")
        .values(status="pending", error_message=None, started_at=None, completed_at=None)
    )
    await session.commit()
    return {"status": "ok", "message": "Failed jobs re-queued"}
