"""Query-library workflows."""

from typing import Optional

from app.db.models.query_library import SaveQueryInput, ScheduleConfig, UpdateQueryInput
from app.db.repositories import query_library_repository
from app.services import connection_service, query_template_service, scheduling_service
from app.services.query_execution_service import execute_for_connection


async def list_queries(
    user_id: str,
    folder: Optional[str] = None,
    tag: Optional[str] = None,
    connection_id: Optional[str] = None,
    recently_run: bool = False,
):
    return await query_library_repository.list_queries(
        user_id=user_id,
        folder=folder,
        tag=tag,
        connection_id=connection_id,
        recently_run=recently_run,
    )


async def get_query(user_id: str, query_id: str):
    return await query_library_repository.get_query(user_id, query_id)


async def save_query(user_id: str, req: SaveQueryInput):
    query, created = await query_library_repository.save_query(user_id, req)
    if created and query.schedule and query.schedule.enabled:
        await scheduling_service.sync_saved_query_runtime(user_id, query.id, query.schedule)
        refreshed = await query_library_repository.get_query(user_id, query.id)
        if refreshed:
            query = refreshed
    return query, created


async def update_query(user_id: str, query_id: str, req: UpdateQueryInput):
    query = await query_library_repository.update_query(user_id, query_id, req)
    if not query:
        return None

    if "schedule" in req.model_dump(exclude_unset=True):
        if query.schedule and query.schedule.enabled:
            await scheduling_service.sync_saved_query_runtime(user_id, query.id, query.schedule)
        else:
            await scheduling_service.clear_saved_query_runtime(user_id, query.id)
        refreshed = await query_library_repository.get_query(user_id, query.id)
        if refreshed:
            query = refreshed
    return query


async def delete_query(user_id: str, query_id: str) -> bool:
    return await query_library_repository.delete_query(user_id, query_id)


async def run_saved_query(user_id: str, query_id: str, *, row_limit: int = 500):
    query = await get_query(user_id, query_id)
    if not query:
        raise ValueError("Query not found.")
    if not query.connection_id:
        raise ValueError("No connection_id associated with this query.")

    result = await execute_for_connection(
        user_id,
        query.connection_id,
        query.sql,
        row_limit=row_limit,
    )
    await query_library_repository.increment_run_count(user_id, query_id)
    await query_library_repository.log_run(
        user_id=user_id,
        query_id=query_id,
        success=result.success,
        row_count=result.row_count,
        execution_time_ms=result.execution_time_ms,
        error=result.error,
    )
    return result


async def get_run_history(user_id: str, query_id: str, limit: int = 20):
    return await query_library_repository.get_run_history(user_id, query_id, limit=limit)


async def create_folder(user_id: str, name: str):
    return await query_library_repository.create_folder(user_id, name)


async def list_folders(user_id: str):
    return await query_library_repository.list_folders(user_id)


async def list_tags(user_id: str):
    return await query_library_repository.list_tags(user_id)


async def get_stats(user_id: str):
    return await query_library_repository.get_stats(user_id)


async def get_schedule_status(user_id: str, query_id: str) -> dict:
    query = await get_query(user_id, query_id)
    if not query:
        raise ValueError("Query not found.")
    return {
        "query_id": query_id,
        "schedule": query.schedule,
        "schedule_label": query.schedule_label,
        "message": "OK",
    }


async def set_schedule(user_id: str, query_id: str, config: ScheduleConfig) -> dict:
    query = await get_query(user_id, query_id)
    if not query:
        raise ValueError("Query not found.")
    if not query.connection_id:
        raise ValueError("Cannot schedule a query without a database connection.")

    updated = await query_library_repository.update_schedule(user_id, query_id, config)
    if config.enabled:
        await scheduling_service.sync_saved_query_runtime(user_id, query_id, config)
    else:
        await scheduling_service.clear_saved_query_runtime(user_id, query_id)

    refreshed = await query_library_repository.get_query(user_id, query_id)
    final_query = refreshed or updated
    return {
        "query_id": query_id,
        "schedule": final_query.schedule if final_query else None,
        "schedule_label": final_query.schedule_label if final_query else None,
        "message": "Schedule updated." if config.enabled else "Schedule disabled.",
    }


async def remove_schedule(user_id: str, query_id: str) -> dict:
    query = await get_query(user_id, query_id)
    if not query:
        raise ValueError("Query not found.")

    await query_library_repository.update_schedule(user_id, query_id, None)
    await scheduling_service.clear_saved_query_runtime(user_id, query_id)
    return {
        "query_id": query_id,
        "schedule": None,
        "schedule_label": None,
        "message": "Schedule removed.",
    }


async def get_public_templates(user_id: str, connection_id: Optional[str]) -> dict:
    if not connection_id:
        return {"status": "not_started", "connection_id": None, "templates": []}

    if not await connection_service.get_engine(user_id, connection_id):
        raise ValueError("Connection not found.")

    status = query_template_service.get_generation_status(user_id, connection_id)
    templates = query_template_service.list_templates(user_id, connection_id)
    return {
        "status": status,
        "connection_id": connection_id,
        "templates": [template.model_dump() for template in templates],
    }


async def trigger_template_generation(user_id: str, connection_id: str) -> dict:
    schema_text = await connection_service.get_schema_for_ai(user_id, connection_id)
    if not schema_text:
        raise ValueError("Connection not found.")

    all_connections = await connection_service.get_all_connections(user_id)
    db_type = next((conn.db_type for conn in all_connections if conn.id == connection_id), "postgresql")
    query_template_service.start_template_generation(user_id, connection_id, schema_text, db_type)
    return {"message": "Template generation started.", "connection_id": connection_id}


async def clone_public_template(
    user_id: str,
    template_id: str,
    connection_id: Optional[str] = None,
):
    template = query_template_service.get_template(user_id, template_id)
    if not template:
        raise ValueError("Template not found.")

    target_connection_id = connection_id or template.connection_id
    if connection_id and not await connection_service.get_engine(user_id, connection_id):
        raise ValueError("Target connection not found.")

    request = SaveQueryInput(
        title=template.title,
        sql=template.sql,
        description=template.description,
        folder_name="Uncategorized",
        connection_id=target_connection_id,
        icon=template.icon,
        icon_bg=template.icon_bg,
        tags=template.tags,
    )
    return await save_query(user_id, request)


async def find_duplicate(user_id: str, sql: str, connection_id: Optional[str] = None):
    return await query_library_repository.find_duplicate(user_id, sql, connection_id)


async def increment_run_count(user_id: str, query_id: str):
    return await query_library_repository.increment_run_count(user_id, query_id)


async def get_scheduled_queries(user_id: Optional[str] = None):
    return await query_library_repository.get_scheduled_queries(user_id)


async def update_schedule(user_id: str, query_id: str, config: Optional[ScheduleConfig]):
    return await query_library_repository.update_schedule(user_id, query_id, config)


async def log_run(
    user_id: str,
    query_id: str,
    success: bool,
    row_count: int = 0,
    execution_time_ms: float = 0.0,
    error: Optional[str] = None,
    triggered_by: str = "manual",
):
    return await query_library_repository.log_run(
        user_id=user_id,
        query_id=query_id,
        success=success,
        row_count=row_count,
        execution_time_ms=execution_time_ms,
        error=error,
        triggered_by=triggered_by,
    )


def sync_get_query(user_id: str, query_id: str):
    return query_library_repository.sync_get_query(user_id, query_id)


def sync_get_scheduled_queries(user_id: Optional[str] = None):
    return query_library_repository.sync_get_scheduled_queries(user_id)


def sync_increment_run_count(user_id: str, query_id: str):
    return query_library_repository.sync_increment_run_count(user_id, query_id)


def sync_log_run(
    user_id: str,
    query_id: str,
    success: bool,
    row_count: int = 0,
    execution_time_ms: float = 0.0,
    error: Optional[str] = None,
    triggered_by: str = "scheduler",
):
    return query_library_repository.sync_log_run(
        user_id=user_id,
        query_id=query_id,
        success=success,
        row_count=row_count,
        execution_time_ms=execution_time_ms,
        error=error,
        triggered_by=triggered_by,
    )


__all__ = [
    "find_duplicate",
    "save_query",
    "list_queries",
    "get_query",
    "update_query",
    "delete_query",
    "increment_run_count",
    "create_folder",
    "list_folders",
    "list_tags",
    "get_stats",
    "get_scheduled_queries",
    "update_schedule",
    "log_run",
    "get_run_history",
    "run_saved_query",
    "get_schedule_status",
    "set_schedule",
    "remove_schedule",
    "get_public_templates",
    "trigger_template_generation",
    "clone_public_template",
    "sync_get_query",
    "sync_get_scheduled_queries",
    "sync_increment_run_count",
    "sync_log_run",
]
