from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class CreateDashboardRequest(BaseModel):
    """Request body for creating a dashboard."""

    name: str
    icon: str = "\U0001f4ca"
    filters: Optional[dict] = None


class RenameDashboardRequest(BaseModel):
    """Request body for renaming a dashboard."""

    name: str


class UpdateDashboardRequest(BaseModel):
    """Patchable dashboard fields."""

    name: Optional[str] = None
    icon: Optional[str] = None
    filters: Optional[dict] = None
    is_public: Optional[bool] = None
    lifecycle_status: Optional[Literal["draft", "ready"]] = None


class AddWidgetRequest(BaseModel):
    """Request body for adding a widget."""

    dashboard_id: str
    title: str
    viz_type: str = "table"
    size: str = "half"
    connection_id: Optional[str] = None
    sql: Optional[str] = None
    columns: list[str] = Field(default_factory=list)
    rows: list[dict] = Field(default_factory=list)
    chart_config: Optional[ChartConfig] = None
    cadence: str = "Manual only"
    x: Optional[int] = None
    y: Optional[int] = None
    w: Optional[int] = None
    h: Optional[int] = None
    minW: Optional[int] = None
    minH: Optional[int] = None
    bar_orientation: Optional[str] = None
    order_index: Optional[int] = None
    source_type: str = "manual"
    source_prompt: Optional[str] = None
    assumptions: list[str] = Field(default_factory=list)


class UpdateWidgetRequest(BaseModel):
    """Patchable widget fields for layout and preferences."""

    title: Optional[str] = None
    size: Optional[str] = None
    columns: Optional[list[str]] = None
    rows: Optional[list[dict]] = None
    cadence: Optional[str] = None
    x: Optional[int] = None
    y: Optional[int] = None
    w: Optional[int] = None
    h: Optional[int] = None
    minW: Optional[int] = None
    minH: Optional[int] = None
    bar_orientation: Optional[str] = None
    order_index: Optional[int] = None


class ChartConfig(BaseModel):
    """API-facing chart configuration payload."""

    x_column: Optional[str] = None
    y_columns: list[str] = Field(default_factory=list)
    color_column: Optional[str] = None
    is_grouped: bool = False
    title: Optional[str] = None
    x_label: Optional[str] = None
    y_label: Optional[str] = None


class Dashboard(BaseModel):
    """API-facing dashboard payload."""

    id: str
    owner_id: str
    name: str
    icon: str = "\U0001f4ca"
    filters: dict = Field(default_factory=dict)
    is_public: bool = False
    share_token: Optional[str] = None
    creation_mode: str = "manual"
    lifecycle_status: str = "ready"
    created_at: datetime


class DashboardWidget(BaseModel):
    """API-facing dashboard widget payload."""

    id: str
    owner_id: str
    dashboard_id: str
    title: str
    viz_type: str
    size: str = "half"
    connection_id: Optional[str] = None
    sql: Optional[str] = None
    columns: list[str] = Field(default_factory=list)
    rows: list[dict] = Field(default_factory=list)
    chart_config: Optional[ChartConfig] = None
    cadence: str = "Manual only"
    x: int = 0
    y: int = 0
    w: int = 1
    h: int = 7
    minW: int = 1
    minH: int = 5
    bar_orientation: str = "horizontal"
    order_index: int = 0
    source_type: str = "manual"
    source_prompt: Optional[str] = None
    generation_item_id: Optional[str] = None
    generation_status: str = "ready"
    generation_error: Optional[str] = None
    assumptions: list[str] = Field(default_factory=list)
    created_at: datetime


class DashboardSummary(Dashboard):
    """API-facing dashboard summary payload."""

    widget_count: int = 0


class DashboardStats(BaseModel):
    """API-facing aggregate dashboard stats payload."""

    total_widgets: int = 0
    viz_breakdown: dict[str, int] = Field(default_factory=dict)


class WidgetInsightResponse(BaseModel):
    """Generated narrative insight for a widget."""

    insight: str


__all__ = [
    "ChartConfig",
    "Dashboard",
    "DashboardWidget",
    "DashboardSummary",
    "DashboardStats",
    "CreateDashboardRequest",
    "RenameDashboardRequest",
    "UpdateDashboardRequest",
    "AddWidgetRequest",
    "UpdateWidgetRequest",
    "WidgetInsightResponse",
]
