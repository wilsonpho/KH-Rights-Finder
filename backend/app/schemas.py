from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


# --- Marks ---

class SearchRequest(BaseModel):
    brand_name: str


# --- Evidence ---

class EvidenceOut(BaseModel):
    id: UUID
    source: str
    source_type: str
    title: Optional[str]
    detail: Optional[Dict]
    snapshot_id: Optional[UUID]
    confidence: Optional[int]
    found_at: datetime

    model_config = {"from_attributes": True}


# --- Jobs ---

class JobOut(BaseModel):
    id: UUID
    source: str
    status: str
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


# --- Scoring ---

class ScoreFactor(BaseModel):
    source: str
    status: Optional[str] = None
    points: int


class ScoreOut(BaseModel):
    total: int
    authoritative: int
    secondary: int
    label: str
    factors: List[ScoreFactor]


# --- Search result ---

class MarkOut(BaseModel):
    id: UUID
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SearchResultOut(BaseModel):
    mark: MarkOut
    jobs: List[JobOut]
    score: ScoreOut
    evidence: List[EvidenceOut]


# --- Watchlist ---

class WatchlistAddRequest(BaseModel):
    mark_id: UUID


class WatchlistEntryOut(BaseModel):
    id: UUID
    mark: MarkOut
    last_checked: Optional[datetime]
    check_interval_days: float
    active: bool
    score: ScoreOut

    model_config = {"from_attributes": True}
