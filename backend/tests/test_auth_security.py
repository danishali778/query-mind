import ipaddress
import base64
import json
import time

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt

from app.core import auth_rate_limit
from app.core.config import Settings, settings
from app.core.errors import ServiceUnavailableError
from app.core.middleware import configure_cors
from app.core.supabase_auth import ACCESS_TOKEN_COOKIE_NAME, REFRESH_TOKEN_COOKIE_NAME
from app.integrations.supabase_auth import jwt as jwt_module
from app.services import auth as auth_service


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes(32, byteorder="big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _public_ec_jwk() -> dict[str, str]:
    numbers = ec.generate_private_key(ec.SECP256R1()).public_key().public_numbers()
    return {
        "kty": "EC",
        "crv": "P-256",
        "x": _b64url_uint(numbers.x),
        "y": _b64url_uint(numbers.y),
    }


def _request(*, peer: str = "203.0.113.10", forwarded_for: str | None = None) -> Request:
    headers = []
    if forwarded_for:
        headers.append((b"x-forwarded-for", forwarded_for.encode("ascii")))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/auth/login",
            "headers": headers,
            "client": (peer, 12345),
        }
    )


def test_production_security_configuration_rejects_dev_auth():
    candidate = Settings(
        app_env="production",
        allowed_origins_raw="https://app.example.com",
        supabase_jwt_secret="secret",
        backend_dev_mode=True,
    )

    with pytest.raises(RuntimeError, match="BACKEND_DEV_MODE"):
        candidate.validate_security_configuration()


def test_production_security_configuration_rejects_loopback_origin():
    candidate = Settings(
        app_env="production",
        allowed_origins_raw="https://app.example.com,http://localhost:5173",
        supabase_jwt_secret="secret",
        auth_cookie_secure=True,
    )

    with pytest.raises(RuntimeError, match="HTTPS origins"):
        candidate.validate_security_configuration()


def test_jwt_validation_supplies_expected_issuer(monkeypatch):
    captured: dict[str, object] = {}
    monkeypatch.setattr(settings, "supabase_url", "https://project.supabase.co", raising=False)
    monkeypatch.setattr(settings, "supabase_jwt_secret", "secret", raising=False)

    def decode(_token, _key, **kwargs):
        captured.update(kwargs)
        return {
            "sub": "user-1",
            "session_id": "session-1",
            "exp": int(time.time()) + 3600,
            "aud": "authenticated",
            "iss": "https://project.supabase.co/auth/v1",
        }

    monkeypatch.setattr(jwt_module.jwt, "decode", decode)

    assert jwt_module.decode_supabase_jwt("token")["sub"] == "user-1"
    assert captured["issuer"] == "https://project.supabase.co/auth/v1"
    assert captured["audience"] == "authenticated"
    assert captured["algorithms"] == ["HS256"]


def test_jwt_algorithm_is_derived_from_ec_jwk(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", json.dumps(_public_ec_jwk()), raising=False)

    _key, algorithm = jwt_module.get_jwt_verification_config()

    assert algorithm == "ES256"
    jwt_module.validate_jwt_configuration()


def test_ec_jwk_rejects_hs256_token_before_verification(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "https://project.supabase.co", raising=False)
    monkeypatch.setattr(settings, "supabase_jwt_secret", json.dumps(_public_ec_jwk()), raising=False)
    token = jose_jwt.encode(
        {
            "sub": "user-1",
            "session_id": "session-1",
            "exp": int(time.time()) + 3600,
            "aud": "authenticated",
            "iss": "https://project.supabase.co/auth/v1",
        },
        "attacker-secret",
        algorithm="HS256",
    )

    with pytest.raises(jwt_module.JWTError):
        jwt_module.decode_supabase_jwt(token)


@pytest.mark.parametrize(
    "value",
    [
        "-----BEGIN PUBLIC KEY-----\nnot-a-shared-secret\n-----END PUBLIC KEY-----",
        '{"kty":"EC",',
        "[]",
        json.dumps({"kty": "RSA", "n": "x", "e": "AQAB"}),
        json.dumps({**_public_ec_jwk(), "d": "private"}),
    ],
)
def test_invalid_server_verification_material_is_rejected(monkeypatch, value):
    monkeypatch.setattr(settings, "supabase_jwt_secret", value, raising=False)

    with pytest.raises(jwt_module.JwtConfigurationError):
        jwt_module.validate_jwt_configuration()


def test_unrepresentable_expiration_claim_is_rejected():
    with pytest.raises(jwt_module.JWTError):
        jwt_module.claims_from_payload(
            {
                "sub": "user-1",
                "session_id": "session-1",
                "exp": 10**100,
            }
        )


def test_password_configuration_rejects_minimum_above_maximum():
    candidate = Settings(
        auth_signup_password_min_length=128,
        auth_password_max_length=64,
    )

    with pytest.raises(RuntimeError, match="cannot exceed"):
        candidate.validate_security_configuration()


def test_cookie_origin_middleware_allows_configured_origin_and_bearer_clients():
    app = FastAPI()
    configure_cors(app, ["https://app.example.com"], is_production=True)

    @app.post("/protected")
    def protected():
        return {"ok": True}

    client = TestClient(app)
    client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, "cookie-token")
    allowed = client.post("/protected", headers={"Origin": "https://app.example.com"})
    rejected = client.post("/protected", headers={"Origin": "https://evil.example.com"})
    client.cookies.clear()
    bearer = client.post("/protected", headers={"Authorization": "Bearer api-token"})

    assert allowed.status_code == 200
    assert rejected.status_code == 403
    assert rejected.json()["error"]["code"] == "csrf_origin_invalid"
    assert bearer.status_code == 200


def test_auth_rate_limit_uses_memory_fallback_in_development(monkeypatch):
    auth_rate_limit._memory_rate_limits.clear()
    monkeypatch.setattr(settings, "app_env", "development", raising=False)
    monkeypatch.setattr(settings, "redis_url", None, raising=False)
    monkeypatch.setattr(settings, "celery_broker_url", None, raising=False)
    monkeypatch.setattr(settings, "auth_rate_limit_attempts", 2, raising=False)
    monkeypatch.setattr(settings, "auth_rate_limit_window_seconds", 60, raising=False)

    request = _request()
    auth_rate_limit.enforce_auth_attempt_rate_limit(request, "user@example.com")
    auth_rate_limit.enforce_auth_attempt_rate_limit(request, "user@example.com")
    with pytest.raises(auth_rate_limit.AuthRateLimitError):
        auth_rate_limit.enforce_auth_attempt_rate_limit(request, "user@example.com")


def test_auth_rate_limit_fails_closed_in_production(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production", raising=False)
    monkeypatch.setattr(settings, "redis_url", None, raising=False)
    monkeypatch.setattr(settings, "celery_broker_url", None, raising=False)

    with pytest.raises(ServiceUnavailableError):
        auth_rate_limit.enforce_auth_attempt_rate_limit(_request(), "user@example.com")


def test_auth_rate_limit_trusts_forwarded_ip_only_from_configured_proxy(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_cidrs_raw", "10.0.0.0/8", raising=False)
    request = _request(peer="10.1.2.3", forwarded_for="198.51.100.20, 10.1.2.3")
    untrusted = _request(peer="192.0.2.10", forwarded_for="198.51.100.20")

    assert auth_rate_limit._client_ip(request) == "198.51.100.20"
    assert auth_rate_limit._client_ip(untrusted) == "192.0.2.10"
    assert ipaddress.ip_address(auth_rate_limit._client_ip(request)).is_global is False


def test_logout_reports_remote_revocation_failure(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "https://project.supabase.co", raising=False)
    monkeypatch.setattr(settings, "supabase_anon_key", "test-anon-key", raising=False)

    class FailedResponse:
        is_success = False
        status_code = 503

    monkeypatch.setattr(auth_service.httpx, "post", lambda *args, **kwargs: FailedResponse())
    monkeypatch.setattr(
        auth_service,
        "decode_supabase_jwt",
        lambda _token: {
            "sub": "00000000-0000-0000-0000-000000000001",
            "session_id": "session-1",
            "exp": int(time.time()) + 3600,
        },
    )
    monkeypatch.setattr(
        auth_service.auth_session_repository,
        "revoke_session",
        lambda *_args: "a" * 64,
    )

    result = auth_service.logout("access-token")
    assert result.local_revocation_confirmed is True
    assert result.remote_revocation_confirmed is False

