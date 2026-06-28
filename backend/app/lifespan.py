import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    from app.services.connection_service import seed_dev_connection

    logger.info("[startup] Lifespan started.")
    try:
        logger.info("[startup] Seeding dev connection...")
        await seed_dev_connection()
        logger.info("[startup] Seeding dev connection DONE.")
    except Exception as exc:
        logger.error("[startup] ERROR during lifespan: %s", exc, exc_info=True)

    yield

    logger.info("[startup] Shutting down.")
