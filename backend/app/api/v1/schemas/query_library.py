from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, computed_field


DAY_ABBREV = {
    "monday": "Mon",
    "tuesday": "Tue",
    "wednesday": "Wed",
    "thursday": "Thu",
    "friday": "Fri",
    "saturday": "Sat",
    "sunday": "Sun",
}


class ScheduleConfig(BaseModel):
    """API-facing schedule payload."""

    enabled: bool = True
    frequency: Literal["daily", "weekly", "monthly"]
    day_of_week: Optional[str] = None
    day_of_month: Optional[int] = None
    hour: int = 9
    minute: int = 0
    timezone: str = "UTC"
    next_run_at: Optional[datetime] = None


class SavedQuery(BaseModel):
    """API-facing saved-query payload."""

    id: str
    title: str
    sql: str
    description: str = ""
    folder_name: str = "Uncategorized"
    connection_id: Optional[str] = None
    icon: str = "\U0001f4c4"
    icon_bg: str = "rgba(0,229,255,0.1)"
    tags: list[str] = Field(default_factory=list)
    schedule: Optional[ScheduleConfig] = None
    owner_id: str
    created_at: datetime
    updated_at: datetime
    run_count: int = 0
    last_run_at: Optional[datetime] = None

    @computed_field
    @property
    def schedule_label(self) -> Optional[str]:
        if not self.schedule or not self.schedule.enabled:
            return None
        schedule = self.schedule
        period = f"{schedule.hour % 12 or 12}:{schedule.minute:02d} {'AM' if schedule.hour < 12 else 'PM'}"
        if schedule.frequency == "daily":
            return f"Daily at {period} {schedule.timezone}"
        if schedule.frequency == "weekly" and schedule.day_of_week:
            day = DAY_ABBREV.get(schedule.day_of_week, schedule.day_of_week)
            return f"Weekly, {day} {period} {schedule.timezone}"
        if schedule.frequency == "monthly" and schedule.day_of_month:
            return f"Monthly, day {schedule.day_of_month} {period} {schedule.timezone}"
        return f"{schedule.frequency.title()} {period} {schedule.timezone}"


class QueryRunRecord(BaseModel):
    """API-facing saved-query run-history payload."""

    id: str
    sql: str
    connection_id: Optional[str] = None
    query_id: Optional[str] = None
    success: bool
    row_count: int = 0
    execution_time_ms: float = 0.0
    error: Optional[str] = None
    error_code: Optional[str] = None
    triggered_by: str = "manual"
    owner_id: str
    ran_at: datetime


class SaveQueryRequest(BaseModel):
    """Request to save a new query."""

    title: str
    sql: str
    description: str = ""
    folder_name: str = "Uncategorized"
    connection_id: Optional[str] = None
    icon: str = "\U0001f4c4"
    icon_bg: str = "rgba(0,229,255,0.1)"
    tags: list[str] = Field(default_factory=list)
    schedule: Optional[ScheduleConfig] = None


class UpdateQueryRequest(BaseModel):
    """Request to update an existing query."""

    title: Optional[str] = None
    sql: Optional[str] = None
    description: Optional[str] = None
    folder_name: Optional[str] = None
    connection_id: Optional[str] = None
    icon: Optional[str] = None
    icon_bg: Optional[str] = None
    tags: Optional[list[str]] = None
    schedule: Optional[ScheduleConfig] = None


class SaveQueryResponse(SavedQuery):
    """Saved query payload plus duplicate status."""

    created: bool


class FolderSummary(BaseModel):
    """Folder name and query count."""

    name: str
    count: int


class FolderCreateResponse(BaseModel):
    """Response after creating a folder placeholder."""

    name: str


class LibraryStats(BaseModel):
    """Aggregate library statistics."""

    total_queries: int = 0
    scheduled: int = 0
    total_runs: int = 0
    recently_run: int = 0
    folders: int = 0


class RunSavedQueryResponse(BaseModel):
    """Execution result when running a saved query."""

    query_id: str
    success: bool
    columns: list[str] = Field(default_factory=list)
    rows: list[dict] = Field(default_factory=list)
    row_count: int = 0
    execution_time_ms: float = 0.0
    error: Optional[str] = None


class ScheduleStatusResponse(BaseModel):
    """Response for schedule-specific operations."""

    query_id: str
    schedule: Optional[ScheduleConfig] = None
    schedule_label: Optional[str] = None
    message: str


class PublicTemplateSummary(BaseModel):
    """AI-generated library template summary."""

    id: str
    connection_id: str
    title: str
    description: str
    sql: str
    category: str
    category_color: str
    tags: list[str] = Field(default_factory=list)
    icon: str
    icon_bg: str
    difficulty: str


class PublicTemplatesResponse(BaseModel):
    """Templates plus generation status for a connection."""

    status: str
    connection_id: Optional[str] = None
    templates: list[PublicTemplateSummary] = Field(default_factory=list)


class TemplateGenerationResponse(BaseModel):
    """Background template generation kickoff payload."""

    message: str
    connection_id: str


__all__ = [
    "ScheduleConfig",
    "SavedQuery",
    "SaveQueryRequest",
    "UpdateQueryRequest",
    "SaveQueryResponse",
    "FolderSummary",
    "FolderCreateResponse",
    "LibraryStats",
    "RunSavedQueryResponse",
    "QueryRunRecord",
    "ScheduleStatusResponse",
    "PublicTemplateSummary",
    "PublicTemplatesResponse",
    "TemplateGenerationResponse",
]
