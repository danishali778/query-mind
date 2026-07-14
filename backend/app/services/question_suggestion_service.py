"""Business workflows for schema-aware question discovery."""

from __future__ import annotations

import functools
from typing import Any

import anyio

from app.agents.question_suggestions import (
    SuggestionGenerationContext,
    build_generation_context,
    generate_deterministic_bundle,
)
from app.core.config import settings
from app.core.errors import AppError, ConflictError, NotFoundError, ServiceUnavailableError
from app.db.models.question_suggestions import (
    DEFAULT_SURFACE_LIMITS,
    QuestionSuggestion,
    SuggestionSetRecord,
    SuggestionSurface,
)
from app.db.repositories import (
    connection_repository,
    question_suggestion_repository,
    semantic_repository,
)
from app.db.session import read_session_scope, session_scope
from app.services import connection_service
from app.services.chat_progress import ensure_available


async def build_current_context(
    owner_id: str, connection_id: str
) -> SuggestionGenerationContext:
    catalog = await connection_service.get_catalog(owner_id, connection_id)
    if catalog is None:
        raise NotFoundError(
            "Database connection not found.", code="question_suggestions_not_found"
        )

    def load_metadata():
        with read_session_scope() as session:
            scope = connection_repository.get_scope_sync(session, owner_id, connection_id)
            if scope is None:
                return None
            rows = semantic_repository.list_active_verified_sync(
                session, owner_id, connection_id
            )
            return scope, rows

    metadata = await anyio.to_thread.run_sync(load_metadata)
    if metadata is None:
        raise NotFoundError(
            "Database connection not found.", code="question_suggestions_not_found"
        )
    scope, rows = metadata
    return build_generation_context(
        catalog=catalog,
        scope_revision=int(scope["revision"]),
        rows=rows,
        max_characters=settings.question_suggestions_max_context_characters,
    )


def _filter_surface(
    record: SuggestionSetRecord | None,
    fallback: dict[str, list[dict]],
    surface: SuggestionSurface,
    limit: int,
) -> list[dict]:
    source = record.suggestions_json if record else fallback
    dismissed = set(record.dismissed_ids if record else [])
    validated: list[dict] = []
    for raw in source.get(surface, []):
        if raw.get("id") in dismissed:
            continue
        try:
            item = QuestionSuggestion.model_validate(raw)
        except ValueError:
            continue
        if item.surface == surface:
            validated.append(item.model_dump(mode="json"))
        if len(validated) >= limit:
            break
    return validated


def _response(
    *,
    connection_id: str,
    context: SuggestionGenerationContext,
    fallback: dict[str, list[dict]],
    surface: SuggestionSurface,
    limit: int,
    record: SuggestionSetRecord | None,
) -> dict[str, Any]:
    matching = record if record and record.context_fingerprint == context.context_fingerprint else None
    if not settings.question_suggestions_enabled:
        status = "disabled"
    elif matching is None or not settings.question_suggestions_ai_enabled:
        status = "fallback"
    else:
        status = matching.status
    failure = None
    if matching and matching.failure_code:
        failure = {
            "code": matching.failure_code,
            "message": matching.failure_message or "Suggestions could not be personalized.",
        }
    return {
        "connection_id": connection_id,
        "surface": surface,
        "status": status,
        "context_fingerprint": context.context_fingerprint,
        "schema_hash": context.schema_hash,
        "suggestions": (
            []
            if status == "disabled"
            else _filter_surface(matching, fallback, surface, limit)
        ),
        "refresh_required": bool(
            status == "fallback"
            and settings.question_suggestions_ai_enabled
            and settings.question_suggestions_enabled
        ),
        "ai_available": bool(
            settings.question_suggestions_enabled
            and settings.question_suggestions_ai_enabled
        ),
        "generated_at": matching.completed_at if matching and matching.status == "ready" else None,
        "failure": failure,
    }


async def get(
    owner_id: str,
    connection_id: str,
    surface: SuggestionSurface,
    limit: int | None = None,
) -> dict[str, Any]:
    context = await build_current_context(owner_id, connection_id)
    fallback = generate_deterministic_bundle(context)
    effective_limit = min(
        limit or DEFAULT_SURFACE_LIMITS[surface],
        settings.question_suggestions_max_per_surface,
    )

    def read():
        with read_session_scope() as session:
            return question_suggestion_repository.get_sync(
                session, owner_id, connection_id
            )

    record = await anyio.to_thread.run_sync(read)
    return _response(
        connection_id=connection_id,
        context=context,
        fallback=fallback,
        surface=surface,
        limit=effective_limit,
        record=record,
    )


async def refresh(
    *,
    owner_id: str,
    connection_id: str,
    surface: SuggestionSurface,
    client_request_id: str,
    expected_context_fingerprint: str,
    force: bool,
    limit: int | None = None,
) -> dict[str, Any]:
    context = await build_current_context(owner_id, connection_id)
    if expected_context_fingerprint != context.context_fingerprint:
        raise ConflictError(
            "The schema or semantic context changed. Reload suggestions and try again.",
            code="question_suggestion_context_changed",
        )
    fallback = generate_deterministic_bundle(context)
    if not settings.question_suggestions_enabled or not settings.question_suggestions_ai_enabled:
        return _response(
            connection_id=connection_id,
            context=context,
            fallback=fallback,
            surface=surface,
            limit=limit or DEFAULT_SURFACE_LIMITS[surface],
            record=None,
        )
    if force:
        from app.services import llm_credential_service

        await anyio.to_thread.run_sync(
            lambda: llm_credential_service.preflight(
                owner_id,
                "question_suggestions",
                interaction_type="explicit",
            )
        )
    try:
        await anyio.to_thread.run_sync(ensure_available)
    except RuntimeError as exc:
        raise ServiceUnavailableError(
            "AI suggestion enrichment is temporarily unavailable.",
            code="question_suggestions_ai_unavailable",
        ) from exc

    def begin():
        with session_scope() as session:
            return question_suggestion_repository.begin_generation_sync(
                session,
                owner_id=owner_id,
                connection_id=connection_id,
                schema_hash=context.schema_hash,
                semantic_fingerprint=context.semantic_fingerprint,
                context_fingerprint=context.context_fingerprint,
                semantic_version_ids=context.semantic_version_ids,
                deterministic_suggestions=fallback,
                client_request_id=client_request_id,
                force=force,
                cooldown_seconds=settings.question_suggestions_refresh_cooldown_seconds,
            )

    try:
        record, should_dispatch = await anyio.to_thread.run_sync(begin)
    except question_suggestion_repository.SuggestionRefreshRateLimitedError as exc:
        raise AppError(
            str(exc),
            code="question_suggestion_refresh_rate_limited",
            status_code=429,
        ) from exc
    if should_dispatch:
        try:
            from app.workers.jobs.generate_question_suggestions import (
                generate_question_suggestions_task,
            )

            task = generate_question_suggestions_task.apply_async(
                args=[
                    record.id,
                    record.generation_revision,
                    "explicit" if force else "automatic",
                ],
                queue=settings.celery_suggestions_queue,
            )

            def save_task_id():
                with session_scope() as session:
                    question_suggestion_repository.set_task_id_sync(
                        session, record.id, record.generation_revision, task.id
                    )

            await anyio.to_thread.run_sync(save_task_id)
        except Exception as exc:
            def fail_dispatch():
                with session_scope() as session:
                    question_suggestion_repository.finalize_sync(
                        session,
                        set_id=record.id,
                        generation_revision=record.generation_revision,
                        context_fingerprint=record.context_fingerprint,
                        status="failed",
                        failure_code="question_suggestions_ai_unavailable",
                        failure_message="The suggestion worker could not be started.",
                    )

            await anyio.to_thread.run_sync(fail_dispatch)
            raise ServiceUnavailableError(
                "AI suggestion enrichment is temporarily unavailable.",
                code="question_suggestions_ai_unavailable",
            ) from exc
    return await get(owner_id, connection_id, surface, limit)


async def dismiss(
    *,
    owner_id: str,
    connection_id: str,
    suggestion_id: str,
    expected_context_fingerprint: str,
    surface: SuggestionSurface,
    limit: int | None = None,
) -> dict[str, Any]:
    context = await build_current_context(owner_id, connection_id)
    if context.context_fingerprint != expected_context_fingerprint:
        raise ConflictError(
            "The schema or semantic context changed. Reload suggestions and try again.",
            code="question_suggestion_context_changed",
        )

    def write():
        with session_scope() as session:
            question_suggestion_repository.ensure_fallback_sync(
                session,
                owner_id=owner_id,
                connection_id=connection_id,
                schema_hash=context.schema_hash,
                semantic_fingerprint=context.semantic_fingerprint,
                context_fingerprint=context.context_fingerprint,
                semantic_version_ids=context.semantic_version_ids,
                deterministic_suggestions=generate_deterministic_bundle(context),
            )
            return question_suggestion_repository.dismiss_sync(
                session,
                owner_id=owner_id,
                connection_id=connection_id,
                context_fingerprint=context.context_fingerprint,
                suggestion_id=suggestion_id,
            )

    result = await anyio.to_thread.run_sync(write)
    if result is None:
        raise NotFoundError(
            "Suggestion not found.", code="question_suggestions_not_found"
        )
    return await get(owner_id, connection_id, surface, limit)


__all__ = ["build_current_context", "dismiss", "get", "refresh"]
