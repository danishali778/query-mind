"""SQLAlchemy engine and session helpers for query-mind app persistence."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


_engine: Engine | None = None
_read_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_read_session_factory: sessionmaker[Session] | None = None


def get_app_database_url() -> str:
    """Return the direct app database URL used by SQLAlchemy repositories."""
    if not settings.app_database_url:
        raise RuntimeError(
            "APP_DATABASE_URL is required for SQLAlchemy app persistence. "
            "Use the direct Supabase Postgres connection string, not the REST API URL."
        )
    return settings.app_database_url


def get_engine() -> Engine:
    """Return a lazily initialized SQLAlchemy engine for the app database.

    Note: `pool_pre_ping` is intentionally omitted. It would send a `SELECT 1`
    round trip on every pool checkout to guard against stale connections, but
    `pool_recycle=1800` already covers the common staleness cause (idle
    timeouts) by discarding connections older than 30 minutes. Against a
    remote database with meaningful per-round-trip latency, that extra
    round trip on every checkout is not worth paying for the residual case
    of a connection dying within its 30-minute window.
    """
    global _engine
    if _engine is None:
        _engine = create_engine(
            get_app_database_url(),
            pool_recycle=1800,
            future=True,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return a lazily initialized session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
    return _session_factory


def get_read_engine() -> Engine:
    """Return a lazily initialized AUTOCOMMIT engine for read-only sessions.

    This is a dedicated engine (own small pool) rather than
    `get_engine().execution_options(isolation_level="AUTOCOMMIT")` sharing the
    write pool. Sharing the pool looks cheaper, but SQLAlchemy then switches
    the isolation level per checkout and restores it with a server command on
    check-in — measured as one extra ~180ms round-trip per read against the
    remote database. A dedicated pool keeps its connections permanently in
    AUTOCOMMIT, so a read costs exactly one round-trip.
    """
    global _read_engine
    if _read_engine is None:
        _read_engine = create_engine(
            get_app_database_url(),
            pool_recycle=1800,
            future=True,
            isolation_level="AUTOCOMMIT",
        )
    return _read_engine


def get_read_session_factory() -> sessionmaker[Session]:
    """Return a lazily initialized session factory for read-only operations.

    Statements execute under AUTOCOMMIT isolation, so there is no BEGIN or
    COMMIT/ROLLBACK round trip — only the query itself crosses the network.
    """
    global _read_session_factory
    if _read_session_factory is None:
        _read_session_factory = sessionmaker(
            bind=get_read_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
    return _read_session_factory


def new_session() -> Session:
    """Create a new SQLAlchemy session."""
    return get_session_factory()()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional scope around repository operations."""
    session = new_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def read_session_scope() -> Generator[Session, None, None]:
    """Provide a read-only scope with no transaction, for pure query paths.

    Statements execute under AUTOCOMMIT isolation, so there is no
    COMMIT/ROLLBACK round trip on scope exit — only the query itself crosses
    the network. The session is still closed deterministically, and
    exceptions propagate normally without ever attempting a commit.

    Never use this for writes: no commit is issued, so any `session.add`,
    `session.delete`, or attribute mutation performed here would either be
    silently lost or (under autocommit) applied outside of any rollback
    safety net. Reserve it strictly for reads.
    """
    session = get_read_session_factory()()
    try:
        yield session
    finally:
        session.close()


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI dependency-compatible session generator."""
    with session_scope() as session:
        yield session


def reset_engine_for_tests() -> None:
    """Dispose and clear engine state for tests that override configuration."""
    global _engine, _read_engine, _session_factory, _read_session_factory
    if _engine is not None:
        _engine.dispose()
    if _read_engine is not None:
        _read_engine.dispose()
    _engine = None
    _read_engine = None
    _session_factory = None
    _read_session_factory = None


__all__ = [
    "get_app_database_url",
    "get_engine",
    "get_session_factory",
    "get_read_session_factory",
    "new_session",
    "session_scope",
    "read_session_scope",
    "get_db_session",
    "reset_engine_for_tests",
]
