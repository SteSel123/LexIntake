"""SQLAlchemy engine and session helpers (PostgreSQL only).

Centralizes connection pooling and transaction boundaries so structured queries,
Alembic migrations, and pgvector access share one engine per process.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config import require_database_url

# Process-wide singletons; recreated when DATABASE_URL changes (e.g. in tests).
_engine: Engine | None = None
_engine_key: str | None = None
_SessionLocal: sessionmaker[Session] | None = None


def database_url() -> str:
    """Return the configured PostgreSQL URL (raises if unset)."""
    return require_database_url()


def get_engine() -> Engine:
    """Return a process-wide SQLAlchemy engine for ``DATABASE_URL``.

    Uses ``pool_pre_ping`` so stale connections are dropped before use, and a
    short connect timeout to fail fast when Postgres is unreachable.
    """
    global _engine, _engine_key, _SessionLocal
    url = database_url()
    if _engine is None or _engine_key != url:
        if _engine is not None:
            _engine.dispose()
        _engine = create_engine(
            url,
            future=True,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 5},
        )
        _engine_key = url
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def dispose_engine() -> None:
    """Close the cached engine (useful in tests / process shutdown)."""
    global _engine, _engine_key, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _engine_key = None
    _SessionLocal = None


def get_session_factory() -> sessionmaker[Session]:
    """Return the bound sessionmaker, creating the engine if needed."""
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope: commit on success, rollback on error."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_postgres_extensions(engine: Engine | None = None) -> None:
    """Create ``vector`` (pgvector) and ``pg_trgm`` extensions if missing.

    Required for embedding search and fuzzy text fallback on ``kb_docs``.
    """
    eng = engine or get_engine()
    with eng.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
