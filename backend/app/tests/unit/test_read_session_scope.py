"""Regression tests for the session round-trip reductions in app.db.session.

Covers: pool liveness and bounds, the guarded AUTOCOMMIT read session,
and that session_scope's commit/rollback behavior on the write path is
unchanged.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, InvalidRequestError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db import session as db_session


@pytest.fixture(autouse=True)
def _reset_session_state():
    """Ensure engine/session-factory globals don't leak between tests."""
    db_session.reset_engine_for_tests()
    yield
    db_session.reset_engine_for_tests()


def _use_sqlite_engine(monkeypatch) -> None:
    """Point both engines at in-memory SQLite for these tests."""
    engine = create_engine("sqlite:///:memory:", future=True)
    read_engine = create_engine(
        "sqlite:///:memory:", future=True, isolation_level="AUTOCOMMIT"
    )
    monkeypatch.setattr(db_session, "_engine", engine)
    monkeypatch.setattr(db_session, "_read_engine", read_engine)
    monkeypatch.setattr(db_session, "_session_factory", None)
    monkeypatch.setattr(db_session, "_read_session_factory", None)


def test_engines_keep_pre_ping():
    """Both pools must detect stale connections before serving work."""
    engine = db_session.get_engine()
    read_engine = db_session.get_read_engine()
    assert engine.pool._pre_ping is True
    assert read_engine.pool._pre_ping is True
    assert engine.pool.size() == db_session.settings.app_db_write_pool_size
    assert read_engine.pool.size() == db_session.settings.app_db_read_pool_size


def test_read_session_scope_yields_working_session(monkeypatch):
    """read_session_scope() should hand back a session that can run queries
    against the shared engine (AUTOCOMMIT, no surrounding transaction)."""
    _use_sqlite_engine(monkeypatch)

    with db_session.read_session_scope() as session:
        session.execute(text("CREATE TABLE widgets (id INTEGER)"))
        session.execute(text("INSERT INTO widgets VALUES (1)"))
        rows = session.execute(text("SELECT * FROM widgets")).all()
        assert rows == [(1,)]


def test_read_factory_uses_dedicated_autocommit_engine():
    """The read-only factory must be bound to a DEDICATED engine created with
    AUTOCOMMIT isolation. Sharing the write engine's pool via
    execution_options() switches isolation per checkout, and SQLAlchemy
    restores it with a server command on check-in — measured as one extra
    ~180ms round-trip per read against the remote database."""
    db_session.reset_engine_for_tests()
    try:
        engine = db_session.get_engine()
        read_engine = db_session.get_read_engine()

        assert read_engine is not engine
        assert db_session.get_read_session_factory().kw["bind"] is read_engine
        isolation = getattr(read_engine.dialect, "_on_connect_isolation_level", None)
        assert isolation == "AUTOCOMMIT", (
            "read engine must be created with isolation_level='AUTOCOMMIT' "
            f"(got {isolation!r}); if SQLAlchemy renamed this attribute, "
            "update the assertion rather than deleting it"
        )
        assert read_engine.pool._pre_ping is True
        assert read_engine.pool.size() == db_session.settings.app_db_read_pool_size
    finally:
        db_session.reset_engine_for_tests()


def test_read_session_scope_never_commits_directly(monkeypatch):
    """The scope never requests commit/rollback and always closes."""

    calls: list[str] = []

    class _RecordingSession:
        def commit(self):
            calls.append("commit")

        def rollback(self):
            calls.append("rollback")

        def close(self):
            calls.append("close")

    fake_session = _RecordingSession()
    monkeypatch.setattr(db_session, "get_read_session_factory", lambda: (lambda: fake_session))

    with db_session.read_session_scope() as session:
        assert session is fake_session

    assert "commit" not in calls
    assert "rollback" not in calls
    assert calls == ["close"]


def test_read_session_scope_closes_on_exception(monkeypatch):
    """Even when the caller raises, the session must still be closed and no
    commit attempted."""

    calls: list[str] = []

    class _RecordingSession:
        def commit(self):
            calls.append("commit")

        def rollback(self):
            calls.append("rollback")

        def close(self):
            calls.append("close")

    fake_session = _RecordingSession()
    monkeypatch.setattr(db_session, "get_read_session_factory", lambda: (lambda: fake_session))

    with pytest.raises(RuntimeError):
        with db_session.read_session_scope():
            raise RuntimeError("boom")

    assert "commit" not in calls
    assert calls == ["close"]


def test_session_scope_commits_on_success(monkeypatch):
    """Regression guard: the write path must still commit when the block
    completes without error."""

    calls: list[str] = []

    class _RecordingSession:
        def commit(self):
            calls.append("commit")

        def rollback(self):
            calls.append("rollback")

        def close(self):
            calls.append("close")

    fake_session = _RecordingSession()
    monkeypatch.setattr(db_session, "new_session", lambda: fake_session)

    with db_session.session_scope() as session:
        assert session is fake_session

    assert calls == ["commit", "close"]


def test_session_scope_rolls_back_on_exception(monkeypatch):
    """Regression guard: the write path must roll back (not commit) when the
    block raises."""

    calls: list[str] = []

    class _RecordingSession:
        def commit(self):
            calls.append("commit")

        def rollback(self):
            calls.append("rollback")

        def close(self):
            calls.append("close")

    fake_session = _RecordingSession()
    monkeypatch.setattr(db_session, "new_session", lambda: fake_session)

    with pytest.raises(RuntimeError):
        with db_session.session_scope():
            raise RuntimeError("boom")

    assert calls == ["rollback", "close"]


def test_reset_engine_for_tests_clears_read_factory(monkeypatch):
    """reset_engine_for_tests() must also drop the cached read-only factory
    so a subsequent get_read_session_factory() rebuilds against the current
    engine instead of a disposed one."""
    _use_sqlite_engine(monkeypatch)

    first_factory = db_session.get_read_session_factory()
    db_session.reset_engine_for_tests()

    _use_sqlite_engine(monkeypatch)
    second_factory = db_session.get_read_session_factory()

    assert first_factory is not second_factory


def test_postgres_read_only_connection_setup():
    calls: list[str] = []

    class _Cursor:
        def execute(self, statement):
            calls.append(statement)

        def close(self):
            calls.append("close")

    class _Connection:
        autocommit = False

        def cursor(self):
            return _Cursor()

    connection = _Connection()
    db_session._configure_postgres_read_only(connection, None)

    assert connection.autocommit is True
    assert calls == ["SET default_transaction_read_only = on", "close"]


def test_read_only_session_rejects_orm_writes(monkeypatch):
    class _Base(DeclarativeBase):
        pass

    class _Widget(_Base):
        __tablename__ = "widgets"
        id: Mapped[int] = mapped_column(primary_key=True)

    engine = create_engine("sqlite:///:memory:", future=True)
    _Base.metadata.create_all(engine)
    monkeypatch.setattr(db_session, "_read_engine", engine)
    monkeypatch.setattr(db_session, "_read_session_factory", None)

    with db_session.read_session_scope() as session:
        session.add(_Widget(id=1))
        with pytest.raises(InvalidRequestError, match="Read-only session"):
            session.flush()


@pytest.mark.integration
def test_postgres_read_engine_rejects_raw_writes():
    """The database, not only the ORM session, must reject raw writes."""
    with db_session.read_session_scope() as session:
        with pytest.raises(DBAPIError, match="(?i)read.only"):
            session.execute(text("CREATE TABLE qm_readonly_probe (id integer)"))
