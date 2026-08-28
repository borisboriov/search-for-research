"""Engine/session factory and programmatic alembic migrations."""

from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def _ensure_sqlite_dir(db_url: str) -> None:
    if db_url.startswith("sqlite:///"):
        db_path = Path(db_url.removeprefix("sqlite:///"))
        if db_path.parent != Path():
            db_path.parent.mkdir(parents=True, exist_ok=True)


def make_engine(db_url: str) -> Engine:
    _ensure_sqlite_dir(db_url)
    return create_engine(db_url)


def upgrade_to_head(db_url: str) -> None:
    """Run alembic migrations up to head (idempotent)."""
    _ensure_sqlite_dir(db_url)
    script_location = str(files("sfr_core").joinpath("alembic"))
    config = Config()
    config.set_main_option("script_location", script_location)
    config.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(config, "head")


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    factory = sessionmaker(bind=engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
