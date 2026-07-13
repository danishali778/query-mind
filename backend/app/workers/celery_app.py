from __future__ import annotations

from celery import Celery
from celery.schedules import crontab
from kombu import Queue

from app.core.config import settings


celery_app = Celery(
    "query_mind",
    broker=settings.resolved_celery_broker_url,
    include=[
        "app.workers.tasks",
        "app.workers.jobs.run_saved_query",
        "app.workers.jobs.refresh_dashboard_widget",
        "app.workers.jobs.generate_library_templates",
        "app.workers.jobs.run_chat_agent",
        "app.workers.jobs.plan_dashboard",
        "app.workers.jobs.execute_dashboard_generation",
        "app.workers.jobs.suggest_semantics",
        "app.workers.jobs.generate_question_suggestions",
    ],
)

celery_app.conf.update(
    enable_utc=True,
    timezone="UTC",
    task_ignore_result=True,
    task_serializer="json",
    accept_content=["json"],
    result_backend=None,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    broker_connection_retry_on_startup=True,
    task_default_queue=settings.celery_default_queue,
    task_queues=(
        Queue(settings.celery_default_queue),
        Queue(settings.celery_scheduled_queue),
        Queue(settings.celery_templates_queue),
        Queue(settings.celery_interactive_queue),
        Queue(settings.celery_dashboards_queue),
        Queue(settings.celery_semantics_queue),
        Queue(settings.celery_suggestions_queue),
    ),
    beat_schedule={
        "dispatch-due-schedules": {
            "task": "app.workers.tasks.dispatch_due_schedules",
            "schedule": crontab(),
            "options": {"queue": settings.celery_scheduled_queue},
        },
        "recover-stale-chat-runs": {
            "task": "app.workers.tasks.recover_stale_chat_runs",
            "schedule": crontab(),
            "options": {"queue": settings.celery_default_queue},
        },
        "recover-stale-dashboard-runs": {
            "task": "app.workers.tasks.recover_stale_dashboard_runs",
            "schedule": crontab(),
            "options": {"queue": settings.celery_default_queue},
        },
        "recover-stale-question-suggestions": {
            "task": "app.workers.tasks.recover_stale_question_suggestions",
            "schedule": crontab(),
            "options": {"queue": settings.celery_default_queue},
        },
        "dispatch-connection-maintenance": {
            "task": "app.workers.tasks.dispatch_connection_maintenance",
            "schedule": crontab(),
            "options": {"queue": settings.celery_scheduled_queue},
        },
        "cleanup-connection-health-events": {
            "task": "app.workers.tasks.cleanup_connection_health_events",
            "schedule": crontab(hour=3, minute=15),
            "options": {"queue": settings.celery_scheduled_queue},
        },
    },
)


__all__ = ["celery_app"]

