import asyncio
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import desc

from app.db.models.query_library import (
    QueryRunRecord,
    SaveQueryInput,
    SavedQuery,
    ScheduleConfig,
    UpdateQueryInput,
)
from app.db.orm_models import QueryExecutionORM, SavedQueryORM
from app.db.session import session_scope


def _normalize_sql(sql: str) -> str:
    """Normalize SQL for duplicate comparison."""
    return " ".join(sql.strip().lower().split())


def _parse_dt(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _map_to_saved_query(row: SavedQueryORM) -> SavedQuery:
    metadata = row.metadata_ or {}
    schedule_data = row.schedule or {}
    created_at = _parse_dt(row.created_at) or datetime.now(timezone.utc)
    last_run_at = _parse_dt(row.last_run_at)
    updated_at = last_run_at or created_at
    return SavedQuery(
        id=row.id,
        title=row.title,
        sql=row.sql,
        description=row.description or "",
        folder_name=metadata.get("folder_name", "Uncategorized"),
        connection_id=row.connection_id,
        icon=metadata.get("icon", "\U0001f4c4"),
        icon_bg=metadata.get("icon_bg", "rgba(0,229,255,0.1)"),
        tags=metadata.get("tags", []),
        schedule=ScheduleConfig(**schedule_data) if schedule_data and schedule_data.get("frequency") else None,
        owner_id=row.owner_id,
        created_at=created_at,
        updated_at=updated_at,
        run_count=row.run_count or 0,
        last_run_at=last_run_at,
    )


def _map_to_run_record(row: QueryExecutionORM) -> QueryRunRecord:
    return QueryRunRecord(
        id=row.id,
        query_id=row.query_id,
        sql=row.sql,
        connection_id=row.connection_id,
        owner_id=row.owner_id,
        success=row.success,
        row_count=row.row_count or 0,
        execution_time_ms=row.execution_time_ms or 0.0,
        error=row.error,
        triggered_by=row.triggered_by or "manual",
        ran_at=_parse_dt(row.ran_at) or datetime.now(timezone.utc),
    )


async def find_duplicate(user_id: str, sql: str, connection_id: Optional[str] = None) -> Optional[SavedQuery]:
    with session_scope() as session:
        query = session.query(SavedQueryORM).filter(SavedQueryORM.owner_id == user_id)
        if connection_id:
            query = query.filter(SavedQueryORM.connection_id == connection_id)
        else:
            query = query.filter(SavedQueryORM.connection_id.is_(None))
        normalized_input = _normalize_sql(sql)
        for row in query.all():
            if _normalize_sql(row.sql) == normalized_input:
                return _map_to_saved_query(row)
    return None


async def save_query(user_id: str, req: SaveQueryInput) -> tuple[SavedQuery, bool]:
    existing = await find_duplicate(user_id, req.sql, req.connection_id)
    if existing:
        return existing, False

    metadata = {
        "folder_name": req.folder_name,
        "icon": req.icon,
        "icon_bg": req.icon_bg,
        "tags": req.tags,
    }
    schedule = req.schedule.model_dump() if req.schedule else {}

    with session_scope() as session:
        row = SavedQueryORM(
            owner_id=user_id,
            title=req.title,
            sql=req.sql,
            description=req.description,
            connection_id=req.connection_id,
            metadata_=metadata,
            schedule=schedule,
            run_count=0,
        )
        session.add(row)
        session.flush()
        return _map_to_saved_query(row), True


async def get_query(user_id: str, query_id: str) -> Optional[SavedQuery]:
    with session_scope() as session:
        row = (
            session.query(SavedQueryORM)
            .filter(SavedQueryORM.id == query_id, SavedQueryORM.owner_id == user_id)
            .one_or_none()
        )
        return _map_to_saved_query(row) if row else None


async def list_queries(
    user_id: str,
    folder: Optional[str] = None,
    tag: Optional[str] = None,
    connection_id: Optional[str] = None,
    recently_run: bool = False,
) -> list[SavedQuery]:
    with session_scope() as session:
        query = session.query(SavedQueryORM).filter(SavedQueryORM.owner_id == user_id)
        if connection_id:
            query = query.filter(SavedQueryORM.connection_id == connection_id)
        rows = query.all()

    result = [_map_to_saved_query(row) for row in rows]

    if folder and folder not in ("All Queries", "Recently Run", "Scheduled"):
        result = [q for q in result if q.folder_name == folder]

    if folder == "Scheduled":
        result = [q for q in result if q.schedule and q.schedule.enabled]

    if tag:
        result = [q for q in result if tag in q.tags]

    if recently_run or folder == "Recently Run":
        result = [q for q in result if q.last_run_at is not None]
        result.sort(key=lambda q: q.last_run_at or datetime.min, reverse=True)
        return result

    result.sort(key=lambda q: q.updated_at, reverse=True)
    return result


async def update_query(user_id: str, query_id: str, req: UpdateQueryInput) -> Optional[SavedQuery]:
    with session_scope() as session:
        row = (
            session.query(SavedQueryORM)
            .filter(SavedQueryORM.id == query_id, SavedQueryORM.owner_id == user_id)
            .one_or_none()
        )
        if not row:
            return None

        update_data = req.model_dump(exclude_unset=True)
        for field in ["title", "sql", "description", "connection_id"]:
            if field in update_data:
                setattr(row, field, update_data[field])

        metadata = dict(row.metadata_ or {})
        metadata_changed = False
        for field in ["folder_name", "icon", "icon_bg", "tags"]:
            if field in update_data:
                metadata[field] = update_data[field]
                metadata_changed = True
        if metadata_changed:
            row.metadata_ = metadata

        if "schedule" in update_data:
            row.schedule = update_data["schedule"].model_dump() if update_data["schedule"] else {}


        session.flush()
        return _map_to_saved_query(row)


async def delete_query(user_id: str, query_id: str) -> bool:
    with session_scope() as session:
        row = (
            session.query(SavedQueryORM)
            .filter(SavedQueryORM.id == query_id, SavedQueryORM.owner_id == user_id)
            .one_or_none()
        )
        if not row:
            return False
        session.delete(row)
        return True


async def increment_run_count(user_id: str, query_id: str) -> Optional[SavedQuery]:
    with session_scope() as session:
        row = (
            session.query(SavedQueryORM)
            .filter(SavedQueryORM.id == query_id, SavedQueryORM.owner_id == user_id)
            .one_or_none()
        )
        if not row:
            return None
        row.run_count = (row.run_count or 0) + 1
        row.last_run_at = datetime.now(timezone.utc)

        session.flush()
        return _map_to_saved_query(row)


async def create_folder(user_id: str, name: str) -> bool:
    return True


async def list_folders(user_id: str) -> list[dict]:
    queries = await list_queries(user_id)
    folders: dict[str, int] = {}
    for q in queries:
        folders[q.folder_name] = folders.get(q.folder_name, 0) + 1
    return [{"name": name, "count": count} for name, count in sorted(folders.items())]


async def list_tags(user_id: str) -> list[str]:
    queries = await list_queries(user_id)
    tags: set[str] = set()
    for q in queries:
        tags.update(q.tags)
    return sorted(tags)


async def get_stats(user_id: str) -> dict:
    queries = await list_queries(user_id)
    total = len(queries)
    scheduled = len([q for q in queries if q.schedule and q.schedule.enabled])
    total_runs = sum(q.run_count for q in queries)
    return {
        "total_queries": total,
        "scheduled": scheduled,
        "total_runs": total_runs,
        "recently_run": len([q for q in queries if q.last_run_at]),
        "folders": len(set(q.folder_name for q in queries)),
    }


async def get_scheduled_queries(user_id: Optional[str] = None) -> list[SavedQuery]:
    with session_scope() as session:
        query = session.query(SavedQueryORM)
        if user_id:
            query = query.filter(SavedQueryORM.owner_id == user_id)
        result = [_map_to_saved_query(row) for row in query.all()]
    return [q for q in result if q.schedule and q.schedule.enabled]


async def update_schedule(user_id: str, query_id: str, config: Optional[ScheduleConfig]) -> Optional[SavedQuery]:
    with session_scope() as session:
        row = (
            session.query(SavedQueryORM)
            .filter(SavedQueryORM.id == query_id, SavedQueryORM.owner_id == user_id)
            .one_or_none()
        )
        if not row:
            return None
        row.schedule = config.model_dump() if config else {}

        session.flush()
        return _map_to_saved_query(row)


async def log_run(
    user_id: str,
    query_id: str,
    success: bool,
    row_count: int = 0,
    execution_time_ms: float = 0.0,
    error: Optional[str] = None,
    triggered_by: str = "manual",
) -> QueryRunRecord:
    query = await get_query(user_id, query_id)
    if not query:
        raise Exception(f"Query {query_id} not found for logging")

    with session_scope() as session:
        row = QueryExecutionORM(
            query_id=query_id,
            owner_id=user_id,
            connection_id=query.connection_id,
            sql=query.sql,
            success=success,
            row_count=row_count,
            execution_time_ms=execution_time_ms,
            error=error,
            triggered_by=triggered_by,
        )
        session.add(row)
        session.flush()
        return _map_to_run_record(row)


async def get_run_history(user_id: str, query_id: str, limit: int = 20) -> list[QueryRunRecord]:
    with session_scope() as session:
        rows = (
            session.query(QueryExecutionORM)
            .filter(QueryExecutionORM.query_id == query_id, QueryExecutionORM.owner_id == user_id)
            .order_by(desc(QueryExecutionORM.ran_at))
            .limit(limit)
            .all()
        )
        return [_map_to_run_record(row) for row in rows]


def sync_get_query(user_id: str, query_id: str) -> Optional[SavedQuery]:
    return asyncio.run(get_query(user_id, query_id))


def sync_get_scheduled_queries(user_id: Optional[str] = None) -> list[SavedQuery]:
    return asyncio.run(get_scheduled_queries(user_id))


def sync_increment_run_count(user_id: str, query_id: str) -> Optional[SavedQuery]:
    return asyncio.run(increment_run_count(user_id, query_id))


def sync_log_run(
    user_id: str,
    query_id: str,
    success: bool,
    row_count: int = 0,
    execution_time_ms: float = 0.0,
    error: Optional[str] = None,
    triggered_by: str = "scheduler",
) -> QueryRunRecord:
    return asyncio.run(log_run(
        user_id=user_id,
        query_id=query_id,
        success=success,
        row_count=row_count,
        execution_time_ms=execution_time_ms,
        error=error,
        triggered_by=triggered_by,
    ))