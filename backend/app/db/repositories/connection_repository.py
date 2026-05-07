"""Connection persistence and settings access."""

from app.db.models.connection import ActiveConnection, ConnectionRequest
from app.db.retry import async_supabase_retry
from app.integrations.supabase_db import async_supabase
from app.core.security import decrypt, encrypt


def _row_to_active_connection(row: dict) -> ActiveConnection:
    return ActiveConnection(
        id=row["id"],
        owner_id=row["owner_id"],
        name=row["name"],
        db_type=row["db_type"],
        database=row["database"],
        host=row.get("host"),
        port=row.get("port"),
        username=row.get("username"),
        status="connected",
        tables_count=row.get("tables_count", 0),
        ssl_mode=row.get("ssl_mode", "disable"),
        readonly=row.get("readonly", True),
        use_ssh=row.get("use_ssh", False),
        ssh_host=row.get("ssh_host"),
    )


def _row_to_connection_request(row: dict) -> ConnectionRequest:
    return ConnectionRequest(
        owner_id=row.get("owner_id"),
        name=row.get("name"),
        db_type=row["db_type"],
        host=row.get("host"),
        port=row.get("port"),
        database=row["database"],
        username=row.get("username"),
        password=decrypt(row.get("password")) if row.get("password") else None,
        ssl_mode=row.get("ssl_mode", "disable"),
        readonly=row.get("readonly", True),
        use_ssh=row.get("use_ssh", False),
        ssh_host=row.get("ssh_host"),
        ssh_port=row.get("ssh_port", 22),
        ssh_username=row.get("ssh_username"),
        ssh_password=decrypt(row.get("ssh_password")) if row.get("ssh_password") else None,
        ssh_private_key=decrypt(row.get("ssh_private_key")) if row.get("ssh_private_key") else None,
    )


def _connection_insert_data(user_id: str, config: ConnectionRequest) -> dict:
    name = config.name or f"{config.db_type}-{config.database}"
    return {
        "owner_id": user_id,
        "name": name,
        "db_type": config.db_type,
        "host": config.host,
        "port": config.port,
        "database": config.database,
        "username": config.username,
        "password": encrypt(config.password) if config.password else None,
        "ssl_mode": getattr(config, "ssl_mode", "disable"),
        "readonly": getattr(config, "readonly", True),
        "use_ssh": getattr(config, "use_ssh", False),
        "ssh_host": getattr(config, "ssh_host", None),
        "ssh_port": getattr(config, "ssh_port", 22),
        "ssh_username": getattr(config, "ssh_username", None),
        "ssh_password": encrypt(config.ssh_password) if getattr(config, "ssh_password", None) else None,
        "ssh_private_key": encrypt(config.ssh_private_key) if getattr(config, "ssh_private_key", None) else None,
    }


@async_supabase_retry
async def create_connection(user_id: str, config: ConnectionRequest) -> str:
    response = await async_supabase.table("database_connections").insert(
        _connection_insert_data(user_id, config)
    ).execute()
    if not response.data:
        raise Exception("Failed to save connection to database")
    return response.data[0]["id"]


@async_supabase_retry
async def list_connections(user_id: str) -> list[ActiveConnection]:
    response = await async_supabase.table("database_connections").select("*").eq("owner_id", user_id).execute()
    return [_row_to_active_connection(row) for row in response.data]


@async_supabase_retry
async def get_connection_row(user_id: str, connection_id: str) -> dict | None:
    response = (
        await async_supabase.table("database_connections")
        .select("*")
        .eq("id", connection_id)
        .eq("owner_id", user_id)
        .execute()
    )
    return response.data[0] if response.data else None


async def get_connection_config(user_id: str, connection_id: str) -> ConnectionRequest | None:
    row = await get_connection_row(user_id, connection_id)
    if not row:
        return None
    return _row_to_connection_request(row)


@async_supabase_retry
async def delete_connection(user_id: str, connection_id: str) -> bool:
    response = (
        await async_supabase.table("database_connections")
        .delete()
        .eq("id", connection_id)
        .eq("owner_id", user_id)
        .execute()
    )
    return len(response.data) > 0


@async_supabase_retry
async def update_connection_settings_record(
    user_id: str,
    connection_id: str,
    ssl_mode: str | None,
    readonly: bool | None,
) -> bool:
    updates = {}
    if ssl_mode is not None:
        updates["ssl_mode"] = ssl_mode
    if readonly is not None:
        updates["readonly"] = readonly
    if not updates:
        return True

    response = (
        await async_supabase.table("database_connections")
        .update(updates)
        .eq("id", connection_id)
        .eq("owner_id", user_id)
        .execute()
    )
    return bool(response.data)


@async_supabase_retry
async def get_readonly_setting(user_id: str, connection_id: str) -> bool:
    response = (
        await async_supabase.table("database_connections")
        .select("readonly")
        .eq("id", connection_id)
        .eq("owner_id", user_id)
        .execute()
    )
    if not response.data:
        return True
    return response.data[0].get("readonly", True)


@async_supabase_retry
async def find_dev_connection(owner_id: str, name: str) -> str | None:
    response = (
        await async_supabase.table("database_connections")
        .select("id")
        .eq("owner_id", owner_id)
        .eq("name", name)
        .execute()
    )
    return response.data[0]["id"] if response.data else None


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
