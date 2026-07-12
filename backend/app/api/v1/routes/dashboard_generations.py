"""AI dashboard generation routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUserDep, RateLimitChecker
from app.api.v1.schemas.dashboard_generation import (
    ApproveDashboardPlanRequest,
    ApproveDashboardPlanResponse,
    CreateDashboardGenerationRequest,
    CreateDashboardGenerationResponse,
    DashboardGenerationRunResponse,
    RegenerateWidgetRequest,
    UpdateDashboardPlanRequest,
)
from app.services import dashboard_generation_service as generation_service


router = APIRouter(prefix="/api/dashboard/generations", tags=["Dashboard Generation"])


@router.post("", response_model=CreateDashboardGenerationResponse, status_code=202)
async def create_generation(
    request: CreateDashboardGenerationRequest,
    current_user: CurrentUserDep,
    _: object = Depends(RateLimitChecker("ai")),
):
    return await generation_service.start_planning(
        owner_id=current_user.id,
        connection_id=request.connection_id,
        prompt=request.prompt,
        client_request_id=request.client_request_id,
        requested_widget_count=request.requested_widget_count,
        default_time_range=request.default_time_range,
        extra_instructions=request.extra_instructions,
    )


@router.get("/{run_id}", response_model=DashboardGenerationRunResponse)
async def get_generation(run_id: str, current_user: CurrentUserDep):
    return await generation_service.get_generation(current_user.id, run_id)


@router.get("/{run_id}/events")
async def stream_generation_events(
    run_id: str,
    current_user: CurrentUserDep,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
):
    # Ownership check before opening the stream (also provides an await for the
    # async route concurrency guard — StreamingResponse itself is sync to create).
    await generation_service.get_generation(current_user.id, run_id)
    generator = generation_service.stream_events(current_user.id, run_id, last_event_id)
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.put("/{run_id}/plan", response_model=DashboardGenerationRunResponse)
async def update_generation_plan(
    run_id: str,
    request: UpdateDashboardPlanRequest,
    current_user: CurrentUserDep,
):
    return await generation_service.update_plan(
        current_user.id,
        run_id,
        expected_revision=request.expected_revision,
        plan=request.plan,
    )


@router.post("/{run_id}/approve", response_model=ApproveDashboardPlanResponse, status_code=202)
async def approve_generation_plan(
    run_id: str,
    request: ApproveDashboardPlanRequest,
    current_user: CurrentUserDep,
    _: object = Depends(RateLimitChecker("ai")),
):
    return await generation_service.approve(
        current_user.id,
        run_id,
        expected_revision=request.expected_revision,
    )


@router.post("/{run_id}/cancel", response_model=DashboardGenerationRunResponse)
async def cancel_generation(run_id: str, current_user: CurrentUserDep):
    return await generation_service.cancel(current_user.id, run_id)


@router.post("/{run_id}/items/{item_id}/retry", response_model=DashboardGenerationRunResponse)
async def retry_generation_item(
    run_id: str,
    item_id: str,
    current_user: CurrentUserDep,
    _: object = Depends(RateLimitChecker("ai")),
):
    return await generation_service.retry_item(current_user.id, run_id, item_id)


@router.post("/{run_id}/items/{item_id}/regenerate", response_model=DashboardGenerationRunResponse)
async def regenerate_generation_item(
    run_id: str,
    item_id: str,
    request: RegenerateWidgetRequest,
    current_user: CurrentUserDep,
    _: object = Depends(RateLimitChecker("ai")),
):
    return await generation_service.regenerate_item(
        current_user.id,
        run_id,
        item_id,
        instruction=request.instruction,
    )
