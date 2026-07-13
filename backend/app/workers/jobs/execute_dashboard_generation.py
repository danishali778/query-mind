"""Celery tasks: execute / regenerate AI dashboard widgets."""

from __future__ import annotations

import asyncio
import logging
import threading

from app.core.config import settings
from app.services.dashboard_generation_progress import DashboardGenerationReporter, cancel_signalled
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_with_cancel_watcher(run_id: str, execute) -> None:
    reporter = DashboardGenerationReporter(run_id)
    watcher_stop = threading.Event()

    def _watch_for_cancel() -> None:
        while not watcher_stop.wait(0.25):
            if cancel_signalled(run_id):
                reporter.cancellation_token.cancel()
                return

    watcher = threading.Thread(target=_watch_for_cancel, name=f"dashboard-cancel-{run_id}", daemon=True)
    watcher.start()
    try:
        asyncio.run(execute(reporter))
    finally:
        watcher_stop.set()
        watcher.join(timeout=1)


@celery_app.task(
    name="execute_dashboard_generation_task",
    bind=True,
    max_retries=0,
    queue=settings.celery_dashboards_queue,
    acks_late=True,
    reject_on_worker_lost=True,
)
def execute_dashboard_generation_task(self, run_id: str) -> None:
    from app.services import dashboard_generation_service

    logger.info("Executing dashboard generation run_id=%s task_id=%s", run_id, self.request.id)
    _run_with_cancel_watcher(
        run_id,
        lambda reporter: dashboard_generation_service.execute_run(run_id, reporter=reporter),
    )


@celery_app.task(
    name="regenerate_dashboard_widget_task",
    bind=True,
    max_retries=0,
    queue=settings.celery_dashboards_queue,
    acks_late=True,
    reject_on_worker_lost=True,
)
def regenerate_dashboard_widget_task(self, run_id: str, item_id: str, instruction: str | None = None) -> None:
    from app.services import dashboard_generation_service

    logger.info(
        "Regenerating dashboard widget run_id=%s item_id=%s task_id=%s",
        run_id,
        item_id,
        self.request.id,
    )
    _run_with_cancel_watcher(
        run_id,
        lambda reporter: dashboard_generation_service.execute_single_item(
            run_id,
            item_id,
            instruction,
            reporter=reporter,
        ),
    )
