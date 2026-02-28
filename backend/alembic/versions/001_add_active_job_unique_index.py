"""Add partial unique index on ingestion_jobs(mark_id, source)
for active (pending/running) jobs to prevent duplicate enqueues.

Revision ID: 001
Create Date: 2026-02-25
"""

from alembic import op
from sqlalchemy import text

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def _index_exists(conn, index_name: str) -> bool:
    result = conn.execute(
        text("SELECT 1 FROM pg_indexes WHERE indexname = :name"),
        {"name": index_name},
    )
    return result.scalar() is not None


def upgrade() -> None:
    conn = op.get_bind()
    if not _index_exists(conn, "uq_active_job_per_mark_source"):
        op.create_index(
            "uq_active_job_per_mark_source",
            "ingestion_jobs",
            ["mark_id", "source"],
            unique=True,
            postgresql_where=text("status IN ('pending', 'running')"),
        )


def downgrade() -> None:
    op.drop_index("uq_active_job_per_mark_source", table_name="ingestion_jobs")
