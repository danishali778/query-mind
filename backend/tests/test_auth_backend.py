import asyncio
from datetime import datetime, timezone
import time
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt
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
from app.db.orm_models import RevokedAuthSessionORM, UserSettingsORM
from app.db.repositories import auth_session_repository, settings_repository
from app.db.session import session_scope
from app.integrations.supabase_auth import dependencies as auth_dependencies
from app.services.auth import AuthSessionResult, LogoutResult
from app.services import account_state_service, auth as auth_service


def _jwt_payload(user_id: str, email: str | None = None, session_id: str = "session-1") -> dict:
    return {
        "sub": user_id,
        "email": email,
        "session_id": session_id,
        "exp": int(time.time()) + 3600,
    }


def _signed_token(user_id: str, *, session_id: str = "session-1") -> str:
    return jose_jwt.encode(
        {
            **_jwt_payload(user_id, "user@example.com", session_id),
            "aud": "authenticated",
            "iss": "https://example.supabase.co/auth/v1",
        },
        "test-secret",
        algorithm="HS256",
    )


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
    db_session._read_engine = engine
    db_session._session_factory = SessionLocal
    db_session._read_session_factory = SessionLocal
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
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Path=/api/auth" in set_cookie


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
    monkeypatch.setattr(
        auth_route.auth_service,
        "logout",
        lambda token: LogoutResult(True, True),
    )
    client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, "access-token")

    response = client.post("/api/auth/logout")

    assert response.status_code == 200
    set_cookie = "\n".join(response.headers.get_list("set-cookie"))
    assert f"{ACCESS_TOKEN_COOKIE_NAME}=" in set_cookie
    assert f"{REFRESH_TOKEN_COOKIE_NAME}=" in set_cookie


def test_logout_revokes_access_token_locally(client, monkeypatch):
    user_id = str(uuid.uuid4())
    settings_repository.onboard_user(user_id)
    token = _signed_token(user_id)

    class SuccessfulResponse:
        is_success = True
        status_code = 204

    monkeypatch.setattr(auth_route.auth_service.httpx, "post", lambda *args, **kwargs: SuccessfulResponse())
    client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, token)

    response = client.post("/api/auth/logout")

    assert response.status_code == 200
    with session_scope() as session:
        row = session.query(RevokedAuthSessionORM).one()
        assert row.owner_id == user_id
        assert row.session_id_hash == auth_session_repository.hash_session_id("session-1")
        assert "session-1" not in row.session_id_hash

    client.cookies.clear()
    replay = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert replay.status_code == 401


def test_remote_logout_failure_is_silent_but_token_stays_revoked(client, monkeypatch):
    user_id = str(uuid.uuid4())
    settings_repository.onboard_user(user_id)
    token = _signed_token(user_id)

    class FailedResponse:
        is_success = False
        status_code = 503

    monkeypatch.setattr(auth_route.auth_service.httpx, "post", lambda *args, **kwargs: FailedResponse())
    client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, token)

    response = client.post("/api/auth/logout")
    client.cookies.clear()
    replay = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["status"] == "signed_out"
    assert replay.status_code == 401


def test_remote_logout_failure_cannot_refresh_the_revoked_session(client, monkeypatch):
    user_id = str(uuid.uuid4())
    settings_repository.onboard_user(user_id)
    token = _signed_token(user_id)
    auth_session_repository.revoke_session(
        user_id,
        "session-1",
        datetime.fromtimestamp(time.time() + 3600, tz=timezone.utc),
    )
    monkeypatch.setattr(settings, "supabase_url", "https://example.supabase.co", raising=False)
    monkeypatch.setattr(
        auth_service,
        "_request_supabase",
        lambda *_args, **_kwargs: {
            "access_token": token,
            "refresh_token": "rotated-refresh-token",
            "expires_in": 3600,
            "user": {"id": user_id, "email": "user@example.com"},
        },
    )
    client.cookies.set(REFRESH_TOKEN_COOKIE_NAME, "stolen-refresh-token")

    response = client.post("/api/auth/refresh")

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Could not validate credentials"
    set_cookie = "\n".join(response.headers.get_list("set-cookie"))
    assert f"{ACCESS_TOKEN_COOKIE_NAME}=" in set_cookie
    assert f"{REFRESH_TOKEN_COOKIE_NAME}=" in set_cookie


def test_local_revocation_failure_returns_503_and_clears_cookies(client, monkeypatch):
    monkeypatch.setattr(
        auth_route.auth_service,
        "logout",
        lambda _token: LogoutResult(False, False),
    )
    client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, "access-token")
    client.cookies.set(REFRESH_TOKEN_COOKIE_NAME, "refresh-token")

    response = client.post("/api/auth/logout")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "auth_revocation_unavailable"
    set_cookie = "\n".join(response.headers.get_list("set-cookie"))
    assert f"{ACCESS_TOKEN_COOKIE_NAME}=" in set_cookie
    assert f"{REFRESH_TOKEN_COOKIE_NAME}=" in set_cookie


def test_logout_revokes_only_the_current_session(client, monkeypatch):
    user_id = str(uuid.uuid4())
    settings_repository.onboard_user(user_id)
    first_token = _signed_token(user_id, session_id="session-1")
    second_token = _signed_token(user_id, session_id="session-2")

    class SuccessfulResponse:
        is_success = True
        status_code = 204

    monkeypatch.setattr(auth_route.auth_service.httpx, "post", lambda *args, **kwargs: SuccessfulResponse())
    client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, first_token)
    assert client.post("/api/auth/logout").status_code == 200

    client.cookies.clear()
    response = client.get("/protected", headers={"Authorization": f"Bearer {second_token}"})
    assert response.status_code == 200


def test_account_state_service_invalidates_positive_cache(monkeypatch):
    user_id = str(uuid.uuid4())
    settings_repository.onboard_user(user_id)
    monkeypatch.setattr(settings, "app_env", "development", raising=False)
    monkeypatch.setattr(auth_dependencies.user_cache, "_get_client", lambda: None)
    auth_dependencies.user_cache.reset_for_tests()
    asyncio.run(auth_dependencies.user_cache.mark_user_active(user_id))
    assert asyncio.run(auth_dependencies.user_cache.is_user_cached_active(user_id)) is True

    assert asyncio.run(account_state_service.set_user_active(user_id, False)) is True

    assert asyncio.run(auth_dependencies.user_cache.is_user_cached_active(user_id)) is False
    assert settings_repository.is_user_active(user_id) is False


def test_revocation_cleanup_keeps_unexpired_records():
    now = time.time()
    first_owner = str(uuid.uuid4())
    second_owner = str(uuid.uuid4())
    settings_repository.onboard_user(first_owner)
    settings_repository.onboard_user(second_owner)
    auth_session_repository.revoke_session(
        first_owner,
        "expired-session",
        datetime.fromtimestamp(now - 60, tz=timezone.utc),
    )
    auth_session_repository.revoke_session(
        second_owner,
        "active-session",
        datetime.fromtimestamp(now + 3600, tz=timezone.utc),
    )

    deleted = auth_session_repository.cleanup_expired(
        datetime.fromtimestamp(now, tz=timezone.utc)
    )

    assert deleted == 1
    assert auth_session_repository.is_session_revoked(second_owner, "active-session") is True


def test_session_rejects_missing_local_account(client, monkeypatch):
    user_id = str(uuid.uuid4())

    def decode(_token: str):
        return _jwt_payload(user_id, "new@example.com")

    monkeypatch.setattr(auth_dependencies, "decode_supabase_jwt", decode)
    client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, "valid-token")

    response = client.get("/api/auth/session")

    assert response.status_code == 401


def test_session_returns_401_without_auth(client):
    response = client.get("/api/auth/session")

    assert response.status_code == 401


def test_signup_rejects_invalid_email_and_short_password(client, monkeypatch):
    called = False

    def signup(*_args):
        nonlocal called
        called = True

    monkeypatch.setattr(auth_route.auth_service, "signup", signup)

    invalid_email = client.post(
        "/api/auth/signup",
        json={"email": "not-an-email", "password": "a-valid-password"},
    )
    short_password = client.post(
        "/api/auth/signup",
        json={"email": "user@example.com", "password": "short"},
    )

    assert invalid_email.status_code == 422
    assert short_password.status_code == 422
    assert called is False


def test_login_accepts_legacy_six_character_password(client, monkeypatch):
    result = AuthSessionResult(
        authenticated=True,
        user_id="user-1",
        email="user@example.com",
        access_token="access-token",
        refresh_token="refresh-token",
    )
    captured = {}

    def login(email, password):
        captured.update(email=str(email), password=password)
        return result

    monkeypatch.setattr(auth_route.auth_service, "login", login)
    response = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "secret"},
    )

    assert response.status_code == 200
    assert captured["password"] == "secret"


def test_protected_route_accepts_cookie_auth(client, monkeypatch):
    user_id = str(uuid.uuid4())
    settings_repository.onboard_user(user_id)

    def decode(_token: str):
        return _jwt_payload(user_id, "cookie@example.com")

    monkeypatch.setattr(auth_dependencies, "decode_supabase_jwt", decode)
    client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, "cookie-token")

    response = client.get("/protected")

    assert response.status_code == 200
    assert response.json()["id"] == user_id


def test_protected_route_falls_back_to_authorization_header(client, monkeypatch):
    user_id = str(uuid.uuid4())
    settings_repository.onboard_user(user_id)

    def decode(_token: str):
        return _jwt_payload(user_id, "header@example.com")

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

    monkeypatch.setattr(connection_manager.connection_pool, "diagnose_connection", fail_if_called)
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
    assert response.json()["error"]["code"] == "connection_target_blocked"


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
    from app.db.models.connection import ConnectionTestResult

    called = {"value": False}

    async def fake_test_connection(config):
        called["value"] = True
        return ConnectionTestResult(success=True, message="Connection successful", code="connection_healthy")

    monkeypatch.setattr(settings, "app_env", "development", raising=False)
    monkeypatch.setattr(settings, "db_connect_allow_private_in_dev", True, raising=False)
    monkeypatch.setattr(connection_manager, "enforce_connection_attempt_rate_limit", lambda owner_id: None)
    monkeypatch.setattr(connection_manager.connection_pool, "diagnose_connection", fake_test_connection)
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

@pytest.mark.parametrize("db_type", ["mysql", "sqlite", "mssql", "snowflake", ""])
def test_unsupported_database_test_returns_bad_request(client, monkeypatch, db_type):
    from app.core.db_connection_guardrails import UNSUPPORTED_DATABASE_MESSAGE
    from app.db import connection_manager

    monkeypatch.setattr(connection_manager, "enforce_connection_attempt_rate_limit", lambda owner_id: None)

    async def fail_if_called(config):
        raise AssertionError("connection pool should not be called for unsupported database types")

    monkeypatch.setattr(connection_manager.connection_pool, "diagnose_connection", fail_if_called)
    test_client = _connection_test_client(monkeypatch)

    response = test_client.post(
        "/api/database/test",
        json={
            "db_type": db_type,
            "host": "8.8.8.8",
            "port": 5432,
            "database": "demo",
            "username": "demo",
            "password": "secret",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "bad_request"
    assert body["error"]["message"] == UNSUPPORTED_DATABASE_MESSAGE


def test_unsupported_database_connect_does_not_open_connection(client, monkeypatch):
    from app.core.db_connection_guardrails import UNSUPPORTED_DATABASE_MESSAGE
    from app.db import connection_manager

    monkeypatch.setattr(connection_manager, "enforce_connection_attempt_rate_limit", lambda owner_id: None)

    def fail_if_called(config):
        raise AssertionError("open_connection should not be called for unsupported database types")

    monkeypatch.setattr(connection_manager.connection_pool, "open_connection", fail_if_called)
    test_client = _connection_test_client(monkeypatch)

    response = test_client.post(
        "/api/database/connect",
        json={
            "db_type": "mysql",
            "host": "8.8.8.8",
            "port": 3306,
            "database": "demo",
            "username": "demo",
            "password": "secret",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "bad_request"
    assert body["error"]["message"] == UNSUPPORTED_DATABASE_MESSAGE


def test_saved_connection_diagnostic_updates_persistent_health(client, monkeypatch):
    from cryptography.fernet import Fernet

    from app.core import config as core_config
    from app.core import secrets, security
    from app.db import connection_manager
    from app.db.models.connection import ConnectionRequest, ConnectionTestResult
    from app.db.repositories import connection_repository

    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))
    core_config.get_settings.cache_clear()
    secrets.settings = core_config.get_settings()
    security._cipher_suite = None

    owner_id = "00000000-0000-0000-0000-000000000001"
    connection_id = asyncio.run(
        connection_repository.create_connection(
            owner_id,
            ConnectionRequest(
                db_type="postgresql",
                host="127.0.0.1",
                port=5432,
                database="demo",
                username="demo",
                password="secret",
                name="Demo",
            ),
        )
    )

    monkeypatch.setattr(connection_manager, "enforce_connection_attempt_rate_limit", lambda owner_id: None)

    async def fake_test_connection(config):
        return ConnectionTestResult(
            success=False,
            message="Database authentication failed. Verify the connection credentials.",
            code="connection_auth_failed",
            category="authentication",
            latency_ms=12.0,
        )

    monkeypatch.setattr(connection_manager.connection_pool, "diagnose_connection", fake_test_connection)
    test_client = _connection_test_client(monkeypatch)

    response = test_client.post(f"/api/database/connections/{connection_id}/test")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["latency_ms"] is not None
    assert body["message"] == "Database authentication failed. Verify the connection credentials."

    row = asyncio.run(connection_repository.get_connection_row(owner_id, connection_id))
    assert row is not None
    assert row["last_status"] == "failed"
    assert row["last_error"] == "Database authentication failed. Verify the connection credentials."
    assert row["latency_ms"] is not None


def test_disabled_local_account_is_rejected(client, monkeypatch):
    user_id = str(uuid.uuid4())
    settings_repository.onboard_user(user_id)
    with session_scope() as session:
        row = session.get(UserSettingsORM, user_id)
        assert row is not None
        row.is_active = False

    monkeypatch.setattr(
        auth_dependencies,
        "decode_supabase_jwt",
        lambda _token: _jwt_payload(user_id, "disabled@example.com"),
    )
    client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, "valid-token")

    response = client.get("/protected")

    assert response.status_code == 401

def test_refresh_auth_failure_clears_cookies(client, monkeypatch):
    from app.api.v1.routes import auth as auth_route
    from app.services import auth as auth_service

    monkeypatch.setattr(
        auth_route.auth_service,
        "refresh_session",
        lambda _token: (_ for _ in ()).throw(auth_service.AuthServiceError("expired", status_code=401)),
    )
    client.cookies.set(REFRESH_TOKEN_COOKIE_NAME, "stale-refresh")

    response = client.post("/api/auth/refresh")

    assert response.status_code == 401
    set_cookie = "\n".join(response.headers.get_list("set-cookie"))
    assert f"{ACCESS_TOKEN_COOKIE_NAME}=" in set_cookie
    assert f"{REFRESH_TOKEN_COOKIE_NAME}=" in set_cookie
