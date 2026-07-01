import asyncio
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.session as db_session
from app.api.deps import CurrentUserDep
from app.api.v1.routes import auth as auth_route
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.supabase_auth import ACCESS_TOKEN_COOKIE_NAME, REFRESH_TOKEN_COOKIE_NAME
from app.db.base import Base
from app.db.repositories import settings_repository
from app.integrations.supabase_auth import dependencies as auth_dependencies
from app.services.auth import AuthSessionResult


@pytest.fixture(autouse=True)
def sqlite_app_db():
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)
    db_session._engine = engine
    db_session._session_factory = SessionLocal
    Base.metadata.create_all(engine)
    try:
        yield
    finally:
        Base.metadata.drop_all(engine)
        db_session.reset_engine_for_tests()


@pytest.fixture
def app():
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(auth_route.router)

    @app.get("/protected")
    def protected(current_user: CurrentUserDep):
        return {"id": current_user.id, "email": current_user.email}

    return app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def reset_mock_auth(monkeypatch):
    monkeypatch.setattr(settings, "backend_dev_mode", False, raising=False)
    monkeypatch.setattr(settings, "supabase_jwt_secret", "test-secret", raising=False)


def test_login_sets_auth_cookies_and_returns_user(client, monkeypatch):
    result = AuthSessionResult(
        authenticated=True,
        user_id="user-1",
        email="user@example.com",
        access_token="access-token",
        refresh_token="refresh-token",
        expires_in=3600,
    )
    monkeypatch.setattr(auth_route.auth_service, "login", lambda email, password: result)

    response = client.post("/api/auth/login", json={"email": "user@example.com", "password": "secret"})

    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is True
    assert body["user"]["id"] == "user-1"
    set_cookie = "\n".join(response.headers.get_list("set-cookie"))
    assert ACCESS_TOKEN_COOKIE_NAME in set_cookie
    assert REFRESH_TOKEN_COOKIE_NAME in set_cookie


def test_refresh_sets_rotated_auth_cookies(client, monkeypatch):
    result = AuthSessionResult(
        authenticated=True,
        user_id="user-1",
        email="user@example.com",
        access_token="next-access",
        refresh_token="next-refresh",
        expires_in=3600,
    )
    monkeypatch.setattr(auth_route.auth_service, "refresh_session", lambda token: result)
    client.cookies.set(REFRESH_TOKEN_COOKIE_NAME, "refresh-token")

    response = client.post("/api/auth/refresh")

    assert response.status_code == 200
    set_cookie = "\n".join(response.headers.get_list("set-cookie"))
    assert "next-access" in set_cookie
    assert "next-refresh" in set_cookie


def test_logout_clears_cookies(client, monkeypatch):
    monkeypatch.setattr(auth_route.auth_service, "logout", lambda token: None)
    client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, "access-token")

    response = client.post("/api/auth/logout")

    assert response.status_code == 200
    set_cookie = "\n".join(response.headers.get_list("set-cookie"))
    assert f"{ACCESS_TOKEN_COOKIE_NAME}=" in set_cookie
    assert f"{REFRESH_TOKEN_COOKIE_NAME}=" in set_cookie


def test_session_bootstraps_user_rows_from_valid_cookie(client, monkeypatch):
    user_id = str(uuid.uuid4())

    def decode(_token: str):
        return {"sub": user_id, "email": "new@example.com"}

    monkeypatch.setattr(auth_dependencies, "decode_supabase_jwt", decode)
    client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, "valid-token")

    response = client.get("/api/auth/session")

    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is True
    assert body["user"]["id"] == user_id
    user_settings = settings_repository.get_user_settings(user_id)
    subscription = settings_repository.get_user_subscription(user_id)
    assert user_settings.owner_id == user_id
    assert subscription.owner_id == user_id


def test_session_returns_401_without_auth(client):
    response = client.get("/api/auth/session")

    assert response.status_code == 401


def test_protected_route_accepts_cookie_auth(client, monkeypatch):
    user_id = str(uuid.uuid4())
    settings_repository.onboard_user(user_id)

    def decode(_token: str):
        return {"sub": user_id, "email": "cookie@example.com"}

    monkeypatch.setattr(auth_dependencies, "decode_supabase_jwt", decode)
    client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, "cookie-token")

    response = client.get("/protected")

    assert response.status_code == 200
    assert response.json()["id"] == user_id


def test_protected_route_falls_back_to_authorization_header(client, monkeypatch):
    user_id = str(uuid.uuid4())
    settings_repository.onboard_user(user_id)

    def decode(_token: str):
        return {"sub": user_id, "email": "header@example.com"}

    monkeypatch.setattr(auth_dependencies, "decode_supabase_jwt", decode)

    response = client.get("/protected", headers={"Authorization": "Bearer header-token"})

    assert response.status_code == 200
    assert response.json()["email"] == "header@example.com"


def test_invalid_token_returns_401(client, monkeypatch):
    def decode(_token: str):
        raise auth_dependencies.JWTError("bad token")

    monkeypatch.setattr(auth_dependencies, "decode_supabase_jwt", decode)
    client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, "bad-token")

    response = client.get("/protected")

    assert response.status_code == 401


def test_mock_auth_bypass_still_works(client, monkeypatch):
    monkeypatch.setattr(settings, "backend_dev_mode", True, raising=False)
    monkeypatch.setattr(settings, "supabase_jwt_secret", None, raising=False)

    response = client.get("/protected")

    assert response.status_code == 200
    assert response.json()["id"] == settings.dev_user_id


def _connection_test_client(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.v1.routes import connections as connections_route
    from app.core.errors import register_exception_handlers
    from app.integrations.supabase_auth import User, get_current_user

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(connections_route.router)
    app.dependency_overrides[get_current_user] = lambda: User(id="00000000-0000-0000-0000-000000000001", email="user@example.com")
    return TestClient(app, raise_server_exceptions=False)


def test_blocked_database_test_does_not_call_connection_pool(client, monkeypatch):
    from app.core.config import settings
    from app.db import connection_manager

    monkeypatch.setattr(settings, "app_env", "production", raising=False)
    monkeypatch.setattr(settings, "db_connect_allowed_hosts_raw", "", raising=False)
    monkeypatch.setattr(settings, "db_connect_allowed_cidrs_raw", "", raising=False)
    monkeypatch.setattr(connection_manager, "enforce_connection_attempt_rate_limit", lambda owner_id: None)

    def fail_if_called(config):
        raise AssertionError("connection pool should not be called for blocked targets")

    monkeypatch.setattr(connection_manager.connection_pool, "test_connection", fail_if_called)
    test_client = _connection_test_client(monkeypatch)

    response = test_client.post(
        "/api/database/test",
        json={
            "db_type": "postgresql",
            "host": "127.0.0.1",
            "port": 5432,
            "database": "demo",
            "username": "demo",
            "password": "secret",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"


def test_blocked_database_connect_does_not_save_connection(client, monkeypatch):
    from app.core.config import settings
    from app.db import connection_manager
    from app.db.repositories import connection_repository

    monkeypatch.setattr(settings, "app_env", "production", raising=False)
    monkeypatch.setattr(settings, "db_connect_allowed_hosts_raw", "", raising=False)
    monkeypatch.setattr(settings, "db_connect_allowed_cidrs_raw", "", raising=False)
    monkeypatch.setattr(connection_manager, "enforce_connection_attempt_rate_limit", lambda owner_id: None)

    def fail_if_called(config):
        raise AssertionError("open_connection should not be called for blocked targets")

    monkeypatch.setattr(connection_manager.connection_pool, "open_connection", fail_if_called)
    test_client = _connection_test_client(monkeypatch)

    response = test_client.post(
        "/api/database/connect",
        json={
            "db_type": "postgresql",
            "host": "127.0.0.1",
            "port": 5432,
            "database": "demo",
            "username": "demo",
            "password": "secret",
        },
    )

    assert response.status_code == 400
    assert asyncio.run(connection_repository.list_connections("00000000-0000-0000-0000-000000000001")) == []


def test_successful_database_test_uses_existing_connection_flow(client, monkeypatch):
    from app.core.config import settings
    from app.db import connection_manager

    called = {"value": False}

    async def fake_test_connection(config):
        called["value"] = True
        return True, "Connection successful"

    monkeypatch.setattr(settings, "app_env", "development", raising=False)
    monkeypatch.setattr(settings, "db_connect_allow_private_in_dev", True, raising=False)
    monkeypatch.setattr(connection_manager, "enforce_connection_attempt_rate_limit", lambda owner_id: None)
    monkeypatch.setattr(connection_manager.connection_pool, "test_connection", fake_test_connection)
    test_client = _connection_test_client(monkeypatch)

    response = test_client.post(
        "/api/database/test",
        json={
            "db_type": "postgresql",
            "host": "127.0.0.1",
            "port": 5432,
            "database": "demo",
            "username": "demo",
            "password": "secret",
        },
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert called["value"] is True
