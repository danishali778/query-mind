from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.core.config import settings
from app.db.repositories import chat_run_repository, dashboard_repository, query_library_repository
from app.db.repositories import connection_health_repository, connection_repository
from app.db.session import read_session_scope, session_scope
from app.services import connection_service
from app.services.chat_progress import publish_event
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


@celery_app.task(
    name="app.workers.tasks.run_connection_health_check",
    queue=settings.celery_scheduled_queue,
)
def run_connection_health_check(connection_id: str, owner_id: str) -> dict[str, str]:
    result = asyncio.run(
        connection_service.test_saved_connection(
            owner_id, connection_id, source="scheduled_check"
        )
    )
    return {"status": "healthy" if result and result.success else "failed"}


@celery_app.task(
    name="app.workers.tasks.run_connection_schema_refresh",
    queue=settings.celery_scheduled_queue,
)
def run_connection_schema_refresh(connection_id: str, owner_id: str) -> dict[str, str]:
    try:
        asyncio.run(connection_service.refresh_schema(owner_id, connection_id))
        return {"status": "healthy"}
    except Exception:
        return {"status": "failed"}


@celery_app.task(
    name="app.workers.tasks.dispatch_connection_maintenance",
    queue=settings.celery_scheduled_queue,
)
def dispatch_connection_maintenance() -> dict[str, int]:
    with read_session_scope() as session:
        due = connection_repository.due_maintenance_sync(
            session, settings.connection_maintenance_batch_size
        )
    dispatched_health = 0
    dispatched_schema = 0
    for item in due:
        health_dispatched = False
        schema_dispatched = False
        if item["health_due"] and acquire_dispatch_lock(
            f"celery:connection-health:{item['id']}", ttl_seconds=90
        ):
            run_connection_health_check.apply_async(
                args=[item["id"], item["owner_id"]],
                queue=settings.celery_scheduled_queue,
            )
            health_dispatched = True
            dispatched_health += 1
        if item["schema_due"] and acquire_dispatch_lock(
            f"celery:connection-schema:{item['id']}", ttl_seconds=90
        ):
            run_connection_schema_refresh.apply_async(
                args=[item["id"], item["owner_id"]],
                queue=settings.celery_scheduled_queue,
            )
            schema_dispatched = True
            dispatched_schema += 1
        if health_dispatched or schema_dispatched:
            with session_scope() as session:
                connection_repository.advance_maintenance_sync(
                    session,
                    item["id"],
                    health=health_dispatched,
                    schema=schema_dispatched,
                )
    return {
        "dispatched_health": dispatched_health,
        "dispatched_schema": dispatched_schema,
    }


@celery_app.task(
    name="app.workers.tasks.cleanup_connection_health_events",
    queue=settings.celery_scheduled_queue,
)
def cleanup_connection_health_events() -> dict[str, int]:
    return {
        "deleted": connection_health_repository.cleanup(
            settings.connection_health_retention_days
        )
    }


@celery_app.task(name="app.workers.tasks.recover_stale_chat_runs", queue=settings.celery_default_queue)
def recover_stale_chat_runs() -> dict[str, int]:
    run_ids = chat_run_repository.fail_stale_runs(settings.agent_wall_clock_seconds + 30)
    for run_id in run_ids:
        publish_event(run_id, "run.failed", "Response worker stopped")
    return {"failed_stale_runs": len(run_ids)}


@celery_app.task(name="app.workers.tasks.recover_stale_dashboard_runs", queue=settings.celery_default_queue)
def recover_stale_dashboard_runs() -> dict[str, int]:
    from app.db.repositories import dashboard_generation_repository

    count = asyncio.run(
        dashboard_generation_repository.fail_stale_runs(
            older_than_seconds=settings.agent_wall_clock_seconds + 30
        )
    )
    return {"failed_stale_dashboard_runs": count}
