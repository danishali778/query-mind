"""Connection persistence and runtime connection orchestration."""

from __future__ import annotations

import functools
import logging
import time

import anyio

from sqlalchemy.engine import Engine, make_url

from app.core.db_connection_guardrails import (
    RateLimitError,
    connection_attempt_target,
    enforce_connection_attempt_rate_limit,
    validate_connection_target,
)
from app.core.errors import AppError
from app.agents.schema_context.catalog import build_catalog
from app.agents.schema_context.types import SchemaCatalog
from app.db.models.connection import (
    ActiveConnection,
    ColumnInfo,
    ConnectionRequest,
    ConnectionTestResult,
    ForeignKeyInfo,
    TableInfo,
)
from app.db.repositories import (
    connection_attempt_repository,
    connection_health_repository,
    connection_repository,
    schema_snapshot_repository,
)
from app.db.sentinels import UNSET
from app.db.session import session_scope
from app.core.config import settings
from app.query_engine.results import QueryExecutionResult
from app.query_engine.schema_inspector import generate_erd_json, generate_erd_mermaid
from app.query_engine import schema_inspector
from app.query_engine.connection_scope import (
    invalidate_scope_cache,
    normalize_scope,
    validate_scope_inventory,
)
import app.query_engine.connection_pool as connection_pool


logger = logging.getLogger(__name__)


def sanitize_connection_error(exc: Exception | str) -> str:
    message = str(exc).lower()
    if "ssh" in message or "tunnel" in message:
        return "Unable to establish the SSH tunnel with the provided connection settings."
    if "authentication" in message or "password" in message or "access denied" in message:
        return "Database authentication failed. Verify the connection credentials."
    if "timeout" in message:
        return "Connection attempt timed out. Verify the host, port, and network access."
    if "could not translate host" in message or "name or service not known" in message:
        return "Database host could not be resolved. Verify the host and port."
    return "Database connection could not be established with the provided settings."


def _error_code(exc: Exception) -> str:
    if isinstance(exc, AppError):
        return exc.code
    return exc.__class__.__name__.lower() or "connection_failed"


def _target_for_audit(config: ConnectionRequest) -> tuple[str | None, int | None]:
    target = connection_attempt_target(config)
    return target.host, target.port


def _log_attempt(
    *,
    user_id: str,
    action: str,
    config: ConnectionRequest,
    decision: str,
    success: bool,
    error_code: str | None,
    started_at: float,
) -> None:
    host, port = _target_for_audit(config)
    try:
        connection_attempt_repository.log_connection_attempt(
            owner_id=user_id,
            action=action,
            db_type=config.db_type,
            host=host,
            port=port,
            decision=decision,
            success=success,
            error_code=error_code,
            duration_ms=round((time.monotonic() - started_at) * 1000, 2),
        )
    except Exception:
        logger.warning("Failed to write database connection attempt audit row", exc_info=True)


def _preflight_connection_attempt(user_id: str, action: str, config: ConnectionRequest, started_at: float) -> None:
    try:
        enforce_connection_attempt_rate_limit(user_id)
    except Exception as exc:
        decision = "rate_limited" if isinstance(exc, RateLimitError) else "rate_limit_unavailable"
        _log_attempt(
            user_id=user_id,
            action=action,
            config=config,
            decision=decision,
            success=False,
            error_code=_error_code(exc),
            started_at=started_at,
        )
        raise

    try:
        validate_connection_target(config)
    except Exception as exc:
        _log_attempt(
            user_id=user_id,
            action=action,
            config=config,
            decision="blocked",
            success=False,
            error_code=_error_code(exc),
            started_at=started_at,
        )
        raise


async def _preflight_connection_attempt_async(
    user_id: str, action: str, config: ConnectionRequest, started_at: float
) -> None:
    await anyio.to_thread.run_sync(
        functools.partial(_preflight_connection_attempt, user_id, action, config, started_at)
    )


async def _log_attempt_async(**kwargs) -> None:
    await anyio.to_thread.run_sync(functools.partial(_log_attempt, **kwargs))


async def _release_connection_async(user_id: str, connection_id: str) -> None:
    await anyio.to_thread.run_sync(
        functools.partial(connection_pool.release_connection, user_id, connection_id)
    )


async def _cache_connection_async(user_id, connection_id, engine, tunnel) -> None:
    await anyio.to_thread.run_sync(
        functools.partial(
            connection_pool.cache_connection,
            user_id,
            connection_id,
            engine,
            tunnel,
        )
    )


async def _dispose_resources_async(engine, tunnel) -> None:
    await anyio.to_thread.run_sync(
        functools.partial(connection_pool.dispose_connection_resources, engine, tunnel)
    )


async def test_connection(user_id: str, config: ConnectionRequest) -> ConnectionTestResult:
    started_at = time.monotonic()
    await _preflight_connection_attempt_async(user_id, "test", config, started_at)

    result = await connection_pool.diagnose_connection(config)
    success, message, latency_ms = result.success, result.message, result.latency_ms
    await _log_attempt_async(
        user_id=user_id,
        action="test",
        config=config,
        decision="allowed",
        success=success,
        error_code=None if success else result.code,
        started_at=started_at,
    )
    return result


async def test_saved_connection(
    user_id: str,
    connection_id: str,
    *,
    source: str = "manual_test",
) -> ConnectionTestResult | None:
    config = await connection_repository.get_connection_config(user_id, connection_id)
    if not config:
        return None

    started_at = time.monotonic()
    await _preflight_connection_attempt_async(user_id, "test", config, started_at)

    result = await connection_pool.diagnose_connection(config)
    success, message, latency_ms = result.success, result.message, result.latency_ms
    persisted_error = None if success else sanitize_connection_error(message)
    await connection_repository.record_connection_health(
        user_id,
        connection_id,
        last_status="healthy" if success else "failed",
        last_error=persisted_error,
        latency_ms=latency_ms,
    )
    await anyio.to_thread.run_sync(
        functools.partial(
            connection_health_repository.record,
            owner_id=user_id,
            connection_id=connection_id,
            source=source,
            status="healthy" if success else "failed",
            diagnostic_code=result.code,
            message=result.message,
            latency_ms=latency_ms,
        )
    )
    if not success:
        await _release_connection_async(user_id, connection_id)

    await _log_attempt_async(
        user_id=user_id,
        action="test",
        config=config,
        decision="allowed",
        success=success,
        error_code=None if success else result.code,
        started_at=started_at,
    )
    return result


async def connect(user_id: str, config: ConnectionRequest) -> tuple[str, Engine, float]:
    started_at = time.monotonic()
    await _preflight_connection_attempt_async(user_id, "connect", config, started_at)

    engine = None
    tunnel = None
    try:
        normalized_scope = normalize_scope(config.scope_mode, config.included_schemas, config.included_tables)
        config.scope_mode = normalized_scope["mode"]
        config.included_schemas = normalized_scope["included_schemas"]
        config.included_tables = normalized_scope["included_tables"]
        engine, tunnel = await anyio.to_thread.run_sync(connection_pool.open_connection, config)
        inventory, _truncated = await anyio.to_thread.run_sync(
            schema_inspector.discover_schema_inventory,
            engine,
            settings.connection_diagnostic_max_objects,
        )
        scope_errors = validate_scope_inventory(normalized_scope, inventory)
        if scope_errors:
            raise ValueError(scope_errors[0]["message"])
        schema = await anyio.to_thread.run_sync(
            lambda: schema_inspector.get_schema(
                engine,
                scope_mode=config.scope_mode,
                included_schemas=config.included_schemas,
                included_tables=config.included_tables,
            )
        )
        if not schema:
            raise ValueError("No accessible tables are available in the selected connection scope.")
        latency_ms = round((time.monotonic() - started_at) * 1000, 2)
        connection_id, catalog = await connection_repository.create_connection_bundle(
            user_id, config, schema, latency_ms=latency_ms
        )
    except Exception as exc:
        await _dispose_resources_async(engine, tunnel)
        await _log_attempt_async(
            user_id=user_id,
            action="connect",
            config=config,
            decision="allowed",
            success=False,
            error_code=_error_code(exc),
            started_at=started_at,
        )
        raise

    await _cache_connection_async(user_id, connection_id, engine, tunnel)
    connection_pool.cache_schema(user_id, connection_id, schema)
    connection_pool.cache_catalog(user_id, connection_id, catalog)
    await _log_attempt_async(
        user_id=user_id,
        action="connect",
        config=config,
        decision="allowed",
        success=True,
        error_code=None,
        started_at=started_at,
    )
    return connection_id, engine, latency_ms


async def get_all_connections(user_id: str) -> list[ActiveConnection]:
    return await connection_repository.list_connections(user_id)


async def get_connection(user_id: str, connection_id: str) -> ActiveConnection | None:
    return await connection_repository.get_active_connection(user_id, connection_id)


async def get_engine(user_id: str, connection_id: str) -> Engine | None:
    cached = connection_pool.get_cached_engine(user_id, connection_id)
    if cached:
        return cached

    config = await connection_repository.get_connection_config(user_id, connection_id)
    if not config:
        return None

    try:
        engine, tunnel = await anyio.to_thread.run_sync(connection_pool.open_connection, config)
    except Exception as exc:
        await connection_repository.record_connection_health(
            user_id,
            connection_id,
            last_status="failed",
            last_error=sanitize_connection_error(exc),
        )
        raise

    await _cache_connection_async(user_id, connection_id, engine, tunnel)
    return engine


async def disconnect(user_id: str, connection_id: str) -> bool:
    await _release_connection_async(user_id, connection_id)
    invalidate_scope_cache(user_id, connection_id)
    return await connection_repository.delete_connection(user_id, connection_id)


async def update_settings(
    user_id: str,
    connection_id: str,
    ssl_mode: str | None,
) -> bool:
    ok = await connection_repository.update_connection_settings_record(
        user_id=user_id,
        connection_id=connection_id,
        ssl_mode=ssl_mode,
    )
    if not ok:
        return False

    await _release_connection_async(user_id, connection_id)
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
        config_loader=connection_repository.get_connection_config,
    )


def catalog_to_table_info(catalog: SchemaCatalog) -> list[TableInfo]:
    """Convert a persisted catalog snapshot into API/domain table schema rows."""
    tables: list[TableInfo] = []
    for table in catalog.tables:
        columns: list[ColumnInfo] = []
        foreign_keys: list[ForeignKeyInfo] = []
        for col in table.columns:
            columns.append(
                ColumnInfo(
                    name=col.name,
                    type=col.type,
                    nullable=col.nullable,
                    primary_key=col.primary_key,
                    sample_values=col.sample_values,
                )
            )
            if col.fk_referred_table:
                foreign_keys.append(
                    ForeignKeyInfo(
                        column=col.name,
                        referred_table=col.fk_referred_table,
                        referred_column=col.fk_referred_column or "",
                    )
                )
        tables.append(
            TableInfo(
                name=table.name,
                columns=columns,
                foreign_keys=foreign_keys,
                row_count=table.row_estimate,
            )
        )
    return tables


async def get_connection_schema(user_id: str, connection_id: str) -> list[TableInfo] | None:
    """Return the last synced schema without forcing a live re-introspection."""
    if not await get_connection(user_id, connection_id):
        return None

    cached = connection_pool.peek_cached_schema(user_id, connection_id)
    if cached is not None:
        return cached

    catalog = connection_pool.get_cached_catalog_entry(user_id, connection_id)
    if catalog is None:
        catalog = await anyio.to_thread.run_sync(
            functools.partial(schema_snapshot_repository.get, user_id, connection_id)
        )
        if catalog:
            connection_pool.cache_catalog(user_id, connection_id, catalog)

    if catalog:
        schema = catalog_to_table_info(catalog)
        connection_pool.cache_schema(user_id, connection_id, schema)
        return schema

    return []


async def refresh_schema(user_id: str, connection_id: str) -> list[TableInfo] | None:
    connection = await get_connection(user_id, connection_id)
    if not connection:
        return None
    config = await connection_repository.get_connection_config(user_id, connection_id)
    if not config:
        return None
    engine = await get_engine(user_id, connection_id)
    if not engine:
        return None
    try:
        schema = await anyio.to_thread.run_sync(
            lambda: schema_inspector.get_schema(
                engine,
                scope_mode=config.scope_mode,
                included_schemas=config.included_schemas,
                included_tables=config.included_tables,
            )
        )
        if not schema:
            raise ValueError("The active connection scope contains no accessible tables.")
        catalog = build_catalog(connection_id, connection.db_type, schema)

        def persist_replacement() -> None:
            with session_scope() as session:
                schema_snapshot_repository.upsert_sync(session, catalog, user_id)
                connection_repository._record_connection_health_sync(
                    session,
                    user_id,
                    connection_id,
                    last_status="healthy",
                    last_error=None,
                )
                connection_repository._record_schema_sync_sync(session, user_id, connection_id)
                connection_health_repository.record_sync(
                    session,
                    owner_id=user_id,
                    connection_id=connection_id,
                    source="schema_refresh",
                    status="healthy",
                    diagnostic_code="connection_healthy",
                    message="Schema refreshed successfully.",
                    latency_ms=None,
                )

        await anyio.to_thread.run_sync(persist_replacement)
    except Exception as exc:
        await anyio.to_thread.run_sync(
            functools.partial(
                connection_health_repository.record,
                owner_id=user_id,
                connection_id=connection_id,
                source="schema_refresh",
                status="failed",
                diagnostic_code="connection_unavailable",
                message="Schema refresh failed; the last good schema was preserved.",
                latency_ms=None,
            )
        )
        raise
    connection_pool.invalidate_schema_cache(user_id, connection_id)
    invalidate_scope_cache(user_id, connection_id)
    connection_pool.cache_schema(user_id, connection_id, schema)
    connection_pool.cache_catalog(user_id, connection_id, catalog)
    return schema


async def _persist_catalog_from_schema(
    user_id: str,
    connection_id: str,
    schema: list[TableInfo],
) -> None:
    try:
        connection = await get_connection(user_id, connection_id)
        db_type = connection.db_type if connection else "postgresql"
        catalog = build_catalog(connection_id, db_type, schema)
        await anyio.to_thread.run_sync(
            functools.partial(schema_snapshot_repository.upsert, catalog, user_id)
        )
        connection_pool.cache_catalog(user_id, connection_id, catalog)
    except Exception:
        logger.warning("Failed to build catalog snapshot for connection %s", connection_id)


async def _persist_catalog_for_connection(user_id: str, connection_id: str) -> None:
    schema = await get_cached_schema(user_id, connection_id)
    if schema:
        await _persist_catalog_from_schema(user_id, connection_id, schema)


async def _refresh_catalog_for_connection(user_id: str, connection_id: str) -> None:
    await refresh_schema(user_id, connection_id)


async def record_connection_health(
    user_id: str,
    connection_id: str,
    *,
    success: bool,
    error: str | None = None,
    latency_ms: float | None | object = UNSET,
) -> bool:
    last_status = "healthy" if success else "failed"
    return await connection_repository.record_connection_health(
        user_id,
        connection_id,
        last_status=last_status,
        last_error=None if success else error,
        latency_ms=latency_ms,
    )


async def record_schema_sync(user_id: str, connection_id: str) -> bool:
    return await connection_repository.record_schema_sync(user_id, connection_id)


def record_query_execution_health_sync(
    user_id: str,
    connection_id: str | None,
    result: QueryExecutionResult,
) -> None:
    if not connection_id:
        return
    if not result.success and not result.connection_failure:
        return
    connection_repository.sync_record_connection_health(
        user_id,
        connection_id,
        last_status="healthy" if result.success else "failed",
        last_error=None if result.success else result.error,
    )


async def record_query_execution_health(
    user_id: str,
    connection_id: str | None,
    result: QueryExecutionResult,
) -> None:
    if not connection_id:
        return
    if not result.success and not result.connection_failure:
        return
    await connection_repository.record_connection_health(
        user_id,
        connection_id,
        last_status="healthy" if result.success else "failed",
        last_error=None if result.success else result.error,
    )


async def get_readonly(user_id: str, connection_id: str) -> bool:
    return await connection_repository.get_readonly_setting(user_id, connection_id)


async def get_schema_for_ai(user_id: str, connection_id: str) -> str | None:
    schema = await get_cached_schema(user_id, connection_id)
    if not schema:
        return None
    return connection_pool.build_schema_prompt_text(schema)


async def get_catalog(user_id: str, connection_id: str, *, force_refresh: bool = False) -> SchemaCatalog | None:
    if not force_refresh:
        cached = connection_pool.get_cached_catalog_entry(user_id, connection_id)
        if cached:
            return cached

        snapshot = await anyio.to_thread.run_sync(
            functools.partial(schema_snapshot_repository.get, user_id, connection_id)
        )
        if snapshot:
            connection_pool.cache_catalog(user_id, connection_id, snapshot)
            return snapshot

    schema = await get_cached_schema(user_id, connection_id, force_refresh=force_refresh)
    if not schema:
        return None

    connection = await get_connection(user_id, connection_id)
    db_type = connection.db_type if connection else "postgresql"
    catalog = build_catalog(connection_id, db_type, schema)
    await anyio.to_thread.run_sync(
        functools.partial(schema_snapshot_repository.upsert, catalog, user_id)
    )
    connection_pool.cache_catalog(user_id, connection_id, catalog)
    return catalog


async def invalidate_catalog(user_id: str, connection_id: str) -> None:
    connection_pool.invalidate_schema_cache(user_id, connection_id)
    invalidate_scope_cache(user_id, connection_id)
    await anyio.to_thread.run_sync(
        functools.partial(schema_snapshot_repository.delete, user_id, connection_id)
    )


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
            readonly=True,
        )
        connection_id, _, _ = await connect(owner_id, config)
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
    "sanitize_connection_error",
    "test_connection",
    "test_saved_connection",
    "connect",
    "get_all_connections",
    "get_connection",
    "disconnect",
    "get_engine",
    "get_readonly",
    "get_cached_schema",
    "get_connection_schema",
    "catalog_to_table_info",
    "refresh_schema",
    "get_schema_for_ai",
    "get_catalog",
    "invalidate_catalog",
    "seed_dev_connection",
    "update_settings",
    "record_connection_health",
    "record_query_execution_health",
    "record_query_execution_health_sync",
    "record_schema_sync",
    "generate_erd_mermaid",
    "generate_erd_json",
]
