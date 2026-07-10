"""Rate limiting for credential-based authentication endpoints."""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import time

from fastapi import Request
from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.errors import AppError, ServiceUnavailableError


logger = logging.getLogger(__name__)
_memory_rate_limits: dict[str, tuple[int, float]] = {}


class AuthRateLimitError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "Too many authentication attempts. Please wait and try again.",
            code="auth_rate_limited",
            status_code=429,
        )


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _trusted_proxy_networks() -> list[ipaddress._BaseNetwork]:
    return [ipaddress.ip_network(cidr, strict=False) for cidr in settings.trusted_proxy_cidrs]


def _parse_ip(value: str | None) -> ipaddress._BaseAddress | None:
    if not value:
        return None
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


def _client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    peer_ip = _parse_ip(peer)
    trusted_networks = _trusted_proxy_networks()
    if not peer_ip or not any(peer_ip in network for network in trusted_networks):
        return peer

    forwarded = request.headers.get("x-forwarded-for", "")
    forwarded_ip = _parse_ip(forwarded.split(",", maxsplit=1)[0])
    return str(forwarded_ip) if forwarded_ip else peer


def _keys(email: str, request: Request) -> tuple[str, str]:
    normalized_email = email.strip().casefold()
    client_ip = _client_ip(request)
    return (
        f"qm:auth-attempt:email:{_digest(normalized_email)}",
        f"qm:auth-attempt:ip:{_digest(client_ip)}",
    )


def _increment_memory(key: str, *, limit: int, window_seconds: int) -> None:
    now = time.monotonic()
    count, reset_at = _memory_rate_limits.get(key, (0, now + window_seconds))
    if now >= reset_at:
        count = 0
        reset_at = now + window_seconds
    count += 1
    _memory_rate_limits[key] = (count, reset_at)
    if count > limit:
        raise AuthRateLimitError()


def _increment_redis(client: Redis, key: str, *, limit: int, window_seconds: int) -> None:
    count = int(client.incr(key))
    if count == 1:
        client.expire(key, window_seconds)
    if count > limit:
        raise AuthRateLimitError()


def enforce_auth_attempt_rate_limit(request: Request, email: str) -> None:
    """Rate-limit by both normalized email and client address."""
    limit = settings.auth_rate_limit_attempts
    window_seconds = settings.auth_rate_limit_window_seconds
    if limit <= 0 or window_seconds <= 0:
        return

    keys = _keys(email, request)
    redis_url = settings.resolved_redis_url
    try:
        if not redis_url:
            raise RedisError("Redis URL is not configured.")
        client = Redis.from_url(redis_url, decode_responses=True)
        for key in keys:
            _increment_redis(client, key, limit=limit, window_seconds=window_seconds)
    except AuthRateLimitError:
        raise
    except Exception as exc:
        if settings.is_production:
            raise ServiceUnavailableError("Authentication rate limiting is temporarily unavailable.") from exc
        logger.warning("Falling back to in-memory authentication rate limiting: %s", exc)
        for key in keys:
            _increment_memory(key, limit=limit, window_seconds=window_seconds)


__all__ = ["AuthRateLimitError", "enforce_auth_attempt_rate_limit"]
