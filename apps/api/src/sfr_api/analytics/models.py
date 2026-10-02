"""PostgreSQL-only analytics metadata, deliberately separate from ETL."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Search(Base):
    __tablename__ = "analytics_searches"
    search_id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True)
    request_id: Mapped[UUID] = mapped_column(PGUUID, unique=True)
    visit_id: Mapped[UUID | None] = mapped_column(PGUUID)
    persisted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[int] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(16))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    __table_args__ = (
        Index("ix_analytics_search_received", "received_at"),
        Index("ix_analytics_search_visit", "visit_id", "received_at"),
    )


class Context(Base):
    __tablename__ = "analytics_context"
    search_id: Mapped[UUID] = mapped_column(
        ForeignKey("analytics_searches.search_id"), primary_key=True
    )
    raw_query: Mapped[str] = mapped_column(Text)
    normalized_query: Mapped[str] = mapped_column(Text)
    raw_ip: Mapped[str | None] = mapped_column(String(64))
    url: Mapped[str | None] = mapped_column(String(2048))
    referer: Mapped[str | None] = mapped_column(String(2048))
    diagnostic_headers: Mapped[dict[str, str]] = mapped_column(JSONB)


class ProductEvent(Base):
    __tablename__ = "analytics_events"
    event_id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True)
    visit_id: Mapped[UUID] = mapped_column(PGUUID)
    search_id: Mapped[UUID | None] = mapped_column(PGUUID)
    request_id: Mapped[UUID | None] = mapped_column(PGUUID)
    persisted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    client_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    client_seq: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(40))
    page: Mapped[str] = mapped_column(String(16))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    schema_version: Mapped[int] = mapped_column(Integer)
    app_version: Mapped[str] = mapped_column(String(100))
    traffic_type: Mapped[str] = mapped_column(String(32))
    __table_args__ = (
        UniqueConstraint("visit_id", "client_seq", name="uq_analytics_visit_seq"),
        Index("ix_analytics_event_received", "received_at"),
        Index("ix_analytics_event_search", "search_id", "name"),
        Index("ix_analytics_event_visit", "visit_id", "client_seq"),
    )


class EventContext(Base):
    __tablename__ = "analytics_event_context"
    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("analytics_events.event_id"), primary_key=True
    )
    raw_ip: Mapped[str | None] = mapped_column(String(64))
    url: Mapped[str | None] = mapped_column(String(2048))
    referer: Mapped[str | None] = mapped_column(String(2048))
    diagnostic_headers: Mapped[dict[str, str]] = mapped_column(JSONB)
