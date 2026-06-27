"""SQLAlchemy engine and session helpers for query-mind app persistence."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_app_database_url() -> str:
    """Return the direct app database URL used by SQLAlchemy repositories."""
    if not settings.app_database_url:
        raise RuntimeError(
            "APP_DATABASE_URL is required for SQLAlchemy app persistence. "
            "Use the direct Supabase Postgres connection string, not the REST API URL."
        )
    return settings.app_database_url


def get_engine() -> Engine:
    """Return a lazily initialized SQLAlchemy engine for the app database."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            get_app_database_url(),
            pool_pre_ping=True,
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


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI dependency-compatible session generator."""
    with session_scope() as session:
        yield session


def reset_engine_for_tests() -> None:
    """Dispose and clear engine state for tests that override configuration."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


__all__ = [
    "get_app_database_url",
    "get_engine",
    "get_session_factory",
    "new_session",
    "session_scope",
    "get_db_session",
    "reset_engine_for_tests",
]
