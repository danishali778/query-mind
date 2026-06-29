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
