"""Persistence and guarded state transitions for durable chat agent runs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import anyio
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.chat import ChatAgentRun, ChatMessage
from app.db.orm_models import ChatAgentRunORM, ChatMessageORM, ChatSessionORM
from app.db.repositories.chat_repository import (
    _add_message_sync,
    _create_session_sync,
    _get_history_for_llm_sync,
    _get_latest_user_message_id_sync,
    _track_connection_sync,
)
from app.db.session import read_session_scope, session_scope


ACTIVE_STATUSES = ("queued", "running", "cancel_requested")
TERMINAL_STATUSES = ("completed", "failed", "cancelled")


class ActiveRunConflictError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else (str(value) if value else None)


def _assistant_id(session: Session, run_id: str) -> str | None:
    row = session.query(ChatMessageORM.id).filter(ChatMessageORM.agent_run_id == run_id).one_or_none()
    return row.id if row else None


def _map_run(session: Session, row: ChatAgentRunORM) -> ChatAgentRun:
    return ChatAgentRun(
        id=row.id,
        owner_id=row.owner_id,
        session_id=row.session_id,
        connection_id=row.connection_id,
        user_message_id=row.user_message_id,
        assistant_message_id=_assistant_id(session, row.id),
        client_request_id=row.client_request_id,
        celery_task_id=row.celery_task_id,
        status=row.status,
        current_stage=row.current_stage,
        current_stage_label=row.current_stage_label,
        failure_code=row.failure_code,
        failure_message=row.failure_message,
        created_at=_iso(row.created_at) or _now().isoformat(),
        started_at=_iso(row.started_at),
        heartbeat_at=_iso(row.heartbeat_at),
        cancel_requested_at=_iso(row.cancel_requested_at),
        finished_at=_iso(row.finished_at),
        updated_at=_iso(row.updated_at),
    )


def create_queued_run_sync(
    session: Session,
    *,
    user_id: str,
    connection_id: str,
    message: str,
    client_request_id: str,
    session_id: str | None,
) -> tuple[ChatAgentRun, ChatMessage, ChatMessage, list[dict], bool]:
    existing = (
        session.query(ChatAgentRunORM)
        .filter(
            ChatAgentRunORM.owner_id == user_id,
            ChatAgentRunORM.client_request_id == client_request_id,
        )
        .one_or_none()
    )
    if existing:
        user_row = session.query(ChatMessageORM).filter(ChatMessageORM.id == existing.user_message_id).one()
        assistant_row = session.query(ChatMessageORM).filter(ChatMessageORM.agent_run_id == existing.id).one()
        from app.db.repositories.chat_repository import _map_message

        return _map_run(session, existing), _map_message(user_row), _map_message(assistant_row, existing), [], False

    created_session = False
    if session_id:
        session_row = (
            session.query(ChatSessionORM)
            .filter(ChatSessionORM.id == session_id, ChatSessionORM.owner_id == user_id)
            .one_or_none()
        )
        if not session_row:
            raise ValueError("Session not found.")
    else:
        created = _create_session_sync(session, user_id, connection_id)
        session_id = created.id
        created_session = True

    active = (
        session.query(ChatAgentRunORM.id)
        .filter(ChatAgentRunORM.session_id == session_id, ChatAgentRunORM.status.in_(ACTIVE_STATUSES))
        .first()
    )
    if active:
        raise ActiveRunConflictError("This conversation already has an active response.")

    _track_connection_sync(session, user_id, session_id, connection_id)
    previous_user_id = _get_latest_user_message_id_sync(session, user_id, session_id)
    user_message = ChatMessage(
        role="user",
        content=message,
        connection_id=connection_id,
        prev_query_id=previous_user_id,
    )
    _add_message_sync(session, user_id, session_id, user_message)
    session.flush()
    history = _get_history_for_llm_sync(session, user_id, session_id)

    run_row = ChatAgentRunORM(
        id=str(uuid.uuid4()),
        owner_id=user_id,
        session_id=session_id,
        connection_id=connection_id,
        user_message_id=user_message.id,
        client_request_id=client_request_id,
        status="queued",
        current_stage="preparing",
        current_stage_label="Preparing your request",
    )
    session.add(run_row)
    session.flush()
    assistant_message = ChatMessage(
        role="assistant",
        content="",
        connection_id=connection_id,
        parent_id=user_message.id,
        agent_run_id=run_row.id,
        agent_run_status="queued",
        agent_run_stage="preparing",
        agent_run_stage_label="Preparing your request",
    )
    _add_message_sync(session, user_id, session_id, assistant_message)
    if created_session:
        title = message[:50].strip() + ("..." if len(message) > 50 else "")
        session.query(ChatSessionORM).filter(ChatSessionORM.id == session_id).update({"title": title})
    session.flush()
    return _map_run(session, run_row), user_message, assistant_message, history, True


async def create_queued_run(**kwargs) -> tuple[ChatAgentRun, ChatMessage, ChatMessage, list[dict], bool]:
    def _run():
        try:
            with session_scope() as session:
                return create_queued_run_sync(session, **kwargs)
        except IntegrityError as exc:
            user_id = kwargs["user_id"]
            client_request_id = kwargs["client_request_id"]
            with read_session_scope() as session:
                existing = session.query(ChatAgentRunORM).filter(
                    ChatAgentRunORM.owner_id == user_id,
                    ChatAgentRunORM.client_request_id == client_request_id,
                ).one_or_none()
                if existing:
                    user_row = session.query(ChatMessageORM).filter(ChatMessageORM.id == existing.user_message_id).one()
                    assistant_row = session.query(ChatMessageORM).filter(ChatMessageORM.agent_run_id == existing.id).one()
                    from app.db.repositories.chat_repository import _map_message

                    return _map_run(session, existing), _map_message(user_row), _map_message(assistant_row, existing), [], False
            raise ActiveRunConflictError("This conversation already has an active response.") from exc

    return await anyio.to_thread.run_sync(_run)


def get_run_sync(session: Session, user_id: str, run_id: str) -> ChatAgentRun | None:
    row = session.query(ChatAgentRunORM).filter(ChatAgentRunORM.id == run_id, ChatAgentRunORM.owner_id == user_id).one_or_none()
    return _map_run(session, row) if row else None


async def get_run(user_id: str, run_id: str) -> ChatAgentRun | None:
    def _run():
        with read_session_scope() as session:
            return get_run_sync(session, user_id, run_id)

    return await anyio.to_thread.run_sync(_run)


async def get_run_by_client_request(user_id: str, client_request_id: str) -> ChatAgentRun | None:
    def _run():
        with read_session_scope() as session:
            row = session.query(ChatAgentRunORM).filter(
                ChatAgentRunORM.owner_id == user_id,
                ChatAgentRunORM.client_request_id == client_request_id,
            ).one_or_none()
            return _map_run(session, row) if row else None

    return await anyio.to_thread.run_sync(_run)


def get_run_unscoped_sync(run_id: str) -> ChatAgentRun | None:
    with read_session_scope() as session:
        row = session.query(ChatAgentRunORM).filter(ChatAgentRunORM.id == run_id).one_or_none()
        return _map_run(session, row) if row else None


def set_task_id(run_id: str, task_id: str) -> None:
    with session_scope() as session:
        session.query(ChatAgentRunORM).filter(ChatAgentRunORM.id == run_id, ChatAgentRunORM.status == "queued").update(
            {"celery_task_id": task_id, "updated_at": _now()}, synchronize_session=False
        )


def claim_run(run_id: str) -> ChatAgentRun | None:
    with session_scope() as session:
        now = _now()
        changed = session.query(ChatAgentRunORM).filter(
            ChatAgentRunORM.id == run_id, ChatAgentRunORM.status == "queued"
        ).update(
            {"status": "running", "started_at": now, "heartbeat_at": now, "updated_at": now},
            synchronize_session=False,
        )
        if not changed:
            return None
        row = session.query(ChatAgentRunORM).filter(ChatAgentRunORM.id == run_id).one()
        return _map_run(session, row)


def update_stage(run_id: str, stage: str, label: str) -> bool:
    with session_scope() as session:
        now = _now()
        changed = session.query(ChatAgentRunORM).filter(
            ChatAgentRunORM.id == run_id, ChatAgentRunORM.status.in_(("running", "cancel_requested"))
        ).update(
            {"current_stage": stage, "current_stage_label": label, "heartbeat_at": now, "updated_at": now},
            synchronize_session=False,
        )
        return bool(changed)


def request_cancel(user_id: str, run_id: str) -> ChatAgentRun | None:
    with session_scope() as session:
        row = session.query(ChatAgentRunORM).filter(ChatAgentRunORM.id == run_id, ChatAgentRunORM.owner_id == user_id).one_or_none()
        if not row:
            return None
        if row.status in TERMINAL_STATUSES:
            return _map_run(session, row)
        now = _now()
        row.status = "cancel_requested"
        row.cancel_requested_at = row.cancel_requested_at or now
        row.current_stage_label = "Stopping response"
        row.updated_at = now
        session.flush()
        return _map_run(session, row)


def is_cancel_requested(run_id: str) -> bool:
    with read_session_scope() as session:
        status = session.query(ChatAgentRunORM.status).filter(ChatAgentRunORM.id == run_id).scalar()
        return status in ("cancel_requested", "cancelled")


def finalize_run(
    run_id: str,
    *,
    status: str,
    message_updates: dict | None = None,
    failure_code: str | None = None,
    failure_message: str | None = None,
) -> bool:
    if status not in TERMINAL_STATUSES:
        raise ValueError("Run final status must be terminal.")
    with session_scope() as session:
        row = session.query(ChatAgentRunORM).filter(ChatAgentRunORM.id == run_id).one_or_none()
        if not row or row.status in TERMINAL_STATUSES:
            return False
        if status == "completed" and row.status == "cancel_requested":
            return False
        now = _now()
        row.status = status
        row.current_stage = "completed" if status == "completed" else row.current_stage
        row.current_stage_label = {
            "completed": "Answer ready",
            "failed": "Response failed",
            "cancelled": "Response stopped",
        }[status]
        row.failure_code = failure_code
        row.failure_message = failure_message
        row.finished_at = now
        row.heartbeat_at = now
        row.updated_at = now
        if message_updates:
            message_row = session.query(ChatMessageORM).filter(ChatMessageORM.agent_run_id == run_id).one()
            for key, value in message_updates.items():
                if hasattr(message_row, key):
                    setattr(message_row, key, value)
        return True


def get_history_for_run(run_id: str) -> list[dict]:
    with read_session_scope() as session:
        run = session.query(ChatAgentRunORM).filter(ChatAgentRunORM.id == run_id).one()
        rows = session.query(ChatMessageORM).filter(
            ChatMessageORM.session_id == run.session_id,
            ChatMessageORM.owner_id == run.owner_id,
            ChatMessageORM.created_at <= session.query(ChatMessageORM.created_at).filter(ChatMessageORM.id == run.user_message_id).scalar_subquery(),
        ).order_by(ChatMessageORM.created_at.asc()).all()
        return [
            {"role": row.role, "content": f"{row.content}\n```sql\n{row.sql}\n```" if row.role == "assistant" and row.sql else row.content}
            for row in rows
            if row.content or row.role == "user"
        ]


def get_assistant_message(run_id: str) -> ChatMessage | None:
    from app.db.repositories.chat_repository import _map_message

    with read_session_scope() as session:
        run = session.query(ChatAgentRunORM).filter(ChatAgentRunORM.id == run_id).one_or_none()
        if not run:
            return None
        row = session.query(ChatMessageORM).filter(ChatMessageORM.agent_run_id == run_id).one_or_none()
        return _map_message(row, run) if row else None


def get_triggering_user_message(run_id: str) -> ChatMessage | None:
    from app.db.repositories.chat_repository import _map_message

    with read_session_scope() as session:
        run = session.query(ChatAgentRunORM).filter(ChatAgentRunORM.id == run_id).one_or_none()
        if not run:
            return None
        row = session.query(ChatMessageORM).filter(ChatMessageORM.id == run.user_message_id).one_or_none()
        return _map_message(row) if row else None


def active_run_count(user_id: str) -> int:
    with read_session_scope() as session:
        return int(session.query(func.count(ChatAgentRunORM.id)).filter(
            ChatAgentRunORM.owner_id == user_id, ChatAgentRunORM.status.in_(ACTIVE_STATUSES)
        ).scalar() or 0)


def run_health_counts(stale_after_seconds: int) -> dict[str, int]:
    with read_session_scope() as session:
        active = int(session.query(func.count(ChatAgentRunORM.id)).filter(
            ChatAgentRunORM.status.in_(ACTIVE_STATUSES)
        ).scalar() or 0)
        cutoff = _now() - timedelta(seconds=stale_after_seconds)
        stale = int(session.query(func.count(ChatAgentRunORM.id)).filter(
            ChatAgentRunORM.status.in_(("running", "cancel_requested")),
            ChatAgentRunORM.heartbeat_at < cutoff,
        ).scalar() or 0)
        return {"active_runs": active, "stale_runs": stale}


def fail_stale_runs(stale_after_seconds: int) -> list[str]:
    with session_scope() as session:
        cutoff = _now() - timedelta(seconds=stale_after_seconds)
        rows = session.query(ChatAgentRunORM).filter(
            ChatAgentRunORM.status.in_(("running", "cancel_requested")),
            ChatAgentRunORM.heartbeat_at < cutoff,
        ).all()
        now = _now()
        run_ids: list[str] = []
        for row in rows:
            row.status = "failed"
            row.failure_code = "worker_stale"
            row.failure_message = "The response worker stopped before completing this request."
            row.current_stage_label = "Response worker stopped"
            row.finished_at = now
            row.updated_at = now
            message = session.query(ChatMessageORM).filter(ChatMessageORM.agent_run_id == row.id).one_or_none()
            if message:
                message.error = row.failure_message
            run_ids.append(row.id)
        return run_ids


__all__ = [
    "ACTIVE_STATUSES", "TERMINAL_STATUSES", "ActiveRunConflictError", "create_queued_run",
    "get_run", "get_run_by_client_request", "get_run_unscoped_sync", "set_task_id", "claim_run", "update_stage",
    "request_cancel", "is_cancel_requested", "finalize_run", "get_history_for_run",
    "get_assistant_message", "get_triggering_user_message", "active_run_count", "run_health_counts", "fail_stale_runs",
]
