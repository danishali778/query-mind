"""SQLAlchemy engine and session helpers for query-mind app persistence."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import InvalidRequestError
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

    Pre-ping is retained so a pooler restart or other stale connection is
    recovered before a write-path operation is attempted. Pool recycle only
    handles connection age and is not a substitute for liveness detection.
    """
    global _engine
    if _engine is None:
        _engine = create_engine(
            get_app_database_url(),
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_size=settings.app_db_write_pool_size,
            max_overflow=settings.app_db_write_max_overflow,
            pool_timeout=settings.app_db_pool_timeout_seconds,
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


def _configure_postgres_read_only(dbapi_connection, _connection_record) -> None:
    """Make every transaction on a read-pool connection database read-only.

    The application database currently uses psycopg2. The read engine itself
    runs in DBAPI autocommit mode, so this session-level setting is applied
    once when a physical connection is created and persists across checkouts.
    """
    dbapi_connection.autocommit = True
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("SET default_transaction_read_only = on")
    finally:
        cursor.close()


class ReadOnlySession(Session):
    """Session that rejects ORM persistence before it reaches the database."""

    def flush(self, objects=None) -> None:
        if self.new or self.dirty or self.deleted:
            raise InvalidRequestError("Read-only session cannot flush ORM changes.")
        super().flush(objects)


def get_read_engine() -> Engine:
    """Return a lazily initialized AUTOCOMMIT engine for read-only sessions.

    This is a dedicated engine (own bounded pool) rather than
    `get_engine().execution_options(isolation_level="AUTOCOMMIT")` sharing the
    write pool. Sharing the pool looks cheaper, but SQLAlchemy then switches
    the isolation level per checkout and restores it with a server command on
    check-in — measured as one extra ~180ms round-trip per read against the
    remote database. A dedicated pool keeps its connections permanently in
    AUTOCOMMIT. SQLAlchemy 2.0.43's ``skip_autocommit_rollback`` prevents a
    DBAPI rollback when the connection is returned to the pool. Pre-ping is
    still retained intentionally for stale-connection recovery.
    """
    global _read_engine
    if _read_engine is None:
        _read_engine = create_engine(
            get_app_database_url(),
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_size=settings.app_db_read_pool_size,
            max_overflow=settings.app_db_read_max_overflow,
            pool_timeout=settings.app_db_pool_timeout_seconds,
            future=True,
            isolation_level="AUTOCOMMIT",
            skip_autocommit_rollback=True,
        )
        if _read_engine.dialect.name == "postgresql":
            event.listen(_read_engine, "connect", _configure_postgres_read_only)
    return _read_engine


def get_read_session_factory() -> sessionmaker[Session]:
    """Return a lazily initialized session factory for read-only operations.

    PostgreSQL connections default to read-only transactions, ORM flushes are
    rejected locally, and DBAPI rollback calls are skipped under AUTOCOMMIT.
    """
    global _read_session_factory
    if _read_session_factory is None:
        _read_session_factory = sessionmaker(
            bind=get_read_engine(),
            class_=ReadOnlySession,
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
    """Provide a guarded read-only scope for pure query paths.

    Statements use DBAPI AUTOCOMMIT, and SQLAlchemy is configured not to call
    DBAPI rollback on scope exit. PostgreSQL also enforces read-only defaults
    on every physical read connection. Pre-ping remains an intentional
    liveness round trip before a pooled connection is used.

    Never use this for writes. ORM persistence is rejected locally, and the
    database rejects raw write statements on PostgreSQL.
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
    "get_read_engine",
    "get_read_session_factory",
    "new_session",
    "session_scope",
    "read_session_scope",
    "get_db_session",
    "reset_engine_for_tests",
]
