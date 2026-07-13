import uuid
from datetime import datetime, timezone
from typing import Optional

import anyio
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.dashboard import (
    AddWidgetInput,
    CreateDashboardInput,
    Dashboard,
    DashboardSummary,
    DashboardWidget,
    UpdateDashboardInput,
    UpdateWidgetInput,
)
from app.db.orm_models import DashboardORM, DashboardWidgetORM
from app.db.session import read_session_scope, session_scope


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _map_dashboard(row: DashboardORM) -> Dashboard:
    return Dashboard(
        id=row.id,
        owner_id=row.owner_id,
        name=row.name,
        icon=row.icon or "\U0001f4ca",
        filters=row.filters or {},
        is_public=bool(row.is_public),
        share_token=row.share_token,
        creation_mode=getattr(row, "creation_mode", None) or "manual",
        lifecycle_status=getattr(row, "lifecycle_status", None) or "ready",
        created_at=row.created_at,
    )


def _map_widget(row: DashboardWidgetORM) -> DashboardWidget:
    layout_params = row.layout_params or {}
    chart_config = row.chart_config or None
    assumptions = row.assumptions if isinstance(getattr(row, "assumptions", None), list) else []
    return DashboardWidget(
        id=row.id,
        owner_id=row.owner_id,
        dashboard_id=row.dashboard_id,
        title=row.title,
        viz_type=row.viz_type,
        size=row.size,
        connection_id=row.connection_id,
        sql=row.sql,
        chart_config=chart_config,
        cadence=row.cadence or "Manual only",
        x=layout_params.get("x", 0),
        y=layout_params.get("y", 0),
        w=layout_params.get("w", 1),
        h=layout_params.get("h", 7),
        minW=layout_params.get("minW", 1),
        minH=layout_params.get("minH", 5),
        bar_orientation=layout_params.get("bar_orientation", "horizontal"),
        order_index=row.order_index or 0,
        source_type=getattr(row, "source_type", None) or "manual",
        source_prompt=getattr(row, "source_prompt", None),
        generation_item_id=getattr(row, "generation_item_id", None),
        generation_status=getattr(row, "generation_status", None) or "ready",
        generation_error=getattr(row, "generation_error", None),
        assumptions=[str(item) for item in assumptions],
        created_at=row.created_at,
        columns=row.columns or [],
        rows=row.rows or [],
    )


async def create_dashboard(user_id: str, req: CreateDashboardInput) -> Dashboard:
    def _run() -> Dashboard:
        with session_scope() as session:
            return _create_dashboard_sync(session, user_id, req)
    return await anyio.to_thread.run_sync(_run)


def _create_dashboard_sync(session: Session, user_id: str, req: CreateDashboardInput) -> Dashboard:
    row = DashboardORM(
        id=str(uuid.uuid4()),
        owner_id=user_id,
        name=req.name,
        icon=req.icon,
        filters=req.filters or {},
        is_public=False,
        creation_mode=req.creation_mode,
        lifecycle_status=req.lifecycle_status,
    )
    session.add(row)
    session.flush()
    return _map_dashboard(row)


async def list_dashboards(user_id: str) -> list[DashboardSummary]:
    def _run() -> list[DashboardSummary]:
        with read_session_scope() as session:
            return _list_dashboards_sync(session, user_id)
    return await anyio.to_thread.run_sync(_run)


def _list_dashboards_sync(session: Session, user_id: str) -> list[DashboardSummary]:
    rows = (
        session.query(DashboardORM, func.count(DashboardWidgetORM.id).label("widget_count"))
        .outerjoin(DashboardWidgetORM, DashboardWidgetORM.dashboard_id == DashboardORM.id)
        .filter(DashboardORM.owner_id == user_id)
        .group_by(DashboardORM.id)
        .order_by(DashboardORM.created_at.asc())
        .all()
    )
    result: list[DashboardSummary] = []
    for dashboard, widget_count in rows:
        result.append(DashboardSummary(**_map_dashboard(dashboard).model_dump(), widget_count=int(widget_count or 0)))
    return result


async def get_dashboard(user_id: str, dashboard_id: str) -> Optional[Dashboard]:
    def _run() -> Optional[Dashboard]:
        with read_session_scope() as session:
            return _get_dashboard_sync(session, user_id, dashboard_id)
    return await anyio.to_thread.run_sync(_run)


def _get_dashboard_sync(session: Session, user_id: str, dashboard_id: str) -> Optional[Dashboard]:
    row = (
        session.query(DashboardORM)
        .filter(DashboardORM.id == dashboard_id, DashboardORM.owner_id == user_id)
        .one_or_none()
    )
    return _map_dashboard(row) if row else None


async def rename_dashboard(user_id: str, dashboard_id: str, name: str) -> Optional[Dashboard]:
    def _run() -> Optional[Dashboard]:
        with session_scope() as session:
            return _rename_dashboard_sync(session, user_id, dashboard_id, name)
    return await anyio.to_thread.run_sync(_run)


def _rename_dashboard_sync(session: Session, user_id: str, dashboard_id: str, name: str) -> Optional[Dashboard]:
    row = (
        session.query(DashboardORM)
        .filter(DashboardORM.id == dashboard_id, DashboardORM.owner_id == user_id)
        .one_or_none()
    )
    if not row:
        return None
    row.name = name.strip()
    session.flush()
    return _map_dashboard(row)


async def update_dashboard(
    user_id: str,
    dashboard_id: str,
    req: UpdateDashboardInput,
) -> Optional[Dashboard]:
    def _run() -> Optional[Dashboard]:
        with session_scope() as session:
            return _update_dashboard_sync(session, user_id, dashboard_id, req)
    return await anyio.to_thread.run_sync(_run)


def _update_dashboard_sync(
    session: Session,
    user_id: str,
    dashboard_id: str,
    req: UpdateDashboardInput,
) -> Optional[Dashboard]:
    row = (
        session.query(DashboardORM)
        .filter(DashboardORM.id == dashboard_id, DashboardORM.owner_id == user_id)
        .one_or_none()
    )
    if not row:
        return None
    if req.name is not None:
        row.name = req.name
    if req.icon is not None:
        row.icon = req.icon
    if req.filters is not None:
        row.filters = req.filters
    if req.is_public is not None:
        row.is_public = False
    if req.lifecycle_status is not None:
        row.lifecycle_status = req.lifecycle_status
    session.flush()
    return _map_dashboard(row)


async def delete_dashboard(user_id: str, dashboard_id: str) -> bool:
    def _run() -> bool:
        with session_scope() as session:
            return _delete_dashboard_sync(session, user_id, dashboard_id)
    return await anyio.to_thread.run_sync(_run)


def _delete_dashboard_sync(session: Session, user_id: str, dashboard_id: str) -> bool:
    row = (
        session.query(DashboardORM)
        .filter(DashboardORM.id == dashboard_id, DashboardORM.owner_id == user_id)
        .one_or_none()
    )
    if not row:
        return False
    session.delete(row)
    return True


async def get_shared_dashboard(token: str) -> Optional[Dashboard]:
    def _run() -> Optional[Dashboard]:
        with read_session_scope() as session:
            return _get_shared_dashboard_sync(session, token)
    return await anyio.to_thread.run_sync(_run)


def _get_shared_dashboard_sync(session: Session, token: str) -> Optional[Dashboard]:
    row = (
        session.query(DashboardORM)
        .filter(DashboardORM.share_token == token, DashboardORM.is_public.is_(True))
        .one_or_none()
    )
    return _map_dashboard(row) if row else None


async def get_shared_widgets(dashboard_id: str) -> list[DashboardWidget]:
    def _run() -> list[DashboardWidget]:
        with read_session_scope() as session:
            return _get_shared_widgets_sync(session, dashboard_id)
    return await anyio.to_thread.run_sync(_run)


def _get_shared_widgets_sync(session: Session, dashboard_id: str) -> list[DashboardWidget]:
    rows = (
        session.query(DashboardWidgetORM)
        .filter(DashboardWidgetORM.dashboard_id == dashboard_id)
        .order_by(DashboardWidgetORM.order_index.asc(), DashboardWidgetORM.created_at.desc())
        .all()
    )
    return [_map_widget(row) for row in rows]


async def add_widget(user_id: str, req: AddWidgetInput) -> DashboardWidget:
    def _run() -> DashboardWidget:
        with session_scope() as session:
            return _add_widget_sync(session, user_id, req)
    return await anyio.to_thread.run_sync(_run)


def _add_widget_sync(session: Session, user_id: str, req: AddWidgetInput) -> DashboardWidget:
    size_defaults = {
        "half": {"w": 1, "h": 7, "minW": 1, "minH": 5},
        "full": {"w": 2, "h": 8, "minW": 2, "minH": 6},
    }
    layout_default = size_defaults.get(req.size, size_defaults["half"])

    dashboard = (
        session.query(DashboardORM)
        .filter(DashboardORM.id == req.dashboard_id, DashboardORM.owner_id == user_id)
        .one_or_none()
    )
    if not dashboard:
        raise Exception("Dashboard not found")

    current_widgets = (
        session.query(DashboardWidgetORM)
        .filter(DashboardWidgetORM.owner_id == user_id, DashboardWidgetORM.dashboard_id == req.dashboard_id)
        .all()
    )
    next_y = max((widget.layout_params or {}).get("y", 0) + (widget.layout_params or {}).get("h", 7) for widget in current_widgets) if current_widgets else 0
    next_order = max(widget.order_index or 0 for widget in current_widgets) + 1 if current_widgets else 0
    layout_params = {
        "x": req.x if req.x is not None else 0,
        "y": req.y if req.y is not None else next_y,
        "w": req.w if req.w is not None else layout_default["w"],
        "h": req.h if req.h is not None else layout_default["h"],
        "minW": req.minW if req.minW is not None else layout_default["minW"],
        "minH": req.minH if req.minH is not None else layout_default["minH"],
        "bar_orientation": req.bar_orientation or "horizontal",
    }
    row = DashboardWidgetORM(
        id=str(uuid.uuid4()),
        dashboard_id=req.dashboard_id,
        owner_id=user_id,
        title=req.title,
        viz_type=req.viz_type,
        size=req.size,
        connection_id=req.connection_id,
        sql=req.sql,
        chart_config=req.chart_config.model_dump() if req.chart_config else {},
        layout_params=layout_params,
        cadence=req.cadence,
        order_index=req.order_index if req.order_index is not None else next_order,
        rows=req.rows or [],
        columns=req.columns or [],
        source_type=req.source_type,
        source_prompt=req.source_prompt,
        generation_item_id=req.generation_item_id,
        generation_status=req.generation_status,
        generation_error=req.generation_error,
        assumptions=list(req.assumptions or []),
    )
    session.add(row)
    session.flush()
    return _map_widget(row)


async def list_widgets(user_id: str, dashboard_id: Optional[str] = None) -> list[DashboardWidget]:
    def _run() -> list[DashboardWidget]:
        with read_session_scope() as session:
            return _list_widgets_sync(session, user_id, dashboard_id)
    return await anyio.to_thread.run_sync(_run)


def _list_widgets_sync(session: Session, user_id: str, dashboard_id: Optional[str] = None) -> list[DashboardWidget]:
    query = session.query(DashboardWidgetORM).filter(DashboardWidgetORM.owner_id == user_id)
    if dashboard_id:
        query = query.filter(DashboardWidgetORM.dashboard_id == dashboard_id)
    rows = query.order_by(DashboardWidgetORM.order_index.asc(), DashboardWidgetORM.created_at.desc()).all()
    return [_map_widget(row) for row in rows]


async def get_widget(user_id: str, widget_id: str) -> Optional[DashboardWidget]:
    def _run() -> Optional[DashboardWidget]:
        with read_session_scope() as session:
            return _get_widget_sync(session, user_id, widget_id)
    return await anyio.to_thread.run_sync(_run)


def _get_widget_sync(session: Session, user_id: str, widget_id: str) -> Optional[DashboardWidget]:
    row = (
        session.query(DashboardWidgetORM)
        .filter(DashboardWidgetORM.id == widget_id, DashboardWidgetORM.owner_id == user_id)
        .one_or_none()
    )
    return _map_widget(row) if row else None


async def delete_widget(user_id: str, widget_id: str) -> bool:
    def _run() -> bool:
        with session_scope() as session:
            return _delete_widget_sync(session, user_id, widget_id)
    return await anyio.to_thread.run_sync(_run)


def _delete_widget_sync(session: Session, user_id: str, widget_id: str) -> bool:
    row = (
        session.query(DashboardWidgetORM)
        .filter(DashboardWidgetORM.id == widget_id, DashboardWidgetORM.owner_id == user_id)
        .one_or_none()
    )
    if not row:
        return False
    session.delete(row)
    return True


async def update_widget(
    user_id: str,
    widget_id: str,
    req: UpdateWidgetInput,
) -> Optional[DashboardWidget]:
    def _run() -> Optional[DashboardWidget]:
        with session_scope() as session:
            return _update_widget_sync(session, user_id, widget_id, req)
    return await anyio.to_thread.run_sync(_run)


def _update_widget_sync(
    session: Session,
    user_id: str,
    widget_id: str,
    req: UpdateWidgetInput,
) -> Optional[DashboardWidget]:
    row = (
        session.query(DashboardWidgetORM)
        .filter(DashboardWidgetORM.id == widget_id, DashboardWidgetORM.owner_id == user_id)
        .one_or_none()
    )
    if not row:
        return None

    if req.title is not None:
        row.title = req.title
    if req.size is not None:
        row.size = req.size
    if req.order_index is not None:
        row.order_index = req.order_index
    if req.cadence is not None:
        row.cadence = req.cadence
    if req.rows is not None:
        row.rows = req.rows
    if req.columns is not None:
        row.columns = req.columns
    if req.sql is not None:
        row.sql = req.sql
    if req.viz_type is not None:
        row.viz_type = req.viz_type
    if req.chart_config is not None:
        row.chart_config = req.chart_config.model_dump()
    if req.source_prompt is not None:
        row.source_prompt = req.source_prompt
    if req.generation_status is not None:
        row.generation_status = req.generation_status
    if req.generation_error is not None:
        row.generation_error = req.generation_error
    if req.assumptions is not None:
        row.assumptions = list(req.assumptions)

    layout_params = dict(row.layout_params or {})
    for field in ["x", "y", "w", "h", "minW", "minH", "bar_orientation"]:
        value = getattr(req, field)
        if value is not None:
            layout_params[field] = value
    row.layout_params = layout_params
    session.flush()
    return _map_widget(row)


async def set_widget_schedule_runtime_state(
    user_id: str,
    widget_id: str,
    *,
    next_run_at: datetime | None = None,
    last_run_at: datetime | None = None,
    last_run_status: str | None = None,
    last_error: str | None = None,
) -> Optional[DashboardWidget]:
    def _run() -> Optional[DashboardWidget]:
        with session_scope() as session:
            return _set_widget_schedule_runtime_state_sync(
                session,
                user_id,
                widget_id,
                next_run_at=next_run_at,
                last_run_at=last_run_at,
                last_run_status=last_run_status,
                last_error=last_error,
            )
    return await anyio.to_thread.run_sync(_run)


def _set_widget_schedule_runtime_state_sync(
    session: Session,
    user_id: str,
    widget_id: str,
    *,
    next_run_at: datetime | None = None,
    last_run_at: datetime | None = None,
    last_run_status: str | None = None,
    last_error: str | None = None,
) -> Optional[DashboardWidget]:
    row = (
        session.query(DashboardWidgetORM)
        .filter(DashboardWidgetORM.id == widget_id, DashboardWidgetORM.owner_id == user_id)
        .one_or_none()
    )
    if not row:
        return None
    row.next_run_at = next_run_at
    if last_run_at is not None:
        row.last_run_at = last_run_at
    row.last_run_status = last_run_status
    row.last_error = last_error
    session.flush()
    return _map_widget(row)


async def finalize_widget_run(
    user_id: str,
    widget_id: str,
    *,
    next_run_at: datetime | None,
    success: bool,
    error: str | None = None,
) -> Optional[DashboardWidget]:
    def _run() -> Optional[DashboardWidget]:
        with session_scope() as session:
            return _finalize_widget_run_sync(
                session,
                user_id,
                widget_id,
                next_run_at=next_run_at,
                success=success,
                error=error,
            )
    return await anyio.to_thread.run_sync(_run)


def _finalize_widget_run_sync(
    session: Session,
    user_id: str,
    widget_id: str,
    *,
    next_run_at: datetime | None,
    success: bool,
    error: str | None = None,
) -> Optional[DashboardWidget]:
    row = (
        session.query(DashboardWidgetORM)
        .filter(DashboardWidgetORM.id == widget_id, DashboardWidgetORM.owner_id == user_id)
        .one_or_none()
    )
    if not row:
        return None
    row.next_run_at = next_run_at
    row.last_run_at = _utcnow()
    row.last_run_status = "success" if success else "error"
    row.last_error = error
    session.flush()
    return _map_widget(row)


async def get_due_scheduled_widgets(now: Optional[datetime] = None, limit: int = 100) -> list[DashboardWidget]:
    def _run() -> list[DashboardWidget]:
        with read_session_scope() as session:
            return _get_due_scheduled_widgets_sync(session, now, limit)
    return await anyio.to_thread.run_sync(_run)


def _get_due_scheduled_widgets_sync(
    session: Session, now: Optional[datetime] = None, limit: int = 100
) -> list[DashboardWidget]:
    due_at = now or _utcnow()
    rows = (
        session.query(DashboardWidgetORM)
        .filter(
            DashboardWidgetORM.next_run_at.is_not(None),
            DashboardWidgetORM.next_run_at <= due_at,
            DashboardWidgetORM.cadence != "Manual only",
        )
        .order_by(DashboardWidgetORM.next_run_at.asc())
        .limit(limit)
        .all()
    )
    return [_map_widget(row) for row in rows]


async def get_stats(user_id: str, dashboard_id: Optional[str] = None) -> dict:
    widgets = await list_widgets(user_id, dashboard_id=dashboard_id)
    viz_counts: dict[str, int] = {}
    for widget in widgets:
        viz_counts[widget.viz_type] = viz_counts.get(widget.viz_type, 0) + 1
    return {
        "total_widgets": len(widgets),
        "viz_breakdown": viz_counts,
    }


async def get_all_scheduled_widgets() -> list[DashboardWidget]:
    def _run() -> list[DashboardWidget]:
        with read_session_scope() as session:
            return _get_all_scheduled_widgets_sync(session)
    return await anyio.to_thread.run_sync(_run)


def _get_all_scheduled_widgets_sync(session: Session) -> list[DashboardWidget]:
    rows = (
        session.query(DashboardWidgetORM)
        .filter(DashboardWidgetORM.cadence != "Manual only")
        .all()
    )
    return [_map_widget(row) for row in rows]
