"""Connection persistence and settings access using SQLAlchemy."""

from app.core.security import decrypt, encrypt
from app.db.models.connection import ActiveConnection, ConnectionRequest
from app.db.orm_models import DatabaseConnectionORM
from app.db.session import session_scope


def _row_to_active_connection(row: DatabaseConnectionORM) -> ActiveConnection:
    return ActiveConnection(
        id=row.id,
        owner_id=row.owner_id,
        name=row.name,
        db_type=row.db_type,
        database=row.database,
        host=row.host,
        port=row.port,
        username=row.username,
        status="connected",
        tables_count=0,
        ssl_mode=row.ssl_mode or "disable",
        readonly=True if row.readonly is None else row.readonly,
        use_ssh=bool(row.use_ssh),
        ssh_host=row.ssh_host,
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
        readonly=True if row.readonly is None else row.readonly,
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
        readonly=getattr(config, "readonly", True),
        use_ssh=getattr(config, "use_ssh", False),
        ssh_host=getattr(config, "ssh_host", None),
        ssh_port=getattr(config, "ssh_port", 22),
        ssh_username=getattr(config, "ssh_username", None),
        ssh_password=encrypt(config.ssh_password) if getattr(config, "ssh_password", None) else None,
        ssh_private_key=encrypt(config.ssh_private_key) if getattr(config, "ssh_private_key", None) else None,
    )


async def create_connection(user_id: str, config: ConnectionRequest) -> str:
    with session_scope() as session:
        row = _connection_row(user_id, config)
        session.add(row)
        session.flush()
        return row.id


async def list_connections(user_id: str) -> list[ActiveConnection]:
    with session_scope() as session:
        rows = (
            session.query(DatabaseConnectionORM)
            .filter(DatabaseConnectionORM.owner_id == user_id)
            .order_by(DatabaseConnectionORM.created_at.desc())
            .all()
        )
        return [_row_to_active_connection(row) for row in rows]


async def get_connection_row(user_id: str, connection_id: str) -> dict | None:
    with session_scope() as session:
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
            "readonly": row.readonly,
            "use_ssh": row.use_ssh,
            "ssh_host": row.ssh_host,
            "ssh_port": row.ssh_port,
            "ssh_username": row.ssh_username,
            "ssh_password": row.ssh_password,
            "ssh_private_key": row.ssh_private_key,
        }


async def get_connection_config(user_id: str, connection_id: str) -> ConnectionRequest | None:
    with session_scope() as session:
        row = (
            session.query(DatabaseConnectionORM)
            .filter(DatabaseConnectionORM.id == connection_id, DatabaseConnectionORM.owner_id == user_id)
            .one_or_none()
        )
        if not row:
            return None
        return _row_to_connection_request(row)


async def delete_connection(user_id: str, connection_id: str) -> bool:
    with session_scope() as session:
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
    readonly: bool | None,
) -> bool:
    with session_scope() as session:
        row = (
            session.query(DatabaseConnectionORM)
            .filter(DatabaseConnectionORM.id == connection_id, DatabaseConnectionORM.owner_id == user_id)
            .one_or_none()
        )
        if not row:
            return False
        if ssl_mode is not None:
            row.ssl_mode = ssl_mode
        if readonly is not None:
            row.readonly = readonly
        return True


async def get_readonly_setting(user_id: str, connection_id: str) -> bool:
    with session_scope() as session:
        row = (
            session.query(DatabaseConnectionORM.readonly)
            .filter(DatabaseConnectionORM.id == connection_id, DatabaseConnectionORM.owner_id == user_id)
            .one_or_none()
        )
        if not row:
            return True
        return True if row.readonly is None else bool(row.readonly)


async def find_dev_connection(owner_id: str, name: str) -> str | None:
    with session_scope() as session:
        row = (
            session.query(DatabaseConnectionORM.id)
            .filter(DatabaseConnectionORM.owner_id == owner_id, DatabaseConnectionORM.name == name)
            .one_or_none()
        )
        return row.id if row else None


__all__ = [
    "create_connection",
    "list_connections",
    "get_connection_row",
    "get_connection_config",
    "delete_connection",
    "update_connection_settings_record",
    "get_readonly_setting",
    "find_dev_connection",
]