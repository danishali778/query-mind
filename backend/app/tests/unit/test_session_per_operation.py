"""Regression tests for the Phase 2 "one session per flow" consolidation.

Covers:
  (a) a converted multi-write flow rolls back ALL of its writes when a later
      step in the same flow raises (query_library_repository.record_run
      bumps run_count and logs the run in one transaction).
  (b) a converted multi-read flow issues its work through a single session
      (template_repository.get_generation_status_and_templates), instead of
      the two separate read-pool checkouts it replaced.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.session as db_session
from app.db.base import Base
from app.db.models.query_library import SaveQueryInput
from app.db.repositories import query_library_repository, template_repository


@pytest.fixture(autouse=True)
def sqlite_app_db():
    # Repositories run their DB work in worker threads (anyio.to_thread), so
    # the in-memory SQLite connection must be shareable across threads.
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)
    db_session._engine = engine
    db_session._read_engine = engine
    db_session._session_factory = SessionLocal
    db_session._read_session_factory = SessionLocal
    Base.metadata.create_all(engine)
    try:
        yield
    finally:
        Base.metadata.drop_all(engine)
        db_session.reset_engine_for_tests()


def test_record_run_rolls_back_run_count_when_log_run_fails(monkeypatch):
    """record_run bumps the saved query's run_count and inserts a new
    execution-history row in one transaction. If logging the run fails, the
    run-count bump from the same call must be rolled back with it -- that's
    the whole point of sharing one session across the two writes."""
    saved, created = asyncio.run(
        query_library_repository.save_query(
            "user-1",
            SaveQueryInput(title="Revenue", sql="select 1", folder_name="Finance"),
        )
    )
    assert created is True
    assert saved.run_count == 0

    def boom(*_args, **_kwargs):
        raise RuntimeError("execution history write failed")

    monkeypatch.setattr(query_library_repository, "_log_run_sync", boom)

    with pytest.raises(RuntimeError, match="execution history write failed"):
        asyncio.run(
            query_library_repository.record_run("user-1", saved.id, success=True, row_count=1)
        )

    refreshed = asyncio.run(query_library_repository.get_query("user-1", saved.id))
    assert refreshed is not None
    assert refreshed.run_count == 0, "run_count bump must roll back with the failed log_run write"
    assert refreshed.last_run_at is None

    history = asyncio.run(query_library_repository.get_run_history("user-1", saved.id))
    assert history == []


def test_record_run_commits_both_writes_together_on_success():
    """Sanity check for the happy path: both writes land together."""
    saved, created = asyncio.run(
        query_library_repository.save_query(
            "user-1",
            SaveQueryInput(title="Revenue", sql="select 1", folder_name="Finance"),
        )
    )
    assert created is True

    updated_query, run_record = asyncio.run(
        query_library_repository.record_run(
            "user-1", saved.id, success=True, row_count=3, execution_time_ms=12.0
        )
    )

    assert updated_query is not None
    assert updated_query.run_count == 1
    assert run_record.row_count == 3

    refreshed = asyncio.run(query_library_repository.get_query("user-1", saved.id))
    assert refreshed.run_count == 1
    history = asyncio.run(query_library_repository.get_run_history("user-1", saved.id))
    assert len(history) == 1


def test_get_generation_status_and_templates_uses_a_single_session(monkeypatch):
    """The merged read flow (generation status + templates) must open the
    read-only session factory exactly once, instead of the two separate
    read_session_scope() checkouts it replaced."""
    factory_calls: list[int] = []
    real_get_read_session_factory = db_session.get_read_session_factory

    def counting_factory():
        factory_calls.append(1)
        return real_get_read_session_factory()

    monkeypatch.setattr(db_session, "get_read_session_factory", counting_factory)

    state, templates = template_repository.get_generation_status_and_templates("user-1", "conn-1")

    assert state is None
    assert templates == []
    assert len(factory_calls) == 1, "expected exactly one session-factory checkout for the merged read flow"
