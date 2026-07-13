import time
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.engine import Engine

from app.db.repositories.query_history_repository import log_query as log_query_history
from app.query_engine.results import QueryExecutionResult
from app.query_engine.result_serializer import serialize_data
from app.query_engine.safety import sanitize_row_limit, validate_query
from app.query_engine.cancellation import QueryCancellationToken
from app.query_engine.connection_scope import validate_connection_scope_sql

QUERY_TIMEOUT = 30


def _apply_readonly_guards(conn, dialect_name: str) -> None:
    if dialect_name == "postgresql":
        conn.execute(text("SET TRANSACTION READ ONLY"))


def execute_query(
    user_id: str,
    engine: Engine,
    sql: str,
    row_limit: int = 500,
    connection_id: Optional[str] = None,
    readonly: bool = True,
    *,
    skip_row_limit_wrap: bool = False,
    timeout_seconds: int | None = None,
    cancellation_token: QueryCancellationToken | None = None,
) -> QueryExecutionResult:
    is_safe, error_msg = validate_query(sql)
    if not is_safe:
        return QueryExecutionResult(success=False, error=error_msg)
    if connection_id:
        scope_allowed, scope_error = validate_connection_scope_sql(user_id, connection_id, sql)
        if not scope_allowed:
            return QueryExecutionResult(
                success=False,
                error=scope_error or "The query violates this connection's access scope.",
                error_code="connection_scope_violation",
            )

    safe_sql = sql if skip_row_limit_wrap else sanitize_row_limit(sql, row_limit)
    effective_timeout = timeout_seconds if timeout_seconds is not None else QUERY_TIMEOUT
    start_time = time.time()

    try:
        with engine.connect() as conn:
            if cancellation_token:
                cancellation_token.register(conn)
                if cancellation_token.cancelled:
                    cancellation_token.unregister()
                    return QueryExecutionResult(success=False, error="Query cancelled by user.")
            transaction = conn.begin()
            try:
                conn.execute(text(f"SET statement_timeout = '{effective_timeout * 1000}'"))
            except Exception:
                pass

            try:
                _apply_readonly_guards(conn, engine.dialect.name)
            except Exception:
                transaction.rollback()
                if cancellation_token:
                    cancellation_token.unregister()
                return _log_and_return(
                    QueryExecutionResult(
                        success=False,
                        error="Unable to enforce read-only execution for this database connection.",
                    ),
                    user_id,
                    connection_id,
                    sql,
                )

            result = conn.execute(text(safe_sql))
            columns = list(result.keys())
            raw_rows = [dict(row._mapping) for row in result.fetchall()]
            rows = serialize_data(raw_rows)
            elapsed = (time.time() - start_time) * 1000
            truncated = len(rows) >= row_limit
            transaction.rollback()
            if cancellation_token:
                cancellation_token.unregister()

            return _log_and_return(
                QueryExecutionResult(
                    success=True,
                    columns=columns,
                    rows=rows,
                    row_count=len(rows),
                    truncated=truncated,
                    execution_time_ms=round(elapsed, 2),
                ),
                user_id,
                connection_id,
                safe_sql,
            )
    except Exception as exc:
        if cancellation_token:
            cancellation_token.unregister()
        elapsed = (time.time() - start_time) * 1000
        error_text = str(exc)

        lowered = error_text.lower()

        if (
            "does not exist" in error_text
            or "doesn't exist" in error_text
            or "no such table" in lowered
            or "no such column" in lowered
        ):
            friendly = f"Table or column not found. {error_text.split(chr(10))[0]}"
        elif "syntax error" in lowered:
            friendly = f"SQL syntax error. {error_text.split(chr(10))[0]}"
        elif cancellation_token and cancellation_token.cancelled:
            friendly = "Query cancelled by user."
        elif "timeout" in lowered or "cancel" in lowered:
            friendly = f"Query timed out after {effective_timeout} seconds. Try a simpler query or add filters."
        elif "permission" in lowered or "denied" in lowered:
            friendly = "Permission denied. Your database user may not have access to this table."
        else:
            friendly = error_text.split("\n")[0]

        connection_failure = bool(
            isinstance(exc, (OperationalError, DBAPIError))
            and (
                getattr(exc, "connection_invalidated", False)
                or any(
                    marker in lowered
                    for marker in (
                        "connection refused",
                        "connection is closed",
                        "connection not open",
                        "could not connect",
                        "server closed the connection",
                        "ssl connection has been closed",
                        "network is unreachable",
                    )
                )
            )
        )

        return _log_and_return(
            QueryExecutionResult(
                success=False,
                execution_time_ms=round(elapsed, 2),
                error=friendly,
                connection_failure=connection_failure,
            ),
            user_id,
            connection_id,
            sql,
        )


def _log_and_return(
    result: QueryExecutionResult,
    user_id: str,
    connection_id: Optional[str],
    sql: str,
) -> QueryExecutionResult:
    if connection_id:
        try:
            log_query_history(
                user_id=user_id,
                connection_id=connection_id,
                sql=sql,
                success=result.success,
                error=result.error,
                execution_time_ms=result.execution_time_ms,
                row_count=result.row_count,
            )
        except Exception:
            pass
    return result


__all__ = ["QUERY_TIMEOUT", "execute_query"]
