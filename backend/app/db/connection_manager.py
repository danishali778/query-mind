"""Connection persistence and runtime connection orchestration."""

from __future__ import annotations

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
from app.db.models.connection import ActiveConnection, ConnectionRequest, ConnectionTestResult, TableInfo
from app.db.repositories import connection_attempt_repository, connection_repository
from app.query_engine.results import QueryExecutionResult
from app.query_engine.schema_inspector import generate_erd_json, generate_erd_mermaid
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


async def test_connection(user_id: str, config: ConnectionRequest) -> ConnectionTestResult:
    started_at = time.monotonic()
    _preflight_connection_attempt(user_id, "test", config, started_at)

    success, message = await connection_pool.test_connection(config)
    latency_ms = round((time.monotonic() - started_at) * 1000, 2)
    _log_attempt(
        user_id=user_id,
        action="test",
        config=config,
        decision="allowed",
        success=success,
        error_code=None if success else "connection_failed",
        started_at=started_at,
    )
    return ConnectionTestResult(success=success, message=message, latency_ms=latency_ms)


async def test_saved_connection(user_id: str, connection_id: str) -> ConnectionTestResult | None:
    config = await connection_repository.get_connection_config(user_id, connection_id)
    if not config:
        return None

    started_at = time.monotonic()
    _preflight_connection_attempt(user_id, "test", config, started_at)

    success, message = await connection_pool.test_connection(config)
    latency_ms = round((time.monotonic() - started_at) * 1000, 2)
    persisted_error = None if success else sanitize_connection_error(message)
    await connection_repository.record_connection_health(
        user_id,
        connection_id,
        last_status="healthy" if success else "failed",
        last_error=persisted_error,
        latency_ms=latency_ms,
    )
    if not success:
        connection_pool.release_connection(user_id, connection_id)

    _log_attempt(
        user_id=user_id,
        action="test",
        config=config,
        decision="allowed",
        success=success,
        error_code=None if success else "connection_failed",
        started_at=started_at,
    )
    return ConnectionTestResult(success=success, message=message, latency_ms=latency_ms)


async def connect(user_id: str, config: ConnectionRequest) -> tuple[str, Engine, float]:
    started_at = time.monotonic()
    _preflight_connection_attempt(user_id, "connect", config, started_at)

    engine = None
    tunnel = None
    try:
        engine, tunnel = await anyio.to_thread.run_sync(connection_pool.open_connection, config)
        connection_id = await connection_repository.create_connection(user_id, config)
        latency_ms = round((time.monotonic() - started_at) * 1000, 2)
        await connection_repository.record_connection_health(
            user_id,
            connection_id,
            last_status="healthy",
            last_error=None,
            latency_ms=latency_ms,
        )
    except Exception as exc:
        if engine:
            engine.dispose()
        if tunnel:
            tunnel.stop()
        _log_attempt(
            user_id=user_id,
            action="connect",
            config=config,
            decision="allowed",
            success=False,
            error_code=_error_code(exc),
            started_at=started_at,
        )
        raise

    connection_pool.cache_connection(user_id, connection_id, engine, tunnel)
    _log_attempt(
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

    connection_pool.cache_connection(user_id, connection_id, engine, tunnel)
    return engine


async def disconnect(user_id: str, connection_id: str) -> bool:
    connection_pool.release_connection(user_id, connection_id)
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
    try:
        schema = await get_cached_schema(user_id, connection_id, force_refresh=True)
    except Exception as exc:
        await connection_repository.record_connection_health(
            user_id,
            connection_id,
            last_status="failed",
            last_error=sanitize_connection_error(exc),
        )
        raise

    if schema is not None:
        await connection_repository.record_connection_health(
            user_id,
            connection_id,
            last_status="healthy",
            last_error=None,
        )
        await connection_repository.record_schema_sync(user_id, connection_id)
    return schema


async def record_connection_health(
    user_id: str,
    connection_id: str,
    *,
    success: bool,
    error: str | None = None,
    latency_ms: float | None | object = connection_repository._UNSET,
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
    "refresh_schema",
    "get_schema_for_ai",
    "seed_dev_connection",
    "update_settings",
    "record_connection_health",
    "record_query_execution_health",
    "record_query_execution_health_sync",
    "record_schema_sync",
    "generate_erd_mermaid",
    "generate_erd_json",
]
