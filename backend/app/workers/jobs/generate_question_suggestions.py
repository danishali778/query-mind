"""Celery job for cached schema-aware question enrichment."""

from __future__ import annotations

import asyncio
import logging

import anyio

from app.agents.question_suggestions.deterministic import generate_deterministic_bundle
from app.agents.question_suggestions.generator import generate_ai_bundle
from app.core.config import settings
from app.db.repositories import question_suggestion_repository
from app.db.session import session_scope
from app.services.question_suggestion_service import build_current_context
from app.workers.celery_app import celery_app


logger = logging.getLogger(__name__)


async def _execute(run):
    context = await build_current_context(run.owner_id, run.connection_id)
    if context.context_fingerprint != run.context_fingerprint:
        return None
    deterministic = generate_deterministic_bundle(context)
    if not settings.question_suggestions_ai_enabled:
        return deterministic
    return await anyio.to_thread.run_sync(
        lambda: generate_ai_bundle(
            context=context,
            deterministic=deterministic,
            max_per_surface=settings.question_suggestions_max_per_surface,
        )
    )


@celery_app.task(
    bind=True,
    name="app.workers.jobs.generate_question_suggestions.generate_question_suggestions_task",
    queue=settings.celery_suggestions_queue,
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=0,
)
def generate_question_suggestions_task(
    self, set_id: str, generation_revision: int
) -> None:
    with session_scope() as session:
        run = question_suggestion_repository.claim_sync(
            session, set_id, generation_revision, self.request.id
        )
    if run is None:
        return
    try:
        suggestions = asyncio.run(_execute(run))
        if suggestions is None:
            with session_scope() as session:
                question_suggestion_repository.finalize_sync(
                    session,
                    set_id=set_id,
                    generation_revision=generation_revision,
                    context_fingerprint=run.context_fingerprint,
                    status="failed",
                    failure_code="question_suggestion_stale",
                    failure_message="The schema changed while suggestions were personalized.",
                )
            return
        with session_scope() as session:
            question_suggestion_repository.finalize_sync(
                session,
                set_id=set_id,
                generation_revision=generation_revision,
                context_fingerprint=run.context_fingerprint,
                status="ready",
                suggestions=suggestions,
            )
    except Exception:
        logger.warning(
            "Question suggestion generation failed set_id=%s revision=%s code=%s",
            set_id,
            generation_revision,
            "question_suggestion_generation_failed",
        )
        with session_scope() as session:
            question_suggestion_repository.finalize_sync(
                session,
                set_id=set_id,
                generation_revision=generation_revision,
                context_fingerprint=run.context_fingerprint,
                status="failed",
                failure_code="question_suggestion_generation_failed",
                failure_message="Suggestions could not be personalized. Safe suggestions remain available.",
            )


__all__ = ["generate_question_suggestions_task"]
