from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ChartConfig(BaseModel):
    """Configuration for chart rendering."""

    x_column: Optional[str] = None
    y_columns: list[str] = Field(default_factory=list)
    color_column: Optional[str] = None
    is_grouped: bool = False
    title: Optional[str] = None
    x_label: Optional[str] = None
    y_label: Optional[str] = None


CreationMode = Literal["manual", "ai"]
LifecycleStatus = Literal["draft", "ready"]
WidgetSourceType = Literal["manual", "chat", "ai"]
WidgetGenerationStatus = Literal["ready", "queued", "running", "failed", "cancelled", "regenerating"]


class Dashboard(BaseModel):
    """A dashboard that holds widgets."""

    id: str
    owner_id: str
    name: str
    icon: str = "\U0001f4ca"
    filters: dict = Field(default_factory=dict)
    is_public: bool = False
    share_token: Optional[str] = None
    creation_mode: CreationMode = "manual"
    lifecycle_status: LifecycleStatus = "ready"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DashboardWidget(BaseModel):
    """A single widget on the dashboard."""

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
    source_type: WidgetSourceType = "manual"
    source_prompt: Optional[str] = None
    generation_item_id: Optional[str] = None
    generation_status: WidgetGenerationStatus = "ready"
    generation_error: Optional[str] = None
    assumptions: list[str] = Field(default_factory=list)
    semantic_lineage: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DashboardSummary(Dashboard):
    """Dashboard summary with widget count."""

    widget_count: int = 0


class DashboardStats(BaseModel):
    """Aggregate widget stats."""

    total_widgets: int = 0
    viz_breakdown: dict[str, int] = Field(default_factory=dict)


class CreateDashboardInput(BaseModel):
    """Domain input for creating a dashboard."""

    name: str
    icon: str = "\U0001f4ca"
    filters: Optional[dict] = None
    creation_mode: CreationMode = "manual"
    lifecycle_status: LifecycleStatus = "ready"


class UpdateDashboardInput(BaseModel):
    """Domain input for updating a dashboard."""

    name: Optional[str] = None
    icon: Optional[str] = None
    filters: Optional[dict] = None
    is_public: Optional[bool] = None
    lifecycle_status: Optional[LifecycleStatus] = None


class AddWidgetInput(BaseModel):
    """Domain input for creating a widget."""

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
    source_type: WidgetSourceType = "manual"
    source_prompt: Optional[str] = None
    generation_item_id: Optional[str] = None
    generation_status: WidgetGenerationStatus = "ready"
    generation_error: Optional[str] = None
    assumptions: list[str] = Field(default_factory=list)
    semantic_lineage: list[dict[str, Any]] = Field(default_factory=list)


class UpdateWidgetInput(BaseModel):
    """Domain input for updating a widget."""

    title: Optional[str] = None
    size: Optional[str] = None
    columns: Optional[list[str]] = None
    rows: Optional[list[dict]] = None
    sql: Optional[str] = None
    viz_type: Optional[str] = None
    chart_config: Optional[ChartConfig] = None
    cadence: Optional[str] = None
    x: Optional[int] = None
    y: Optional[int] = None
    w: Optional[int] = None
    h: Optional[int] = None
    minW: Optional[int] = None
    minH: Optional[int] = None
    bar_orientation: Optional[str] = None
    order_index: Optional[int] = None
    source_prompt: Optional[str] = None
    generation_status: Optional[WidgetGenerationStatus] = None
    generation_error: Optional[str] = None
    assumptions: Optional[list[str]] = None
    semantic_lineage: Optional[list[dict[str, Any]]] = None


GenerationRunStatus = Literal[
    "planning",
    "awaiting_approval",
    "queued",
    "running",
    "partial",
    "completed",
    "failed",
    "cancelled",
]
GenerationItemStatus = Literal[
    "planned",
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
    "regenerating",
]


class DashboardGenerationItem(BaseModel):
    """One planned / generating widget within a generation run."""

    id: str
    run_id: str
    client_key: str
    dashboard_widget_id: Optional[str] = None
    order_index: int = 0
    plan_json: dict[str, Any] = Field(default_factory=dict)
    status: GenerationItemStatus = "planned"
    attempt_count: int = 0
    last_error_code: Optional[str] = None
    last_error_message: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DashboardGenerationRun(BaseModel):
    """Durable AI dashboard generation run."""

    id: str
    owner_id: str
    connection_id: str
    dashboard_id: Optional[str] = None
    client_request_id: str
    prompt: str
    requested_widget_count: int = 6
    default_time_range: Optional[str] = None
    extra_instructions: Optional[str] = None
    plan_json: Optional[dict[str, Any]] = None
    semantic_context_json: Optional[dict[str, Any]] = None
    plan_revision: int = 0
    status: GenerationRunStatus = "planning"
    current_stage: str = "reading_objective"
    current_stage_label: str = "Reading the dashboard objective"
    celery_task_id: Optional[str] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    items: list[DashboardGenerationItem] = Field(default_factory=list)
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    heartbeat_at: Optional[str] = None
    cancel_requested_at: Optional[str] = None
    finished_at: Optional[str] = None
    updated_at: Optional[str] = None
