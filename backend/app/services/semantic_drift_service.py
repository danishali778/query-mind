"""Revalidates verified semantic definitions after physical schema refresh."""

from __future__ import annotations

from datetime import datetime, timezone

import anyio

from app.core.config import settings
from app.db.repositories import semantic_repository
from app.db.session import session_scope
from app.query_engine.semantic_validation import validate_structure


def revalidate_sync(owner_id: str, connection_id: str, catalog) -> dict[str, int]:
    if not settings.semantic_layer_enabled:
        return {"valid": 0, "stale": 0}
    counts = {"valid": 0, "stale": 0}
    with session_scope() as session:
        rows = semantic_repository.list_active_verified_sync(session, owner_id, connection_id)
        # list_active_verified_sync intentionally excludes already-stale rows. Those
        # remain historical until an owner creates a corrected version.
        for definition, version in rows:
            structural = validate_structure(definition.kind, dict(version.payload or {}), catalog)
            status = "stale" if structural.errors else "valid"
            prior_report = dict(version.validation_report or {})
            report = {
                **prior_report,
                "errors": [item.as_dict() for item in structural.errors],
                "warnings": [item.as_dict() for item in structural.warnings],
                "schema_hash": catalog.schema_hash,
                "normalized_payload": structural.normalized_payload,
                "schema_drift_revalidated_at": datetime.now(timezone.utc).isoformat(),
            }
            semantic_repository.update_verified_validation_sync(
                session,
                owner_id=owner_id,
                connection_id=connection_id,
                version_id=version.id,
                schema_hash=catalog.schema_hash,
                validation_status=status,
                validation_report=report,
            )
            counts[status] += 1
    return counts


async def revalidate(owner_id: str, connection_id: str, catalog) -> dict[str, int]:
    return await anyio.to_thread.run_sync(revalidate_sync, owner_id, connection_id, catalog)


__all__ = ["revalidate", "revalidate_sync"]
