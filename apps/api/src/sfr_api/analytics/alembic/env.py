"""Analytics-only Alembic environment; migration URL is never printed."""

from alembic import context
from sqlalchemy.engine import Connection

from sfr_api.analytics.models import Base
from sfr_api.analytics.store import engine_for

config = context.config


def run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        version_table="analytics_alembic_version",
    )
    with context.begin_transaction():
        context.run_migrations()


# An explicit operator/test connection preserves its selected schema and outer
# transaction, allowing an isolated upgrade rehearsal without touching public.
provided = config.attributes.get("connection")
if provided is not None:
    run(provided)
else:
    engine = engine_for(config.attributes["database_url"])
    with engine.connect() as connection:
        run(connection)
    engine.dispose()
