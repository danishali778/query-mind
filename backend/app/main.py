import logging

from fastapi import FastAPI

from app.api.router import api_router
from app.api.v1.schemas.common import HealthResponse
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import configure_cors
from app.core.secrets import validate_core_credentials
from app.lifespan import lifespan
from app.services.chat_progress import ensure_available
from app.db.repositories import (
    chat_run_repository,
    dashboard_generation_repository,
    llm_credential_repository,
    semantic_repository,
    question_suggestion_repository,
)
from app.workers.celery_app import celery_app


configure_logging()
validate_core_credentials()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="query-mind API",
    description="Chat with your data - Text-to-SQL powered by AI",
    version="2.0.0",
    lifespan=lifespan,
)

origins = configure_cors(app, settings.allowed_origins, is_production=settings.is_production)
logger.info("[startup] CORS allowed origins: %s", origins)

register_exception_handlers(app)
app.include_router(api_router)


@app.get("/api/health", response_model=HealthResponse)
def health_check():
    return {"status": "ok", "service": "query-mind API", "version": "2.0.0"}


@app.get("/api/health/streaming")
def streaming_health_check():
    redis_status = "healthy"
    try:
        ensure_available()
    except RuntimeError:
        redis_status = "unavailable"
    interactive_worker_status = "unavailable"
    dashboard_worker_status = "unavailable"
    semantics_worker_status = "unavailable"
    suggestions_worker_status = "unavailable"
    try:
        queues = celery_app.control.inspect(timeout=0.75).active_queues() or {}
        if any(
            queue.get("name") == settings.celery_interactive_queue
            for worker_queues in queues.values()
            for queue in worker_queues
        ):
            interactive_worker_status = "healthy"
        if any(
            queue.get("name") == settings.celery_dashboards_queue
            for worker_queues in queues.values()
            for queue in worker_queues
        ):
            dashboard_worker_status = "healthy"
        if any(
            queue.get("name") == settings.celery_semantics_queue
            for worker_queues in queues.values()
            for queue in worker_queues
        ):
            semantics_worker_status = "healthy"
        if any(
            queue.get("name") == settings.celery_suggestions_queue
            for worker_queues in queues.values()
            for queue in worker_queues
        ):
            suggestions_worker_status = "healthy"
    except Exception:
        pass
    try:
        counts = chat_run_repository.run_health_counts(settings.agent_wall_clock_seconds + 30)
    except Exception:
        counts = {"active_runs": 0, "stale_runs": 0}
    try:
        dashboard_counts = dashboard_generation_repository.run_health_counts(
            stale_after_seconds=settings.agent_wall_clock_seconds + 30
        )
    except Exception:
        dashboard_counts = {"active_runs": 0, "stale_runs": 0}
    try:
        semantic_counts = semantic_repository.semantic_health_counts()
    except Exception:
        semantic_counts = {
            "active_verified_definitions": 0,
            "stale_definitions": 0,
            "invalid_definitions": 0,
            "failed_previews": 0,
            "suggestion_active_runs": 0,
            "suggestion_failed_runs": 0,
            "suggestion_failure_rate": 0.0,
            "suggestion_average_duration_seconds": 0.0,
        }
    try:
        from app.db.session import read_session_scope

        with read_session_scope() as session:
            suggestion_counts = question_suggestion_repository.health_counts_sync(
                session, settings.question_suggestions_stale_run_seconds
            )
    except Exception:
        suggestion_counts = {
            "question_suggestion_ready_sets": 0,
            "question_suggestion_queued_sets": 0,
            "question_suggestion_running_sets": 0,
            "question_suggestion_failed_sets": 0,
            "question_suggestion_stale_sets": 0,
        }
    try:
        llm_counts = llm_credential_repository.health_counts()
    except Exception:
        llm_counts = {
            "llm_valid_credentials": 0,
            "llm_invalid_credentials": 0,
            "llm_byok_invocations": 0,
            "llm_deployment_invocations": 0,
            "llm_trial_exhaustions": 0,
            "llm_provider_failure_rate": 0.0,
            "llm_average_latency_ms": 0.0,
        }
    dashboard_healthy = (
        not settings.dashboard_ai_enabled
        or (dashboard_worker_status == "healthy" and dashboard_counts["stale_runs"] == 0)
    )
    semantics_healthy = (
        not settings.semantic_suggestions_enabled
        or semantics_worker_status == "healthy"
    )
    suggestions_healthy = (
        not settings.question_suggestions_ai_enabled
        or suggestions_worker_status == "healthy"
    )
    healthy = (
        redis_status == "healthy"
        and interactive_worker_status == "healthy"
        and counts["stale_runs"] == 0
        and dashboard_healthy
        and semantics_healthy
        and suggestions_healthy
    )
    return {
        "status": "ok" if healthy else "degraded",
        "streaming_enabled": settings.chat_streaming_enabled,
        "redis": redis_status,
        "interactive_worker": interactive_worker_status,
        "interactive_queue": settings.celery_interactive_queue,
        "dashboard_worker": dashboard_worker_status,
        "dashboard_queue": settings.celery_dashboards_queue,
        "dashboard_active_runs": dashboard_counts["active_runs"],
        "dashboard_stale_runs": dashboard_counts["stale_runs"],
        "semantic_layer_enabled": settings.semantic_layer_enabled,
        "semantic_suggestions_enabled": settings.semantic_suggestions_enabled,
        "semantics_worker": semantics_worker_status,
        "semantics_queue": settings.celery_semantics_queue,
        "question_suggestions_enabled": settings.question_suggestions_enabled,
        "question_suggestions_ai_enabled": settings.question_suggestions_ai_enabled,
        "suggestions_worker": suggestions_worker_status,
        "suggestions_queue": settings.celery_suggestions_queue,
        "llm_credential_mode": settings.llm_credential_mode,
        "llm_enabled_providers": [
            provider for provider in ("gemini", "groq", "openai")
            if settings.llm_allowed_models[provider]
        ],
        "llm_deployment_fallback_available": bool(
            settings.deployment_llm_api_key(settings.resolved_llm_provider)
        ) and settings.llm_credential_mode != "byok_required",
        **llm_counts,
        **suggestion_counts,
        **semantic_counts,
        **counts,
    }


__all__ = ["app", "health_check", "streaming_health_check", "lifespan"]
