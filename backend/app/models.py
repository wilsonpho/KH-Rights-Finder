import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Interval,
    LargeBinary,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Mark(Base):
    __tablename__ = "marks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_normalized: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    evidence: Mapped[List["Evidence"]] = relationship(back_populates="mark", cascade="all, delete-orphan")
    jobs: Mapped[List["IngestionJob"]] = relationship(back_populates="mark", cascade="all, delete-orphan")
    watchlist_entry: Mapped[Optional["WatchlistEntry"]] = relationship(back_populates="mark", cascade="all, delete-orphan")


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingestion_jobs.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    mark_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marks.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(
        Text,
        CheckConstraint("source_type IN ('authoritative', 'secondary')"),
        nullable=False,
    )
    title: Mapped[Optional[str]] = mapped_column(Text)
    detail: Mapped[Optional[Dict]] = mapped_column(JSONB)
    snapshot_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("snapshots.id", ondelete="SET NULL")
    )
    confidence: Mapped[Optional[int]] = mapped_column(
        SmallInteger, CheckConstraint("confidence BETWEEN 0 AND 100")
    )
    found_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    mark: Mapped["Mark"] = relationship(back_populates="evidence")

    __table_args__ = (Index("idx_evidence_mark", "mark_id"),)


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    mark_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marks.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text,
        CheckConstraint("status IN ('pending', 'running', 'done', 'failed')"),
        nullable=False,
        server_default=text("'pending'"),
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    mark: Mapped["Mark"] = relationship(back_populates="jobs")

    __table_args__ = (
        Index("idx_jobs_status", "status", "created_at"),
        Index(
            "uq_active_job_per_mark_source",
            "mark_id",
            "source",
            unique=True,
            postgresql_where=text("status IN ('pending', 'running')"),
        ),
    )


class WatchlistEntry(Base):
    __tablename__ = "watchlist"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    mark_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marks.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    last_checked: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    check_interval: Mapped[timedelta] = mapped_column(
        Interval, server_default=text("interval '7 days'")
    )
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))

    mark: Mapped["Mark"] = relationship(back_populates="watchlist_entry")
