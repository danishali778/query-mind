"""Connection persistence and runtime connection orchestration."""

from sqlalchemy.engine import Engine, make_url

from app.db.models.connection import ActiveConnection, ConnectionRequest, TableInfo
from app.db.repositories import connection_repository
from app.query_engine.schema_inspector import generate_erd_json, generate_erd_mermaid
import app.query_engine.connection_pool as connection_pool


async def test_connection(config: ConnectionRequest) -> tuple[bool, str]:
    return await connection_pool.test_connection(config)


async def connect(user_id: str, config: ConnectionRequest) -> tuple[str, Engine]:
    engine, tunnel = connection_pool.open_connection(config)
    try:
        connection_id = await connection_repository.create_connection(user_id, config)
    except Exception:
        engine.dispose()
        if tunnel:
            tunnel.stop()
        raise

    connection_pool.cache_connection(user_id, connection_id, engine, tunnel)
    return connection_id, engine


async def get_all_connections(user_id: str) -> list[ActiveConnection]:
    return await connection_repository.list_connections(user_id)


async def get_engine(user_id: str, connection_id: str) -> Engine | None:
    cached = connection_pool.get_cached_engine(user_id, connection_id)
    if cached:
        return cached

    config = await connection_repository.get_connection_config(user_id, connection_id)
    if not config:
        return None

    engine, tunnel = connection_pool.open_connection(config)
    connection_pool.cache_connection(user_id, connection_id, engine, tunnel)
    return engine


async def disconnect(user_id: str, connection_id: str) -> bool:
    connection_pool.release_connection(user_id, connection_id)
    return await connection_repository.delete_connection(user_id, connection_id)


async def update_settings(
    user_id: str,
    connection_id: str,
    ssl_mode: str | None,
    readonly: bool | None,
) -> bool:
    ok = await connection_repository.update_connection_settings_record(
        user_id=user_id,
        connection_id=connection_id,
        ssl_mode=ssl_mode,
        readonly=readonly,
    )
    if not ok:
        return False

    connection_pool.release_connection(user_id, connection_id)
    await get_engine(user_id, connection_id)
    return True


async def get_cached_schema(
    user_id: str,
    connection_id: str,
    force_refresh: bool = False,
) -> list[TableInfo] | None:
    return await connection_pool.get_cached_schema(
        user_id=user_id,
        connection_id=connection_id,
        engine_loader=get_engine,
        force_refresh=force_refresh,
    )


async def refresh_schema(user_id: str, connection_id: str) -> list[TableInfo] | None:
    return await get_cached_schema(user_id, connection_id, force_refresh=True)


async def get_readonly(user_id: str, connection_id: str) -> bool:
    return await connection_repository.get_readonly_setting(user_id, connection_id)


async def get_schema_for_ai(user_id: str, connection_id: str) -> str | None:
    schema = await get_cached_schema(user_id, connection_id)
    if not schema:
        return None
    return connection_pool.build_schema_prompt_text(schema)


async def seed_dev_connection() -> str | None:
    from app.core.config import settings

    url = settings.database_url
    if not url or not settings.backend_dev_mode:
        return None

    try:
        parsed = make_url(url)
        name = f"Dev - {parsed.database}"
        owner_id = settings.dev_user_id
        existing_id = await connection_repository.find_dev_connection(owner_id, name)
        if existing_id:
            return existing_id

        config = ConnectionRequest(
            db_type=parsed.drivername.split("+")[0],
            host=str(parsed.host or "localhost"),
            port=parsed.port,
            database=str(parsed.database or ""),
            username=str(parsed.username or ""),
            password=str(parsed.password or ""),
            name=name,
            readonly=False,
        )
        connection_id, _ = await connect(owner_id, config)
        return connection_id
    except Exception:
        return None


_engines = connection_pool._engines
_schema_cache = connection_pool._schema_cache
_tunnels = connection_pool._tunnels


__all__ = [
    "_engines",
    "_schema_cache",
    "_tunnels",
    "test_connection",
    "connect",
    "get_all_connections",
    "disconnect",
    "get_engine",
    "get_readonly",
    "get_cached_schema",
    "refresh_schema",
    "get_schema_for_ai",
    "seed_dev_connection",
    "update_settings",
    "generate_erd_mermaid",
    "generate_erd_json",
]
