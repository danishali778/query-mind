import os

os.environ.setdefault("ENCRYPTION_KEY", "TZZoA4e_0aRy3zO0u7FzjHwBq2L8y6b9R9oV8XmQ_Jw=")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "jwt-secret")
os.environ.setdefault("GROQ_API_KEY", "groq-test-key")
os.environ.setdefault("LEMON_SQUEEZY_WEBHOOK_SECRET", "webhook-secret")

import hmac
import hashlib

from fastapi.testclient import TestClient

from app.integrations.supabase_auth import get_current_user
from app.integrations.supabase_auth.dependencies import User
from app.main import app
from app.api.v1.routes import connections as connections_route
from app.api.v1.routes import webhooks as webhooks_route


app.dependency_overrides[get_current_user] = lambda: User(id="user-1", email="user@example.com")


def test_schema_route_sanitizes_internal_errors(monkeypatch):
    async def fail(*_args, **_kwargs):
        raise RuntimeError("password=secret host=db.example.com")

    monkeypatch.setattr(connections_route.connection_service, "refresh_schema", fail)
    client = TestClient(app)

    response = client.get("/api/database/connections/conn-1/schema")

    assert response.status_code == 503
    payload = response.json()
    assert payload["error"]["message"] == "Schema could not be loaded for this connection."
    assert "secret" not in response.text


def test_webhook_rejects_invalid_signature():
    client = TestClient(app)
    response = client.post(
        "/api/webhooks/lemonsqueezy",
        content=b'{"meta":{"event_name":"subscription_created"}}',
        headers={"X-Signature": "bad"},
    )

    assert response.status_code == 401


def test_webhook_upgrades_user_with_valid_signature(monkeypatch):
    upgraded = {}

    async def fake_upgrade(user_id: str):
        upgraded["user_id"] = user_id

    monkeypatch.setattr(webhooks_route, "upgrade_to_pro_async", fake_upgrade)
    monkeypatch.setattr(webhooks_route, "has_webhook_secret", lambda: True)
    monkeypatch.setattr(webhooks_route, "verify_webhook_signature", lambda _body, _sig: True)
    raw_body = b'{"meta":{"event_name":"subscription_created","custom_data":{"user_id":"user-1"}}}'
    client = TestClient(app)

    response = client.post(
        "/api/webhooks/lemonsqueezy",
        content=raw_body,
        headers={"X-Signature": "valid"},
    )

    assert response.status_code == 200
    assert upgraded["user_id"] == "user-1"
