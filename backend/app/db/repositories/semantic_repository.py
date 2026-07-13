"""Owner-scoped persistence for semantic definitions and their immutable history."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.models.semantic import (
    SemanticDefinition,
    SemanticDefinitionVersion,
    SemanticSuggestionRun,
)
from app.db.orm_models import (
    SemanticDefinitionORM,
    SemanticDefinitionUsageORM,
    SemanticDefinitionVersionORM,
    SemanticSuggestionRunORM,
)


class SemanticConflictError(RuntimeError):
    pass


class SemanticRevisionConflictError(RuntimeError):
    pass


class SemanticNotFoundError(LookupError):
    pass


class SemanticDefinitionInUseError(RuntimeError):
    pass


class SemanticSuggestionConflictError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _map_version(row: SemanticDefinitionVersionORM) -> SemanticDefinitionVersion:
    return SemanticDefinitionVersion(
        id=row.id,
        definition_id=row.definition_id,
        version=row.version,
        status=row.status,
        display_name=row.display_name,
        description=row.description or "",
        payload=dict(row.payload or {}),
        schema_hash=row.schema_hash,
        validation_status=row.validation_status,
        validation_report=dict(row.validation_report or {}),
        change_note=row.change_note,
        draft_revision=row.draft_revision,
        created_by=row.created_by,
        verified_by=row.verified_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
        validated_at=row.validated_at,
        verified_at=row.verified_at,
        deprecated_at=row.deprecated_at,
    )


def _map_definition(row: SemanticDefinitionORM) -> SemanticDefinition:
    versions = [_map_version(version) for version in list(row.versions or [])]
    versions.sort(key=lambda item: item.version, reverse=True)
    return SemanticDefinition(
        id=row.id,
        owner_id=row.owner_id,
        connection_id=row.connection_id,
        kind=row.kind,
        key=row.key,
        versions=versions,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _map_suggestion(row: SemanticSuggestionRunORM) -> SemanticSuggestionRun:
    return SemanticSuggestionRun(
        id=row.id,
        owner_id=row.owner_id,
        connection_id=row.connection_id,
        client_request_id=row.client_request_id,
        schema_hash=row.schema_hash,
        requested_kinds=list(row.requested_kinds or []),
        business_context=row.business_context,
        status=row.status,
        candidates_json=list(row.candidates_json or []),
        celery_task_id=row.celery_task_id,
        failure_code=row.failure_code,
        failure_message=row.failure_message,
        created_at=row.created_at,
        started_at=row.started_at,
        cancel_requested_at=row.cancel_requested_at,
        finished_at=row.finished_at,
        updated_at=row.updated_at,
    )


def _definition_query(session: Session, owner_id: str, connection_id: str):
    return (
        session.query(SemanticDefinitionORM)
        .options(selectinload(SemanticDefinitionORM.versions))
        .filter(
            SemanticDefinitionORM.owner_id == owner_id,
            SemanticDefinitionORM.connection_id == connection_id,
        )
    )


def create_definition_sync(
    session: Session,
    *,
    owner_id: str,
    connection_id: str,
    kind: str,
    key: str,
    display_name: str,
    description: str,
    payload: dict[str, Any],
    change_note: str | None = None,
) -> SemanticDefinition:
    row = SemanticDefinitionORM(
        id=str(uuid.uuid4()),
        owner_id=owner_id,
        connection_id=connection_id,
        kind=kind,
        key=key,
    )
    version = SemanticDefinitionVersionORM(
        id=str(uuid.uuid4()),
        definition_id=row.id,
        version=1,
        status="draft",
        display_name=display_name,
        description=description,
        payload=payload,
        change_note=change_note,
        created_by=owner_id,
    )
    row.versions.append(version)
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        raise SemanticConflictError("A semantic definition with this key already exists.") from exc
    return _map_definition(row)


def get_definition_sync(
    session: Session,
    owner_id: str,
    connection_id: str,
    definition_id: str,
    *,
    for_update: bool = False,
) -> SemanticDefinitionORM | None:
    query = _definition_query(session, owner_id, connection_id).filter(
        SemanticDefinitionORM.id == definition_id
    )
    if for_update:
        query = query.with_for_update()
    return query.one_or_none()


def get_definition_model_sync(
    session: Session,
    owner_id: str,
    connection_id: str,
    definition_id: str,
) -> SemanticDefinition | None:
    row = get_definition_sync(session, owner_id, connection_id, definition_id)
    return _map_definition(row) if row else None


def list_definitions_sync(
    session: Session,
    owner_id: str,
    connection_id: str,
    *,
    kind: str | None = None,
    status: str | None = None,
    validation_status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[SemanticDefinition], int]:
    query = _definition_query(session, owner_id, connection_id)
    if kind:
        query = query.filter(SemanticDefinitionORM.kind == kind)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.join(SemanticDefinitionVersionORM).filter(
            or_(
                SemanticDefinitionORM.key.ilike(pattern),
                SemanticDefinitionVersionORM.display_name.ilike(pattern),
                SemanticDefinitionVersionORM.description.ilike(pattern),
            )
        )
    if status or validation_status:
        query = query.join(SemanticDefinitionVersionORM)
        if status:
            query = query.filter(SemanticDefinitionVersionORM.status == status)
        if validation_status:
            query = query.filter(SemanticDefinitionVersionORM.validation_status == validation_status)
    query = query.distinct()
    total = query.count()
    rows = (
        query.order_by(SemanticDefinitionORM.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return [_map_definition(row) for row in rows], total


def update_draft_sync(
    session: Session,
    *,
    owner_id: str,
    connection_id: str,
    definition_id: str,
    expected_revision: int,
    display_name: str,
    description: str,
    payload: dict[str, Any],
) -> SemanticDefinition:
    definition = get_definition_sync(
        session, owner_id, connection_id, definition_id, for_update=True
    )
    if not definition:
        raise SemanticNotFoundError("Semantic definition not found.")
    draft = next((version for version in definition.versions if version.status == "draft"), None)
    if not draft:
        raise SemanticNotFoundError("Semantic draft not found.")
    if draft.draft_revision != expected_revision:
        raise SemanticRevisionConflictError("The semantic draft was changed in another request.")
    draft.display_name = display_name
    draft.description = description
    draft.payload = payload
    draft.draft_revision += 1
    draft.validation_status = "unvalidated"
    draft.validation_report = {}
    draft.schema_hash = None
    draft.validated_at = None
    definition.updated_at = _now()
    session.flush()
    return _map_definition(definition)


def create_version_sync(
    session: Session,
    *,
    owner_id: str,
    connection_id: str,
    definition_id: str,
    display_name: str,
    description: str,
    payload: dict[str, Any],
    change_note: str | None,
) -> SemanticDefinition:
    definition = get_definition_sync(
        session, owner_id, connection_id, definition_id, for_update=True
    )
    if not definition:
        raise SemanticNotFoundError("Semantic definition not found.")
    if any(version.status == "draft" for version in definition.versions):
        raise SemanticConflictError("This definition already has an active draft.")
    next_version = max((version.version for version in definition.versions), default=0) + 1
    definition.versions.append(
        SemanticDefinitionVersionORM(
            id=str(uuid.uuid4()),
            definition_id=definition.id,
            version=next_version,
            status="draft",
            display_name=display_name,
            description=description,
            payload=payload,
            change_note=change_note,
            created_by=owner_id,
        )
    )
    definition.updated_at = _now()
    session.flush()
    return _map_definition(definition)


def delete_draft_sync(
    session: Session, owner_id: str, connection_id: str, definition_id: str
) -> bool:
    definition = get_definition_sync(
        session, owner_id, connection_id, definition_id, for_update=True
    )
    if not definition:
        return False
    draft = next((version for version in definition.versions if version.status == "draft"), None)
    if not draft:
        return False
    usage_count = session.query(SemanticDefinitionUsageORM.id).filter(
        SemanticDefinitionUsageORM.owner_id == owner_id,
        SemanticDefinitionUsageORM.connection_id == connection_id,
        SemanticDefinitionUsageORM.definition_version_id == draft.id,
    ).count()
    if usage_count:
        raise SemanticDefinitionInUseError("Semantic draft is already referenced.")
    session.delete(draft)
    remaining = [version for version in definition.versions if version.id != draft.id]
    if not remaining:
        session.delete(definition)
    return True


def save_validation_sync(
    session: Session,
    *,
    owner_id: str,
    connection_id: str,
    definition_id: str,
    version: int,
    schema_hash: str,
    validation_status: str,
    validation_report: dict[str, Any],
) -> SemanticDefinition:
    definition = get_definition_sync(
        session, owner_id, connection_id, definition_id, for_update=True
    )
    if not definition:
        raise SemanticNotFoundError("Semantic definition not found.")
    target = next((item for item in definition.versions if item.version == version), None)
    if not target:
        raise SemanticNotFoundError("Semantic definition version not found.")
    target.schema_hash = schema_hash
    target.validation_status = validation_status
    target.validation_report = validation_report
    if target.status == "draft" and validation_report.get("normalized_payload"):
        target.payload = dict(validation_report["normalized_payload"])
    target.validated_at = _now()
    session.flush()
    return _map_definition(definition)


def verify_version_sync(
    session: Session,
    *,
    owner_id: str,
    connection_id: str,
    definition_id: str,
    version: int,
    expected_schema_hash: str,
    acknowledged_warning_codes: list[str],
    change_note: str | None,
) -> SemanticDefinition:
    definition = get_definition_sync(
        session, owner_id, connection_id, definition_id, for_update=True
    )
    if not definition:
        raise SemanticNotFoundError("Semantic definition not found.")
    target = next((item for item in definition.versions if item.version == version), None)
    if not target or target.status != "draft":
        raise SemanticConflictError("Only an active draft can be verified.")
    if target.validation_status != "valid" or target.schema_hash != expected_schema_hash:
        raise SemanticConflictError("The draft must be validated against the current schema.")
    warning_codes = {
        str(item.get("code"))
        for item in (target.validation_report or {}).get("warnings", [])
        if item.get("code")
    }
    if warning_codes - set(acknowledged_warning_codes):
        raise SemanticConflictError("All validation warnings must be acknowledged.")
    now = _now()
    for existing in definition.versions:
        if existing.status == "verified":
            existing.status = "deprecated"
            existing.deprecated_at = now
    target.status = "verified"
    target.verified_by = owner_id
    target.verified_at = now
    target.change_note = change_note or target.change_note
    definition.updated_at = now
    session.flush()
    return _map_definition(definition)


def deprecate_version_sync(
    session: Session,
    *,
    owner_id: str,
    connection_id: str,
    definition_id: str,
    version: int,
) -> SemanticDefinition:
    definition = get_definition_sync(
        session, owner_id, connection_id, definition_id, for_update=True
    )
    if not definition:
        raise SemanticNotFoundError("Semantic definition not found.")
    target = next((item for item in definition.versions if item.version == version), None)
    if not target or target.status != "verified":
        raise SemanticConflictError("Only the active verified version can be deprecated.")
    target.status = "deprecated"
    target.deprecated_at = _now()
    definition.updated_at = _now()
    session.flush()
    return _map_definition(definition)


def list_active_verified_sync(
    session: Session, owner_id: str, connection_id: str
) -> list[tuple[SemanticDefinitionORM, SemanticDefinitionVersionORM]]:
    return (
        session.query(SemanticDefinitionORM, SemanticDefinitionVersionORM)
        .join(
            SemanticDefinitionVersionORM,
            SemanticDefinitionVersionORM.definition_id == SemanticDefinitionORM.id,
        )
        .filter(
            SemanticDefinitionORM.owner_id == owner_id,
            SemanticDefinitionORM.connection_id == connection_id,
            SemanticDefinitionVersionORM.status == "verified",
            SemanticDefinitionVersionORM.validation_status == "valid",
        )
        .order_by(SemanticDefinitionORM.kind, SemanticDefinitionORM.key)
        .all()
    )


def list_verified_for_revalidation_sync(
    session: Session, owner_id: str, connection_id: str
) -> list[tuple[SemanticDefinitionORM, SemanticDefinitionVersionORM]]:
    """Include stale verified versions so compatible schema/scope changes can recover them."""
    return (
        session.query(SemanticDefinitionORM, SemanticDefinitionVersionORM)
        .join(
            SemanticDefinitionVersionORM,
            SemanticDefinitionVersionORM.definition_id == SemanticDefinitionORM.id,
        )
        .filter(
            SemanticDefinitionORM.owner_id == owner_id,
            SemanticDefinitionORM.connection_id == connection_id,
            SemanticDefinitionVersionORM.status == "verified",
            SemanticDefinitionVersionORM.validation_status.in_(("valid", "stale")),
        )
        .order_by(SemanticDefinitionORM.kind, SemanticDefinitionORM.key)
        .all()
    )


def update_verified_validation_sync(
    session: Session,
    *,
    owner_id: str,
    connection_id: str,
    version_id: str,
    schema_hash: str,
    validation_status: str,
    validation_report: dict[str, Any],
) -> bool:
    """Update validation metadata only; verified definition content stays immutable."""
    row = (
        session.query(SemanticDefinitionVersionORM)
        .join(SemanticDefinitionORM)
        .filter(
            SemanticDefinitionORM.owner_id == owner_id,
            SemanticDefinitionORM.connection_id == connection_id,
            SemanticDefinitionVersionORM.id == version_id,
            SemanticDefinitionVersionORM.status == "verified",
        )
        .one_or_none()
    )
    if not row:
        return False
    row.schema_hash = schema_hash
    row.validation_status = validation_status
    row.validation_report = validation_report
    row.validated_at = _now()
    return True


def get_summary_sync(session: Session, owner_id: str, connection_id: str) -> dict[str, Any]:
    rows = (
        session.query(
            SemanticDefinitionVersionORM.status,
            SemanticDefinitionVersionORM.validation_status,
            func.count(SemanticDefinitionVersionORM.id),
            func.max(SemanticDefinitionVersionORM.validated_at),
        )
        .join(SemanticDefinitionORM)
        .filter(
            SemanticDefinitionORM.owner_id == owner_id,
            SemanticDefinitionORM.connection_id == connection_id,
        )
        .group_by(
            SemanticDefinitionVersionORM.status,
            SemanticDefinitionVersionORM.validation_status,
        )
        .all()
    )
    counts = {"draft": 0, "verified": 0, "deprecated": 0, "invalid": 0, "stale": 0}
    latest_validation = None
    for status, validation_status, count, validated_at in rows:
        counts[status] = counts.get(status, 0) + count
        if validation_status in {"invalid", "stale"}:
            counts[validation_status] = counts.get(validation_status, 0) + count
        if validated_at and (latest_validation is None or validated_at > latest_validation):
            latest_validation = validated_at
    return {
        "total": int(
            session.query(func.count(SemanticDefinitionORM.id))
            .filter(
                SemanticDefinitionORM.owner_id == owner_id,
                SemanticDefinitionORM.connection_id == connection_id,
            )
            .scalar()
            or 0
        ),
        **counts,
        "last_validated_at": latest_validation,
    }


def semantic_health_counts() -> dict[str, Any]:
    """Return aggregate, value-free diagnostics for the semantic subsystem."""
    from app.db.session import read_session_scope

    with read_session_scope() as session:
        version_rows = session.query(
            SemanticDefinitionVersionORM.status,
            SemanticDefinitionVersionORM.validation_status,
            SemanticDefinitionVersionORM.validation_report,
        ).all()
        active_verified = 0
        stale = 0
        invalid = 0
        failed_previews = 0
        for status, validation_status, report in version_rows:
            if status == "verified" and validation_status == "valid":
                active_verified += 1
            if validation_status == "stale":
                stale += 1
            if validation_status == "invalid":
                invalid += 1
            errors = (report or {}).get("errors", [])
            if any(item.get("code") == "semantic_preview_failed" for item in errors):
                failed_previews += 1

        suggestion_rows = session.query(
            SemanticSuggestionRunORM.status,
            SemanticSuggestionRunORM.started_at,
            SemanticSuggestionRunORM.finished_at,
        ).all()
        status_counts = {
            "queued": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
        }
        durations: list[float] = []
        for status, started_at, finished_at in suggestion_rows:
            status_counts[status] = status_counts.get(status, 0) + 1
            if started_at and finished_at:
                durations.append(max(0.0, (finished_at - started_at).total_seconds()))
        terminal = status_counts["completed"] + status_counts["failed"]
        failure_rate = status_counts["failed"] / terminal if terminal else 0.0
        return {
            "active_verified_definitions": active_verified,
            "stale_definitions": stale,
            "invalid_definitions": invalid,
            "failed_previews": failed_previews,
            "suggestion_active_runs": status_counts["queued"] + status_counts["running"],
            "suggestion_failed_runs": status_counts["failed"],
            "suggestion_failure_rate": round(failure_rate, 4),
            "suggestion_average_duration_seconds": (
                round(sum(durations) / len(durations), 3) if durations else 0.0
            ),
        }


def record_usages_sync(
    session: Session,
    *,
    owner_id: str,
    connection_id: str,
    version_ids: list[str],
    consumer_type: str,
    consumer_id: str,
    usage_role: str = "applied",
) -> None:
    if not version_ids:
        return
    owned_ids = {
        version_id
        for (version_id,) in (
            session.query(SemanticDefinitionVersionORM.id)
            .join(SemanticDefinitionORM)
            .filter(
                SemanticDefinitionORM.owner_id == owner_id,
                SemanticDefinitionORM.connection_id == connection_id,
                SemanticDefinitionVersionORM.id.in_(set(version_ids)),
            )
            .all()
        )
    }
    for version_id in owned_ids:
        exists = session.query(SemanticDefinitionUsageORM.id).filter(
            SemanticDefinitionUsageORM.definition_version_id == version_id,
            SemanticDefinitionUsageORM.consumer_type == consumer_type,
            SemanticDefinitionUsageORM.consumer_id == consumer_id,
            SemanticDefinitionUsageORM.usage_role == usage_role,
        ).first()
        if not exists:
            session.add(
                SemanticDefinitionUsageORM(
                    id=str(uuid.uuid4()),
                    owner_id=owner_id,
                    connection_id=connection_id,
                    definition_version_id=version_id,
                    consumer_type=consumer_type,
                    consumer_id=consumer_id,
                    usage_role=usage_role,
                )
            )


def impact_sync(
    session: Session, owner_id: str, connection_id: str, definition_id: str
) -> list[dict[str, Any]]:
    definition = get_definition_sync(session, owner_id, connection_id, definition_id)
    if not definition:
        raise SemanticNotFoundError("Semantic definition not found.")
    version_ids = [version.id for version in definition.versions]
    rows = (
        session.query(SemanticDefinitionUsageORM, SemanticDefinitionVersionORM.version)
        .join(
            SemanticDefinitionVersionORM,
            SemanticDefinitionVersionORM.id == SemanticDefinitionUsageORM.definition_version_id,
        )
        .filter(
            SemanticDefinitionUsageORM.owner_id == owner_id,
            SemanticDefinitionUsageORM.connection_id == connection_id,
            SemanticDefinitionUsageORM.definition_version_id.in_(version_ids),
        )
        .order_by(SemanticDefinitionUsageORM.created_at.desc())
        .all()
    )
    return [
        {
            "definition_version_id": usage.definition_version_id,
            "version": version,
            "consumer_type": usage.consumer_type,
            "consumer_id": usage.consumer_id,
            "usage_role": usage.usage_role,
            "created_at": usage.created_at,
        }
        for usage, version in rows
    ]


def create_suggestion_run_sync(
    session: Session,
    *,
    owner_id: str,
    connection_id: str,
    client_request_id: str,
    schema_hash: str,
    requested_kinds: list[str],
    business_context: str | None,
) -> tuple[SemanticSuggestionRun, bool]:
    existing = session.query(SemanticSuggestionRunORM).filter(
        SemanticSuggestionRunORM.owner_id == owner_id,
        SemanticSuggestionRunORM.client_request_id == client_request_id,
    ).one_or_none()
    if existing:
        return _map_suggestion(existing), False
    active = session.query(SemanticSuggestionRunORM.id).filter(
        SemanticSuggestionRunORM.owner_id == owner_id,
        SemanticSuggestionRunORM.connection_id == connection_id,
        SemanticSuggestionRunORM.status.in_(("queued", "running")),
    ).first()
    if active:
        raise SemanticSuggestionConflictError(
            "A semantic suggestion run is already active for this connection."
        )
    row = SemanticSuggestionRunORM(
        id=str(uuid.uuid4()),
        owner_id=owner_id,
        connection_id=connection_id,
        client_request_id=client_request_id,
        schema_hash=schema_hash,
        requested_kinds=requested_kinds,
        business_context=business_context,
        status="queued",
        candidates_json=[],
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        raise SemanticSuggestionConflictError(
            "A semantic suggestion run is already active."
        ) from exc
    return _map_suggestion(row), True


def get_suggestion_run_sync(
    session: Session, owner_id: str, connection_id: str, run_id: str
) -> SemanticSuggestionRun | None:
    row = session.query(SemanticSuggestionRunORM).filter(
        SemanticSuggestionRunORM.id == run_id,
        SemanticSuggestionRunORM.owner_id == owner_id,
        SemanticSuggestionRunORM.connection_id == connection_id,
    ).one_or_none()
    return _map_suggestion(row) if row else None


def get_suggestion_by_client_request_sync(
    session: Session, owner_id: str, client_request_id: str
) -> SemanticSuggestionRun | None:
    row = session.query(SemanticSuggestionRunORM).filter(
        SemanticSuggestionRunORM.owner_id == owner_id,
        SemanticSuggestionRunORM.client_request_id == client_request_id,
    ).one_or_none()
    return _map_suggestion(row) if row else None


def set_suggestion_task_id_sync(session: Session, run_id: str, task_id: str) -> None:
    row = session.query(SemanticSuggestionRunORM).filter(
        SemanticSuggestionRunORM.id == run_id
    ).one_or_none()
    if row and row.status == "queued":
        row.celery_task_id = task_id
        row.updated_at = _now()


def claim_suggestion_run_sync(session: Session, run_id: str) -> SemanticSuggestionRun | None:
    row = session.query(SemanticSuggestionRunORM).filter(
        SemanticSuggestionRunORM.id == run_id
    ).with_for_update().one_or_none()
    if not row or row.status != "queued":
        return None
    now = _now()
    row.status = "running"
    row.started_at = now
    row.updated_at = now
    session.flush()
    return _map_suggestion(row)


def suggestion_cancel_requested_sync(session: Session, run_id: str) -> bool:
    status = session.query(SemanticSuggestionRunORM.status).filter(
        SemanticSuggestionRunORM.id == run_id
    ).scalar()
    return status == "cancelled"


def cancel_suggestion_run_sync(
    session: Session, owner_id: str, connection_id: str, run_id: str
) -> SemanticSuggestionRun | None:
    row = session.query(SemanticSuggestionRunORM).filter(
        SemanticSuggestionRunORM.id == run_id,
        SemanticSuggestionRunORM.owner_id == owner_id,
        SemanticSuggestionRunORM.connection_id == connection_id,
    ).with_for_update().one_or_none()
    if not row:
        return None
    if row.status in {"completed", "failed", "cancelled"}:
        return _map_suggestion(row)
    now = _now()
    row.status = "cancelled"
    row.cancel_requested_at = now
    row.finished_at = now
    row.updated_at = now
    session.flush()
    return _map_suggestion(row)


def finalize_suggestion_run_sync(
    session: Session,
    run_id: str,
    *,
    status: str,
    candidates: list[dict[str, Any]] | None = None,
    failure_code: str | None = None,
    failure_message: str | None = None,
) -> bool:
    if status not in {"completed", "failed", "cancelled"}:
        raise ValueError("Suggestion run final status must be terminal.")
    row = session.query(SemanticSuggestionRunORM).filter(
        SemanticSuggestionRunORM.id == run_id
    ).with_for_update().one_or_none()
    if not row or row.status in {"completed", "failed", "cancelled"}:
        return False
    now = _now()
    row.status = status
    row.candidates_json = list(candidates or [])
    row.failure_code = failure_code
    row.failure_message = failure_message
    row.finished_at = now
    row.updated_at = now
    return True


__all__ = [
    "SemanticConflictError",
    "SemanticDefinitionInUseError",
    "SemanticNotFoundError",
    "SemanticRevisionConflictError",
    "create_definition_sync",
    "create_version_sync",
    "delete_draft_sync",
    "deprecate_version_sync",
    "get_definition_model_sync",
    "get_definition_sync",
    "get_summary_sync",
    "impact_sync",
    "list_active_verified_sync",
    "list_verified_for_revalidation_sync",
    "list_definitions_sync",
    "record_usages_sync",
    "save_validation_sync",
    "semantic_health_counts",
    "update_draft_sync",
    "verify_version_sync",
]
