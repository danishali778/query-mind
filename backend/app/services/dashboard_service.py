"""Dashboard and widget workflows."""

from typing import Optional

from app.agents.insights.generator import generate_widget_insight
from app.db.models.dashboard import (
    AddWidgetInput,
    CreateDashboardInput,
    Dashboard,
    DashboardWidget,
    UpdateDashboardInput,
    UpdateWidgetInput,
)
from app.db.repositories import dashboard_repository
from app.services import scheduling_service
from app.services.query_execution_service import execute_for_connection


def apply_global_filters(sql: str, filters: dict) -> str:
    """Wrap SQL in a CTE and apply global dashboard filters."""
    if not filters:
        return sql
    clean_sql = sql.strip().rstrip(";")
    wrapped = f"WITH __user_query AS (\n{clean_sql}\n)\nSELECT * FROM __user_query WHERE 1=1"

    date_range = filters.get("date_range")
    if date_range and date_range != "all":
        try:
            days = int(date_range)
            wrapped += f" AND created_at >= NOW() - INTERVAL '{days} days'"
        except Exception:
            pass

    status = filters.get("status")
    if status:
        wrapped += f" AND status = '{status}'"

    limit = filters.get("limit")
    if limit:
        try:
            limit_value = int(limit)
            wrapped += f" LIMIT {limit_value}"
        except Exception:
            pass

    return wrapped


async def create_dashboard(user_id: str, req: CreateDashboardInput) -> Dashboard:
    return await dashboard_repository.create_dashboard(user_id, req)


async def list_dashboards(user_id: str):
    return await dashboard_repository.list_dashboards(user_id)


async def get_dashboard(user_id: str, dashboard_id: str) -> Optional[Dashboard]:
    return await dashboard_repository.get_dashboard(user_id, dashboard_id)


async def rename_dashboard(user_id: str, dashboard_id: str, name: str) -> Optional[Dashboard]:
    return await dashboard_repository.rename_dashboard(user_id, dashboard_id, name)


async def update_dashboard(
    user_id: str,
    dashboard_id: str,
    req: UpdateDashboardInput,
) -> Optional[Dashboard]:
    return await dashboard_repository.update_dashboard(user_id, dashboard_id, req)


async def delete_dashboard(user_id: str, dashboard_id: str) -> bool:
    return await dashboard_repository.delete_dashboard(user_id, dashboard_id)


async def get_shared_dashboard(token: str) -> Optional[Dashboard]:
    return await dashboard_repository.get_shared_dashboard(token)


async def get_shared_widgets(dashboard_id: str):
    return await dashboard_repository.get_shared_widgets(dashboard_id)


async def list_widgets(user_id: str, dashboard_id: Optional[str] = None):
    return await dashboard_repository.list_widgets(user_id, dashboard_id=dashboard_id)


async def get_widget(user_id: str, widget_id: str) -> Optional[DashboardWidget]:
    return await dashboard_repository.get_widget(user_id, widget_id)


async def add_widget(user_id: str, req: AddWidgetInput) -> DashboardWidget:
    dashboard = await get_dashboard(user_id, req.dashboard_id)
    if not dashboard:
        raise ValueError("Dashboard not found.")
    widget = await dashboard_repository.add_widget(user_id, req)
    await scheduling_service.sync_widget_runtime(user_id, widget.id, widget.cadence)
    refreshed = await dashboard_repository.get_widget(user_id, widget.id)
    return refreshed or widget


async def update_widget(
    user_id: str,
    widget_id: str,
    req: UpdateWidgetInput,
) -> Optional[DashboardWidget]:
    widget = await dashboard_repository.update_widget(user_id, widget_id, req)
    if not widget:
        return None
    if req.cadence is not None:
        await scheduling_service.sync_widget_runtime(user_id, widget.id, widget.cadence)
        refreshed = await dashboard_repository.get_widget(user_id, widget.id)
        if refreshed:
            widget = refreshed
    return widget


async def delete_widget(user_id: str, widget_id: str) -> bool:
    return await dashboard_repository.delete_widget(user_id, widget_id)


async def refresh_widget(
    user_id: str,
    widget_id: str,
    *,
    row_limit: int = 500,
) -> DashboardWidget:
    widget = await get_widget(user_id, widget_id)
    if not widget or not widget.sql or not widget.connection_id:
        raise ValueError("Invalid widget for refresh.")

    dashboard = await get_dashboard(user_id, widget.dashboard_id)
    final_sql = apply_global_filters(widget.sql, dashboard.filters if dashboard else {})
    result = await execute_for_connection(
        user_id,
        widget.connection_id,
        final_sql,
        row_limit=row_limit,
    )
    if not result.success:
        raise RuntimeError(result.error or "Widget refresh failed.")

    updated = await update_widget(
        user_id,
        widget_id,
        UpdateWidgetInput(columns=result.columns, rows=result.rows),
    )
    if not updated:
        raise ValueError("Widget not found.")
    return updated


async def build_widget_insight(user_id: str, widget_id: str) -> str:
    widget = await get_widget(user_id, widget_id)
    if not widget:
        raise ValueError("Widget not found.")

    dashboard = await get_dashboard(user_id, widget.dashboard_id)
    return generate_widget_insight(
        widget.title,
        widget.viz_type,
        widget.rows,
        dashboard.filters if dashboard else {},
    )


async def get_stats(user_id: str, dashboard_id: Optional[str] = None) -> dict:
    return await dashboard_repository.get_stats(user_id, dashboard_id=dashboard_id)


async def get_all_scheduled_widgets():
    return await dashboard_repository.get_all_scheduled_widgets()


__all__ = [
    "create_dashboard",
    "list_dashboards",
    "get_dashboard",
    "rename_dashboard",
    "update_dashboard",
    "delete_dashboard",
    "get_shared_dashboard",
    "get_shared_widgets",
    "add_widget",
    "list_widgets",
    "get_widget",
    "delete_widget",
    "update_widget",
    "refresh_widget",
    "build_widget_insight",
    "get_stats",
    "get_all_scheduled_widgets",
    "apply_global_filters",
]
