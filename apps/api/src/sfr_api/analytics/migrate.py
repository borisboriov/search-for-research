"""Operator-only migrations: python -m sfr_api.analytics.migrate [--runtime-role NAME]."""

import argparse
import os
from pathlib import Path

import psycopg
from alembic import command
from alembic.config import Config
from psycopg import sql


def migrate(url: str, runtime_role: str | None = None, reader_role: str | None = None) -> None:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent / "alembic"))
    config.attributes["database_url"] = url
    command.upgrade(config, "head")
    if runtime_role:
        # Runtime writes facts; only PK reads required by INSERT ... RETURNING.
        # Full private-data reads belong to the separately configured operator.
        with psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://")) as connection:
            for table in (
                "analytics_searches",
                "analytics_context",
                "analytics_events",
                "analytics_event_context",
            ):
                connection.execute(
                    sql.SQL("REVOKE ALL ON {} FROM {}").format(
                        sql.Identifier(table), sql.Identifier(runtime_role)
                    )
                )
                connection.execute(
                    sql.SQL("GRANT INSERT ON {} TO {}").format(
                        sql.Identifier(table), sql.Identifier(runtime_role)
                    )
                )
            for table, key in (
                ("analytics_searches", "search_id"),
                ("analytics_events", "event_id"),
            ):
                connection.execute(
                    sql.SQL("GRANT SELECT ({}) ON {} TO {}").format(
                        sql.Identifier(key), sql.Identifier(table), sql.Identifier(runtime_role)
                    )
                )
    if reader_role:
        with psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://")) as connection:
            for table in (
                "analytics_searches",
                "analytics_context",
                "analytics_events",
                "analytics_event_context",
                "analytics_alembic_version",
            ):
                connection.execute(
                    sql.SQL("GRANT SELECT ON {} TO {}").format(
                        sql.Identifier(table), sql.Identifier(reader_role)
                    )
                )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-role")
    parser.add_argument("--reader-role")
    args = parser.parse_args()
    url = os.environ.get("SFR_ANALYTICS_MIGRATION_DATABASE_URL") or os.environ.get(
        "SFR_API_ANALYTICS_DATABASE_URL", ""
    )
    if not url:
        parser.error("migration connection environment is required")
    migrate(url, args.runtime_role, args.reader_role)


if __name__ == "__main__":
    main()
