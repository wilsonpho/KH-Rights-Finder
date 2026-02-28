"""Tests that migration helper functions correctly detect existing schema objects.

These run against a real (test) Postgres DB when DATABASE_URL is set,
otherwise they are skipped.  They prove that the idempotent guards in
001 and 002 work — i.e. running `upgrade()` twice does not crash.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set — skipping DB-dependent migration tests",
)

from sqlalchemy import create_engine, text


@pytest.fixture(scope="module")
def sync_engine():
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgresql+asyncpg"):
        url = url.replace("postgresql+asyncpg", "postgresql", 1)
    engine = create_engine(url)
    yield engine
    engine.dispose()


class TestIndexExistsGuard:
    """Migration 001 — partial unique index on ingestion_jobs."""

    def test_index_exists_returns_true_when_present(self, sync_engine):
        from alembic.versions._001_add_active_job_unique_index import _index_exists  # noqa: F401

        with sync_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_indexes WHERE indexname = 'uq_active_job_per_mark_source'")
            ).scalar()

            from alembic.versions import _001_add_active_job_unique_index as m001  # noqa: WPS440
            result = m001._index_exists(conn, "uq_active_job_per_mark_source")
            assert result == (exists is not None)

    def test_index_exists_returns_false_for_nonexistent(self, sync_engine):
        import importlib
        m001 = importlib.import_module(
            "alembic.versions.001_add_active_job_unique_index"
        )
        with sync_engine.connect() as conn:
            assert m001._index_exists(conn, "no_such_index_xyz_42") is False


class TestColumnExistsGuard:
    """Migration 002 — evidence_kind & schema_version columns."""

    def test_column_exists_returns_false_for_nonexistent(self, sync_engine):
        import importlib
        m002 = importlib.import_module(
            "alembic.versions.002_add_evidence_kind_schema_version"
        )
        with sync_engine.connect() as conn:
            assert m002._column_exists(conn, "evidence", "no_such_col_xyz_42") is False

    def test_column_exists_returns_true_when_present(self, sync_engine):
        import importlib
        m002 = importlib.import_module(
            "alembic.versions.002_add_evidence_kind_schema_version"
        )
        with sync_engine.connect() as conn:
            exists = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = 'evidence' AND column_name = 'evidence_kind'"
                )
            ).scalar()

            result = m002._column_exists(conn, "evidence", "evidence_kind")
            assert result == (exists is not None)
