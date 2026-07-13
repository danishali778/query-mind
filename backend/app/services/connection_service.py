"""Connection workflows backed by the DB connection manager."""

from app.db.models.connection import ActiveConnection, ConnectionRequest, ConnectionTestResult, TableInfo
from app.db.connection_manager import (
    connect,
    disconnect,
    generate_erd_json,
    generate_erd_mermaid,
    get_all_connections,
    get_cached_schema,
    get_connection,
    get_connection_schema,
    get_engine,
    get_readonly,
    get_schema_for_ai,
    get_catalog,
    catalog_to_table_info,
    invalidate_catalog,
    record_connection_health,
    record_query_execution_health,
    record_query_execution_health_sync,
    record_schema_sync,
    refresh_schema as _refresh_schema,
    sanitize_connection_error,
    seed_dev_connection,
    test_connection,
    test_saved_connection,
    update_settings,
)


async def refresh_schema(user_id: str, connection_id: str):
    schema = await _refresh_schema(user_id, connection_id)
    if schema is not None:
        catalog = await get_catalog(user_id, connection_id)
        if catalog:
            from app.services.semantic_drift_service import revalidate

            await revalidate(user_id, connection_id, catalog)
    return schema


__all__ = [
    "connect",
    "disconnect",
    "generate_erd_json",
    "generate_erd_mermaid",
    "get_all_connections",
    "get_cached_schema",
    "get_connection",
    "get_connection_schema",
    "catalog_to_table_info",
    "get_engine",
    "get_readonly",
    "get_schema_for_ai",
    "record_connection_health",
    "record_query_execution_health",
    "record_query_execution_health_sync",
    "record_schema_sync",
    "refresh_schema",
    "sanitize_connection_error",
    "seed_dev_connection",
    "test_connection",
    "test_saved_connection",
    "update_settings",
]
