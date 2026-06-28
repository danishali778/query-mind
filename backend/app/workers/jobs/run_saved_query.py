from __future__ import annotations

import asyncio

from app.core.config import settings
from app.db.repositories import query_library_repository
from app.services import scheduling_service
from app.services.connection_service import get_engine, get_readonly
from app.services.query_execution_service import execute_query
from app.workers.celery_app import celery_app
from app.workers.runtime import release_dispatch_lock


@celery_app.task(
    bind=True,
    name="app.workers.jobs.run_saved_query.run_saved_query_task",
    queue=settings.celery_scheduled_queue,
    autoretry_for=(ConnectionError, TimeoutError, OSError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def run_saved_query_task(self, query_id: str, owner_id: str) -> None:
    lock_key = f"celery:schedule:query:{query_id}"
    try:
        query = query_library_repository.sync_get_query(owner_id, query_id)
        if not query:
            return
        if not query.schedule or not query.schedule.enabled:
            query_library_repository.sync_set_schedule_runtime_state(
                owner_id,
                query_id,
                next_run_at=None,
                last_run_status=None,
                last_error=None,
            )
            return

        query_library_repository.sync_set_schedule_runtime_state(
            owner_id,
            query_id,
            next_run_at=query.schedule.next_run_at,
            last_run_status="running",
            last_error=None,
        )

        next_run_at = scheduling_service.compute_next_saved_query_run(query.schedule)

        if not query.connection_id:
            error = "No connection configured"
            query_library_repository.sync_log_run(
                user_id=owner_id,
                query_id=query_id,
                success=False,
                error=error,
                triggered_by="schedule",
            )
            query_library_repository.sync_finalize_scheduled_run(
                owner_id,
                query_id,
                next_run_at=next_run_at,
                success=False,
                error=error,
            )
            return

        engine = asyncio.run(get_engine(owner_id, query.connection_id))
        if not engine:
            error = "Connection not found"
            query_library_repository.sync_log_run(
                user_id=owner_id,
                query_id=query_id,
                success=False,
                error=error,
                triggered_by="schedule",
            )
            query_library_repository.sync_finalize_scheduled_run(
                owner_id,
                query_id,
                next_run_at=next_run_at,
                success=False,
                error=error,
            )
            return

        readonly = asyncio.run(get_readonly(owner_id, query.connection_id))
        result = execute_query(
            owner_id,
            engine,
            query.sql,
            row_limit=500,
            connection_id=query.connection_id,
            readonly=readonly,
        )
        query_library_repository.sync_log_run(
            user_id=owner_id,
            query_id=query_id,
            success=result.success,
            row_count=result.row_count,
            execution_time_ms=result.execution_time_ms,
            error=result.error,
            triggered_by="schedule",
        )
        query_library_repository.sync_finalize_scheduled_run(
            owner_id,
            query_id,
            next_run_at=next_run_at,
            success=result.success,
            error=result.error,
        )
    finally:
        release_dispatch_lock(lock_key)


def enqueue_saved_query(query_id: str, owner_id: str) -> None:
    run_saved_query_task.apply_async(
        args=[query_id, owner_id],
        queue=settings.celery_scheduled_queue,
    )
