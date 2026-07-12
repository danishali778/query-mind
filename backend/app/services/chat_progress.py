"""Durable, sanitized progress events for interactive chat runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.db.repositories import chat_run_repository
from app.query_engine.cancellation import AgentRunCancelled, QueryCancellationToken


PUBLIC_TOOL_LABELS = {
    "list_tables": ("schema_search", "Searching available tables"),
    "describe_table": ("schema_inspection", "Inspecting table structure"),
    "find_join_path": ("schema_inspection", "Finding relationships between tables"),
    "validate_sql": ("sql_validation", "Validating generated SQL"),
    "preview_sql": ("query_execution", "Previewing query results"),
    "execute_sql": ("query_execution", "Running a read-only query"),
    "profile_columns": ("reasoning", "Analyzing result patterns"),
    "get_column_stats": ("reasoning", "Analyzing result patterns"),
    "agent_repair": ("repair", "Correcting the query"),
    "backend_validation": ("sql_validation", "Validating generated SQL"),
    "backend_execution": ("query_execution", "Running a read-only query"),
}

TERMINAL_EVENTS = {"run.completed", "run.failed", "run.cancelled"}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@lru_cache(maxsize=1)
def _client() -> Redis:
    if not settings.resolved_redis_url:
        raise RuntimeError("Redis is required for durable chat streaming.")
    return Redis.from_url(
        settings.resolved_redis_url,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=max(2, settings.chat_run_heartbeat_seconds + 2),
    )


def ensure_available() -> None:
    try:
        if not _client().ping():
            raise RuntimeError("Redis did not respond.")
    except (RedisError, OSError) as exc:
        raise RuntimeError("Durable chat streaming is unavailable.") from exc


def _stream_key(run_id: str) -> str:
    return f"querymind:chat-run:{run_id}:events"


def _sequence_key(run_id: str) -> str:
    return f"querymind:chat-run:{run_id}:sequence"


def _cancel_key(run_id: str) -> str:
    return f"querymind:chat-run:{run_id}:cancel"


def publish_event(
    run_id: str,
    event_type: str,
    label: str,
    *,
    stage: str | None = None,
    duration_ms: float | None = None,
    outcome: str | None = None,
    retry_count: int | None = None,
    row_count: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        client = _client()
        sequence = int(client.incr(_sequence_key(run_id)))
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
        safe_metadata = {key: value for key, value in metadata.items() if key in {"message_id", "reason"}}
        event.setdefault("metadata", {}).update(safe_metadata)
    if client is not None:
        try:
            key = _stream_key(run_id)
            client.xadd(
                key,
                {"event": event_type, "data": json.dumps(event)},
                id=f"{sequence}-0",
                maxlen=settings.chat_run_event_maxlen,
            )
            client.expire(key, settings.chat_run_event_ttl_seconds)
            client.expire(_sequence_key(run_id), settings.chat_run_event_ttl_seconds)
        except RedisError:
            pass
    return event


def read_events(run_id: str, last_sequence: int, block_ms: int = 5000) -> list[tuple[str, dict]]:
    rows = _client().xread({_stream_key(run_id): f"{max(0, last_sequence)}-0"}, block=block_ms, count=50)
    events: list[tuple[str, dict]] = []
    for _, entries in rows:
        for redis_id, fields in entries:
            events.append((redis_id.split("-", 1)[0], json.loads(fields["data"])))
    return events


def signal_cancel(run_id: str) -> None:
    client = _client()
    client.set(_cancel_key(run_id), "1", ex=max(settings.agent_wall_clock_seconds * 2, 300))
    publish_event(run_id, "run.cancel_requested", "Stopping response")


def cancel_signalled(run_id: str) -> bool:
    try:
        return bool(_client().exists(_cancel_key(run_id)))
    except (RedisError, RuntimeError):
        return chat_run_repository.is_cancel_requested(run_id)


class ProgressReporter:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.cancellation_token = QueryCancellationToken()

    def check_cancelled(self) -> None:
        if cancel_signalled(self.run_id):
            self.cancellation_token.cancel()
            raise AgentRunCancelled("Chat run cancellation requested.")

    def stage_started(self, stage: str, label: str) -> None:
        self.check_cancelled()
        chat_run_repository.update_stage(self.run_id, stage, label)
        publish_event(self.run_id, "stage.started", label, stage=stage)

    def stage_completed(self, stage: str, label: str, *, duration_ms: float | None = None, row_count: int | None = None) -> None:
        publish_event(self.run_id, "stage.completed", label, stage=stage, duration_ms=duration_ms, row_count=row_count)
        self.check_cancelled()

    def tool_started(self, tool_name: str) -> None:
        stage, label = PUBLIC_TOOL_LABELS.get(tool_name, ("reasoning", "Analyzing your question"))
        self.stage_started(stage, label)
        publish_event(self.run_id, "tool.started", label, stage=stage)

    def tool_completed(self, step) -> None:
        stage, label = PUBLIC_TOOL_LABELS.get(step.tool, ("reasoning", "Analysis step completed"))
        publish_event(
            self.run_id,
            "tool.completed",
            label,
            stage=stage,
            duration_ms=step.duration_ms,
            outcome=step.outcome,
            retry_count=step.retry_count,
            row_count=step.output_row_count,
        )
        self.check_cancelled()

    def fallback(self, reason: str | None = None) -> None:
        chat_run_repository.update_stage(self.run_id, "fallback", "Switching to the reliable fallback pipeline")
        publish_event(
            self.run_id,
            "run.fallback",
            "Switching to the reliable fallback pipeline",
            stage="fallback",
            metadata={"reason": (reason or "agent_unavailable")[:80]},
        )


__all__ = [
    "AgentRunCancelled", "ProgressReporter", "TERMINAL_EVENTS", "ensure_available",
    "publish_event", "read_events", "signal_cancel", "cancel_signalled",
]
