import pytest

from app.core.errors import ServiceUnavailableError
from app.db.models.settings import UserSubscription
from app.services import billing_service


def _subscription(**overrides):
    data = {
        "owner_id": "user-1",
        "plan_type": "free",
        "queries_used": 0,
        "queries_limit": 100,
        "ai_used": 0,
        "ai_limit": 30,
        "next_reset_date": "soon",
    }
    data.update(overrides)
    return UserSubscription(**data)


def test_increment_usage_returns_false_when_limit_reached(monkeypatch):
    monkeypatch.setattr(
        billing_service,
        "get_user_subscription",
        lambda _: _subscription(queries_used=100, queries_limit=100),
    )

    assert billing_service.increment_usage("user-1", "query") is False


def test_increment_usage_raises_when_billing_state_unavailable(monkeypatch):
    monkeypatch.setattr(
        billing_service.settings_repository,
        "get_user_subscription",
        lambda _: (_ for _ in ()).throw(RuntimeError("down")),
    )

    with pytest.raises(ServiceUnavailableError, match="Billing information"):
        billing_service.get_user_subscription("user-1")


def test_increment_usage_raises_when_usage_update_fails(monkeypatch):
    monkeypatch.setattr(
        billing_service,
        "get_user_subscription",
        lambda _: _subscription(),
    )

    def fail(*_args, **_kwargs):
        raise RuntimeError("down")

    monkeypatch.setattr(billing_service.settings_repository, "increment_usage", fail)

    with pytest.raises(ServiceUnavailableError, match="Usage enforcement"):
        billing_service.increment_usage("user-1", "query")
