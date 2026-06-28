from __future__ import annotations

from datetime import datetime, timezone

from app.agents.nl_to_sql.template_recommender import generate_templates
from app.core.config import settings
from app.db.models.templates import GeneratedQueryTemplate
from app.db.repositories import template_repository
from app.workers.celery_app import celery_app


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@celery_app.task(
    bind=True,
    name="app.workers.jobs.generate_library_templates.generate_templates_task",
    queue=settings.celery_templates_queue,
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def generate_templates_task(self, connection_id: str, owner_id: str, schema_text: str, db_type: str) -> None:
    template_repository.mark_generation_started(owner_id, connection_id)
    try:
        templates = generate_templates(connection_id, schema_text, db_type)
        persisted_templates = [
            GeneratedQueryTemplate(
                id=template.id,
                owner_id=owner_id,
                connection_id=connection_id,
                title=template.title,
                description=template.description,
                sql=template.sql,
                category=template.category,
                category_color=template.category_color,
                tags=template.tags,
                icon=template.icon,
                icon_bg=template.icon_bg,
                difficulty=template.difficulty,
                created_at=_utcnow(),
            )
            for template in templates
        ]
        template_repository.mark_generation_ready(owner_id, connection_id, persisted_templates)
    except (ConnectionError, TimeoutError, OSError) as exc:
        template_repository.mark_generation_error(owner_id, connection_id, str(exc))
        raise self.retry(exc=exc, countdown=30)
    except Exception as exc:
        template_repository.mark_generation_error(owner_id, connection_id, str(exc))


def enqueue_template_generation(connection_id: str, owner_id: str, schema_text: str, db_type: str) -> None:
    template_repository.mark_generation_started(owner_id, connection_id)
    generate_templates_task.apply_async(
        args=[connection_id, owner_id, schema_text, db_type],
        queue=settings.celery_templates_queue,
    )
