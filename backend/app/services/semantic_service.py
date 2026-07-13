"""Business lifecycle for connection-scoped semantic definitions."""

from __future__ import annotations

import functools
import json
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

import anyio

from app.core.config import settings
from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.db.models.semantic import normalize_key, validate_payload, validate_safe_text
from app.db.repositories import semantic_repository as repository
from app.db.session import read_session_scope, session_scope
from app.query_engine.semantic_validation import (
    ValidationFinding,
    compile_preview,
    execute_preview,
    validate_structure,
)
from app.services import connection_service
from app.services import semantic_context_service
from app.agents.schema_context.user_semantics import apply_semantic_catalog_overlay


PREVIEW_KINDS = {"metric", "relationship", "filter", "date_policy"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _ensure_connection(owner_id: str, connection_id: str) -> None:
    if not await connection_service.get_connection(owner_id, connection_id):
        raise NotFoundError("Database connection not found.", code="semantic_definition_not_found")


def _map_repository_error(exc: Exception) -> Exception:
    if isinstance(exc, repository.SemanticNotFoundError):
        return NotFoundError(str(exc), code="semantic_definition_not_found")
    if isinstance(exc, repository.SemanticRevisionConflictError):
        return ConflictError(str(exc), code="semantic_definition_revision_conflict")
    if isinstance(exc, repository.SemanticDefinitionInUseError):
        return ConflictError(str(exc), code="semantic_definition_in_use")
    if isinstance(exc, repository.SemanticConflictError):
        return ConflictError(str(exc), code="semantic_definition_conflict")
    return exc


async def _write(operation: Callable[[Session], Any]) -> Any:
    def run():
        with session_scope() as session:
            return operation(session)

    return await anyio.to_thread.run_sync(run)


def _safe_inputs(
    *,
    kind: str,
    display_name: str,
    description: str,
    payload: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    try:
        safe_name = validate_safe_text(display_name, field_name="display_name", max_length=160)
        safe_description = description.strip()
        if safe_description:
            safe_description = validate_safe_text(
                safe_description, field_name="description", max_length=2000
            )
        typed_payload = validate_payload(kind, payload)
    except ValueError as exc:
        raise BadRequestError(str(exc), code="semantic_definition_invalid") from exc
    return safe_name, safe_description, typed_payload


async def create_definition(
    owner_id: str,
    connection_id: str,
    *,
    kind: str,
    key: str | None,
    display_name: str,
    description: str,
    payload: dict[str, Any],
    change_note: str | None = None,
) -> dict[str, Any]:
    if not settings.semantic_layer_enabled:
        raise BadRequestError("Semantic definitions are disabled.", code="semantic_layer_disabled")
    await _ensure_connection(owner_id, connection_id)
    safe_name, safe_description, typed_payload = _safe_inputs(
        kind=kind, display_name=display_name, description=description, payload=payload
    )
    try:
        stable_key = normalize_key(key or safe_name)

        def operation(session: Session):
            return repository.create_definition_sync(
                session,
                owner_id=owner_id,
                connection_id=connection_id,
                kind=kind,
                key=stable_key,
                display_name=safe_name,
                description=safe_description,
                payload=typed_payload,
                change_note=change_note,
            )

        definition = await _write(operation)
        return definition.model_dump(mode="json")
    except Exception as exc:
        mapped = _map_repository_error(exc)
        if mapped is not exc:
            raise mapped from exc
        raise


async def get_definition(owner_id: str, connection_id: str, definition_id: str) -> dict[str, Any]:
    await _ensure_connection(owner_id, connection_id)

    def run():
        with read_session_scope() as session:
            return repository.get_definition_model_sync(session, owner_id, connection_id, definition_id)

    definition = await anyio.to_thread.run_sync(run)
    if not definition:
        raise NotFoundError("Semantic definition not found.", code="semantic_definition_not_found")
    return definition.model_dump(mode="json")


async def list_definitions(
    owner_id: str,
    connection_id: str,
    *,
    kind: str | None = None,
    status: str | None = None,
    validation_status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    await _ensure_connection(owner_id, connection_id)
    page = max(1, page)
    page_size = max(1, min(100, page_size))

    def run():
        with read_session_scope() as session:
            return repository.list_definitions_sync(
                session,
                owner_id,
                connection_id,
                kind=kind,
                status=status,
                validation_status=validation_status,
                search=search,
                page=page,
                page_size=page_size,
            )

    items, total = await anyio.to_thread.run_sync(run)
    return {
        "items": [item.model_dump(mode="json") for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def update_draft(
    owner_id: str,
    connection_id: str,
    definition_id: str,
    *,
    expected_revision: int,
    display_name: str,
    description: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    current = await get_definition(owner_id, connection_id, definition_id)
    safe_name, safe_description, typed_payload = _safe_inputs(
        kind=current["kind"], display_name=display_name, description=description, payload=payload
    )
    try:
        def operation(session: Session):
            return repository.update_draft_sync(
                session,
                owner_id=owner_id,
                connection_id=connection_id,
                definition_id=definition_id,
                expected_revision=expected_revision,
                display_name=safe_name,
                description=safe_description,
                payload=typed_payload,
            )

        definition = await _write(operation)
        return definition.model_dump(mode="json")
    except Exception as exc:
        mapped = _map_repository_error(exc)
        if mapped is not exc:
            raise mapped from exc
        raise


async def create_version(
    owner_id: str,
    connection_id: str,
    definition_id: str,
    *,
    display_name: str,
    description: str,
    payload: dict[str, Any],
    change_note: str | None,
) -> dict[str, Any]:
    current = await get_definition(owner_id, connection_id, definition_id)
    safe_name, safe_description, typed_payload = _safe_inputs(
        kind=current["kind"], display_name=display_name, description=description, payload=payload
    )
    try:
        def operation(session: Session):
            return repository.create_version_sync(
                session,
                owner_id=owner_id,
                connection_id=connection_id,
                definition_id=definition_id,
                display_name=safe_name,
                description=safe_description,
                payload=typed_payload,
                change_note=change_note,
            )

        definition = await _write(operation)
        return definition.model_dump(mode="json")
    except Exception as exc:
        mapped = _map_repository_error(exc)
        if mapped is not exc:
            raise mapped from exc
        raise


async def delete_draft(owner_id: str, connection_id: str, definition_id: str) -> None:
    await _ensure_connection(owner_id, connection_id)
    try:
        def operation(session: Session):
            return repository.delete_draft_sync(
                session, owner_id, connection_id, definition_id
            )

        deleted = await _write(operation)
        if not deleted:
            raise NotFoundError("Semantic draft not found.", code="semantic_definition_not_found")
    except Exception as exc:
        mapped = _map_repository_error(exc)
        if mapped is not exc:
            raise mapped from exc
        raise


def _verified_map_sync(owner_id: str, connection_id: str) -> dict[str, dict[str, Any]]:
    with read_session_scope() as session:
        rows = repository.list_active_verified_sync(session, owner_id, connection_id)
        return {
            definition.id: {
                "id": definition.id,
                "kind": definition.kind,
                "key": definition.key,
                "version_id": version.id,
                "version": version.version,
                "display_name": version.display_name,
                "description": version.description,
                "payload": dict(version.payload or {}),
                "schema_hash": version.schema_hash,
            }
            for definition, version in rows
        }


def _append_synonym_conflicts(
    structural,
    definition: dict[str, Any],
    version: dict[str, Any],
    verified: dict[str, dict[str, Any]],
) -> None:
    phrase_targets: dict[tuple[str, str], set[str]] = {}
    for existing_id, existing in verified.items():
        existing_kind = existing["kind"]
        payload = existing.get("payload") or {}
        for phrase in payload.get("synonyms", []):
            phrase_targets.setdefault((existing_kind, str(phrase).strip().casefold()), set()).add(existing_id)
        if existing_kind == "synonym":
            target_id = str(payload.get("target_definition_id") or "")
            target = verified.get(target_id)
            phrase = str(payload.get("phrase") or "").strip().casefold()
            if target and phrase:
                phrase_targets.setdefault((target["kind"], phrase), set()).add(target_id)

    payload = version.get("payload") or {}
    proposed: list[tuple[str, str, str]] = []
    if definition["kind"] == "synonym":
        target_id = str(payload.get("target_definition_id") or "")
        target = verified.get(target_id)
        if target:
            proposed.append((target["kind"], str(payload.get("phrase") or ""), target_id))
    else:
        proposed.extend(
            (definition["kind"], str(phrase), definition["id"])
            for phrase in payload.get("synonyms", [])
        )
    for target_kind, phrase, target_id in proposed:
        normalized = phrase.strip().casefold()
        conflicts = phrase_targets.get((target_kind, normalized), set()) - {target_id}
        if normalized and conflicts:
            structural.errors.append(
                ValidationFinding(
                    "ambiguous_semantic_synonym",
                    f"The phrase '{phrase}' already targets another verified {target_kind} definition.",
                    "phrase" if definition["kind"] == "synonym" else "synonyms",
                )
            )


def _append_preview_findings(
    structural,
    *,
    definition: dict[str, Any],
    version: dict[str, Any],
    preview: dict[str, Any],
    catalog,
) -> None:
    kind = definition["kind"]
    payload = version["payload"]
    if kind == "relationship":
        left_duplicates = int(preview.get("left_duplicate_keys") or 0)
        right_duplicates = int(preview.get("right_duplicate_keys") or 0)
        cardinality = payload.get("cardinality")
        mismatch = (
            (cardinality == "one_to_one" and (left_duplicates or right_duplicates))
            or (cardinality == "one_to_many" and left_duplicates)
            or (cardinality == "many_to_one" and right_duplicates)
        )
        if mismatch:
            structural.warnings.append(
                ValidationFinding(
                    "relationship_cardinality_mismatch",
                    "Observed sampled duplicate keys do not match the declared cardinality.",
                    "cardinality",
                )
            )
    elif kind == "metric":
        previous = next(
            (
                item
                for item in definition.get("versions", [])
                if item.get("status") == "verified" and item.get("version") != version.get("version")
            ),
            None,
        )
        old_value = ((previous or {}).get("validation_report") or {}).get("preview", {}).get(
            "metric_value"
        )
        new_value = preview.get("metric_value")
        try:
            old_number = float(old_value)
            new_number = float(new_value)
            denominator = max(abs(old_number), 1.0)
            if abs(new_number - old_number) / denominator >= 0.2:
                structural.warnings.append(
                    ValidationFinding(
                        "metric_preview_material_change",
                        "The preview differs materially from the currently verified version.",
                    )
                )
        except (TypeError, ValueError):
            pass
    elif kind == "date_policy":
        table = next(
            (
                item
                for item in catalog.tables
                if item.name.casefold() == str(payload["table_name"]).casefold()
                or item.name.split(".")[-1].casefold()
                == str(payload["table_name"]).casefold()
            ),
            None,
        )
        column = next(
            (
                item
                for item in (table.columns if table else [])
                if item.name.casefold() == str(payload["column_name"]).casefold()
            ),
            None,
        )
        preview["physical_type"] = column.type if column else "unknown"
        preview["configured_timezone"] = payload.get("timezone")
        total = int(preview.get("total_count") or 0)
        nulls = int(preview.get("null_count") or 0)
        preview["null_percentage"] = round((nulls / total * 100), 2) if total else 0.0


async def validate_version(
    owner_id: str,
    connection_id: str,
    definition_id: str,
    version_number: int,
    *,
    run_preview: bool = True,
) -> dict[str, Any]:
    definition = await get_definition(owner_id, connection_id, definition_id)
    version = next((item for item in definition["versions"] if item["version"] == version_number), None)
    if not version:
        raise NotFoundError("Semantic definition version not found.", code="semantic_definition_not_found")
    if version["status"] != "draft":
        raise ConflictError("Only a draft can be validated for verification.", code="semantic_definition_conflict")

    catalog = await connection_service.get_catalog(owner_id, connection_id)
    if not catalog:
        raise BadRequestError("Schema metadata is unavailable.", code="semantic_preview_failed")
    verified = await anyio.to_thread.run_sync(_verified_map_sync, owner_id, connection_id)
    semantic_context = await semantic_context_service.load_context(
        owner_id,
        connection_id,
        catalog,
        json.dumps(version["payload"], default=str),
    )
    effective_catalog = apply_semantic_catalog_overlay(catalog, semantic_context)
    structural = validate_structure(
        definition["kind"],
        version["payload"],
        effective_catalog,
        verified_definitions=verified,
        description=version["description"],
    )
    preview: dict[str, Any] = {}
    _append_synonym_conflicts(structural, definition, version, verified)
    if not structural.errors and definition["kind"] in PREVIEW_KINDS:
        if not run_preview:
            structural.errors.append(
                ValidationFinding(
                    "semantic_preview_required",
                    "This definition requires a successful live preview before verification.",
                )
            )
        else:
            spec = compile_preview(
                definition["kind"],
                structural.normalized_payload,
                related_definitions=verified,
                sample_limit=settings.semantic_relationship_sample_limit,
            )
            if not spec:
                structural.errors.append(
                    ValidationFinding(
                        "semantic_preview_required", "This definition requires a live preview."
                    )
                )
            else:
                engine = await connection_service.get_engine(owner_id, connection_id)
                if not engine:
                    raise NotFoundError("Database connection not found.", code="semantic_definition_not_found")
                try:
                    preview = await anyio.to_thread.run_sync(
                        functools.partial(
                            execute_preview,
                            engine,
                            spec,
                            timeout_seconds=settings.semantic_preview_timeout_seconds,
                        )
                    )
                except Exception:
                    structural.errors.append(
                        ValidationFinding(
                            "semantic_preview_failed",
                            "The safe preview could not be completed. Check the connection and definition.",
                        )
                    )

    if preview:
        _append_preview_findings(
            structural,
            definition=definition,
            version=version,
            preview=preview,
            catalog=effective_catalog,
        )

    report = {
        "errors": [item.as_dict() for item in structural.errors],
        "warnings": [item.as_dict() for item in structural.warnings],
        "schema_hash": catalog.schema_hash,
        "normalized_payload": structural.normalized_payload,
        "preview": preview,
        "validated_at": _now().isoformat(),
    }
    status = "valid" if not structural.errors else "invalid"
    try:
        def operation(session: Session):
            return repository.save_validation_sync(
                session,
                owner_id=owner_id,
                connection_id=connection_id,
                definition_id=definition_id,
                version=version_number,
                schema_hash=catalog.schema_hash,
                validation_status=status,
                validation_report=report,
            )

        updated = await _write(operation)
        return updated.model_dump(mode="json")
    except Exception as exc:
        mapped = _map_repository_error(exc)
        if mapped is not exc:
            raise mapped from exc
        raise


async def verify_version(
    owner_id: str,
    connection_id: str,
    definition_id: str,
    version_number: int,
    *,
    expected_schema_hash: str,
    acknowledged_warning_codes: list[str],
    change_note: str | None,
) -> dict[str, Any]:
    catalog = await connection_service.get_catalog(owner_id, connection_id)
    if not catalog or catalog.schema_hash != expected_schema_hash:
        raise ConflictError(
            "The database schema changed after validation.",
            code="semantic_definition_stale",
        )
    definition = await get_definition(owner_id, connection_id, definition_id)
    target = next((item for item in definition["versions"] if item["version"] == version_number), None)
    if not target or target["validation_status"] != "valid":
        raise ConflictError("The draft has not passed validation.", code="semantic_definition_invalid")
    warning_codes = {
        item.get("code") for item in target["validation_report"].get("warnings", []) if item.get("code")
    }
    if warning_codes - set(acknowledged_warning_codes):
        raise ConflictError(
            "All validation warnings must be acknowledged.",
            code="semantic_warning_acknowledgement_required",
        )
    try:
        def operation(session: Session):
            return repository.verify_version_sync(
                session,
                owner_id=owner_id,
                connection_id=connection_id,
                definition_id=definition_id,
                version=version_number,
                expected_schema_hash=expected_schema_hash,
                acknowledged_warning_codes=acknowledged_warning_codes,
                change_note=change_note,
            )

        updated = await _write(operation)
        return updated.model_dump(mode="json")
    except Exception as exc:
        mapped = _map_repository_error(exc)
        if mapped is not exc:
            raise mapped from exc
        raise


async def deprecate_version(
    owner_id: str, connection_id: str, definition_id: str, version_number: int
) -> dict[str, Any]:
    await _ensure_connection(owner_id, connection_id)
    try:
        def operation(session: Session):
            return repository.deprecate_version_sync(
                session,
                owner_id=owner_id,
                connection_id=connection_id,
                definition_id=definition_id,
                version=version_number,
            )

        updated = await _write(operation)
        return updated.model_dump(mode="json")
    except Exception as exc:
        mapped = _map_repository_error(exc)
        if mapped is not exc:
            raise mapped from exc
        raise


async def summary(owner_id: str, connection_id: str) -> dict[str, Any]:
    await _ensure_connection(owner_id, connection_id)
    catalog = await connection_service.get_catalog(owner_id, connection_id)

    def run():
        with read_session_scope() as session:
            return repository.get_summary_sync(session, owner_id, connection_id)

    result = await anyio.to_thread.run_sync(run)
    return {"connection_id": connection_id, "schema_hash": catalog.schema_hash if catalog else None, **result}


async def impact(owner_id: str, connection_id: str, definition_id: str) -> list[dict[str, Any]]:
    await _ensure_connection(owner_id, connection_id)

    def run():
        with read_session_scope() as session:
            return repository.impact_sync(session, owner_id, connection_id, definition_id)

    try:
        return await anyio.to_thread.run_sync(run)
    except Exception as exc:
        mapped = _map_repository_error(exc)
        if mapped is not exc:
            raise mapped from exc
        raise


__all__ = [
    "create_definition",
    "create_version",
    "delete_draft",
    "deprecate_version",
    "get_definition",
    "impact",
    "list_definitions",
    "summary",
    "update_draft",
    "validate_version",
    "verify_version",
]
