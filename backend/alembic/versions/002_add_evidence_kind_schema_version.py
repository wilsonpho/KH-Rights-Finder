"""Add evidence_kind and schema_version columns to evidence table.

Nullable so existing rows remain valid (backwards compatible).

Revision ID: 002
Revises: 001
Create Date: 2026-02-27
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evidence", sa.Column("evidence_kind", sa.Text(), nullable=True))
    op.add_column("evidence", sa.Column("schema_version", sa.SmallInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("evidence", "schema_version")
    op.drop_column("evidence", "evidence_kind")
