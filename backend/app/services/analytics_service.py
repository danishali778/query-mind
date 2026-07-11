import functools

import anyio

import app.services.connection_service as connection_service
import app.services.dashboard_service as dashboard_store
import app.services.query_history_service as query_history_store
import app.services.query_library_service as library_store


async def build_analytics_overview(user_id: str) -> dict:
    """Return workspace-level analytics aggregated from existing persistent stores."""
    connections = await connection_service.get_all_connections(user_id)
    history = await anyio.to_thread.run_sync(
        functools.partial(query_history_store.get_history, user_id, limit=500)
    )
    library_stats = await library_store.get_stats(user_id)
    dashboards = await dashboard_store.list_dashboards(user_id)
    dashboard_stats = await dashboard_store.get_stats(user_id)

    successful = [record for record in history if record.success]
    failed = [record for record in history if not record.success]
    durations = [record.execution_time_ms for record in history if record.execution_time_ms is not None]

    connection_lookup = {conn.id: conn for conn in connections}
    usage_counts: dict[str, int] = {}
    for record in history:
        usage_counts[record.connection_id] = usage_counts.get(record.connection_id, 0) + 1

    top_connections = [
        {
            "connection_id": connection_id,
            "name": getattr(connection_lookup.get(connection_id), "name", "Unknown") if connection_lookup.get(connection_id) else "Unknown",
            "database": getattr(connection_lookup.get(connection_id), "database", "Unknown") if connection_lookup.get(connection_id) else "Unknown",
            "db_type": getattr(connection_lookup.get(connection_id), "db_type", "unknown") if connection_lookup.get(connection_id) else "unknown",
            "query_count": query_count,
        }
        for connection_id, query_count in sorted(usage_counts.items(), key=lambda item: item[1], reverse=True)[:5]
    ]

    recent_queries = []
    for record in history[:10]:
        conn = connection_lookup.get(record.connection_id)
        recent_queries.append({
            "id": record.id,
            "connection_id": record.connection_id,
            "connection_name": getattr(conn, "name", None) or getattr(conn, "database", None) or "Unknown" if conn else "Unknown",
            "sql": record.sql,
            "success": record.success,
            "error": record.error,
            "execution_time_ms": record.execution_time_ms,
            "row_count": record.row_count,
            "timestamp": record.timestamp.isoformat(),
        })

    return {
        "overview": {
            "active_connections": len(connections),
            "total_queries": len(history),
            "successful_queries": len(successful),
            "failed_queries": len(failed),
            "success_rate": round((len(successful) / len(history)) * 100, 1) if history else 0,
            "avg_time_ms": round(sum(durations) / len(durations), 2) if durations else 0,
            "saved_queries": library_stats["total_queries"],
            "scheduled_queries": library_stats["scheduled"],
            "dashboards": len(dashboards),
            "total_widgets": dashboard_stats["total_widgets"],
        },
        "library": library_stats,
        "dashboards": {
            "total_dashboards": len(dashboards),
            "total_widgets": dashboard_stats["total_widgets"],
            "viz_breakdown": dashboard_stats["viz_breakdown"],
            "items": dashboards,
        },
        "query_health": {
            "successful": len(successful),
            "failed": len(failed),
        },
        "top_connections": top_connections,
        "recent_queries": recent_queries,
    }
