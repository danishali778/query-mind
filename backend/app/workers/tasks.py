from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.core.config import settings
from app.db.repositories import dashboard_repository, query_library_repository
from app.workers.celery_app import celery_app
from app.workers.jobs.refresh_dashboard_widget import refresh_dashboard_widget_task
from app.workers.jobs.run_saved_query import run_saved_query_task
from app.workers.runtime import acquire_dispatch_lock


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@celery_app.task(name="app.workers.tasks.dispatch_due_schedules", queue=settings.celery_scheduled_queue)
def dispatch_due_schedules() -> dict[str, int]:
    due_queries = query_library_repository.sync_get_due_scheduled_queries(limit=100)
    due_widgets = asyncio.run(dashboard_repository.get_due_scheduled_widgets(limit=100))

    dispatched_queries = 0
    dispatched_widgets = 0

    for query in due_queries:
        lock_key = f"celery:schedule:query:{query.id}"
        if not acquire_dispatch_lock(lock_key):
            continue
        query_library_repository.sync_set_schedule_runtime_state(
            query.owner_id,
            query.id,
            next_run_at=query.schedule.next_run_at if query.schedule else None,
            last_run_status="queued",
            last_error=None,
        )
        run_saved_query_task.apply_async(
            args=[query.id, query.owner_id],
            queue=settings.celery_scheduled_queue,
        )
        dispatched_queries += 1

    for widget in due_widgets:
        lock_key = f"celery:schedule:widget:{widget.id}"
        if not acquire_dispatch_lock(lock_key):
            continue
        asyncio.run(
            dashboard_repository.set_widget_schedule_runtime_state(
                widget.owner_id,
                widget.id,
                next_run_at=_utcnow(),
                last_run_status="queued",
                last_error=None,
            )
        )
        refresh_dashboard_widget_task.apply_async(
            args=[widget.id, widget.owner_id],
            queue=settings.celery_scheduled_queue,
        )
        dispatched_widgets += 1

    return {
        "dispatched_queries": dispatched_queries,
        "dispatched_widgets": dispatched_widgets,
    }
