from datetime import datetime
from typing import Optional

from sqlalchemy import desc, func, select

from app.db.models.query_history import QueryRecord
from app.db.orm_models import QueryExecutionORM
from app.db.session import session_scope


def _record_to_domain(row: QueryExecutionORM) -> QueryRecord:
    return QueryRecord(
        id=row.id,
        connection_id=row.connection_id or "",
        sql=row.sql,
        success=row.success,
        error=row.error,
        execution_time_ms=row.execution_time_ms,
        row_count=row.row_count,
        owner_id=row.owner_id,
        timestamp=row.ran_at if isinstance(row.ran_at, datetime) else datetime.fromisoformat(str(row.ran_at)),
    )


def log_query(
    user_id: str,
    connection_id: str,
    sql: str,
    success: bool,
    error: Optional[str] = None,
    execution_time_ms: Optional[float] = None,
    row_count: Optional[int] = None,
) -> QueryRecord:
    """Log a query execution. Called automatically after every query."""
    with session_scope() as session:
        row = QueryExecutionORM(
            owner_id=user_id,
            connection_id=connection_id,
            sql=sql.strip(),
            success=success,
            error=error,
            execution_time_ms=execution_time_ms or 0.0,
            row_count=row_count or 0,
            triggered_by="manual",
        )
        session.add(row)
        session.flush()
        return _record_to_domain(row)


def get_history(
    user_id: str,
    connection_id: Optional[str] = None,
    limit: int = 20,
) -> list[QueryRecord]:
    """Get recent ad-hoc query history for a user, optionally filtered by connection."""
    with session_scope() as session:
        stmt = (
            select(QueryExecutionORM)
            .where(QueryExecutionORM.owner_id == user_id)
            .where(QueryExecutionORM.query_id.is_(None))
            .order_by(desc(QueryExecutionORM.ran_at))
            .limit(limit)
        )
        if connection_id:
            stmt = stmt.where(QueryExecutionORM.connection_id == connection_id)

        return [_record_to_domain(row) for row in session.scalars(stmt).all()]


def get_stats(user_id: str, connection_id: str) -> dict:
    """Get quick stats for a connection's query activity."""
    with session_scope() as session:
        stmt = (
            select(QueryExecutionORM.success, QueryExecutionORM.execution_time_ms)
            .where(QueryExecutionORM.owner_id == user_id)
            .where(QueryExecutionORM.connection_id == connection_id)
            .limit(100)
        )
        records = session.execute(stmt).all()

    if not records:
        return {"total": 0, "successful": 0, "failed": 0, "avg_time_ms": 0}

    successful = [record for record in records if record.success]
    failed = [record for record in records if not record.success]
    times = [record.execution_time_ms for record in records if record.execution_time_ms is not None]

    return {
        "total": len(records),
        "successful": len(successful),
        "failed": len(failed),
        "avg_time_ms": round(sum(times) / len(times), 2) if times else 0,
    }


def get_connection_totals(user_id: str) -> dict[str, int]:
    """Return query counts grouped by connection for analytics use cases."""
    with session_scope() as session:
        stmt = (
            select(QueryExecutionORM.connection_id, func.count(QueryExecutionORM.id))
            .where(QueryExecutionORM.owner_id == user_id)
            .group_by(QueryExecutionORM.connection_id)
        )
        return {
            str(connection_id): int(count)
            for connection_id, count in session.execute(stmt).all()
            if connection_id is not None
        }