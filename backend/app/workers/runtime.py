from __future__ import annotations

from redis import Redis

from app.core.config import settings


def get_redis_client() -> Redis | None:
    redis_url = settings.resolved_redis_url
    if not redis_url:
        return None
    return Redis.from_url(redis_url, decode_responses=True)


def acquire_dispatch_lock(lock_key: str, ttl_seconds: int | None = None) -> bool:
    client = get_redis_client()
    if client is None:
        return True
    ttl = ttl_seconds or settings.celery_dispatch_lock_seconds
    return bool(client.set(lock_key, "1", nx=True, ex=ttl))


def release_dispatch_lock(lock_key: str) -> None:
    client = get_redis_client()
    if client is None:
        return
    client.delete(lock_key)

