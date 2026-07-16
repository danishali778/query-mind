"""Connection persistence and settings access using SQLAlchemy."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import anyio
from sqlalchemy.orm import Session

from app.core.security import decrypt, encrypt
from app.db.models.connection import ActiveConnection, ConnectionRequest, derive_connection_status
from app.db.orm_models import DatabaseConnectionORM
from app.db.models.connection import TableInfo
from app.db.repositories import connection_health_repository, schema_snapshot_repository
from app.db.sentinels import UNSET
from app.db.session import read_session_scope, session_scope


class ConnectionRevisionConflictError(RuntimeError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _row_to_active_connection(row: DatabaseConnectionORM) -> ActiveConnection:
    health_state, status = derive_connection_status(row.last_status, row.last_tested_at)
    return ActiveConnection(
        id=row.id,
        owner_id=row.owner_id,
        name=row.name,
        db_type=row.db_type,
        database=row.database,
        host=row.host,
        port=row.port,
        username=row.username,
        status=status,
        health_state=health_state,
        tables_count=0,
        ssl_mode=row.ssl_mode or "disable",
        readonly=True,
        use_ssh=bool(row.use_ssh),
        ssh_host=row.ssh_host,
        last_tested_at=_normalize_utc(row.last_tested_at),
        last_status=row.last_status or "unknown",
        last_error=row.last_error,
        latency_ms=row.latency_ms,
        last_schema_sync_at=_normalize_utc(row.last_schema_sync_at),
        credential_revision=row.credential_revision or 1,
        credentials_updated_at=_normalize_utc(row.credentials_updated_at),
        has_ssl_root_certificate=bool(row.ssl_root_certificate),
        has_ssl_client_certificate=bool(row.ssl_client_certificate),
        has_ssl_client_private_key=bool(row.ssl_client_private_key),
        scope_mode=row.scope_mode or "all",
        included_schemas=list(row.included_schemas or []),
        included_tables=list(row.included_tables or []),
        scope_revision=row.scope_revision or 1,
        scope_updated_at=_normalize_utc(row.scope_updated_at),
        health_check_enabled=bool(row.health_check_enabled),
        health_check_interval_minutes=row.health_check_interval_minutes or 60,
        next_health_check_at=_normalize_utc(row.next_health_check_at),
        schema_refresh_enabled=bool(row.schema_refresh_enabled),
        schema_refresh_interval_hours=row.schema_refresh_interval_hours or 24,
        next_schema_refresh_at=_normalize_utc(row.next_schema_refresh_at),
    )


def _row_to_connection_request(row: DatabaseConnectionORM) -> ConnectionRequest:
    return ConnectionRequest(
        owner_id=row.owner_id,
        name=row.name,
        db_type=row.db_type,
        host=row.host,
        port=row.port,
        database=row.database,
        username=row.username,
        password=decrypt(row.password) if row.password else None,
        ssl_mode=row.ssl_mode or "disable",
        readonly=True,
        use_ssh=bool(row.use_ssh),
        ssh_host=row.ssh_host,
        ssh_port=row.ssh_port or 22,
        ssh_username=row.ssh_username,
        ssh_password=decrypt(row.ssh_password) if row.ssh_password else None,
        ssh_private_key=decrypt(row.ssh_private_key) if row.ssh_private_key else None,
        ssl_root_certificate=decrypt(row.ssl_root_certificate) if row.ssl_root_certificate else None,
        ssl_client_certificate=decrypt(row.ssl_client_certificate) if row.ssl_client_certificate else None,
        ssl_client_private_key=decrypt(row.ssl_client_private_key) if row.ssl_client_private_key else None,
        scope_mode=row.scope_mode or "all",
        included_schemas=list(row.included_schemas or []),
        included_tables=list(row.included_tables or []),
    )


def _connection_row(user_id: str, config: ConnectionRequest) -> DatabaseConnectionORM:
    return DatabaseConnectionORM(
        owner_id=user_id,
        name=config.name or f"{config.db_type}-{config.database}",
        db_type=config.db_type,
        host=config.host,
        port=config.port,
        database=config.database,
        username=config.username,
        password=encrypt(config.password) if config.password else None,
        ssl_mode=getattr(config, "ssl_mode", "disable"),
        readonly=True,
        use_ssh=getattr(config, "use_ssh", False),
        ssh_host=getattr(config, "ssh_host", None),
        ssh_port=getattr(config, "ssh_port", 22),
        ssh_username=getattr(config, "ssh_username", None),
        ssh_password=encrypt(config.ssh_password) if getattr(config, "ssh_password", None) else None,
        ssh_private_key=encrypt(config.ssh_private_key) if getattr(config, "ssh_private_key", None) else None,
        ssl_root_certificate=encrypt(config.ssl_root_certificate) if config.ssl_root_certificate else None,
        ssl_client_certificate=encrypt(config.ssl_client_certificate) if config.ssl_client_certificate else None,
        ssl_client_private_key=encrypt(config.ssl_client_private_key) if config.ssl_client_private_key else None,
        scope_mode=config.scope_mode,
        included_schemas=list(config.included_schemas),
        included_tables=list(config.included_tables),
        last_status="unknown",
    )


async def create_connection(user_id: str, config: ConnectionRequest) -> str:
    def _run() -> str:
        with session_scope() as session:
            return _create_connection_sync(session, user_id, config)
    return await anyio.to_thread.run_sync(_run)


def _create_connection_sync(session: Session, user_id: str, config: ConnectionRequest) -> str:
    row = _connection_row(user_id, config)
    session.add(row)
    session.flush()
    return row.id


async def list_connections(user_id: str) -> list[ActiveConnection]:
    def _run() -> list[ActiveConnection]:
        with read_session_scope() as session:
            return _list_connections_sync(session, user_id)
    return await anyio.to_thread.run_sync(_run)


def _list_connections_sync(session: Session, user_id: str) -> list[ActiveConnection]:
    rows = (
        session.query(DatabaseConnectionORM)
        .filter(DatabaseConnectionORM.owner_id == user_id)
        .order_by(DatabaseConnectionORM.created_at.desc())
        .all()
    )
    return [_row_to_active_connection(row) for row in rows]


def _get_active_connection_sync(session: Session, user_id: str, connection_id: str) -> ActiveConnection | None:
    row = (
        session.query(DatabaseConnectionORM)
        .filter(DatabaseConnectionORM.id == connection_id, DatabaseConnectionORM.owner_id == user_id)
        .one_or_none()
    )
    if not row:
        return None
    return _row_to_active_connection(row)


def sync_get_active_connection(user_id: str, connection_id: str) -> ActiveConnection | None:
    with read_session_scope() as session:
        return _get_active_connection_sync(session, user_id, connection_id)


async def get_active_connection(user_id: str, connection_id: str) -> ActiveConnection | None:
    def _run() -> ActiveConnection | None:
        with read_session_scope() as session:
            return _get_active_connection_sync(session, user_id, connection_id)
    return await anyio.to_thread.run_sync(_run)


async def get_connection_row(user_id: str, connection_id: str) -> dict | None:
    def _run() -> dict | None:
        with read_session_scope() as session:
            return _get_connection_row_sync(session, user_id, connection_id)
    return await anyio.to_thread.run_sync(_run)


def _get_connection_row_sync(session: Session, user_id: str, connection_id: str) -> dict | None:
    row = (
        session.query(DatabaseConnectionORM)
        .filter(DatabaseConnectionORM.id == connection_id, DatabaseConnectionORM.owner_id == user_id)
        .one_or_none()
    )
    if not row:
        return None
    return {
        "id": row.id,
        "owner_id": row.owner_id,
        "name": row.name,
        "db_type": row.db_type,
        "host": row.host,
        "port": row.port,
        "database": row.database,
        "username": row.username,
        "password": row.password,
        "ssl_mode": row.ssl_mode,
        "readonly": True,
        "use_ssh": row.use_ssh,
        "ssh_host": row.ssh_host,
        "ssh_port": row.ssh_port,
        "ssh_username": row.ssh_username,
        "ssh_password": row.ssh_password,
        "ssh_private_key": row.ssh_private_key,
        "last_tested_at": _normalize_utc(row.last_tested_at),
        "last_status": row.last_status or "unknown",
        "last_error": row.last_error,
        "latency_ms": row.latency_ms,
        "last_schema_sync_at": _normalize_utc(row.last_schema_sync_at),
        "credential_revision": row.credential_revision or 1,
        "credentials_updated_at": _normalize_utc(row.credentials_updated_at),
        "has_ssl_root_certificate": bool(row.ssl_root_certificate),
        "has_ssl_client_certificate": bool(row.ssl_client_certificate),
        "has_ssl_client_private_key": bool(row.ssl_client_private_key),
        "scope_mode": row.scope_mode or "all",
        "included_schemas": list(row.included_schemas or []),
        "included_tables": list(row.included_tables or []),
        "scope_revision": row.scope_revision or 1,
        "scope_updated_at": _normalize_utc(row.scope_updated_at),
        "health_check_enabled": bool(row.health_check_enabled),
        "health_check_interval_minutes": row.health_check_interval_minutes or 60,
        "next_health_check_at": _normalize_utc(row.next_health_check_at),
        "schema_refresh_enabled": bool(row.schema_refresh_enabled),
        "schema_refresh_interval_hours": row.schema_refresh_interval_hours or 24,
        "next_schema_refresh_at": _normalize_utc(row.next_schema_refresh_at),
    }


async def get_connection_config(user_id: str, connection_id: str) -> ConnectionRequest | None:
    def _run() -> ConnectionRequest | None:
        with read_session_scope() as session:
            return _get_connection_config_sync(session, user_id, connection_id)
    return await anyio.to_thread.run_sync(_run)


def _get_connection_config_sync(session: Session, user_id: str, connection_id: str) -> ConnectionRequest | None:
    row = (
        session.query(DatabaseConnectionORM)
        .filter(DatabaseConnectionORM.id == connection_id, DatabaseConnectionORM.owner_id == user_id)
        .one_or_none()
    )
    if not row:
        return None
    return _row_to_connection_request(row)


async def delete_connection(user_id: str, connection_id: str) -> bool:
    def _run() -> bool:
        with session_scope() as session:
            return _delete_connection_sync(session, user_id, connection_id)
    return await anyio.to_thread.run_sync(_run)


def _delete_connection_sync(session: Session, user_id: str, connection_id: str) -> bool:
    row = (
        session.query(DatabaseConnectionORM)
        .filter(DatabaseConnectionORM.id == connection_id, DatabaseConnectionORM.owner_id == user_id)
        .one_or_none()
    )
    if not row:
        return False
    session.delete(row)
    return True


async def update_connection_settings_record(
    user_id: str,
    connection_id: str,
    ssl_mode: str | None,
) -> bool:
    def _run() -> bool:
        with session_scope() as session:
            return _update_connection_settings_record_sync(session, user_id, connection_id, ssl_mode)
    return await anyio.to_thread.run_sync(_run)


async def create_connection_bundle(
    user_id: str,
    config: ConnectionRequest,
    schema: list[TableInfo],
    *,
    latency_ms: float,
) -> tuple[str, Any]:
    from app.agents.schema_context.catalog import build_catalog

    def _run():
        with session_scope() as session:
            row = _connection_row(user_id, config)
            session.add(row)
            session.flush()
            catalog = build_catalog(row.id, config.db_type, schema)
            schema_snapshot_repository.upsert_sync(session, catalog, user_id)
            _record_connection_health_sync(
                session,
                user_id,
                row.id,
                last_status="healthy",
                last_error=None,
                latency_ms=latency_ms,
            )
            _record_schema_sync_sync(session, user_id, row.id)
            connection_health_repository.record_sync(
                session,
                owner_id=user_id,
                connection_id=row.id,
                source="initial_connect",
                status="healthy",
                diagnostic_code="connection_healthy",
                message="Connection established and schema synchronized.",
                latency_ms=latency_ms,
            )
            session.flush()
            return row.id, catalog
    return await anyio.to_thread.run_sync(_run)


def rotate_credentials_sync(
    session: Session,
    *,
    user_id: str,
    connection_id: str,
    expected_revision: int,
    config: ConnectionRequest,
) -> int:
    row = session.query(DatabaseConnectionORM).filter(
        DatabaseConnectionORM.id == connection_id,
        DatabaseConnectionORM.owner_id == user_id,
    ).with_for_update().one_or_none()
    if not row:
        return 0
    if row.credential_revision != expected_revision:
        raise ConnectionRevisionConflictError("Connection credentials changed in another request.")
    row.username = config.username
    row.password = encrypt(config.password) if config.password else None
    row.ssl_mode = config.ssl_mode
    row.ssl_root_certificate = encrypt(config.ssl_root_certificate) if config.ssl_root_certificate else None
    row.ssl_client_certificate = encrypt(config.ssl_client_certificate) if config.ssl_client_certificate else None
    row.ssl_client_private_key = encrypt(config.ssl_client_private_key) if config.ssl_client_private_key else None
    row.ssh_username = config.ssh_username
    row.ssh_password = encrypt(config.ssh_password) if config.ssh_password else None
    row.ssh_private_key = encrypt(config.ssh_private_key) if config.ssh_private_key else None
    row.credential_revision += 1
    row.credentials_updated_at = _utcnow()
    row.last_status = "healthy"
    row.last_error = None
    row.last_tested_at = _utcnow()
    session.flush()
    return row.credential_revision


def get_scope_sync(session: Session, user_id: str, connection_id: str) -> dict | None:
    row = session.query(DatabaseConnectionORM).filter(
        DatabaseConnectionORM.id == connection_id,
        DatabaseConnectionORM.owner_id == user_id,
    ).one_or_none()
    if not row:
        return None
    return {
        "connection_id": row.id,
        "mode": row.scope_mode or "all",
        "included_schemas": list(row.included_schemas or []),
        "included_tables": list(row.included_tables or []),
        "revision": row.scope_revision or 1,
        "updated_at": _normalize_utc(row.scope_updated_at),
    }


def update_scope_sync(
    session: Session,
    *,
    user_id: str,
    connection_id: str,
    expected_revision: int,
    mode: str,
    included_schemas: list[str],
    included_tables: list[str],
) -> dict | None:
    row = session.query(DatabaseConnectionORM).filter(
        DatabaseConnectionORM.id == connection_id,
        DatabaseConnectionORM.owner_id == user_id,
    ).with_for_update().one_or_none()
    if not row:
        return None
    if row.scope_revision != expected_revision:
        raise ConnectionRevisionConflictError("Connection scope changed in another request.")
    row.scope_mode = mode
    row.included_schemas = list(included_schemas)
    row.included_tables = list(included_tables)
    row.scope_revision += 1
    row.scope_updated_at = _utcnow()
    session.flush()
    return get_scope_sync(session, user_id, connection_id)


def update_scope_and_snapshot_sync(
    session: Session,
    *,
    user_id: str,
    connection_id: str,
    expected_revision: int,
    mode: str,
    included_schemas: list[str],
    included_tables: list[str],
    catalog,
) -> dict | None:
    updated = update_scope_sync(
        session,
        user_id=user_id,
        connection_id=connection_id,
        expected_revision=expected_revision,
        mode=mode,
        included_schemas=included_schemas,
        included_tables=included_tables,
    )
    if not updated:
        return None
    schema_snapshot_repository.upsert_sync(session, catalog, user_id)
    return updated


def update_automation_sync(
    session: Session,
    *,
    user_id: str,
    connection_id: str,
    health_check_enabled: bool,
    health_check_interval_minutes: int,
    schema_refresh_enabled: bool,
    schema_refresh_interval_hours: int,
) -> dict | None:
    row = session.query(DatabaseConnectionORM).filter(
        DatabaseConnectionORM.id == connection_id,
        DatabaseConnectionORM.owner_id == user_id,
    ).with_for_update().one_or_none()
    if not row:
        return None
    now = _utcnow()
    row.health_check_enabled = health_check_enabled
    row.health_check_interval_minutes = health_check_interval_minutes
    row.next_health_check_at = now + timedelta(minutes=health_check_interval_minutes) if health_check_enabled else None
    row.schema_refresh_enabled = schema_refresh_enabled
    row.schema_refresh_interval_hours = schema_refresh_interval_hours
    row.next_schema_refresh_at = now + timedelta(hours=schema_refresh_interval_hours) if schema_refresh_enabled else None
    session.flush()
    return {
        "connection_id": row.id,
        "health_check_enabled": row.health_check_enabled,
        "health_check_interval_minutes": row.health_check_interval_minutes,
        "next_health_check_at": _normalize_utc(row.next_health_check_at),
        "schema_refresh_enabled": row.schema_refresh_enabled,
        "schema_refresh_interval_hours": row.schema_refresh_interval_hours,
        "next_schema_refresh_at": _normalize_utc(row.next_schema_refresh_at),
    }


def due_maintenance_sync(session: Session, limit: int = 100) -> list[dict]:
    now = _utcnow()
    rows = session.query(DatabaseConnectionORM).filter(
        (
            (DatabaseConnectionORM.health_check_enabled.is_(True))
            & (DatabaseConnectionORM.next_health_check_at.is_not(None))
            & (DatabaseConnectionORM.next_health_check_at <= now)
        )
        | (
            (DatabaseConnectionORM.schema_refresh_enabled.is_(True))
            & (DatabaseConnectionORM.next_schema_refresh_at.is_not(None))
            & (DatabaseConnectionORM.next_schema_refresh_at <= now)
        )
    ).order_by(DatabaseConnectionORM.created_at.asc()).limit(limit).all()
    return [
        {
            "id": row.id,
            "owner_id": row.owner_id,
            "health_due": bool(row.health_check_enabled and row.next_health_check_at and row.next_health_check_at <= now),
            "schema_due": bool(row.schema_refresh_enabled and row.next_schema_refresh_at and row.next_schema_refresh_at <= now),
        }
        for row in rows
    ]


def advance_maintenance_sync(
    session: Session, connection_id: str, *, health: bool = False, schema: bool = False
) -> None:
    row = session.query(DatabaseConnectionORM).filter(DatabaseConnectionORM.id == connection_id).one_or_none()
    if not row:
        return
    now = _utcnow()
    if health and row.health_check_enabled:
        row.next_health_check_at = now + timedelta(minutes=row.health_check_interval_minutes)
    if schema and row.schema_refresh_enabled:
        row.next_schema_refresh_at = now + timedelta(hours=row.schema_refresh_interval_hours)


def _update_connection_settings_record_sync(
    session: Session,
    user_id: str,
    connection_id: str,
    ssl_mode: str | None,
) -> bool:
    row = (
        session.query(DatabaseConnectionORM)
        .filter(DatabaseConnectionORM.id == connection_id, DatabaseConnectionORM.owner_id == user_id)
        .one_or_none()
    )
    if not row:
        return False
    if ssl_mode is not None:
        row.ssl_mode = ssl_mode
    row.readonly = True
    return True


async def get_readonly_setting(user_id: str, connection_id: str) -> bool:
    return True


async def find_dev_connection(owner_id: str, name: str) -> str | None:
    def _run() -> str | None:
        with read_session_scope() as session:
            return _find_dev_connection_sync(session, owner_id, name)
    return await anyio.to_thread.run_sync(_run)


def _find_dev_connection_sync(session: Session, owner_id: str, name: str) -> str | None:
    row = (
        session.query(DatabaseConnectionORM.id)
        .filter(DatabaseConnectionORM.owner_id == owner_id, DatabaseConnectionORM.name == name)
        .one_or_none()
    )
    return row.id if row else None


def _record_connection_health_sync(
    session: Session,
    user_id: str,
    connection_id: str,
    *,
    last_status: str,
    last_error: str | None | object = UNSET,
    latency_ms: float | None | object = UNSET,
    tested_at: datetime | None = None,
) -> bool:
    row = (
        session.query(DatabaseConnectionORM)
        .filter(DatabaseConnectionORM.id == connection_id, DatabaseConnectionORM.owner_id == user_id)
        .one_or_none()
    )
    if not row:
        return False
    row.last_status = last_status
    row.last_tested_at = _normalize_utc(tested_at or _utcnow())
    if last_error is not UNSET:
        row.last_error = last_error
    if latency_ms is not UNSET:
        row.latency_ms = latency_ms
    return True


def sync_record_connection_health(
    user_id: str,
    connection_id: str,
    *,
    last_status: str,
    last_error: str | None | object = UNSET,
    latency_ms: float | None | object = UNSET,
    tested_at: datetime | None = None,
) -> bool:
    with session_scope() as session:
        return _record_connection_health_sync(
            session,
            user_id,
            connection_id,
            last_status=last_status,
            last_error=last_error,
            latency_ms=latency_ms,
            tested_at=tested_at,
        )


async def record_connection_health(
    user_id: str,
    connection_id: str,
    *,
    last_status: str,
    last_error: str | None | object = UNSET,
    latency_ms: float | None | object = UNSET,
    tested_at: datetime | None = None,
) -> bool:
    def _run() -> bool:
        with session_scope() as session:
            return _record_connection_health_sync(
                session,
                user_id,
                connection_id,
                last_status=last_status,
                last_error=last_error,
                latency_ms=latency_ms,
                tested_at=tested_at,
            )
    return await anyio.to_thread.run_sync(_run)


def _record_schema_sync_sync(
    session: Session,
    user_id: str,
    connection_id: str,
    *,
    synced_at: datetime | None = None,
) -> bool:
    row = (
        session.query(DatabaseConnectionORM)
        .filter(DatabaseConnectionORM.id == connection_id, DatabaseConnectionORM.owner_id == user_id)
        .one_or_none()
    )
    if not row:
        return False
    row.last_schema_sync_at = _normalize_utc(synced_at or _utcnow())
    return True


def sync_record_schema_sync(
    user_id: str,
    connection_id: str,
    *,
    synced_at: datetime | None = None,
) -> bool:
    with session_scope() as session:
        return _record_schema_sync_sync(session, user_id, connection_id, synced_at=synced_at)


async def record_schema_sync(
    user_id: str,
    connection_id: str,
    *,
    synced_at: datetime | None = None,
) -> bool:
    def _run() -> bool:
        with session_scope() as session:
            return _record_schema_sync_sync(session, user_id, connection_id, synced_at=synced_at)
    return await anyio.to_thread.run_sync(_run)


async def record_health_and_schema_sync(
    user_id: str,
    connection_id: str,
    *,
    last_status: str,
    last_error: str | None | object = UNSET,
    latency_ms: float | None | object = UNSET,
    tested_at: datetime | None = None,
    synced_at: datetime | None = None,
) -> bool:
    """Record connection health and the schema-sync timestamp in one transaction.

    Atomicity note: this flow commits atomically — both fields are written to
    the same connection row in a single session/transaction, replacing two
    separate pool checkouts (record_connection_health + record_schema_sync)
    with one.
    """
    def _run() -> bool:
        with session_scope() as session:
            health_ok = _record_connection_health_sync(
                session,
                user_id,
                connection_id,
                last_status=last_status,
                last_error=last_error,
                latency_ms=latency_ms,
                tested_at=tested_at,
            )
            if not health_ok:
                return False
            return _record_schema_sync_sync(session, user_id, connection_id, synced_at=synced_at)
    return await anyio.to_thread.run_sync(_run)


__all__ = [
    "create_connection",
    "create_connection_bundle",
    "list_connections",
    "get_active_connection",
    "sync_get_active_connection",
    "get_connection_row",
    "get_connection_config",
    "delete_connection",
    "update_connection_settings_record",
    "get_readonly_setting",
    "find_dev_connection",
    "record_connection_health",
    "sync_record_connection_health",
    "record_schema_sync",
    "sync_record_schema_sync",
    "record_health_and_schema_sync",
    "ConnectionRevisionConflictError",
    "rotate_credentials_sync",
    "get_scope_sync",
    "update_scope_sync",
    "update_scope_and_snapshot_sync",
    "update_automation_sync",
    "due_maintenance_sync",
    "advance_maintenance_sync",
]
