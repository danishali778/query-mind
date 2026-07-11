import asyncio
import time

import pytest
from fastapi import HTTPException
from redis.exceptions import RedisError

from app.core.config import settings
from app.integrations.supabase_auth import dependencies as auth_dependencies
from app.integrations.supabase_auth import user_cache

_REAL_GET_CLIENT = user_cache._get_client


@pytest.fixture(autouse=True)
def memory_cache_only(monkeypatch):
    """Force the in-memory layer and a clean slate for every test."""
    monkeypatch.setattr(user_cache, "_get_client", lambda: None)
    monkeypatch.setattr(settings, "auth_user_cache_ttl_seconds", 60)
    user_cache.reset_for_tests()
    yield
    user_cache.reset_for_tests()


def _fail_session_scope(*_args, **_kwargs):
    raise AssertionError("database should not be touched on a cache hit")


def test_cached_user_skips_database(monkeypatch):
    user_cache.mark_user_active("user-1")
    monkeypatch.setattr(auth_dependencies, "session_scope", _fail_session_scope)

    asyncio.run(auth_dependencies.assert_user_exists("user-1"))


def test_negative_result_is_not_cached(monkeypatch):
    class _FakeSession:
        def get(self, *_args):
            return None

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(auth_dependencies, "session_scope", lambda: _FakeSession())

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(auth_dependencies.assert_user_exists("user-2"))

    assert exc_info.value.status_code == 401
    assert user_cache.is_user_cached_active("user-2") is False


def test_cache_entry_expires_after_ttl(monkeypatch):
    now = time.monotonic()
    user_cache.mark_user_active("user-3")

    monkeypatch.setattr(user_cache.time, "monotonic", lambda: now + 61)
    assert user_cache.is_user_cached_active("user-3") is False


def test_invalidate_drops_cached_user():
    user_cache.mark_user_active("user-4")
    assert user_cache.is_user_cached_active("user-4") is True

    user_cache.invalidate_user_cache("user-4")
    assert user_cache.is_user_cached_active("user-4") is False


def test_zero_ttl_disables_cache(monkeypatch):
    monkeypatch.setattr(settings, "auth_user_cache_ttl_seconds", 0)

    user_cache.mark_user_active("user-5")
    assert user_cache.is_user_cached_active("user-5") is False


def test_redis_failure_trips_circuit_breaker(monkeypatch):
    monkeypatch.setattr(user_cache, "_get_client", _REAL_GET_CLIENT)
    monkeypatch.setattr(settings, "redis_url", "redis://127.0.0.1:6399/0")

    class _FailingClient:
        def exists(self, _key):
            raise RedisError("connection refused")

    monkeypatch.setattr(user_cache, "_client", _FailingClient())

    # Failure falls back to memory and opens the breaker.
    assert user_cache.is_user_cached_active("user-6") is False
    # While the breaker is open, Redis is skipped entirely.
    assert user_cache._get_client() is None
    # The memory layer still works during the cooldown.
    user_cache.mark_user_active("user-6")
    assert user_cache.is_user_cached_active("user-6") is True
