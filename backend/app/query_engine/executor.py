import time
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.repositories.query_history_repository import log_query as log_query_history
from app.query_engine.results import QueryExecutionResult
from app.query_engine.result_serializer import serialize_data
from app.query_engine.safety import sanitize_row_limit, validate_query

QUERY_TIMEOUT = 30


def _apply_readonly_guards(conn, dialect_name: str) -> None:
    if dialect_name in {"postgresql", "mysql", "mariadb"}:
        conn.execute(text("SET TRANSACTION READ ONLY"))


def execute_query(
    user_id: str,
    engine: Engine,
    sql: str,
    row_limit: int = 500,
    connection_id: Optional[str] = None,
    readonly: bool = True,
) -> QueryExecutionResult:
    is_safe, error_msg = validate_query(sql)
    if not is_safe:
        return QueryExecutionResult(success=False, error=error_msg)

    safe_sql = sanitize_row_limit(sql, row_limit)
    start_time = time.time()

    try:
        with engine.connect() as conn:
            transaction = conn.begin()
            try:
                conn.execute(text(f"SET statement_timeout = '{QUERY_TIMEOUT * 1000}'"))
            except Exception:
                pass

            try:
                _apply_readonly_guards(conn, engine.dialect.name)
            except Exception:
                transaction.rollback()
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
        elif "timeout" in lowered or "cancel" in lowered:
            friendly = f"Query timed out after {QUERY_TIMEOUT} seconds. Try a simpler query or add filters."
        elif "permission" in lowered or "denied" in lowered:
            friendly = "Permission denied. Your database user may not have access to this table."
        else:
            friendly = error_text.split("\n")[0]

        return _log_and_return(
            QueryExecutionResult(
                success=False,
                execution_time_ms=round(elapsed, 2),
                error=friendly,
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
