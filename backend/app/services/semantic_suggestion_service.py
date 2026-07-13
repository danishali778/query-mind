"""Durable optional AI-assisted semantic definition suggestions."""

from __future__ import annotations

from typing import Any

import anyio

from app.core.config import settings
from app.core.errors import BadRequestError, ConflictError, NotFoundError, ServiceUnavailableError
from app.db.models.semantic import SemanticKind, validate_safe_text
from app.db.repositories import semantic_repository
from app.db.session import read_session_scope, session_scope
from app.services import connection_service
from app.services.chat_progress import ensure_available


def snapshot(run) -> dict[str, Any]:
    payload = run.model_dump(mode="json")
    payload["candidates"] = payload.pop("candidates_json", [])
    return payload


async def start(
    *,
    owner_id: str,
    connection_id: str,
    client_request_id: str,
    requested_kinds: list[SemanticKind],
    business_context: str | None,
) -> dict[str, Any]:
    if not settings.semantic_layer_enabled or not settings.semantic_suggestions_enabled:
        raise ServiceUnavailableError(
            "Semantic suggestions are disabled.", code="semantic_suggestions_unavailable"
        )
    kinds = list(dict.fromkeys(requested_kinds))
    if not kinds:
        raise BadRequestError("Select at least one definition kind.")
    if business_context:
        business_context = validate_safe_text(
            business_context, field_name="business_context", max_length=2000
        )

    def find_existing():
        with read_session_scope() as session:
            return semantic_repository.get_suggestion_by_client_request_sync(
                session, owner_id, client_request_id
            )

    existing = await anyio.to_thread.run_sync(find_existing)
    if existing:
        if existing.connection_id != connection_id:
            raise ConflictError(
                "This request ID belongs to another connection.",
                code="semantic_suggestion_conflict",
            )
        return snapshot(existing)
    catalog = await connection_service.get_catalog(owner_id, connection_id)
    if not catalog:
        raise NotFoundError(
            "Database connection not found.", code="semantic_definition_not_found"
        )
    try:
        await anyio.to_thread.run_sync(ensure_available)
    except RuntimeError as exc:
        raise ServiceUnavailableError(
            "Semantic suggestion infrastructure is unavailable.",
            code="semantic_suggestions_unavailable",
        ) from exc

    def create():
        with session_scope() as session:
            return semantic_repository.create_suggestion_run_sync(
                session,
                owner_id=owner_id,
                connection_id=connection_id,
                client_request_id=client_request_id,
                schema_hash=catalog.schema_hash,
                requested_kinds=kinds,
                business_context=business_context,
            )

    try:
        run, created = await anyio.to_thread.run_sync(create)
    except semantic_repository.SemanticSuggestionConflictError as exc:
        raise ConflictError(str(exc), code="semantic_suggestion_conflict") from exc
    if created:
        try:
            from app.workers.jobs.suggest_semantics import suggest_semantics_task

            task = suggest_semantics_task.apply_async(
                args=[run.id], queue=settings.celery_semantics_queue
            )
            with session_scope() as session:
                semantic_repository.set_suggestion_task_id_sync(session, run.id, task.id)
        except Exception as exc:
            with session_scope() as session:
                semantic_repository.finalize_suggestion_run_sync(
                    session,
                    run.id,
                    status="failed",
                    failure_code="dispatch_failed",
                    failure_message="The suggestion worker could not be started.",
                )
            raise ServiceUnavailableError(
                "Semantic suggestion infrastructure is unavailable.",
                code="semantic_suggestions_unavailable",
            ) from exc
    return snapshot(await get(owner_id, connection_id, run.id))


async def get(owner_id: str, connection_id: str, run_id: str):
    def read():
        with read_session_scope() as session:
            return semantic_repository.get_suggestion_run_sync(
                session, owner_id, connection_id, run_id
            )

    run = await anyio.to_thread.run_sync(read)
    if not run:
        raise NotFoundError("Suggestion run not found.", code="semantic_definition_not_found")
    return run


async def cancel(owner_id: str, connection_id: str, run_id: str) -> dict[str, Any]:
    def write():
        with session_scope() as session:
            return semantic_repository.cancel_suggestion_run_sync(
                session, owner_id, connection_id, run_id
            )

    run = await anyio.to_thread.run_sync(write)
    if not run:
        raise NotFoundError("Suggestion run not found.", code="semantic_definition_not_found")
    return snapshot(run)


def load_verified_metadata_sync(owner_id: str, connection_id: str) -> list[dict[str, Any]]:
    with read_session_scope() as session:
        rows = semantic_repository.list_active_verified_sync(session, owner_id, connection_id)
        return [
            {
                "definition_id": definition.id,
                "kind": definition.kind,
                "key": definition.key,
                "display_name": version.display_name,
                "description": version.description,
                "version": version.version,
            }
            for definition, version in rows[: settings.semantic_context_max_definitions]
            if not (
                definition.kind == "table" and version.payload.get("visibility") == "hidden"
            )
            and not (
                definition.kind == "column"
                and version.payload.get("classification") == "restricted"
            )
        ]


__all__ = ["cancel", "get", "load_verified_metadata_sync", "snapshot", "start"]
