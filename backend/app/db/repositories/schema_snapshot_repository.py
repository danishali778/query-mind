"""Persisted schema catalog snapshots."""

from __future__ import annotations

from datetime import datetime, timezone

from app.agents.schema_context.types import SchemaCatalog
from app.db.orm_models import SchemaSnapshotORM
from app.db.session import read_session_scope, session_scope


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get(owner_id: str, connection_id: str) -> SchemaCatalog | None:
    with read_session_scope() as db:
        row = (
            db.query(SchemaSnapshotORM)
            .filter(
                SchemaSnapshotORM.owner_id == owner_id,
                SchemaSnapshotORM.connection_id == connection_id,
            )
            .one_or_none()
        )
        if not row:
            return None
        return SchemaCatalog.model_validate(row.catalog_json)


def upsert(catalog: SchemaCatalog, owner_id: str) -> None:
    payload = catalog.model_dump()
    with session_scope() as db:
        row = (
            db.query(SchemaSnapshotORM)
            .filter(
                SchemaSnapshotORM.owner_id == owner_id,
                SchemaSnapshotORM.connection_id == catalog.connection_id,
            )
            .one_or_none()
        )
        if row:
            row.schema_hash = catalog.schema_hash
            row.db_type = catalog.db_type
            row.catalog_json = payload
            row.updated_at = _utcnow()
        else:
            db.add(
                SchemaSnapshotORM(
                    owner_id=owner_id,
                    connection_id=catalog.connection_id,
                    schema_hash=catalog.schema_hash,
                    db_type=catalog.db_type,
                    catalog_json=payload,
                )
            )


def delete(owner_id: str, connection_id: str) -> bool:
    with session_scope() as db:
        row = (
            db.query(SchemaSnapshotORM)
            .filter(
                SchemaSnapshotORM.owner_id == owner_id,
                SchemaSnapshotORM.connection_id == connection_id,
            )
            .one_or_none()
        )
        if not row:
            return False
        db.delete(row)
        return True


__all__ = ["get", "upsert", "delete"]
