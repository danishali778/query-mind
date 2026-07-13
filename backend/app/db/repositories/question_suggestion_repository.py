"""Owner-scoped persistence for durable question suggestion sets."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.question_suggestions import SuggestionSetRecord
from app.db.orm_models import QuestionSuggestionSetORM


class SuggestionRefreshRateLimitedError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _record(row: QuestionSuggestionSetORM) -> SuggestionSetRecord:
    return SuggestionSetRecord(
        id=row.id,
        owner_id=row.owner_id,
        connection_id=row.connection_id,
        schema_hash=row.schema_hash,
        semantic_fingerprint=row.semantic_fingerprint,
        context_fingerprint=row.context_fingerprint,
        semantic_version_ids=list(row.semantic_version_ids or []),
        generation_revision=row.generation_revision,
        status=row.status,
        suggestions_json=dict(row.suggestions_json or {}),
        dismissed_ids=list(row.dismissed_ids or []),
        client_request_id=row.client_request_id,
        celery_task_id=row.celery_task_id,
        failure_code=row.failure_code,
        failure_message=row.failure_message,
        created_at=row.created_at,
        updated_at=row.updated_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


def get_sync(
    session: Session, owner_id: str, connection_id: str, *, for_update: bool = False
) -> SuggestionSetRecord | None:
    query = session.query(QuestionSuggestionSetORM).filter(
        QuestionSuggestionSetORM.owner_id == owner_id,
        QuestionSuggestionSetORM.connection_id == connection_id,
    )
    if for_update:
        query = query.with_for_update()
    row = query.one_or_none()
    return _record(row) if row else None


def begin_generation_sync(
    session: Session,
    *,
    owner_id: str,
    connection_id: str,
    schema_hash: str,
    semantic_fingerprint: str,
    context_fingerprint: str,
    semantic_version_ids: list[str],
    deterministic_suggestions: dict[str, list[dict]],
    client_request_id: str,
    force: bool,
    cooldown_seconds: int,
) -> tuple[SuggestionSetRecord, bool]:
    now = _now()
    row = (
        session.query(QuestionSuggestionSetORM)
        .filter(
            QuestionSuggestionSetORM.owner_id == owner_id,
            QuestionSuggestionSetORM.connection_id == connection_id,
        )
        .with_for_update()
        .one_or_none()
    )
    if row is not None:
        same_context = row.context_fingerprint == context_fingerprint
        if same_context and row.status in {"queued", "running"}:
            return _record(row), False
        if same_context and str(row.client_request_id or "") == str(client_request_id):
            return _record(row), False
        if (
            same_context
            and not force
            and row.status in {"ready", "failed"}
            and row.client_request_id is not None
        ):
            return _record(row), False
        if (
            same_context
            and force
            and row.updated_at
            and row.updated_at > now - timedelta(seconds=cooldown_seconds)
        ):
            raise SuggestionRefreshRateLimitedError(
                "Suggestions can be refreshed once per minute for this connection."
            )
        row.generation_revision += 1
        if not same_context:
            row.dismissed_ids = []
        row.schema_hash = schema_hash
        row.semantic_fingerprint = semantic_fingerprint
        row.context_fingerprint = context_fingerprint
        row.semantic_version_ids = semantic_version_ids
        row.status = "queued"
        row.suggestions_json = deterministic_suggestions
        row.client_request_id = client_request_id
        row.celery_task_id = None
        row.failure_code = None
        row.failure_message = None
        row.started_at = None
        row.completed_at = None
        row.updated_at = now
    else:
        row = QuestionSuggestionSetORM(
            id=str(uuid.uuid4()),
            owner_id=owner_id,
            connection_id=connection_id,
            schema_hash=schema_hash,
            semantic_fingerprint=semantic_fingerprint,
            context_fingerprint=context_fingerprint,
            semantic_version_ids=semantic_version_ids,
            generation_revision=1,
            status="queued",
            suggestions_json=deterministic_suggestions,
            dismissed_ids=[],
            client_request_id=client_request_id,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    session.flush()
    return _record(row), True


def set_task_id_sync(
    session: Session, set_id: str, generation_revision: int, task_id: str
) -> bool:
    changed = (
        session.query(QuestionSuggestionSetORM)
        .filter(
            QuestionSuggestionSetORM.id == set_id,
            QuestionSuggestionSetORM.generation_revision == generation_revision,
            QuestionSuggestionSetORM.status.in_(("queued", "running")),
        )
        .update(
            {QuestionSuggestionSetORM.celery_task_id: task_id},
            synchronize_session=False,
        )
    )
    return bool(changed)


def claim_sync(
    session: Session, set_id: str, generation_revision: int, task_id: str | None = None
) -> SuggestionSetRecord | None:
    row = (
        session.query(QuestionSuggestionSetORM)
        .filter(
            QuestionSuggestionSetORM.id == set_id,
            QuestionSuggestionSetORM.generation_revision == generation_revision,
            QuestionSuggestionSetORM.status.in_(("queued", "running")),
        )
        .with_for_update()
        .one_or_none()
    )
    if row is None or (
        row.status == "running"
        and (not task_id or str(row.celery_task_id or "") != str(task_id))
    ):
        return None
    row.status = "running"
    row.started_at = _now()
    row.updated_at = row.started_at
    session.flush()
    return _record(row)


def ensure_fallback_sync(
    session: Session,
    *,
    owner_id: str,
    connection_id: str,
    schema_hash: str,
    semantic_fingerprint: str,
    context_fingerprint: str,
    semantic_version_ids: list[str],
    deterministic_suggestions: dict[str, list[dict]],
) -> SuggestionSetRecord:
    """Persist deterministic suggestions only for a state-changing action such as dismiss."""
    now = _now()
    row = (
        session.query(QuestionSuggestionSetORM)
        .filter(
            QuestionSuggestionSetORM.owner_id == owner_id,
            QuestionSuggestionSetORM.connection_id == connection_id,
        )
        .with_for_update()
        .one_or_none()
    )
    if row and row.context_fingerprint == context_fingerprint:
        return _record(row)
    if row is None:
        row = QuestionSuggestionSetORM(
            id=str(uuid.uuid4()), owner_id=owner_id, connection_id=connection_id,
            generation_revision=1, created_at=now,
        )
        session.add(row)
    else:
        row.generation_revision += 1
    row.schema_hash = schema_hash
    row.semantic_fingerprint = semantic_fingerprint
    row.context_fingerprint = context_fingerprint
    row.semantic_version_ids = semantic_version_ids
    row.status = "ready"
    row.suggestions_json = deterministic_suggestions
    row.dismissed_ids = []
    row.client_request_id = None
    row.celery_task_id = None
    row.failure_code = None
    row.failure_message = None
    row.started_at = None
    row.completed_at = now
    row.updated_at = now
    session.flush()
    return _record(row)


def finalize_sync(
    session: Session,
    *,
    set_id: str,
    generation_revision: int,
    context_fingerprint: str,
    status: str,
    suggestions: dict[str, list[dict]] | None = None,
    failure_code: str | None = None,
    failure_message: str | None = None,
) -> bool:
    values = {
        QuestionSuggestionSetORM.status: status,
        QuestionSuggestionSetORM.failure_code: failure_code,
        QuestionSuggestionSetORM.failure_message: failure_message,
        QuestionSuggestionSetORM.completed_at: _now(),
        QuestionSuggestionSetORM.updated_at: _now(),
    }
    if suggestions is not None:
        values[QuestionSuggestionSetORM.suggestions_json] = suggestions
    changed = (
        session.query(QuestionSuggestionSetORM)
        .filter(
            QuestionSuggestionSetORM.id == set_id,
            QuestionSuggestionSetORM.generation_revision == generation_revision,
            QuestionSuggestionSetORM.context_fingerprint == context_fingerprint,
            QuestionSuggestionSetORM.status.in_(("queued", "running")),
        )
        .update(values, synchronize_session=False)
    )
    return bool(changed)


def dismiss_sync(
    session: Session,
    *,
    owner_id: str,
    connection_id: str,
    context_fingerprint: str,
    suggestion_id: str,
) -> SuggestionSetRecord | None:
    row = (
        session.query(QuestionSuggestionSetORM)
        .filter(
            QuestionSuggestionSetORM.owner_id == owner_id,
            QuestionSuggestionSetORM.connection_id == connection_id,
        )
        .with_for_update()
        .one_or_none()
    )
    if row is None or row.context_fingerprint != context_fingerprint:
        return None
    available = {
        str(item.get("id"))
        for items in (row.suggestions_json or {}).values()
        for item in items
        if isinstance(item, dict)
    }
    if suggestion_id not in available:
        return None
    dismissed = list(row.dismissed_ids or [])
    if suggestion_id not in dismissed:
        dismissed.append(suggestion_id)
        row.dismissed_ids = dismissed
        row.updated_at = _now()
        session.flush()
    return _record(row)


def fail_stale_sync(session: Session, stale_after_seconds: int) -> int:
    cutoff = _now() - timedelta(seconds=stale_after_seconds)
    return (
        session.query(QuestionSuggestionSetORM)
        .filter(
            QuestionSuggestionSetORM.status.in_(("queued", "running")),
            QuestionSuggestionSetORM.updated_at < cutoff,
        )
        .update(
            {
                QuestionSuggestionSetORM.status: "failed",
                QuestionSuggestionSetORM.failure_code: "question_suggestion_generation_failed",
                QuestionSuggestionSetORM.failure_message: "Suggestion personalization timed out.",
                QuestionSuggestionSetORM.completed_at: _now(),
                QuestionSuggestionSetORM.updated_at: _now(),
            },
            synchronize_session=False,
        )
    )


def health_counts_sync(session: Session, stale_after_seconds: int) -> dict[str, int]:
    cutoff = _now() - timedelta(seconds=stale_after_seconds)
    counts = dict(
        session.query(QuestionSuggestionSetORM.status, func.count(QuestionSuggestionSetORM.id))
        .group_by(QuestionSuggestionSetORM.status)
        .all()
    )
    stale = (
        session.query(func.count(QuestionSuggestionSetORM.id))
        .filter(
            QuestionSuggestionSetORM.status.in_(("queued", "running")),
            QuestionSuggestionSetORM.updated_at < cutoff,
        )
        .scalar()
        or 0
    )
    return {
        "question_suggestion_ready_sets": int(counts.get("ready", 0)),
        "question_suggestion_queued_sets": int(counts.get("queued", 0)),
        "question_suggestion_running_sets": int(counts.get("running", 0)),
        "question_suggestion_failed_sets": int(counts.get("failed", 0)),
        "question_suggestion_stale_sets": int(stale),
    }


__all__ = [
    "SuggestionRefreshRateLimitedError",
    "begin_generation_sync",
    "claim_sync",
    "dismiss_sync",
    "ensure_fallback_sync",
    "fail_stale_sync",
    "finalize_sync",
    "get_sync",
    "health_counts_sync",
    "set_task_id_sync",
]
