"""Owner-scoped connection health history and aggregate diagnostics."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy.orm import Session

from app.db.models.connection import ConnectionHealthEvent
from app.db.orm_models import ConnectionHealthEventORM, DatabaseConnectionORM
from app.db.session import read_session_scope, session_scope


def _now() -> datetime:
    return datetime.now(timezone.utc)


def record_sync(
    session: Session,
    *,
    owner_id: str,
    connection_id: str,
    source: str,
    status: str,
    diagnostic_code: str | None,
    message: str | None,
    latency_ms: float | None,
) -> str:
    row = ConnectionHealthEventORM(
        id=str(uuid.uuid4()), owner_id=owner_id, connection_id=connection_id,
        source=source, status=status, diagnostic_code=diagnostic_code,
        message=message, latency_ms=latency_ms,
    )
    session.add(row)
    session.flush()
    return row.id


def record(**kwargs) -> str:
    with session_scope() as session:
        return record_sync(session, **kwargs)


def history(owner_id: str, connection_id: str, *, cursor: str | None, limit: int) -> dict | None:
    with read_session_scope() as session:
        connection = session.query(DatabaseConnectionORM).filter(
            DatabaseConnectionORM.id == connection_id,
            DatabaseConnectionORM.owner_id == owner_id,
        ).one_or_none()
        if not connection:
            return None
        query = session.query(ConnectionHealthEventORM).filter(
            ConnectionHealthEventORM.owner_id == owner_id,
            ConnectionHealthEventORM.connection_id == connection_id,
        )
        if cursor:
            try:
                query = query.filter(ConnectionHealthEventORM.created_at < datetime.fromisoformat(cursor))
            except ValueError:
                pass
        rows = query.order_by(ConnectionHealthEventORM.created_at.desc()).limit(limit + 1).all()
        page, extra = rows[:limit], len(rows) > limit
        all_recent = session.query(ConnectionHealthEventORM).filter(
            ConnectionHealthEventORM.owner_id == owner_id,
            ConnectionHealthEventORM.connection_id == connection_id,
            ConnectionHealthEventORM.created_at >= _now() - timedelta(days=7),
        ).all()
        def rate(hours: int) -> float:
            cutoff = _now() - timedelta(hours=hours)
            selected = [item for item in all_recent if item.created_at and item.created_at.replace(tzinfo=item.created_at.tzinfo or timezone.utc) >= cutoff]
            return round(sum(item.status == "healthy" for item in selected) / len(selected) * 100, 1) if selected else 0.0
        latencies = sorted(float(item.latency_ms) for item in all_recent if item.latency_ms is not None)
        def percentile(value: float) -> float | None:
            if not latencies:
                return None
            index = min(len(latencies) - 1, max(0, round((len(latencies) - 1) * value)))
            return round(latencies[index], 2)
        last_schema_row = session.query(ConnectionHealthEventORM.created_at).filter(
            ConnectionHealthEventORM.owner_id == owner_id,
            ConnectionHealthEventORM.connection_id == connection_id,
            ConnectionHealthEventORM.source == "schema_refresh",
            ConnectionHealthEventORM.status == "healthy",
        ).order_by(ConnectionHealthEventORM.created_at.desc()).first()
        last_schema = last_schema_row.created_at if last_schema_row else None
        return {
            "connection_id": connection_id,
            "items": [
                ConnectionHealthEvent(
                    id=item.id,
                    connection_id=item.connection_id,
                    source=item.source,
                    status=item.status,
                    diagnostic_code=item.diagnostic_code,
                    message=item.message,
                    latency_ms=item.latency_ms,
                    created_at=item.created_at,
                ).model_dump(mode="json")
                for item in page
            ],
            "next_cursor": page[-1].created_at.isoformat() if extra and page else None,
            "success_rate_24h": rate(24),
            "success_rate_7d": rate(168),
            "p50_latency_ms": percentile(0.5),
            "p95_latency_ms": percentile(0.95),
            "last_successful_schema_refresh_at": last_schema,
            "next_health_check_at": connection.next_health_check_at,
            "next_schema_refresh_at": connection.next_schema_refresh_at,
        }


def cleanup(retention_days: int) -> int:
    with session_scope() as session:
        return session.query(ConnectionHealthEventORM).filter(
            ConnectionHealthEventORM.created_at < _now() - timedelta(days=retention_days)
        ).delete(synchronize_session=False)


__all__ = ["cleanup", "history", "record", "record_sync"]
