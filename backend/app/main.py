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
from app.db.repositories import chat_run_repository
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
    worker_status = "unavailable"
    try:
        queues = celery_app.control.inspect(timeout=0.75).active_queues() or {}
        if any(
            queue.get("name") == settings.celery_interactive_queue
            for worker_queues in queues.values()
            for queue in worker_queues
        ):
            worker_status = "healthy"
    except Exception:
        pass
    try:
        counts = chat_run_repository.run_health_counts(settings.agent_wall_clock_seconds + 30)
    except Exception:
        counts = {"active_runs": 0, "stale_runs": 0}
    healthy = redis_status == "healthy" and worker_status == "healthy" and counts["stale_runs"] == 0
    return {
        "status": "ok" if healthy else "degraded",
        "streaming_enabled": settings.chat_streaming_enabled,
        "redis": redis_status,
        "interactive_worker": worker_status,
        "interactive_queue": settings.celery_interactive_queue,
        **counts,
    }


__all__ = ["app", "health_check", "streaming_health_check", "lifespan"]
