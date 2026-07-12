"""Transport-only Redis Stream helpers for durable run progress."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@lru_cache(maxsize=1)
def redis_client() -> Redis:
    if not settings.resolved_redis_url:
        raise RuntimeError("Redis is required for durable run streaming.")
    return Redis.from_url(
        settings.resolved_redis_url,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=max(2, settings.chat_run_heartbeat_seconds + 2),
    )


def ensure_stream_available() -> None:
    try:
        if not redis_client().ping():
            raise RuntimeError("Redis did not respond.")
    except (RedisError, OSError) as exc:
        raise RuntimeError("Durable run streaming is unavailable.") from exc


def stream_key(namespace: str, run_id: str) -> str:
    return f"querymind:{namespace}:{run_id}:events"


def sequence_key(namespace: str, run_id: str) -> str:
    return f"querymind:{namespace}:{run_id}:sequence"


def cancel_key(namespace: str, run_id: str) -> str:
    return f"querymind:{namespace}:{run_id}:cancel"


def publish_typed_event(
    *,
    namespace: str,
    run_id: str,
    event_type: str,
    label: str,
    maxlen: int,
    ttl_seconds: int,
    stage: str | None = None,
    duration_ms: float | None = None,
    outcome: str | None = None,
    retry_count: int | None = None,
    row_count: int | None = None,
    metadata: dict[str, Any] | None = None,
    allowed_metadata_keys: set[str] | None = None,
) -> dict[str, Any]:
    try:
        client = redis_client()
        sequence = int(client.incr(sequence_key(namespace, run_id)))
    except (RedisError, RuntimeError):
        sequence = 0
        client = None

    event: dict[str, Any] = {
        "version": 1,
        "run_id": run_id,
        "sequence": sequence,
        "type": event_type,
        "label": label[:200],
        "occurred_at": _utcnow(),
    }
    if stage:
        event["stage"] = stage
    if duration_ms is not None:
        event["duration_ms"] = round(float(duration_ms), 2)
    if outcome:
        event["outcome"] = outcome
    if retry_count is not None:
        event["retry_count"] = retry_count
    if row_count is not None:
        event["metadata"] = {"row_count": int(row_count)}
    if metadata:
        allowed = allowed_metadata_keys or set()
        safe_metadata = {key: value for key, value in metadata.items() if key in allowed}
        if safe_metadata:
            event.setdefault("metadata", {}).update(safe_metadata)

    if client is not None:
        try:
            key = stream_key(namespace, run_id)
            client.xadd(
                key,
                {"event": event_type, "data": json.dumps(event)},
                id=f"{sequence}-0",
                maxlen=maxlen,
            )
            client.expire(key, ttl_seconds)
            client.expire(sequence_key(namespace, run_id), ttl_seconds)
        except RedisError:
            pass
    return event


def read_typed_events(
    *,
    namespace: str,
    run_id: str,
    last_sequence: int,
    block_ms: int = 5000,
) -> list[tuple[str, dict]]:
    rows = redis_client().xread(
        {stream_key(namespace, run_id): f"{max(0, last_sequence)}-0"},
        block=block_ms,
        count=50,
    )
    events: list[tuple[str, dict]] = []
    for _, entries in rows:
        for redis_id, fields in entries:
            events.append((redis_id.split("-", 1)[0], json.loads(fields["data"])))
    return events


def signal_typed_cancel(*, namespace: str, run_id: str, ttl_seconds: int) -> None:
    client = redis_client()
    client.set(cancel_key(namespace, run_id), "1", ex=ttl_seconds)


def cancel_typed_signalled(*, namespace: str, run_id: str) -> bool:
    try:
        return bool(redis_client().exists(cancel_key(namespace, run_id)))
    except (RedisError, RuntimeError):
        return False


__all__ = [
    "ensure_stream_available",
    "publish_typed_event",
    "read_typed_events",
    "signal_typed_cancel",
    "cancel_typed_signalled",
    "redis_client",
]
