"""Production connection management: rotation, scope, automation, and history."""

from __future__ import annotations

import functools
from typing import Any

import anyio

from app.agents.schema_context.catalog import build_catalog
from app.core.config import settings
from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.db import connection_manager
from app.db.repositories import connection_health_repository, connection_repository
from app.db.session import read_session_scope, session_scope
from app.db.orm_models import (
    DashboardGenerationRunORM,
    DashboardWidgetORM,
    SavedQueryORM,
    SemanticDefinitionORM,
    SemanticDefinitionVersionORM,
)
from app.query_engine import connection_pool, schema_inspector
from app.query_engine.connection_scope import (
    invalidate_scope_cache,
    normalize_scope,
    referenced_tables,
    validate_scope_inventory,
)


async def _active(owner_id: str, connection_id: str):
    value = await connection_repository.get_active_connection(owner_id, connection_id)
    if not value:
        raise NotFoundError("Database connection not found.", code="connection_not_found")
    return value


async def rotate_credentials(
    owner_id: str,
    connection_id: str,
    *,
    expected_revision: int,
    changes: dict[str, Any],
) -> dict:
    await _active(owner_id, connection_id)
    current = await connection_repository.get_connection_config(owner_id, connection_id)
    if not current:
        raise NotFoundError("Database connection not found.", code="connection_not_found")
    if "password" in changes and not changes["password"]:
        raise BadRequestError("Database password cannot be cleared.", code="connection_configuration_invalid")
    candidate = current.model_copy(update=changes)
    engine = None
    tunnel = None
    try:
        engine, tunnel = await anyio.to_thread.run_sync(connection_pool.open_connection, candidate)
        inventory, _ = await anyio.to_thread.run_sync(
            schema_inspector.discover_schema_inventory,
            engine,
            settings.connection_diagnostic_max_objects,
        )
        scope = normalize_scope(candidate.scope_mode, candidate.included_schemas, candidate.included_tables)
        errors = validate_scope_inventory(scope, inventory)
        if errors:
            raise BadRequestError(
                "The rotated credentials cannot access the current connection scope.",
                code="connection_permission_denied",
            )

        def persist() -> int:
            with session_scope() as session:
                revision = connection_repository.rotate_credentials_sync(
                    session,
                    user_id=owner_id,
                    connection_id=connection_id,
                    expected_revision=expected_revision,
                    config=candidate,
                )
                if not revision:
                    raise NotFoundError("Database connection not found.", code="connection_not_found")
                connection_health_repository.record_sync(
                    session,
                    owner_id=owner_id,
                    connection_id=connection_id,
                    source="credential_rotation",
                    status="healthy",
                    diagnostic_code="connection_healthy",
                    message="Credentials rotated successfully.",
                    latency_ms=None,
                )
                return revision

        await anyio.to_thread.run_sync(persist)
    except connection_repository.ConnectionRevisionConflictError as exc:
        if engine:
            connection_pool.dispose_connection_resources(engine, tunnel)
        raise ConflictError(str(exc), code="connection_credentials_conflict") from exc
    except Exception as exc:
        if engine:
            connection_pool.dispose_connection_resources(engine, tunnel)
        try:
            code, _category, _message, _suggestions = connection_pool._diagnostic_for_exception(exc)
            await anyio.to_thread.run_sync(
                functools.partial(
                    connection_health_repository.record,
                    owner_id=owner_id,
                    connection_id=connection_id,
                    source="credential_rotation",
                    status="failed",
                    diagnostic_code=code,
                    message="Credential rotation failed; the previous credentials remain active.",
                    latency_ms=None,
                )
            )
        except Exception:
            pass
        raise

    connection_pool.cache_connection(owner_id, connection_id, engine, tunnel)
    updated = await connection_repository.get_active_connection(owner_id, connection_id)
    return updated.model_dump(mode="json")


async def get_scope(owner_id: str, connection_id: str) -> dict:
    await _active(owner_id, connection_id)

    def run():
        with read_session_scope() as session:
            return connection_repository.get_scope_sync(session, owner_id, connection_id)

    return await anyio.to_thread.run_sync(run)


async def discover_scope(owner_id: str, connection_id: str) -> dict:
    await _active(owner_id, connection_id)
    engine = await connection_manager.get_engine(owner_id, connection_id)
    inventory, truncated = await anyio.to_thread.run_sync(
        schema_inspector.discover_schema_inventory,
        engine,
        settings.connection_diagnostic_max_objects,
    )
    return {"inventory": inventory, "inventory_truncated": truncated}


def _allowed(scope: dict, canonical: str) -> bool:
    if scope["mode"] == "all":
        return True
    schema_name, _ = canonical.split(".", 1)
    return (
        schema_name.casefold() in {item.casefold() for item in scope["included_schemas"]}
        or canonical.casefold() in {item.casefold() for item in scope["included_tables"]}
    )


def _sql_outside(sql: str | None, scope: dict) -> bool:
    if not sql:
        return False
    try:
        return any(not _allowed(scope, item) for item in referenced_tables(sql))
    except Exception:
        return True


def _payload_tables(value: Any, key: str = "") -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for child_key, child in value.items():
            if child_key in {"table_name", "primary_table", "left_table", "right_table"} and isinstance(child, str):
                found.add(child if "." in child else f"public.{child}")
            elif child_key in {"tables", "required_tables"} and isinstance(child, list):
                found.update(item if "." in item else f"public.{item}" for item in child if isinstance(item, str))
            else:
                found.update(_payload_tables(child, child_key))
    elif isinstance(value, list):
        for item in value:
            found.update(_payload_tables(item, key))
    return found


def _impacts_sync(owner_id: str, connection_id: str, scope: dict) -> list[dict]:
    impacts: list[dict] = []
    with read_session_scope() as session:
        for row in session.query(SavedQueryORM).filter(
            SavedQueryORM.owner_id == owner_id, SavedQueryORM.connection_id == connection_id
        ).all():
            if _sql_outside(row.sql, scope):
                impacts.append({"code": "saved_query_out_of_scope", "consumer_type": "saved_query", "consumer_id": row.id, "label": row.title})
        for row in session.query(DashboardWidgetORM).filter(
            DashboardWidgetORM.owner_id == owner_id, DashboardWidgetORM.connection_id == connection_id
        ).all():
            if _sql_outside(row.sql, scope):
                impacts.append({"code": "dashboard_widget_out_of_scope", "consumer_type": "dashboard_widget", "consumer_id": row.id, "label": row.title})
        for row in session.query(DashboardGenerationRunORM).filter(
            DashboardGenerationRunORM.owner_id == owner_id,
            DashboardGenerationRunORM.connection_id == connection_id,
        ).all():
            if any(not _allowed(scope, item) for item in _payload_tables(row.plan_json or {})):
                impacts.append({"code": "dashboard_generation_out_of_scope", "consumer_type": "dashboard_generation", "consumer_id": row.id, "label": "Dashboard generation"})
        semantic_rows = session.query(SemanticDefinitionORM, SemanticDefinitionVersionORM).join(
            SemanticDefinitionVersionORM,
            SemanticDefinitionVersionORM.definition_id == SemanticDefinitionORM.id,
        ).filter(
            SemanticDefinitionORM.owner_id == owner_id,
            SemanticDefinitionORM.connection_id == connection_id,
            SemanticDefinitionVersionORM.status == "verified",
        ).all()
        for definition, version in semantic_rows:
            if any(not _allowed(scope, item) for item in _payload_tables(version.payload or {})):
                impacts.append({"code": "semantic_definition_out_of_scope", "consumer_type": "semantic_definition", "consumer_id": definition.id, "label": version.display_name})
    return impacts


async def preview_scope(owner_id: str, connection_id: str, payload: dict) -> dict:
    await _active(owner_id, connection_id)
    try:
        scope = normalize_scope(payload["mode"], payload.get("included_schemas", []), payload.get("included_tables", []))
    except ValueError as exc:
        return {"valid": False, "normalized_scope": payload, "errors": [{"code": "connection_scope_invalid", "message": str(exc)}], "warnings": [], "impacts": []}
    discovery = await discover_scope(owner_id, connection_id)
    errors = validate_scope_inventory(scope, discovery["inventory"])
    impacts = await anyio.to_thread.run_sync(_impacts_sync, owner_id, connection_id, scope)
    warnings = [{"code": item["code"], "message": "An existing consumer references an object outside the proposed scope."} for item in impacts]
    return {"valid": not errors, "normalized_scope": scope, "errors": errors, "warnings": warnings, "impacts": impacts}


async def apply_scope(
    owner_id: str,
    connection_id: str,
    *,
    expected_revision: int,
    payload: dict,
    acknowledged_codes: list[str],
) -> dict:
    preview = await preview_scope(owner_id, connection_id, payload)
    if not preview["valid"]:
        raise BadRequestError("The proposed connection scope is invalid.", code="connection_scope_invalid")
    required = {item["code"] for item in preview["impacts"]}
    if required - set(acknowledged_codes):
        raise ConflictError("Scope impacts must be acknowledged before applying this change.", code="connection_scope_impact_acknowledgement_required")
    scope = preview["normalized_scope"]
    engine = await connection_manager.get_engine(owner_id, connection_id)
    schema = await anyio.to_thread.run_sync(
        lambda: schema_inspector.get_schema(
            engine,
            scope_mode=scope["mode"],
            included_schemas=scope["included_schemas"],
            included_tables=scope["included_tables"],
        )
    )
    if not schema:
        raise BadRequestError("The selected scope contains no accessible tables.", code="connection_scope_invalid")
    catalog = build_catalog(connection_id, "postgresql", schema)

    def persist():
        with session_scope() as session:
            return connection_repository.update_scope_and_snapshot_sync(
                session,
                user_id=owner_id,
                connection_id=connection_id,
                expected_revision=expected_revision,
                mode=scope["mode"],
                included_schemas=scope["included_schemas"],
                included_tables=scope["included_tables"],
                catalog=catalog,
            )

    try:
        updated = await anyio.to_thread.run_sync(persist)
    except connection_repository.ConnectionRevisionConflictError as exc:
        raise ConflictError(str(exc), code="connection_scope_conflict") from exc
    if not updated:
        raise NotFoundError("Database connection not found.", code="connection_not_found")
    invalidate_scope_cache(owner_id, connection_id)
    connection_pool.invalidate_schema_cache(owner_id, connection_id)
    connection_pool.cache_schema(owner_id, connection_id, schema)
    connection_pool.cache_catalog(owner_id, connection_id, catalog)
    from app.services.semantic_drift_service import revalidate
    await revalidate(
        owner_id,
        connection_id,
        catalog,
        "object_excluded_by_connection_scope",
    )
    return updated


async def get_automation(owner_id: str, connection_id: str) -> dict:
    connection = await _active(owner_id, connection_id)
    return {
        "connection_id": connection_id,
        "health_check_enabled": connection.health_check_enabled,
        "health_check_interval_minutes": connection.health_check_interval_minutes,
        "next_health_check_at": connection.next_health_check_at,
        "schema_refresh_enabled": connection.schema_refresh_enabled,
        "schema_refresh_interval_hours": connection.schema_refresh_interval_hours,
        "next_schema_refresh_at": connection.next_schema_refresh_at,
    }


async def update_automation(owner_id: str, connection_id: str, payload: dict) -> dict:
    await _active(owner_id, connection_id)
    def persist():
        with session_scope() as session:
            return connection_repository.update_automation_sync(
                session, user_id=owner_id, connection_id=connection_id, **payload
            )
    result = await anyio.to_thread.run_sync(persist)
    if not result:
        raise NotFoundError("Database connection not found.", code="connection_not_found")
    return result


async def health_history(owner_id: str, connection_id: str, *, cursor: str | None, limit: int) -> dict:
    result = await anyio.to_thread.run_sync(
        functools.partial(
            connection_health_repository.history,
            owner_id,
            connection_id,
            cursor=cursor,
            limit=max(1, min(100, limit)),
        )
    )
    if not result:
        raise NotFoundError("Database connection not found.", code="connection_not_found")
    return result


__all__ = [
    "apply_scope", "discover_scope", "get_automation", "get_scope", "health_history",
    "preview_scope", "rotate_credentials", "update_automation",
]
