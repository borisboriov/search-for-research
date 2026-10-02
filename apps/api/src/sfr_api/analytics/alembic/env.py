"""Analytics-only Alembic environment; migration URL is never printed."""

from alembic import context

from sfr_api.analytics.models import Base
from sfr_api.analytics.store import engine_for

config = context.config
engine = engine_for(config.attributes["database_url"])
with engine.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        version_table="analytics_alembic_version",
    )
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()
