import io
import logging
import threading
import time
from typing import Optional
import uuid

import anyio
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL

try:
    from sshtunnel import SSHTunnelForwarder
except ModuleNotFoundError:  # pragma: no cover - environment-dependent optional import
    SSHTunnelForwarder = None

from app.core.config import settings
from app.core.db_connection_guardrails import (
    SUPPORTED_DATABASE_TYPE,
    validate_connection_target,
    validate_supported_database_type,
)
from app.db.models.connection import ConnectionRequest, TableInfo
from app.db.models.connection import ConnectionTestResult
from app.query_engine.connection_tls import create_tls_material
from app.agents.schema_context.catalog import build_catalog
from app.agents.schema_context.types import SchemaCatalog
import app.query_engine.schema_inspector as schema_inspector


logger = logging.getLogger(__name__)

_engines: dict[tuple[str, str], Engine] = {}
_tunnels: dict[tuple[str, str], SSHTunnelForwarder] = {}
_engine_access_times: dict[tuple[str, str], float] = {}
_schema_cache: dict[tuple[str, str], tuple[list[TableInfo], float]] = {}
_catalog_cache: dict[tuple[str, str], tuple[SchemaCatalog, float]] = {}
_cache_lock = threading.RLock()

MAX_CACHED_ENGINES = 50
SCHEMA_CACHE_TTL_SECONDS = 600


def _pop_connection_locked(key: tuple[str, str]):
    engine = _engines.pop(key, None)
    tunnel = _tunnels.pop(key, None)
    _engine_access_times.pop(key, None)
    _schema_cache.pop(key, None)
    _catalog_cache.pop(key, None)
    return engine, tunnel


def dispose_connection_resources(
    engine: Engine | None,
    tunnel: Optional[SSHTunnelForwarder],
) -> None:
    """Close resources after they have been detached from the shared cache."""
    if engine:
        tls_material = getattr(engine, "_querymind_tls_material", None)
        try:
            engine.dispose()
        except Exception:
            logger.warning("Database engine disposal failed type=%s", engine.__class__.__name__)
        finally:
            if tls_material:
                tls_material.cleanup()
    if tunnel:
        try:
            tunnel.stop()
        except Exception:
            logger.warning("SSH tunnel disposal failed type=%s", tunnel.__class__.__name__)


def build_connection_url(
    config: ConnectionRequest,
    override_host: str | None = None,
    override_port: int | None = None,
) -> URL:
    validate_supported_database_type(config.db_type)
    return URL.create(
        drivername="postgresql+psycopg2",
        username=config.username,
        password=config.password,
        host=override_host or config.host,
        port=override_port or config.port,
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
        ssh_timeout=settings.db_connect_timeout_seconds,
        tunnel_timeout=settings.db_connect_timeout_seconds,
    )
    tunnel.start()
    return tunnel, "127.0.0.1", tunnel.local_bind_port


def build_engine(
    url: URL,
    db_type: str,
    ssl_mode: str = "disable",
    *,
    tls_connect_args: dict[str, str] | None = None,
) -> Engine:
    validate_supported_database_type(db_type)
    connect_args = {"connect_timeout": settings.db_connect_timeout_seconds}

    if db_type == SUPPORTED_DATABASE_TYPE and ssl_mode != "disable":
        connect_args["sslmode"] = ssl_mode
    connect_args.update(tls_connect_args or {})

    return create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_size=5,
        max_overflow=10,
    )


def _diagnostic_for_exception(exc: Exception) -> tuple[str, str, str, list[str]]:
    original = getattr(exc, "orig", exc)
    sqlstate = getattr(original, "pgcode", None) or getattr(original, "sqlstate", None)
    lowered = str(original).lower()
    if sqlstate == "28P01" or "password authentication failed" in lowered:
        return "connection_auth_failed", "authentication", "Database authentication failed.", ["Verify the username and password.", "Confirm the database role can log in."]
    if sqlstate == "3D000" or "database" in lowered and "does not exist" in lowered:
        return "connection_database_not_found", "database", "Authentication succeeded, but the requested database was not found.", ["Check the database name.", "Confirm the user can connect to this database."]
    if sqlstate == "42501" or "permission denied" in lowered:
        return "connection_permission_denied", "permission", "The database user does not have the required read access.", ["Grant CONNECT and SELECT privileges to a dedicated QueryMind user."]
    if "could not translate host" in lowered or "name or service not known" in lowered:
        return "connection_dns_failed", "network", "The database hostname could not be resolved.", ["Check the hostname and DNS configuration."]
    if "connection refused" in lowered:
        return "connection_refused", "network", "The database host refused the connection.", ["Check the port, firewall, and whether PostgreSQL is listening."]
    if "timeout" in lowered or "timed out" in lowered:
        return "connection_timeout", "network", "The database connection timed out.", ["Check firewall rules and network reachability."]
    if "certificate" in lowered or "ssl" in lowered:
        return "connection_tls_failed", "tls", "The secure database connection could not be verified.", ["Check the SSL mode, hostname, and certificate chain."]
    if "ssh" in lowered or "tunnel" in lowered:
        return "connection_ssh_failed", "ssh", "The SSH tunnel could not be established.", ["Check the bastion host and SSH credentials."]
    return "connection_unknown", "unknown", "Database connection could not be established.", ["Verify the connection settings and database logs."]


def diagnose_connection_sync(config: ConnectionRequest) -> ConnectionTestResult:
    validate_connection_target(config)
    tunnel = None
    engine = None
    tls_material = None
    started_at = time.monotonic()
    diagnostic_id = str(uuid.uuid4())
    checks = [{"code": "target_policy", "status": "passed", "label": "Target allowed"}]
    try:
        tls_material = create_tls_material(config)
        tunnel, host, port = start_ssh_tunnel(config)
        if config.use_ssh:
            checks.append({"code": "ssh", "status": "passed", "label": "SSH tunnel established"})
        engine = build_engine(
            build_connection_url(config, host, port),
            config.db_type,
            config.ssl_mode,
            tls_connect_args=tls_material.connect_args if tls_material else None,
        )
        if tls_material:
            setattr(engine, "_querymind_tls_material", tls_material)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            server_version = str(conn.execute(text("SHOW server_version")).scalar() or "")
            has_write = bool(
                conn.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.table_privileges "
                        "WHERE grantee IN (current_user, 'PUBLIC') AND privilege_type IN "
                        "('INSERT','UPDATE','DELETE','TRUNCATE','TRIGGER','REFERENCES'))"
                    )
                ).scalar()
            )
        inventory, truncated = schema_inspector.discover_schema_inventory(
            engine, settings.connection_diagnostic_max_objects
        )
        tables_found = sum(len(item["tables"]) for item in inventory)
        checks.extend(
            [
                {"code": "database", "status": "passed", "label": "Database authenticated"},
                {"code": "schema", "status": "passed" if tables_found else "failed", "label": "Schema readable"},
            ]
        )
        if not tables_found:
            return ConnectionTestResult(
                success=False,
                diagnostic_id=diagnostic_id,
                code="connection_schema_empty",
                category="permission",
                message="The connection succeeded, but no accessible user tables were found.",
                suggestions=["Grant SELECT access to at least one user table."],
                latency_ms=round((time.monotonic() - started_at) * 1000, 2),
                checks=checks,
                inventory=inventory,
                inventory_truncated=truncated,
                server_version=server_version,
                tables_found=0,
                role_has_write_privileges=has_write,
            )
        warnings = []
        if has_write:
            warnings.append(
                {
                    "code": "database_user_has_write_privileges",
                    "message": "Use a dedicated SELECT-only database role. QueryMind still enforces read-only transactions.",
                }
            )
        return ConnectionTestResult(
            success=True,
            diagnostic_id=diagnostic_id,
            code="connection_healthy",
            category="success",
            message="Connection successful",
            suggestions=[],
            latency_ms=round((time.monotonic() - started_at) * 1000, 2),
            checks=checks,
            warnings=warnings,
            inventory=inventory,
            inventory_truncated=truncated,
            server_version=server_version,
            tables_found=tables_found,
            role_has_write_privileges=has_write,
        )
    except Exception as exc:
        code, category, message, suggestions = _diagnostic_for_exception(exc)
        logger.info("Connection diagnostic failed code=%s type=%s", code, exc.__class__.__name__)
        checks.append({"code": category, "status": "failed", "label": message})
        return ConnectionTestResult(
            success=False,
            diagnostic_id=diagnostic_id,
            code=code,
            category=category,
            message=message,
            suggestions=suggestions,
            latency_ms=round((time.monotonic() - started_at) * 1000, 2),
            checks=checks,
        )
    finally:
        if engine:
            dispose_connection_resources(engine, tunnel)
            tunnel = None
            tls_material = None
        if tunnel:
            dispose_connection_resources(None, tunnel)
        if tls_material:
            tls_material.cleanup()


def _test_connection_sync(config: ConnectionRequest) -> tuple[bool, str]:
    result = diagnose_connection_sync(config)
    return result.success, result.message


async def test_connection(config: ConnectionRequest) -> tuple[bool, str]:
    return await anyio.to_thread.run_sync(_test_connection_sync, config)


async def diagnose_connection(config: ConnectionRequest) -> ConnectionTestResult:
    return await anyio.to_thread.run_sync(diagnose_connection_sync, config)

def open_connection(config: ConnectionRequest) -> tuple[Engine, Optional[SSHTunnelForwarder]]:
    validate_connection_target(config)
    tls_material = create_tls_material(config)
    tunnel = None
    try:
        tunnel, host, port = start_ssh_tunnel(config)
        engine = build_engine(
            build_connection_url(config, host, port),
            config.db_type,
            config.ssl_mode,
            tls_connect_args=tls_material.connect_args if tls_material else None,
        )
        if tls_material:
            setattr(engine, "_querymind_tls_material", tls_material)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine, tunnel
    except Exception:
        if tls_material:
            tls_material.cleanup()
        if tunnel:
            dispose_connection_resources(None, tunnel)
        raise


def cache_connection(user_id: str, connection_id: str, engine: Engine, tunnel: Optional[SSHTunnelForwarder] = None) -> None:
    key = (user_id, connection_id)
    detached = []
    with _cache_lock:
        if key in _engines or key in _tunnels:
            detached.append(_pop_connection_locked(key))
        if len(_engines) >= MAX_CACHED_ENGINES:
            oldest_key = min(_engine_access_times, key=_engine_access_times.get)
            detached.append(_pop_connection_locked(oldest_key))
        _engines[key] = engine
        if tunnel:
            _tunnels[key] = tunnel
        _engine_access_times[key] = time.monotonic()

    for old_engine, old_tunnel in detached:
        dispose_connection_resources(old_engine, old_tunnel)


def get_cached_engine(user_id: str, connection_id: str) -> Engine | None:
    key = (user_id, connection_id)
    with _cache_lock:
        engine = _engines.get(key)
        if engine:
            _engine_access_times[key] = time.monotonic()
        return engine


def release_connection(user_id: str, connection_id: str) -> None:
    key = (user_id, connection_id)
    with _cache_lock:
        engine, tunnel = _pop_connection_locked(key)
    dispose_connection_resources(engine, tunnel)


async def get_cached_schema(
    user_id: str,
    connection_id: str,
    engine_loader,
    force_refresh: bool = False,
    config_loader=None,
) -> list[TableInfo] | None:
    key = (user_id, connection_id)
    now = time.monotonic()

    if not force_refresh:
        with _cache_lock:
            cached = _schema_cache.get(key)
        if cached:
            schema, ts = cached
            if now - ts < SCHEMA_CACHE_TTL_SECONDS:
                return schema

    engine = await engine_loader(user_id, connection_id)
    if not engine:
        return None

    config = await config_loader(user_id, connection_id) if config_loader else None
    schema = await anyio.to_thread.run_sync(
        lambda: schema_inspector.get_schema(
            engine,
            scope_mode=config.scope_mode if config else "all",
            included_schemas=config.included_schemas if config else [],
            included_tables=config.included_tables if config else [],
        )
    )
    with _cache_lock:
        _schema_cache[key] = (schema, now)
    return schema


def invalidate_schema_cache(user_id: str, connection_id: str) -> None:
    key = (user_id, connection_id)
    with _cache_lock:
        _schema_cache.pop(key, None)
        _catalog_cache.pop(key, None)


def cache_schema(user_id: str, connection_id: str, schema: list[TableInfo]) -> None:
    with _cache_lock:
        _schema_cache[(user_id, connection_id)] = (schema, time.monotonic())


def peek_cached_schema(user_id: str, connection_id: str) -> list[TableInfo] | None:
    """Return in-memory schema cache only; never introspect the live database."""
    key = (user_id, connection_id)
    with _cache_lock:
        cached = _schema_cache.get(key)
        if not cached:
            return None
        schema, ts = cached
        if time.monotonic() - ts >= SCHEMA_CACHE_TTL_SECONDS:
            _schema_cache.pop(key, None)
            return None
        return schema


def cache_catalog(user_id: str, connection_id: str, catalog: SchemaCatalog) -> None:
    with _cache_lock:
        _catalog_cache[(user_id, connection_id)] = (catalog, time.monotonic())


def get_cached_catalog_entry(user_id: str, connection_id: str) -> SchemaCatalog | None:
    key = (user_id, connection_id)
    with _cache_lock:
        cached = _catalog_cache.get(key)
        if not cached:
            return None
        catalog, ts = cached
        if time.monotonic() - ts >= SCHEMA_CACHE_TTL_SECONDS:
            _catalog_cache.pop(key, None)
            return None
        return catalog


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
    "diagnose_connection",
    "diagnose_connection_sync",
    "open_connection",
    "cache_connection",
    "get_cached_engine",
    "release_connection",
    "dispose_connection_resources",
    "get_cached_schema",
    "invalidate_schema_cache",
    "cache_schema",
    "peek_cached_schema",
    "cache_catalog",
    "get_cached_catalog_entry",
    "build_schema_prompt_text",
]
