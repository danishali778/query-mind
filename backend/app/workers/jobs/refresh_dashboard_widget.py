from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.core.config import settings
from app.db.models.dashboard import UpdateWidgetInput
from app.db.repositories import dashboard_repository
from app.services import dashboard_service, scheduling_service
from app.services.connection_service import get_engine, get_readonly
from app.services.query_execution_service import execute_query
from app.workers.celery_app import celery_app
from app.workers.runtime import release_dispatch_lock


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@celery_app.task(
    bind=True,
    name="app.workers.jobs.refresh_dashboard_widget.refresh_dashboard_widget_task",
    queue=settings.celery_scheduled_queue,
    autoretry_for=(ConnectionError, TimeoutError, OSError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def refresh_dashboard_widget_task(self, widget_id: str, owner_id: str) -> None:
    lock_key = f"celery:schedule:widget:{widget_id}"
    try:
        widget = asyncio.run(dashboard_service.get_widget(owner_id, widget_id))
        if not widget:
            return

        next_run_at = scheduling_service.compute_next_widget_run(widget.cadence)
        if not widget.cadence or widget.cadence == scheduling_service.WIDGET_MANUAL_ONLY or not widget.sql:
            asyncio.run(
                dashboard_repository.set_widget_schedule_runtime_state(
                    owner_id,
                    widget_id,
                    next_run_at=None,
                    last_run_status=None,
                    last_error=None,
                )
            )
            return

        asyncio.run(
            dashboard_repository.set_widget_schedule_runtime_state(
                owner_id,
                widget_id,
                next_run_at=_utcnow(),
                last_run_status="running",
                last_error=None,
            )
        )

        if not widget.connection_id:
            asyncio.run(
                dashboard_repository.finalize_widget_run(
                    owner_id,
                    widget_id,
                    next_run_at=next_run_at,
                    success=False,
                    error="No connection configured",
                )
            )
            return

        engine = asyncio.run(get_engine(owner_id, widget.connection_id))
        if not engine:
            asyncio.run(
                dashboard_repository.finalize_widget_run(
                    owner_id,
                    widget_id,
                    next_run_at=next_run_at,
                    success=False,
                    error="Connection not found",
                )
            )
            return

        dashboard = asyncio.run(dashboard_service.get_dashboard(owner_id, widget.dashboard_id))
        final_sql = widget.sql
        if dashboard and dashboard.filters:
            final_sql = dashboard_service.apply_global_filters(widget.sql, dashboard.filters)

        readonly = asyncio.run(get_readonly(owner_id, widget.connection_id))
        result = execute_query(
            owner_id,
            engine,
            final_sql,
            500,
            widget.connection_id,
            readonly,
        )

        if result.success:
            asyncio.run(
                dashboard_repository.update_widget(
                    owner_id,
                    widget_id,
                    UpdateWidgetInput(columns=result.columns, rows=result.rows),
                )
            )
            asyncio.run(
                dashboard_repository.finalize_widget_run(
                    owner_id,
                    widget_id,
                    next_run_at=next_run_at,
                    success=True,
                    error=None,
                )
            )
        else:
            asyncio.run(
                dashboard_repository.finalize_widget_run(
                    owner_id,
                    widget_id,
                    next_run_at=next_run_at,
                    success=False,
                    error=result.error,
                )
            )
    finally:
        release_dispatch_lock(lock_key)


def enqueue_widget_refresh(widget_id: str, owner_id: str) -> None:
    refresh_dashboard_widget_task.apply_async(
        args=[widget_id, owner_id],
        queue=settings.celery_scheduled_queue,
    )
