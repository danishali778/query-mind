"""Celery tasks: execute / regenerate AI dashboard widgets."""

from __future__ import annotations

import asyncio
import logging

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="execute_dashboard_generation_task", bind=True, max_retries=0)
def execute_dashboard_generation_task(self, run_id: str) -> None:
    from app.services import dashboard_generation_service

    logger.info("Executing dashboard generation run_id=%s task_id=%s", run_id, self.request.id)
    asyncio.run(dashboard_generation_service.execute_run(run_id))


@celery_app.task(name="regenerate_dashboard_widget_task", bind=True, max_retries=0)
def regenerate_dashboard_widget_task(self, run_id: str, item_id: str, instruction: str | None = None) -> None:
    from app.services import dashboard_generation_service

    logger.info(
        "Regenerating dashboard widget run_id=%s item_id=%s task_id=%s",
        run_id,
        item_id,
        self.request.id,
    )
    asyncio.run(dashboard_generation_service.execute_single_item(run_id, item_id, instruction))
