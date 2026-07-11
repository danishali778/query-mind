"""Short-TTL cache for the per-request user existence check.

Every authenticated request verifies that the user still exists and is
active. That verification costs a full database session (multiple network
round-trips to the app database), so positive results are cached briefly:
in Redis when configured (shared across processes), in process memory
otherwise. Only positive results are cached — a missing or inactive user
is always re-verified against the database.

Redis access is guarded by tight socket timeouts and a short circuit
breaker: after a Redis failure, Redis is skipped entirely for a cooldown
period so an unavailable Redis degrades to the memory cache instead of
adding connection-failure latency to every request.

If an account-deactivation path is ever added, it must call
``invalidate_user_cache`` so revocation takes effect immediately instead
of after the TTL expires.
"""

from __future__ import annotations

import logging
import threading
import time

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings


logger = logging.getLogger(__name__)

_KEY_PREFIX = "qm:auth-user-active:"
_SOCKET_TIMEOUT_SECONDS = 0.25
_REDIS_RETRY_COOLDOWN_SECONDS = 30.0

_memory_cache: dict[str, float] = {}
_client: Redis | None = None
_client_lock = threading.Lock()
_redis_down_until = 0.0


def _get_client() -> Redis | None:
    """Return a shared Redis client, or None when unconfigured/cooling down."""
    global _client
    redis_url = settings.resolved_redis_url
    if not redis_url:
        return None
    if time.monotonic() < _redis_down_until:
        return None
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = Redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=_SOCKET_TIMEOUT_SECONDS,
                    socket_timeout=_SOCKET_TIMEOUT_SECONDS,
                )
    return _client


def _mark_redis_down(exc: RedisError) -> None:
    global _redis_down_until
    _redis_down_until = time.monotonic() + _REDIS_RETRY_COOLDOWN_SECONDS
    logger.warning(
        "Auth user cache: Redis unavailable, using memory fallback for %.0fs: %s",
        _REDIS_RETRY_COOLDOWN_SECONDS,
        exc,
    )


def is_user_cached_active(user_id: str) -> bool:
    """Return True when a recent positive check exists for this user."""
    ttl = settings.auth_user_cache_ttl_seconds
    if ttl <= 0:
        return False

    client = _get_client()
    if client is not None:
        try:
            return client.exists(_KEY_PREFIX + user_id) == 1
        except RedisError as exc:
            _mark_redis_down(exc)

    expires_at = _memory_cache.get(user_id)
    return expires_at is not None and time.monotonic() < expires_at


def mark_user_active(user_id: str) -> None:
    """Record a positive existence check for the configured TTL."""
    ttl = settings.auth_user_cache_ttl_seconds
    if ttl <= 0:
        return

    client = _get_client()
    if client is not None:
        try:
            client.set(_KEY_PREFIX + user_id, "1", ex=ttl)
            return
        except RedisError as exc:
            _mark_redis_down(exc)

    _memory_cache[user_id] = time.monotonic() + ttl


def invalidate_user_cache(user_id: str) -> None:
    """Drop a cached positive check (call on deactivation/deletion)."""
    _memory_cache.pop(user_id, None)
    client = _get_client()
    if client is not None:
        try:
            client.delete(_KEY_PREFIX + user_id)
        except RedisError as exc:
            _mark_redis_down(exc)


def reset_for_tests() -> None:
    """Clear cache state and the Redis circuit breaker (memory layer only)."""
    global _client, _redis_down_until
    _memory_cache.clear()
    _client = None
    _redis_down_until = 0.0


__all__ = [
    "is_user_cached_active",
    "mark_user_active",
    "invalidate_user_cache",
    "reset_for_tests",
]
