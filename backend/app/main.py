import logging

from fastapi import FastAPI

from app.api.router import api_router
from app.api.v1.schemas.common import HealthResponse
from app.core.config import ALLOWED_ORIGINS
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import configure_cors
from app.core.secrets import validate_core_credentials
from app.lifespan import lifespan


configure_logging()
validate_core_credentials()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="query-mind API",
    description="Chat with your data - Text-to-SQL powered by AI",
    version="2.0.0",
    lifespan=lifespan,
)

origins = configure_cors(app, ALLOWED_ORIGINS)
logger.info("[startup] CORS allowed origins: %s", origins)

register_exception_handlers(app)
app.include_router(api_router)


@app.get("/api/health", response_model=HealthResponse)
def health_check():
    return {"status": "ok", "service": "query-mind API", "version": "2.0.0"}


__all__ = ["app", "health_check", "lifespan"]
