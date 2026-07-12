"""Celery task: plan an AI dashboard."""

from __future__ import annotations

import asyncio
import logging

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="plan_dashboard_task", bind=True, max_retries=0)
def plan_dashboard_task(self, run_id: str) -> None:
    from app.services import dashboard_generation_service

    logger.info("Planning dashboard run_id=%s task_id=%s", run_id, self.request.id)
    asyncio.run(dashboard_generation_service.execute_planning(run_id))
