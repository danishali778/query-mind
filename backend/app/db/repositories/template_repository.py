from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.db.models.templates import GeneratedQueryTemplate, TemplateGenerationState
from app.db.orm_models import GeneratedTemplateORM, TemplateGenerationORM
from app.db.session import session_scope


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _map_generation(row: TemplateGenerationORM) -> TemplateGenerationState:
    return TemplateGenerationState(
        owner_id=row.owner_id,
        connection_id=row.connection_id,
        status=row.status,
        error=row.error,
        started_at=row.started_at,
        completed_at=row.completed_at,
        updated_at=row.updated_at,
    )


def _map_template(row: GeneratedTemplateORM) -> GeneratedQueryTemplate:
    return GeneratedQueryTemplate(
        id=row.id,
        owner_id=row.owner_id,
        connection_id=row.connection_id,
        title=row.title,
        description=row.description,
        sql=row.sql,
        category=row.category,
        category_color=row.category_color,
        tags=row.tags or [],
        icon=row.icon,
        icon_bg=row.icon_bg,
        difficulty=row.difficulty,
        created_at=row.created_at or _utcnow(),
    )


def get_generation_state(owner_id: str, connection_id: str) -> TemplateGenerationState | None:
    with session_scope() as session:
        row = (
            session.query(TemplateGenerationORM)
            .filter(
                TemplateGenerationORM.owner_id == owner_id,
                TemplateGenerationORM.connection_id == connection_id,
            )
            .one_or_none()
        )
        return _map_generation(row) if row else None


def list_templates(owner_id: str, connection_id: str) -> list[GeneratedQueryTemplate]:
    with session_scope() as session:
        rows = (
            session.query(GeneratedTemplateORM)
            .filter(
                GeneratedTemplateORM.owner_id == owner_id,
                GeneratedTemplateORM.connection_id == connection_id,
            )
            .order_by(GeneratedTemplateORM.created_at.asc())
            .all()
        )
        return [_map_template(row) for row in rows]


def get_template(owner_id: str, template_id: str) -> GeneratedQueryTemplate | None:
    with session_scope() as session:
        row = (
            session.query(GeneratedTemplateORM)
            .filter(
                GeneratedTemplateORM.owner_id == owner_id,
                GeneratedTemplateORM.id == template_id,
            )
            .one_or_none()
        )
        return _map_template(row) if row else None


def mark_generation_started(owner_id: str, connection_id: str) -> TemplateGenerationState:
    now = _utcnow()
    with session_scope() as session:
        row = (
            session.query(TemplateGenerationORM)
            .filter(
                TemplateGenerationORM.owner_id == owner_id,
                TemplateGenerationORM.connection_id == connection_id,
            )
            .one_or_none()
        )
        if row is None:
            row = TemplateGenerationORM(
                owner_id=owner_id,
                connection_id=connection_id,
                status="generating",
                started_at=now,
                completed_at=None,
                error=None,
            )
            session.add(row)
        else:
            row.status = "generating"
            row.error = None
            row.started_at = now
            row.completed_at = None
        session.flush()
        return _map_generation(row)


def mark_generation_ready(
    owner_id: str,
    connection_id: str,
    templates: list[GeneratedQueryTemplate],
) -> TemplateGenerationState:
    now = _utcnow()
    with session_scope() as session:
        generation = (
            session.query(TemplateGenerationORM)
            .filter(
                TemplateGenerationORM.owner_id == owner_id,
                TemplateGenerationORM.connection_id == connection_id,
            )
            .one_or_none()
        )
        if generation is None:
            generation = TemplateGenerationORM(
                owner_id=owner_id,
                connection_id=connection_id,
                started_at=now,
            )
            session.add(generation)
            session.flush()

        (
            session.query(GeneratedTemplateORM)
            .filter(
                GeneratedTemplateORM.owner_id == owner_id,
                GeneratedTemplateORM.connection_id == connection_id,
            )
            .delete(synchronize_session=False)
        )

        generation.status = "ready"
        generation.error = None
        generation.completed_at = now
        generation.updated_at = now

        for template in templates:
            session.add(
                GeneratedTemplateORM(
                    id=template.id or str(uuid.uuid4()),
                    generation_id=generation.id,
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
                )
            )

        session.flush()
        return _map_generation(generation)


def mark_generation_error(owner_id: str, connection_id: str, error: str) -> TemplateGenerationState:
    now = _utcnow()
    with session_scope() as session:
        row = (
            session.query(TemplateGenerationORM)
            .filter(
                TemplateGenerationORM.owner_id == owner_id,
                TemplateGenerationORM.connection_id == connection_id,
            )
            .one_or_none()
        )
        if row is None:
            row = TemplateGenerationORM(
                owner_id=owner_id,
                connection_id=connection_id,
                started_at=now,
            )
            session.add(row)
        row.status = "error"
        row.error = error
        row.completed_at = now
        row.updated_at = now
        session.flush()
        return _map_generation(row)

