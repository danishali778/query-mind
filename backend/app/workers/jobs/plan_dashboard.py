"""Celery task: plan an AI dashboard."""

from __future__ import annotations

import asyncio
import logging
import threading

from app.core.config import settings
from app.services.dashboard_generation_progress import DashboardGenerationReporter, cancel_signalled
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="plan_dashboard_task",
    bind=True,
    max_retries=0,
    queue=settings.celery_dashboards_queue,
    acks_late=True,
    reject_on_worker_lost=True,
)
def plan_dashboard_task(self, run_id: str) -> None:
    from app.services import dashboard_generation_service

    logger.info("Planning dashboard run_id=%s task_id=%s", run_id, self.request.id)
    reporter = DashboardGenerationReporter(run_id)
    watcher_stop = threading.Event()

    def _watch_for_cancel() -> None:
        while not watcher_stop.wait(0.25):
            if cancel_signalled(run_id):
                reporter.cancellation_token.cancel()
                return

    watcher = threading.Thread(target=_watch_for_cancel, name=f"dashboard-plan-cancel-{run_id}", daemon=True)
    watcher.start()
    try:
        asyncio.run(dashboard_generation_service.execute_planning(run_id, reporter=reporter))
    finally:
        watcher_stop.set()
        watcher.join(timeout=1)
