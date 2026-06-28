"""Database/domain row models."""

from app.db.models.chat import ChatMessage, ChatSession, SessionSummary
from app.db.models.connection import (
    ActiveConnection,
    ColumnInfo,
    ConnectionRequest,
    ForeignKeyInfo,
    TableInfo,
)
from app.db.models.dashboard import (
    AddWidgetInput,
    ChartConfig,
    CreateDashboardInput,
    Dashboard,
    DashboardStats,
    DashboardSummary,
    DashboardWidget,
    UpdateDashboardInput,
    UpdateWidgetInput,
)
from app.db.models.query_history import QueryRecord
from app.db.models.query_library import (
    DAY_ABBREV,
    QueryRunRecord,
    SaveQueryInput,
    SavedQuery,
    ScheduleConfig,
    UpdateQueryInput,
)
from app.db.models.settings import UserSettings, UserSettingsBase, UserSettingsUpdate, UserSubscription
from app.db.models.templates import GeneratedQueryTemplate, TemplateGenerationState

__all__ = [
    "ChatMessage",
    "ChatSession",
    "SessionSummary",
    "ConnectionRequest",
    "ActiveConnection",
    "ColumnInfo",
    "ForeignKeyInfo",
    "TableInfo",
    "ChartConfig",
    "Dashboard",
    "DashboardWidget",
    "DashboardSummary",
    "DashboardStats",
    "CreateDashboardInput",
    "UpdateDashboardInput",
    "AddWidgetInput",
    "UpdateWidgetInput",
    "QueryRecord",
    "DAY_ABBREV",
    "SavedQuery",
    "ScheduleConfig",
    "QueryRunRecord",
    "SaveQueryInput",
    "UpdateQueryInput",
    "UserSettingsBase",
    "UserSettings",
    "UserSettingsUpdate",
    "UserSubscription",
    "GeneratedQueryTemplate",
    "TemplateGenerationState",
]
