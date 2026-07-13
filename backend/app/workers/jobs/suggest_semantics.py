"""Celery job for optional AI-assisted semantic draft candidates."""

from __future__ import annotations

import asyncio
import functools
import logging

import anyio

from app.agents.schema_context.semantic_suggester import generate_semantic_candidates
from app.agents.schema_context.user_semantics import apply_semantic_catalog_overlay
from app.core.config import settings
from app.db.repositories import semantic_repository
from app.db.session import read_session_scope, session_scope
from app.services import connection_service, semantic_context_service
from app.services.semantic_suggestion_service import load_verified_metadata_sync
from app.workers.celery_app import celery_app


logger = logging.getLogger(__name__)


def _cancelled(run_id: str) -> bool:
    with read_session_scope() as session:
        return semantic_repository.suggestion_cancel_requested_sync(session, run_id)


async def _execute(run) -> list[dict]:
    catalog = await connection_service.get_catalog(run.owner_id, run.connection_id)
    if not catalog or catalog.schema_hash != run.schema_hash:
        raise RuntimeError("schema_changed")
    question = " ".join([*(run.requested_kinds or []), run.business_context or ""])
    semantic_context = await semantic_context_service.load_context(
        run.owner_id, run.connection_id, catalog, question
    )
    safe_catalog = apply_semantic_catalog_overlay(catalog, semantic_context)
    verified = await anyio.to_thread.run_sync(
        load_verified_metadata_sync, run.owner_id, run.connection_id
    )
    if _cancelled(run.id):
        return []
    candidates = await anyio.to_thread.run_sync(
        functools.partial(
            generate_semantic_candidates,
            catalog=safe_catalog,
            requested_kinds=run.requested_kinds,
            business_context=run.business_context,
            verified_definitions=verified,
            max_candidates=settings.semantic_suggestion_max_candidates,
        )
    )
    return candidates


@celery_app.task(
    bind=True,
    name="app.workers.jobs.suggest_semantics.suggest_semantics_task",
    queue=settings.celery_semantics_queue,
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=0,
)
def suggest_semantics_task(self, run_id: str) -> None:
    with session_scope() as session:
        run = semantic_repository.claim_suggestion_run_sync(session, run_id)
    if not run:
        return
    try:
        candidates = asyncio.run(_execute(run))
        if _cancelled(run_id):
            return
        with session_scope() as session:
            semantic_repository.finalize_suggestion_run_sync(
                session, run_id, status="completed", candidates=candidates
            )
    except Exception as exc:
        logger.exception("Semantic suggestion run failed run_id=%s", run_id)
        code = "schema_changed" if str(exc) == "schema_changed" else "suggestion_failed"
        message = (
            "The schema changed while suggestions were generated. Start a new suggestion run."
            if code == "schema_changed"
            else "Semantic suggestions could not be generated."
        )
        with session_scope() as session:
            semantic_repository.finalize_suggestion_run_sync(
                session,
                run_id,
                status="failed",
                failure_code=code,
                failure_message=message,
            )


__all__ = ["suggest_semantics_task"]
