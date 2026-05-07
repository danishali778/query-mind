import io
import logging
import time
from typing import Optional

import anyio
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL, make_url

try:
    from sshtunnel import SSHTunnelForwarder
except ModuleNotFoundError:  # pragma: no cover - environment-dependent optional import
    SSHTunnelForwarder = None

from app.db.models.connection import ConnectionRequest, TableInfo
import app.query_engine.schema_inspector as schema_inspector


logger = logging.getLogger(__name__)

_engines: dict[tuple[str, str], Engine] = {}
_tunnels: dict[tuple[str, str], SSHTunnelForwarder] = {}
_engine_access_times: dict[tuple[str, str], float] = {}
_schema_cache: dict[tuple[str, str], tuple[list[TableInfo], float]] = {}

MAX_CACHED_ENGINES = 50
SCHEMA_CACHE_TTL_SECONDS = 600


def _evict_lru_engine() -> None:
    if len(_engines) < MAX_CACHED_ENGINES:
        return

    oldest_key = min(_engine_access_times, key=_engine_access_times.get)
    release_connection(*oldest_key)


def build_connection_url(
    config: ConnectionRequest,
    override_host: str | None = None,
    override_port: int | None = None,
) -> URL:
    host = override_host or config.host
    port = override_port or config.port

    drivers = {
        "postgresql": "postgresql+psycopg2",
        "mysql": "mysql+pymysql",
        "sqlite": "sqlite",
        "sqlserver": "mssql+pyodbc",
        "mariadb": "mysql+pymysql",
    }
    driver = drivers.get(config.db_type, config.db_type)

    if config.db_type == "sqlite":
        return make_url(f"sqlite:///{config.database}")

    return URL.create(
        drivername=driver,
        username=config.username,
        password=config.password,
        host=host,
        port=port,
        database=config.database,
    )


def start_ssh_tunnel(config: ConnectionRequest) -> tuple[Optional[SSHTunnelForwarder], str, int]:
    if not config.use_ssh:
        return None, config.host or "localhost", config.port or 0

    if SSHTunnelForwarder is None:
        raise RuntimeError("SSH tunneling support is not installed on the server.")

    ssh_pkey = io.StringIO(config.ssh_private_key) if config.ssh_private_key else None
    tunnel = SSHTunnelForwarder(
        (config.ssh_host, config.ssh_port or 22),
        ssh_username=config.ssh_username,
        ssh_password=config.ssh_password,
        ssh_pkey=ssh_pkey,
        remote_bind_address=(config.host, config.port or 5432),
    )
    tunnel.start()
    return tunnel, "127.0.0.1", tunnel.local_bind_port


def build_engine(url: URL, db_type: str, ssl_mode: str = "disable") -> Engine:
    connect_args = {}
    if db_type in ["postgresql", "mariadb", "mysql"] and ssl_mode != "disable":
        connect_args["sslmode"] = ssl_mode

    return create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_size=5,
        max_overflow=10,
    )


async def test_connection(config: ConnectionRequest) -> tuple[bool, str]:
    tunnel = None
    engine = None
    try:
        tunnel, host, port = start_ssh_tunnel(config)
        engine = build_engine(build_connection_url(config, host, port), config.db_type, config.ssl_mode)

        def _sync_test():
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

        await anyio.to_thread.run_sync(_sync_test)
        return True, "Connection successful"
    except Exception as exc:
        logger.error("Connection test failed: %s", exc)
        return False, str(exc)
    finally:
        if engine:
            engine.dispose()
        if tunnel:
            tunnel.stop()


def open_connection(config: ConnectionRequest) -> tuple[Engine, Optional[SSHTunnelForwarder]]:
    tunnel, host, port = start_ssh_tunnel(config)
    engine = build_engine(build_connection_url(config, host, port), config.db_type, config.ssl_mode)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return engine, tunnel


def cache_connection(user_id: str, connection_id: str, engine: Engine, tunnel: Optional[SSHTunnelForwarder] = None) -> None:
    _evict_lru_engine()
    key = (user_id, connection_id)
    _engines[key] = engine
    if tunnel:
        _tunnels[key] = tunnel
    _engine_access_times[key] = time.monotonic()


def get_cached_engine(user_id: str, connection_id: str) -> Engine | None:
    key = (user_id, connection_id)
    engine = _engines.get(key)
    if engine:
        _engine_access_times[key] = time.monotonic()
    return engine


def release_connection(user_id: str, connection_id: str) -> None:
    key = (user_id, connection_id)
    engine = _engines.pop(key, None)
    tunnel = _tunnels.pop(key, None)
    _engine_access_times.pop(key, None)
    _schema_cache.pop(key, None)
    if engine:
        engine.dispose()
    if tunnel:
        tunnel.stop()


async def get_cached_schema(
    user_id: str,
    connection_id: str,
    engine_loader,
    force_refresh: bool = False,
) -> list[TableInfo] | None:
    key = (user_id, connection_id)
    now = time.monotonic()

    if not force_refresh:
        cached = _schema_cache.get(key)
        if cached:
            schema, ts = cached
            if now - ts < SCHEMA_CACHE_TTL_SECONDS:
                return schema

    engine = await engine_loader(user_id, connection_id)
    if not engine:
        return None

    schema = await anyio.to_thread.run_sync(schema_inspector.get_schema, engine)
    _schema_cache[key] = (schema, now)
    return schema


def build_schema_prompt_text(schema: list[TableInfo]) -> str:
    lines = []
    for table in schema:
        row_info = f" ({table.row_count} rows)" if table.row_count is not None else ""
        lines.append(f"Table: {table.name}{row_info}")
        for col in table.columns:
            pk_tag = " (PK)" if col.primary_key else ""
            null_tag = " NULL" if col.nullable else " NOT NULL"
            values_tag = f" [values: {', '.join(col.sample_values)}]" if col.sample_values else ""
            lines.append(f"  - {col.name}: {col.type}{pk_tag}{null_tag}{values_tag}")
        for fk in table.foreign_keys:
            lines.append(f"  FK: {fk.column} -> {fk.referred_table}.{fk.referred_column}")
        lines.append("")
    return "\n".join(lines)


__all__ = [
    "build_connection_url",
    "start_ssh_tunnel",
    "build_engine",
    "test_connection",
    "open_connection",
    "cache_connection",
    "get_cached_engine",
    "release_connection",
    "get_cached_schema",
    "build_schema_prompt_text",
]
