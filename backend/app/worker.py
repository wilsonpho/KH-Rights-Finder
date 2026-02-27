"""DB-polling implementation of JobQueue + worker loop."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import async_session
from app.evidence_schemas import parse_evidence
from app.models import Evidence, IngestionJob, Mark, Snapshot, WatchlistEntry
from app.queue import Job, JobQueue
import app.scrapers  # noqa: F401  — triggers @register_scraper decorators
from app.scrapers.base import ScraperResult, get_scraper

logger = logging.getLogger(__name__)


class DBJobQueue:
    """JobQueue backed by the ingestion_jobs table with FOR UPDATE SKIP LOCKED."""

    def __init__(self, session_factory=async_session):
        self._session_factory = session_factory

    async def enqueue(self, mark_id: uuid.UUID, source: str) -> uuid.UUID:
        async with self._session_factory() as session:
            job = IngestionJob(mark_id=mark_id, source=source)
            session.add(job)
            await session.commit()
            await session.refresh(job)
            return job.id

    async def dequeue(self) -> Job | None:
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT j.id, j.mark_id, m.name, j.source, j.status, j.created_at
                    FROM ingestion_jobs j
                    JOIN marks m ON j.mark_id = m.id
                    WHERE j.status = 'pending'
                    ORDER BY
                        CASE WHEN j.source IN ('dip_trademark', 'dip_exclusive')
                             THEN 0 ELSE 1 END,
                        j.created_at
                    LIMIT 1
                    FOR UPDATE OF j SKIP LOCKED
                """)
            )
            row = result.first()
            if not row:
                return None

            # Mark as running
            await session.execute(
                update(IngestionJob)
                .where(IngestionJob.id == row[0])
                .values(status="running", started_at=datetime.now(timezone.utc))
            )
            await session.commit()

            return Job(
                id=row[0],
                mark_id=row[1],
                mark_name=row[2],
                source=row[3],
                status="running",
                created_at=row[5],
            )

    async def complete(self, job_id: uuid.UUID) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(IngestionJob)
                .where(IngestionJob.id == job_id)
                .values(status="done", completed_at=datetime.now(timezone.utc))
            )
            await session.commit()

    async def fail(self, job_id: uuid.UUID, error: str) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(IngestionJob)
                .where(IngestionJob.id == job_id)
                .values(
                    status="failed",
                    error_message=error,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()


async def _save_snapshot(
    session: AsyncSession, job_id: uuid.UUID, source: str, url: str, body: bytes, content_type: str
) -> uuid.UUID:
    sha = hashlib.sha256(body).hexdigest()
    snap = Snapshot(
        job_id=job_id,
        source=source,
        url=url,
        content_type=content_type,
        body=body,
        sha256=sha,
    )
    session.add(snap)
    await session.flush()
    return snap.id


async def _store_evidence(
    session: AsyncSession, job_id: uuid.UUID, mark_id: uuid.UUID, source: str, results: list[ScraperResult]
) -> None:
    source_type = "authoritative" if source in ("dip_trademark", "dip_exclusive") else "secondary"

    for r in results:
        snapshot_id = None
        if r.raw_content:
            snapshot_id = await _save_snapshot(
                session, job_id, source, r.source_url or "", r.raw_content, r.content_type or "text/html"
            )

        structured, evidence_kind, schema_version = parse_evidence(source, r.detail)
        confidence = r.confidence
        if structured.pop("_validation_failed", False):
            confidence = 20

        evidence = Evidence(
            mark_id=mark_id,
            source=source,
            source_type=source_type,
            title=r.title,
            detail=structured,
            evidence_kind=evidence_kind,
            schema_version=schema_version,
            snapshot_id=snapshot_id,
            confidence=confidence,
        )
        session.add(evidence)

    await session.flush()


async def process_job(queue: DBJobQueue, job: Job) -> None:
    scraper = get_scraper(job.source)
    try:
        results = await scraper.search(job.mark_name)
        async with async_session() as session:
            await _store_evidence(session, job.id, job.mark_id, job.source, results)
            await session.commit()
        await queue.complete(job.id)
        logger.info("Job %s completed: %d results", job.id, len(results))
    except Exception as exc:
        logger.exception("Job %s failed", job.id)
        await queue.fail(job.id, str(exc))


async def check_watchlist() -> None:
    """Create new ingestion jobs for watchlist entries that are due."""
    async with async_session() as session:
        result = await session.execute(
            text("""
                SELECT w.id, w.mark_id
                FROM watchlist w
                WHERE w.active = true
                AND (w.last_checked IS NULL
                     OR w.last_checked + w.check_interval < now())
            """)
        )
        due = result.fetchall()
        for wl_id, mark_id in due:
            for source in ("dip_trademark", "dip_exclusive"):
                job = IngestionJob(mark_id=mark_id, source=source)
                session.add(job)
            await session.execute(
                update(WatchlistEntry)
                .where(WatchlistEntry.id == wl_id)
                .values(last_checked=datetime.now(timezone.utc))
            )
        await session.commit()
        if due:
            logger.info("Watchlist: queued jobs for %d marks", len(due))


JOB_TIMEOUT_MINUTES = 10


async def reap_stale_jobs() -> None:
    """Fail any job stuck in 'running' longer than JOB_TIMEOUT_MINUTES."""
    async with async_session() as session:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=JOB_TIMEOUT_MINUTES)
        result = await session.execute(
            update(IngestionJob)
            .where(
                IngestionJob.status == "running",
                IngestionJob.started_at < cutoff,
            )
            .values(
                status="failed",
                error_message="timeout",
                completed_at=datetime.now(timezone.utc),
            )
            .returning(IngestionJob.id)
        )
        reaped = result.scalars().all()
        if reaped:
            logger.warning("Reaped %d stale jobs: %s", len(reaped), reaped)
        await session.commit()


async def run_worker() -> None:
    """Main worker loop."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info("Worker started")

    queue = DBJobQueue()
    watchlist_counter = 0

    while True:
        # Reap stale jobs every iteration (single cheap UPDATE)
        await reap_stale_jobs()

        job = await queue.dequeue()
        if job:
            await process_job(queue, job)
            await asyncio.sleep(settings.scrape_delay_seconds)
        else:
            await asyncio.sleep(settings.worker_poll_seconds)

        # Check watchlist periodically
        watchlist_counter += 1
        poll_cycles = int(settings.watchlist_check_seconds / settings.worker_poll_seconds)
        if watchlist_counter >= poll_cycles:
            watchlist_counter = 0
            await check_watchlist()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
