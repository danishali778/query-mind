"""Query execution workflows."""

import functools

import anyio
from sqlalchemy.engine import Engine

from app.query_engine.executor import execute_query as _execute_query
from app.query_engine.results import QueryExecutionResult
from app.query_engine.safety import get_readonly_wrapped_query, sanitize_row_limit, validate_query
from app.services import connection_service


def execute_query(
    user_id: str,
    engine: Engine,
    sql: str,
    row_limit: int = 500,
    connection_id: str | None = None,
    readonly: bool = True,
    *,
    skip_row_limit_wrap: bool = False,
    timeout_seconds: int | None = None,
) -> QueryExecutionResult:
    result = _execute_query(
        user_id,
        engine,
        sql,
        row_limit,
        connection_id,
        True,
        skip_row_limit_wrap=skip_row_limit_wrap,
        timeout_seconds=timeout_seconds,
    )
    connection_service.record_query_execution_health_sync(user_id, connection_id, result)
    return result


async def execute_for_connection(
    user_id: str,
    connection_id: str,
    sql: str,
    row_limit: int = 500,
    readonly: bool | None = None,
) -> QueryExecutionResult:
    engine = await connection_service.get_engine(user_id, connection_id)
    if not engine:
        raise ValueError("Database connection not found.")
    result = await anyio.to_thread.run_sync(
        functools.partial(
            _execute_query,
            user_id,
            engine,
            sql,
            row_limit,
            connection_id,
            True,
        )
    )
    await connection_service.record_query_execution_health(user_id, connection_id, result)
    return result


__all__ = [
    "execute_query",
    "execute_for_connection",
    "validate_query",
    "sanitize_row_limit",
    "get_readonly_wrapped_query",
]
