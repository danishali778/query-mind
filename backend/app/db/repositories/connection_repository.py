"""Connection persistence and settings access using SQLAlchemy."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import anyio
from sqlalchemy.orm import Session

from app.core.security import decrypt, encrypt
from app.db.models.connection import ActiveConnection, ConnectionRequest, derive_connection_status
from app.db.orm_models import DatabaseConnectionORM
from app.db.session import read_session_scope, session_scope


_UNSET = object()


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
    last_error: str | None | object = _UNSET,
    latency_ms: float | None | object = _UNSET,
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
    if last_error is not _UNSET:
        row.last_error = last_error
    if latency_ms is not _UNSET:
        row.latency_ms = latency_ms
    return True


def sync_record_connection_health(
    user_id: str,
    connection_id: str,
    *,
    last_status: str,
    last_error: str | None | object = _UNSET,
    latency_ms: float | None | object = _UNSET,
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
    last_error: str | None | object = _UNSET,
    latency_ms: float | None | object = _UNSET,
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
    last_error: str | None | object = _UNSET,
    latency_ms: float | None | object = _UNSET,
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
]
