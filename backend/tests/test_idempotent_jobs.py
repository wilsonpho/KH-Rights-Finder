"""Tests for idempotent job enqueue and stale-job reaper.

Requires a running Postgres (docker compose up db) and DATABASE_URL set
or defaults to the dev DB at localhost:5432.

Run:  pytest tests/test_idempotent_jobs.py -v
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db import async_session, engine
from app.main import app
from app.models import Base, IngestionJob


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module", autouse=True)
async def _setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture()
async def client():
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_no_duplicate_active_jobs(client: AsyncClient):
    """POST /api/search twice for the same brand must reuse active jobs."""
    r1 = await client.post("/api/search", json={"brand_name": "IdempotentTest"})
    assert r1.status_code == 200
    data1 = r1.json()
    ids1 = sorted(j["id"] for j in data1["jobs"])

    r2 = await client.post("/api/search", json={"brand_name": "IdempotentTest"})
    assert r2.status_code == 200
    data2 = r2.json()
    ids2 = sorted(j["id"] for j in data2["jobs"])

    assert ids1 == ids2, "Second POST must reuse the same active jobs"


@pytest.mark.asyncio
async def test_stale_running_jobs_reaped(client: AsyncClient):
    """GET /api/search/<mark_id> must fail jobs stuck running >10 min."""
    r = await client.post("/api/search", json={"brand_name": "StaleReaperTest"})
    assert r.status_code == 200
    mark_id = r.json()["mark"]["id"]

    # Artificially age one job: set it to running with started_at 15 min ago
    async with async_session() as session:
        row = (
            await session.execute(
                select(IngestionJob).where(
                    IngestionJob.mark_id == UUID(mark_id),
                    IngestionJob.status == "pending",
                )
            )
        ).scalars().first()
        assert row is not None
        row.status = "running"
        row.started_at = datetime.now(timezone.utc) - timedelta(minutes=15)
        await session.commit()
        stale_id = str(row.id)

    # GET should reap the stale job and return it as failed
    r2 = await client.get(f"/api/search/{mark_id}")
    assert r2.status_code == 200
    jobs = r2.json()["jobs"]
    stale = [j for j in jobs if j["id"] == stale_id]
    assert len(stale) == 1
    assert stale[0]["status"] == "failed"
    assert stale[0]["error_message"] == "timeout"
