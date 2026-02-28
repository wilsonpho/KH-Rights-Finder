"""Add evidence_kind and schema_version columns to evidence table.

Nullable so existing rows remain valid (backwards compatible).

Revision ID: 002
Revises: 001
Create Date: 2026-02-27
"""

from alembic import op
from sqlalchemy import text

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS guards against drift caused by Base.metadata.create_all()
    # running at app startup before Alembic has a chance to track the columns.
    op.execute("ALTER TABLE evidence ADD COLUMN IF NOT EXISTS evidence_kind TEXT")
    op.execute("ALTER TABLE evidence ADD COLUMN IF NOT EXISTS schema_version SMALLINT")


def downgrade() -> None:
    op.execute("ALTER TABLE evidence DROP COLUMN IF EXISTS schema_version")
    op.execute("ALTER TABLE evidence DROP COLUMN IF EXISTS evidence_kind")
