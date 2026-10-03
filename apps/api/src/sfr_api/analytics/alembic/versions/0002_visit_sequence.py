"""Secondary delivery deduplication for existing analytics databases."""

from alembic import op

revision = "analytics_0002"
down_revision = "analytics_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_analytics_visit_seq", "analytics_events", ["visit_id", "client_seq"]
    )


def downgrade() -> None:
    raise RuntimeError("Analytics downgrade is non-destructive; roll back the app only")
