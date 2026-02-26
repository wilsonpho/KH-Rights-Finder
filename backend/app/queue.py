"""Queue-agnostic job interface.

All routers and scrapers depend only on JobQueue, never on the
DB-polling internals.  To swap to Celery/Redis later, write a
CeleryJobQueue and change one line in config.py.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass
class Job:
    id: uuid.UUID
    mark_id: uuid.UUID
    mark_name: str
    source: str
    status: str
    created_at: datetime


@runtime_checkable
class JobQueue(Protocol):
    async def enqueue(self, mark_id: uuid.UUID, source: str) -> uuid.UUID:
        """Create a pending job. Returns the job id."""
        ...

    async def dequeue(self) -> Job | None:
        """Pick the next pending job (authoritative first). Returns None if empty."""
        ...

    async def complete(self, job_id: uuid.UUID) -> None:
        """Mark a job as done."""
        ...

    async def fail(self, job_id: uuid.UUID, error: str) -> None:
        """Mark a job as failed with an error message."""
        ...
