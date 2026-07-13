"""API schemas for AI dashboard generation."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class CreateDashboardGenerationRequest(BaseModel):
    connection_id: str
    prompt: str = Field(min_length=1, max_length=2048)
    requested_widget_count: int = Field(default=6, ge=1, le=8)
    default_time_range: Optional[str] = Field(default=None, max_length=100)
    extra_instructions: Optional[str] = Field(default=None, max_length=2000)
    client_request_id: str

    @field_validator("client_request_id")
    @classmethod
    def validate_client_request_id(cls, value: str) -> str:
        from uuid import UUID

        try:
            return str(UUID(value))
        except (ValueError, AttributeError) as exc:
            raise ValueError("client_request_id must be a valid UUID") from exc


class CreateDashboardGenerationResponse(BaseModel):
    run_id: str
    status: str
    events_url: str


class UpdateDashboardPlanRequest(BaseModel):
    expected_revision: int = Field(ge=0)
    plan: dict[str, Any]


class ApproveDashboardPlanRequest(BaseModel):
    expected_revision: int = Field(ge=0)


class ApproveDashboardPlanResponse(BaseModel):
    run_id: str
    dashboard_id: Optional[str] = None
    status: str
    events_url: Optional[str] = None


class RegenerateWidgetRequest(BaseModel):
    instruction: Optional[str] = Field(default=None, max_length=1000)
    use_latest_definitions: bool = False


class DashboardGenerationItemResponse(BaseModel):
    id: str
    run_id: str
    client_key: str
    dashboard_widget_id: Optional[str] = None
    order_index: int = 0
    plan_json: dict[str, Any] = Field(default_factory=dict)
    status: str
    attempt_count: int = 0
    last_error_code: Optional[str] = None
    last_error_message: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DashboardGenerationRunResponse(BaseModel):
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
    status: str
    current_stage: str
    current_stage_label: str
    celery_task_id: Optional[str] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    items: list[DashboardGenerationItemResponse] = Field(default_factory=list)
    events_url: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    heartbeat_at: Optional[str] = None
    cancel_requested_at: Optional[str] = None
    finished_at: Optional[str] = None
    updated_at: Optional[str] = None
