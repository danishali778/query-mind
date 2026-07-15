import asyncio
import time

import pytest
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from jose.exceptions import JWKError

from app.integrations.supabase_auth import dependencies as auth_dependencies


def _bare_request() -> Request:
    """Request with no cookies or headers, so only explicit credentials count."""
    return Request({"type": "http", "headers": []})


def test_authenticate_credentials_requires_token():
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(auth_dependencies.authenticate_credentials(_bare_request(), None))

    assert exc_info.value.status_code == 401


def test_authenticate_credentials_rejects_invalid_jwt(monkeypatch):
    def fake_decode(_: str):
        raise auth_dependencies.JWTError("bad token")

    monkeypatch.setattr(auth_dependencies, "decode_supabase_jwt", fake_decode)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(auth_dependencies.authenticate_credentials(_bare_request(), credentials))

    assert exc_info.value.status_code == 401


def test_authenticate_credentials_treats_jwk_errors_as_401(monkeypatch):
    def fake_decode(_: str):
        raise JWKError("key type mismatch")

    monkeypatch.setattr(auth_dependencies, "decode_supabase_jwt", fake_decode)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="crafted")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(auth_dependencies.authenticate_credentials(_bare_request(), credentials))

    assert exc_info.value.status_code == 401


def test_authenticate_credentials_rejects_missing_user(monkeypatch):
    async def fake_assert_user_exists(_: str):
        raise HTTPException(status_code=401, detail="User account has been deactivated or deleted.")

    monkeypatch.setattr(
        auth_dependencies,
        "decode_supabase_jwt",
        lambda _: {
            "sub": "user-1",
            "email": "user@example.com",
            "session_id": "session-1",
            "exp": int(time.time()) + 3600,
        },
    )
    monkeypatch.setattr(auth_dependencies.auth_service, "is_session_revoked", lambda *_args: False)
    monkeypatch.setattr(auth_dependencies, "assert_user_exists", fake_assert_user_exists)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(auth_dependencies.authenticate_credentials(_bare_request(), credentials))

    assert exc_info.value.status_code == 401
