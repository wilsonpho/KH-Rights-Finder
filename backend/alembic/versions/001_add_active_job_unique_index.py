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


def upgrade() -> None:
    op.create_index(
        "uq_active_job_per_mark_source",
        "ingestion_jobs",
        ["mark_id", "source"],
        unique=True,
        postgresql_where=text("status IN ('pending', 'running')"),
    )


def downgrade() -> None:
    op.drop_index("uq_active_job_per_mark_source", table_name="ingestion_jobs")
