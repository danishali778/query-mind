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
    ),
    beat_schedule={
        "dispatch-due-schedules": {
            "task": "app.workers.tasks.dispatch_due_schedules",
            "schedule": crontab(),
            "options": {"queue": settings.celery_scheduled_queue},
        }
    },
)


__all__ = ["celery_app"]

