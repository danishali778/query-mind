from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.session as db_session
from app.db.base import Base
from app.db.repositories import chat_run_repository
from app.query_engine.cancellation import QueryCancellationToken


@pytest.fixture(autouse=True)
def sqlite_app_db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)
    db_session._engine = engine
    db_session._read_engine = engine
    db_session._session_factory = factory
    db_session._read_session_factory = factory
    Base.metadata.create_all(engine)
    try:
        yield
    finally:
        Base.metadata.drop_all(engine)
        db_session.reset_engine_for_tests()


def _create(client_request_id: str, session_id: str | None = None):
    return asyncio.run(
        chat_run_repository.create_queued_run(
            user_id="user-1",
            connection_id="connection-1",
            message="Show monthly revenue",
            client_request_id=client_request_id,
            session_id=session_id,
        )
    )


def test_run_creation_is_atomic_and_idempotent():
    run, user_message, assistant, history, created = _create("11111111-1111-1111-1111-111111111111")

    assert created is True
    assert run.status == "queued"
    assert run.user_message_id == user_message.id
    assert assistant.agent_run_id == run.id
    assert history[-1] == {"role": "user", "content": "Show monthly revenue"}

    duplicate, duplicate_user, duplicate_assistant, _, duplicate_created = _create(
        "11111111-1111-1111-1111-111111111111"
    )
    assert duplicate_created is False
    assert duplicate.id == run.id
    assert duplicate_user.id == user_message.id
    assert duplicate_assistant.id == assistant.id


def test_only_one_non_terminal_run_is_allowed_per_session():
    run, *_ = _create("11111111-1111-1111-1111-111111111111")

    with pytest.raises(chat_run_repository.ActiveRunConflictError):
        _create("22222222-2222-2222-2222-222222222222", run.session_id)


def test_cancellation_wins_before_completion():
    run, *_ = _create("11111111-1111-1111-1111-111111111111")
    claimed = chat_run_repository.claim_run(run.id)
    assert claimed and claimed.status == "running"

    cancelled = chat_run_repository.request_cancel("user-1", run.id)
    assert cancelled and cancelled.status == "cancel_requested"
    assert chat_run_repository.finalize_run(run.id, status="completed", message_updates={"content": "late"}) is False
    assert chat_run_repository.finalize_run(
        run.id,
        status="cancelled",
        failure_code="cancelled_by_user",
        failure_message="Response stopped by user.",
    ) is True
    assert chat_run_repository.get_run_unscoped_sync(run.id).status == "cancelled"


def test_run_lookup_is_owner_scoped():
    run, *_ = _create("11111111-1111-1111-1111-111111111111")
    assert asyncio.run(chat_run_repository.get_run("other-user", run.id)) is None


def test_query_cancellation_token_calls_driver_cancel():
    class Driver:
        cancelled = False

        def cancel(self):
            self.cancelled = True

    class Fairy:
        driver_connection = Driver()

    class Connection:
        connection = Fairy()

    token = QueryCancellationToken()
    connection = Connection()
    token.register(connection)
    token.cancel()

    assert token.cancelled is True
    assert connection.connection.driver_connection.cancelled is True
