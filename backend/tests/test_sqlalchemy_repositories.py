import asyncio
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.db.session as db_session
from app.db.base import Base
from app.db.models.chat import ChatMessage
from app.db.models.connection import ConnectionRequest
from app.db.models.query_library import SaveQueryInput
from app.db.models.dashboard import CreateDashboardInput
from app.db.repositories import (
    chat_repository,
    connection_repository,
    dashboard_repository,
    query_history_repository,
    query_library_repository,
    settings_repository,
)


@pytest.fixture(autouse=True)
def sqlite_app_db():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)
    db_session._engine = engine
    db_session._session_factory = SessionLocal
    Base.metadata.create_all(engine)
    try:
        yield
    finally:
        Base.metadata.drop_all(engine)
        db_session.reset_engine_for_tests()


def _user_id() -> str:
    return str(uuid.uuid4())


def test_onboard_user_creates_settings_and_subscription_rows():
    user_id = _user_id()

    assert settings_repository.onboard_user(user_id) is True

    settings = settings_repository.get_user_settings(user_id)
    subscription = settings_repository.get_user_subscription(user_id)

    assert settings.owner_id == user_id
    assert settings.timezone == "UTC"
    assert subscription.owner_id == user_id
    assert subscription.plan_type == "free"


def test_increment_usage_is_owner_scoped():
    user_a = _user_id()
    user_b = _user_id()
    settings_repository.onboard_user(user_a)
    settings_repository.onboard_user(user_b)

    assert settings_repository.increment_usage(user_a, "query") is True

    sub_a = settings_repository.get_user_subscription(user_a)
    sub_b = settings_repository.get_user_subscription(user_b)
    assert sub_a.queries_used == 1
    assert sub_b.queries_used == 0


def test_query_history_filters_by_owner():
    user_a = _user_id()
    user_b = _user_id()
    conn_a = _user_id()
    conn_b = _user_id()

    query_history_repository.log_query(user_a, conn_a, "select 1", True, execution_time_ms=1.5, row_count=1)
    query_history_repository.log_query(user_b, conn_b, "select 2", False, error="boom")

    history_a = query_history_repository.get_history(user_a)
    history_b = query_history_repository.get_history(user_b)

    assert [record.sql for record in history_a] == ["select 1"]
    assert [record.sql for record in history_b] == ["select 2"]


def test_connection_lookup_requires_owner():
    user_a = _user_id()
    user_b = _user_id()

    connection_id = asyncio.run(asyncio_create_connection(user_a))

    assert asyncio.run(connection_repository.get_connection_config(user_a, connection_id)) is not None
    assert asyncio.run(connection_repository.get_connection_config(user_b, connection_id)) is None


async def asyncio_create_connection(user_id: str) -> str:
    return await connection_repository.create_connection(
        user_id,
        ConnectionRequest(
            db_type="postgresql",
            host="localhost",
            port=5432,
            database="demo",
            username="demo",
            password=None,
            name="Demo",
        ),
    )


def test_dashboard_lookup_requires_owner():
    user_a = _user_id()
    user_b = _user_id()

    dashboard = asyncio.run(dashboard_repository.create_dashboard(user_a, CreateDashboardInput(name="Revenue")))

    assert asyncio.run(dashboard_repository.get_dashboard(user_a, dashboard.id)) is not None
    assert asyncio.run(dashboard_repository.get_dashboard(user_b, dashboard.id)) is None

def test_saved_query_lookup_requires_owner():
    user_a = _user_id()
    user_b = _user_id()

    saved, created = asyncio.run(
        query_library_repository.save_query(
            user_a,
            SaveQueryInput(title="Revenue", sql="select 1", folder_name="Finance", tags=["kpi"]),
        )
    )

    assert created is True
    assert asyncio.run(query_library_repository.get_query(user_a, saved.id)) is not None
    assert asyncio.run(query_library_repository.get_query(user_b, saved.id)) is None
    assert asyncio.run(query_library_repository.delete_query(user_b, saved.id)) is False
    assert asyncio.run(query_library_repository.delete_query(user_a, saved.id)) is True


def test_chat_session_lookup_and_history_require_owner():
    user_a = _user_id()
    user_b = _user_id()

    session = asyncio.run(chat_repository.create_session(user_a))
    asyncio.run(chat_repository.add_message(user_a, session.id, ChatMessage(role="user", content="hello")))

    owned = asyncio.run(chat_repository.get_session(user_a, session.id))
    other = asyncio.run(chat_repository.get_session(user_b, session.id))

    assert owned is not None
    assert [message.content for message in owned.messages] == ["hello"]
    assert other is None
    assert asyncio.run(chat_repository.get_history_for_llm(user_b, session.id)) == []
