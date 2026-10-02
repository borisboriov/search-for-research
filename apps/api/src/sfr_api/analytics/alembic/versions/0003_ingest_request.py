"""Trace delivery HTTP separately from the HTTP request associated with an event."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "analytics_0003"
down_revision = "analytics_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "analytics_event_context", sa.Column("ingest_request_id", postgresql.UUID(), nullable=True)
    )


def downgrade() -> None:
    raise RuntimeError("Analytics downgrade is non-destructive; roll back the app only")
