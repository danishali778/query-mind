from fastapi import APIRouter, HTTPException
from typing import Optional

from app.api.deps import CurrentUserDep
from app.api.v1.schemas.common import MessageResponse
from app.api.v1.schemas.dashboards import (
    AddWidgetRequest,
    CreateDashboardRequest,
    Dashboard,
    DashboardStats,
    DashboardSummary,
    DashboardWidget,
    RenameDashboardRequest,
    UpdateDashboardRequest,
    UpdateWidgetRequest,
    WidgetInsightResponse,
)
from app.core.errors import ServiceUnavailableError
from app.db.models.dashboard import (
    AddWidgetInput,
    CreateDashboardInput,
    UpdateDashboardInput,
    UpdateWidgetInput,
)
from app.services import dashboard_service as store


router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

# ─── Dashboard CRUD ─────────────────────────────────────────

@router.get("/dashboards", response_model=list[DashboardSummary])
async def list_dashboards(current_user: CurrentUserDep):
    return await store.list_dashboards(current_user.id)


@router.post("/dashboards", response_model=Dashboard)
async def create_dashboard(req: CreateDashboardRequest, current_user: CurrentUserDep):
    return await store.create_dashboard(current_user.id, CreateDashboardInput(**req.model_dump()))


@router.patch("/dashboards/{dashboard_id}", response_model=Dashboard)
async def rename_dashboard(dashboard_id: str, req: RenameDashboardRequest, current_user: CurrentUserDep):
    if not req.name.strip(): raise HTTPException(status_code=400, detail="Name required.")
    dash = await store.rename_dashboard(current_user.id, dashboard_id, req.name)
    if not dash: raise HTTPException(status_code=404, detail="Dashboard not found.")
    return dash


@router.patch("/dashboards/{dashboard_id}/update", response_model=Dashboard)
async def update_dashboard(dashboard_id: str, req: UpdateDashboardRequest, current_user: CurrentUserDep):
    if req.is_public is True:
        raise HTTPException(status_code=400, detail="Public dashboard sharing is disabled.")
    dash = await store.update_dashboard(
        current_user.id,
        dashboard_id,
        UpdateDashboardInput(**req.model_dump(exclude_unset=True)),
    )
    if not dash: raise HTTPException(status_code=404, detail="Dashboard not found.")
    return dash


@router.delete("/dashboards/{dashboard_id}", response_model=MessageResponse)
async def delete_dashboard(dashboard_id: str, current_user: CurrentUserDep):
    success = await store.delete_dashboard(current_user.id, dashboard_id)
    if not success: raise HTTPException(status_code=404, detail="Dashboard not found.")
    return {"message": "Dashboard deleted."}


# ─── Widget CRUD ────────────────────────────────────────────

@router.get("/widgets", response_model=list[DashboardWidget])
async def list_widgets(current_user: CurrentUserDep, dashboard_id: Optional[str] = None):
    return await store.list_widgets(current_user.id, dashboard_id=dashboard_id)


@router.post("/widgets", response_model=DashboardWidget)
async def add_widget(req: AddWidgetRequest, current_user: CurrentUserDep):
    try:
        return await store.add_widget(current_user.id, AddWidgetInput(**req.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/widgets/{widget_id}", response_model=MessageResponse)
async def delete_widget(widget_id: str, current_user: CurrentUserDep):
    success = await store.delete_widget(current_user.id, widget_id)
    if not success: raise HTTPException(status_code=404, detail="Widget not found.")
    return {"message": "Widget deleted."}


@router.patch("/widgets/{widget_id}", response_model=DashboardWidget)
async def update_widget(widget_id: str, req: UpdateWidgetRequest, current_user: CurrentUserDep):
    widget = await store.update_widget(
        current_user.id,
        widget_id,
        UpdateWidgetInput(**req.model_dump(exclude_unset=True)),
    )
    if not widget: raise HTTPException(status_code=404, detail="Widget not found.")
    return widget


@router.post("/widgets/{widget_id}/refresh", response_model=DashboardWidget)
async def refresh_widget(widget_id: str, current_user: CurrentUserDep):
    try:
        return await store.refresh_widget(current_user.id, widget_id, row_limit=500)
    except ValueError as exc:
        detail = str(exc)
        status_code = 400 if "Invalid widget" in detail else 404
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except RuntimeError as exc:
        raise ServiceUnavailableError("Widget refresh failed.") from exc


@router.post("/widgets/{widget_id}/insight", response_model=WidgetInsightResponse)
async def get_widget_insight_route(widget_id: str, current_user: CurrentUserDep):
    try:
        insight = await store.build_widget_insight(current_user.id, widget_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"insight": insight}


@router.get("/stats", response_model=DashboardStats)
async def get_stats(current_user: CurrentUserDep, dashboard_id: Optional[str] = None):
    return await store.get_stats(current_user.id, dashboard_id=dashboard_id)


# ─── Public Sharing ─────────────────────────────────────────

@router.get("/shared/{share_token}", response_model=Dashboard)
async def get_public_dashboard(share_token: str):
    dash = await store.get_shared_dashboard(share_token)
    if not dash: raise HTTPException(status_code=404, detail="Not found.")
    return dash


@router.get("/shared/{share_token}/widgets", response_model=list[DashboardWidget])
async def get_public_dashboard_widgets(share_token: str):
    dash = await store.get_shared_dashboard(share_token)
    if not dash: raise HTTPException(status_code=404, detail="Not found.")
    return await store.get_shared_widgets(dash.id)
