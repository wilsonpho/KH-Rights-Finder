from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Evidence
from app.schemas import EvidenceOut

router = APIRouter(prefix="/api", tags=["evidence"])


@router.get("/evidence", response_model=List[EvidenceOut])
async def list_evidence(
    mark_id: uuid.UUID = Query(...),
    source: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Evidence).where(Evidence.mark_id == mark_id)
    if source:
        stmt = stmt.where(Evidence.source == source)
    stmt = stmt.order_by(Evidence.found_at.desc())

    result = await session.execute(stmt)
    return [EvidenceOut.model_validate(e) for e in result.scalars().all()]
