"""Application service for durable interactive chat runs."""

from __future__ import annotations

import asyncio
import json

import anyio
from redis.exceptions import RedisError

from app.core.config import settings
from app.db.repositories import chat_run_repository
from app.services.chat_progress import ensure_available, publish_event, read_events, signal_cancel


class StreamingUnavailableError(RuntimeError):
    pass


class RunLimitError(RuntimeError):
    pass


def _accepted(run) -> dict:
    return {
        "run_id": run.id,
        "session_id": run.session_id,
        "user_message_id": run.user_message_id,
        "assistant_message_id": run.assistant_message_id or "",
        "status": run.status,
        "events_url": f"/api/chat/runs/{run.id}/events",
    }


async def start_run(user_id: str, request) -> dict:
    if not settings.chat_streaming_enabled:
        raise StreamingUnavailableError("Durable chat streaming is disabled.")
    existing = await chat_run_repository.get_run_by_client_request(user_id, request.client_request_id)
    if existing:
        return _accepted(existing)
    active_count = await anyio.to_thread.run_sync(chat_run_repository.active_run_count, user_id)
    if active_count >= settings.chat_run_max_active_per_user:
        raise RunLimitError("Too many active responses. Wait for an existing response to finish.")
    try:
        await anyio.to_thread.run_sync(ensure_available)
    except RuntimeError as exc:
        raise StreamingUnavailableError(str(exc)) from exc

    run, _, _, _, created = await chat_run_repository.create_queued_run(
        user_id=user_id,
        connection_id=request.connection_id,
        message=request.message,
        client_request_id=request.client_request_id,
        session_id=request.session_id,
    )
    if not created:
        return _accepted(run)

    await anyio.to_thread.run_sync(
        lambda: publish_event(run.id, "run.queued", "Response queued", stage="preparing")
    )
    try:
        from app.workers.jobs.run_chat_agent import run_chat_agent_task

        task = run_chat_agent_task.apply_async(args=[run.id], queue=settings.celery_interactive_queue)
        chat_run_repository.set_task_id(run.id, task.id)
    except Exception as exc:
        chat_run_repository.finalize_run(
            run.id,
            status="failed",
            failure_code="dispatch_failed",
            failure_message="The response worker could not be started.",
            message_updates={"error": "The response worker could not be started."},
        )
        publish_event(run.id, "run.failed", "Response worker unavailable")
        raise StreamingUnavailableError("The response worker could not be started.") from exc
    refreshed = await chat_run_repository.get_run(user_id, run.id)
    return _accepted(refreshed or run)


def _chat_response(run, message, user_message=None) -> dict | None:
    if run.status != "completed" or not message:
        return None
    results = message.results or {}
    return {
        "session_id": run.session_id,
        "message_id": message.id,
        "user_message_id": run.user_message_id,
        "message": message.content,
        "sql": message.sql,
        "columns": message.columns,
        "rows": results.get("rows", []),
        "row_count": results.get("row_count", 0),
        "truncated": results.get("truncated", False),
        "execution_time_ms": results.get("execution_time_ms", 0.0),
        "chart_recommendation": message.chart_recommendation,
        "error": message.error,
        "column_metadata": results.get("column_metadata", {}),
        "is_pinned": message.is_pinned,
        "prev_query_id": user_message.prev_query_id if user_message else None,
        "agent_trace": message.agent_trace,
        "agent_tier": message.agent_tier,
    }


async def get_snapshot(user_id: str, run_id: str) -> dict | None:
    run = await chat_run_repository.get_run(user_id, run_id)
    if not run:
        return None
    message = await anyio.to_thread.run_sync(chat_run_repository.get_assistant_message, run_id)
    user_message = await anyio.to_thread.run_sync(chat_run_repository.get_triggering_user_message, run_id)
    return {
        "run_id": run.id,
        "session_id": run.session_id,
        "user_message_id": run.user_message_id,
        "assistant_message_id": run.assistant_message_id,
        "status": run.status,
        "current_stage": run.current_stage,
        "current_stage_label": run.current_stage_label,
        "failure_code": run.failure_code,
        "failure_message": run.failure_message,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "heartbeat_at": run.heartbeat_at,
        "cancel_requested_at": run.cancel_requested_at,
        "finished_at": run.finished_at,
        "response": _chat_response(run, message, user_message),
    }


async def cancel_run(user_id: str, run_id: str) -> dict | None:
    run = await anyio.to_thread.run_sync(chat_run_repository.request_cancel, user_id, run_id)
    if not run:
        return None
    if run.status == "cancel_requested":
        try:
            await anyio.to_thread.run_sync(signal_cancel, run_id)
        except RedisError:
            pass
        if not run.started_at:
            chat_run_repository.finalize_run(
                run_id,
                status="cancelled",
                failure_code="cancelled_by_user",
                failure_message="Response stopped by user.",
                message_updates={"error": "Response stopped by user."},
            )
            try:
                publish_event(run_id, "run.cancelled", "Response stopped")
            except RedisError:
                pass
    return await get_snapshot(user_id, run_id)


def _sse(event_type: str, data: dict, event_id: str | None = None) -> str:
    prefix = f"id: {event_id}\n" if event_id else ""
    return f"{prefix}event: {event_type}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


async def stream_events(user_id: str, run_id: str, last_sequence: int = 0):
    run = await chat_run_repository.get_run(user_id, run_id)
    if not run:
        return
    sequence = max(0, last_sequence)
    quiet_cycles = 0
    while True:
        try:
            events = await anyio.to_thread.run_sync(read_events, run_id, sequence, 5000)
        except (RedisError, RuntimeError):
            events = []
        if events:
            quiet_cycles = 0
            for event_id, event in events:
                sequence = max(sequence, int(event_id))
                yield _sse(event["type"], event, event_id)
                if event["type"] in {"run.completed", "run.failed", "run.cancelled"}:
                    return
        else:
            quiet_cycles += 1
            snapshot = await get_snapshot(user_id, run_id)
            if not snapshot:
                return
            if snapshot["status"] in {"completed", "failed", "cancelled"}:
                event_type = f"run.{snapshot['status']}"
                yield _sse(event_type, {"version": 1, "run_id": run_id, "type": event_type, "label": snapshot["current_stage_label"]})
                return
            if quiet_cycles % 3 == 0:
                yield _sse("heartbeat", {"run_id": run_id, "type": "heartbeat"})
        await asyncio.sleep(0)


__all__ = [
    "StreamingUnavailableError", "RunLimitError", "start_run", "get_snapshot", "cancel_run", "stream_events",
]
