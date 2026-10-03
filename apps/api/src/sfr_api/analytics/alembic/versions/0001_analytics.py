"""Version 1 analytics storage. Immutable schema, independent from catalogue ETL."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "analytics_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analytics_searches",
        sa.Column("search_id", pg.UUID(), primary_key=True),
        sa.Column("request_id", pg.UUID(), nullable=False, unique=True),
        sa.Column("visit_id", pg.UUID()),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "persisted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("status", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("payload", pg.JSONB(), nullable=False),
    )
    op.create_index("ix_analytics_search_received", "analytics_searches", ["received_at"])
    op.create_index("ix_analytics_search_visit", "analytics_searches", ["visit_id", "received_at"])
    op.create_table(
        "analytics_context",
        sa.Column(
            "search_id", pg.UUID(), sa.ForeignKey("analytics_searches.search_id"), primary_key=True
        ),
        sa.Column("raw_query", sa.Text(), nullable=False),
        sa.Column("normalized_query", sa.Text(), nullable=False),
        sa.Column("raw_ip", sa.String(64)),
        sa.Column("url", sa.String(2048)),
        sa.Column("referer", sa.String(2048)),
        sa.Column("diagnostic_headers", pg.JSONB(), nullable=False),
    )
    op.create_table(
        "analytics_events",
        sa.Column("event_id", pg.UUID(), primary_key=True),
        sa.Column("visit_id", pg.UUID(), nullable=False),
        sa.Column("search_id", pg.UUID()),
        sa.Column("request_id", pg.UUID()),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "persisted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("client_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("client_seq", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(40), nullable=False),
        sa.Column("page", sa.String(16), nullable=False),
        sa.Column("data", pg.JSONB(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("app_version", sa.String(100), nullable=False),
        sa.Column("traffic_type", sa.String(32), nullable=False),
    )
    op.create_index("ix_analytics_event_received", "analytics_events", ["received_at"])
    op.create_index("ix_analytics_event_search", "analytics_events", ["search_id", "name"])
    op.create_index("ix_analytics_event_visit", "analytics_events", ["visit_id", "client_seq"])
    op.create_table(
        "analytics_event_context",
        sa.Column(
            "event_id", pg.UUID(), sa.ForeignKey("analytics_events.event_id"), primary_key=True
        ),
        sa.Column("raw_ip", sa.String(64)),
        sa.Column("url", sa.String(2048)),
        sa.Column("referer", sa.String(2048)),
        sa.Column("diagnostic_headers", pg.JSONB(), nullable=False),
    )


def downgrade() -> None:
    raise RuntimeError("Analytics downgrade is non-destructive; roll back the app only")
