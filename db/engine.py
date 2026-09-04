"""SQLAlchemy engine and session helpers for the structured SQLite DB."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = Path(os.getenv("LEXINTAKE_SQLITE_PATH", ROOT / "db" / "lexintake.db"))

_engine: Engine | None = None
_engine_path: Path | None = None
_SessionLocal: sessionmaker[Session] | None = None


def sqlite_url(db_path: Path | str | None = None) -> str:
    path = Path(db_path or DEFAULT_DB_PATH).resolve()
    return f"sqlite:///{path.as_posix()}"


def _attach_sqlite_pragmas(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()


def get_engine(db_path: Path | str | None = None) -> Engine:
    """Return a process-wide engine for the given SQLite file."""
    global _engine, _engine_path, _SessionLocal
    path = Path(db_path or DEFAULT_DB_PATH).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if _engine is None or _engine_path != path:
        if _engine is not None:
            _engine.dispose()
        _engine = create_engine(sqlite_url(path), future=True)
        _attach_sqlite_pragmas(_engine)
        _engine_path = path
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def dispose_engine() -> None:
    """Close the cached engine (useful in tests / process shutdown)."""
    global _engine, _engine_path, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _engine_path = None
    _SessionLocal = None


def get_session_factory(db_path: Path | str | None = None) -> sessionmaker[Session]:
    get_engine(db_path)
    assert _SessionLocal is not None
    return _SessionLocal


@contextmanager
def session_scope(db_path: Path | str | None = None) -> Iterator[Session]:
    session = get_session_factory(db_path)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
