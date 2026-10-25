"""Database engine, session management and initialisation."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

import config
from finsight.models import Base

_SQLITE_PREFIX = "sqlite:///"
_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def configure_database(url: str | None = None) -> None:
    """Create the engine, session factory and tables. Existing data is never dropped."""
    global _engine, _session_factory
    url = url or config.DATABASE_URL
    if url.startswith(_SQLITE_PREFIX) and ":memory:" not in url:
        Path(url[len(_SQLITE_PREFIX):]).parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(url, connect_args={"check_same_thread": False})
    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
    Base.metadata.create_all(_engine)


def init_database() -> None:
    """Initialise the default database once per process."""
    if _engine is None:
        configure_database()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope: commit on success, roll back on any error."""
    if _session_factory is None:
        configure_database()
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
