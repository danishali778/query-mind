from fastapi import APIRouter

from app.api.v1.routes import (
    analytics,
    auth,
    chat,
    connections,
    dashboards,
    query,
    query_history,
    query_library,
    settings,
    webhooks,
)


api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(connections.router)
api_router.include_router(query.router)
api_router.include_router(chat.router)
api_router.include_router(query_history.router)
api_router.include_router(query_library.router)
api_router.include_router(dashboards.router)
api_router.include_router(analytics.router)
api_router.include_router(settings.router)
api_router.include_router(webhooks.router, prefix="/api")

__all__ = ["api_router"]
