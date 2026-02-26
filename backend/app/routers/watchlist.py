from __future__ import annotations

import uuid

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models import Evidence, Mark, WatchlistEntry
from app.schemas import (
    ScoreFactor,
    ScoreOut,
    MarkOut,
    WatchlistAddRequest,
    WatchlistEntryOut,
)
from app.scoring import compute_score

router = APIRouter(prefix="/api", tags=["watchlist"])


@router.get("/watchlist", response_model=List[WatchlistEntryOut])
async def list_watchlist(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(WatchlistEntry)
        .options(
            selectinload(WatchlistEntry.mark).selectinload(Mark.evidence),
        )
        .where(WatchlistEntry.active == True)
        .order_by(WatchlistEntry.added_at.desc())
    )
    entries = result.scalars().all()

    out = []
    for entry in entries:
        evidence_dicts = [
            {"source": e.source, "source_type": e.source_type, "detail": e.detail}
            for e in entry.mark.evidence
        ]
        sb = compute_score(evidence_dicts)
        out.append(WatchlistEntryOut(
            id=entry.id,
            mark=MarkOut.model_validate(entry.mark),
            last_checked=entry.last_checked,
            check_interval_days=entry.check_interval.total_seconds() / 86400,
            active=entry.active,
            score=ScoreOut(
                total=sb.total,
                authoritative=sb.authoritative,
                secondary=sb.secondary,
                label=sb.label,
                factors=[ScoreFactor(**f) for f in sb.factors],
            ),
        ))
    return out


@router.post("/watchlist", response_model=WatchlistEntryOut)
async def add_to_watchlist(req: WatchlistAddRequest, session: AsyncSession = Depends(get_session)):
    # Check mark exists
    mark_result = await session.execute(
        select(Mark).where(Mark.id == req.mark_id).options(selectinload(Mark.evidence))
    )
    mark = mark_result.scalar_one_or_none()
    if not mark:
        raise HTTPException(status_code=404, detail="Mark not found")

    # Check if already on watchlist
    existing = await session.execute(
        select(WatchlistEntry).where(WatchlistEntry.mark_id == req.mark_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Already on watchlist")

    entry = WatchlistEntry(mark_id=req.mark_id)
    session.add(entry)
    await session.commit()
    await session.refresh(entry)

    evidence_dicts = [
        {"source": e.source, "source_type": e.source_type, "detail": e.detail}
        for e in mark.evidence
    ]
    sb = compute_score(evidence_dicts)

    return WatchlistEntryOut(
        id=entry.id,
        mark=MarkOut.model_validate(mark),
        last_checked=entry.last_checked,
        check_interval_days=entry.check_interval.total_seconds() / 86400,
        active=entry.active,
        score=ScoreOut(
            total=sb.total,
            authoritative=sb.authoritative,
            secondary=sb.secondary,
            label=sb.label,
            factors=[ScoreFactor(**f) for f in sb.factors],
        ),
    )


@router.delete("/watchlist/{entry_id}")
async def remove_from_watchlist(entry_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(WatchlistEntry).where(WatchlistEntry.id == entry_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Watchlist entry not found")

    await session.delete(entry)
    await session.commit()
    return {"status": "ok"}
