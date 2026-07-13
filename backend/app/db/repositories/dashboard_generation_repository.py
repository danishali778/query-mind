"""Persistence for AI dashboard generation runs and items."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

import anyio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.dashboard import (
    Dashboard,
    DashboardGenerationItem,
    DashboardGenerationRun,
    DashboardWidget,
)
from app.db.orm_models import (
    DashboardGenerationItemORM,
    DashboardGenerationRunORM,
    DashboardORM,
    DashboardWidgetORM,
)
from app.db.repositories.dashboard_repository import _map_dashboard, _map_widget
from app.db.session import read_session_scope, session_scope


ACTIVE_RUN_STATUSES = ("planning", "queued", "running")
TERMINAL_RUN_STATUSES = ("partial", "completed", "failed", "cancelled")
RETRYABLE_ITEM_STATUSES = ("failed", "cancelled")


class ActiveGenerationConflictError(RuntimeError):
    pass


class PlanRevisionConflictError(RuntimeError):
    pass


class GenerationNotApprovableError(RuntimeError):
    pass


class GenerationNotFoundError(LookupError):
    pass


class GenerationItemNotFoundError(LookupError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def _map_item(row: DashboardGenerationItemORM) -> DashboardGenerationItem:
    return DashboardGenerationItem(
        id=row.id,
        run_id=row.run_id,
        client_key=row.client_key,
        dashboard_widget_id=row.dashboard_widget_id,
        order_index=row.order_index or 0,
        plan_json=dict(row.plan_json or {}),
        status=row.status,  # type: ignore[arg-type]
        attempt_count=row.attempt_count or 0,
        last_error_code=row.last_error_code,
        last_error_message=row.last_error_message,
        started_at=_iso(row.started_at),
        finished_at=_iso(row.finished_at),
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    )


def _map_run(
    row: DashboardGenerationRunORM,
    items: list[DashboardGenerationItemORM] | None = None,
) -> DashboardGenerationRun:
    mapped_items = [_map_item(item) for item in (items if items is not None else list(row.items or []))]
    mapped_items.sort(key=lambda item: item.order_index)
    return DashboardGenerationRun(
        id=row.id,
        owner_id=row.owner_id,
        connection_id=row.connection_id,
        dashboard_id=row.dashboard_id,
        client_request_id=row.client_request_id,
        prompt=row.prompt,
        requested_widget_count=row.requested_widget_count,
        default_time_range=row.default_time_range,
        extra_instructions=row.extra_instructions,
        plan_json=dict(row.plan_json) if row.plan_json else None,
        plan_revision=row.plan_revision or 0,
        status=row.status,  # type: ignore[arg-type]
        current_stage=row.current_stage,
        current_stage_label=row.current_stage_label,
        celery_task_id=row.celery_task_id,
        failure_code=row.failure_code,
        failure_message=row.failure_message,
        items=mapped_items,
        created_at=_iso(row.created_at),
        started_at=_iso(row.started_at),
        heartbeat_at=_iso(row.heartbeat_at),
        cancel_requested_at=_iso(row.cancel_requested_at),
        finished_at=_iso(row.finished_at),
        updated_at=_iso(row.updated_at),
    )


def compute_placeholder_layouts(widget_plans: list[dict[str, Any]]) -> list[dict[str, int]]:
    """Deterministic layout matching the frontend's 20-column grid."""

    size_dims = {
        "quarter": {"w": 5, "h": 5, "minW": 5, "minH": 4},
        "half": {"w": 10, "h": 7, "minW": 4, "minH": 5},
        "three-quarter": {"w": 15, "h": 8, "minW": 8, "minH": 6},
        "full": {"w": 20, "h": 8, "minW": 10, "minH": 6},
    }
    layouts: list[dict[str, int]] = []
    cursor_x = 0
    cursor_y = 0
    row_height = 0

    for plan in widget_plans:
        size = str(plan.get("size") or "half")
        if size not in size_dims:
            size = "half"
        dims = size_dims[size]
        if cursor_x and cursor_x + dims["w"] > 20:
            cursor_y += row_height
            cursor_x = 0
            row_height = 0
        layouts.append({"x": cursor_x, "y": cursor_y, **dims})
        cursor_x += dims["w"]
        row_height = max(row_height, dims["h"])
        if cursor_x >= 20:
            cursor_y += row_height
            cursor_x = 0
            row_height = 0

    return layouts


def create_planning_run_sync(
    session: Session,
    *,
    owner_id: str,
    connection_id: str,
    prompt: str,
    client_request_id: str,
    requested_widget_count: int = 6,
    default_time_range: str | None = None,
    extra_instructions: str | None = None,
    max_active_runs: int = 1,
) -> tuple[DashboardGenerationRun, bool]:
    existing = (
        session.query(DashboardGenerationRunORM)
        .filter(
            DashboardGenerationRunORM.owner_id == owner_id,
            DashboardGenerationRunORM.client_request_id == client_request_id,
        )
        .one_or_none()
    )
    if existing:
        return _map_run(existing), False

    active_count = (
        session.query(DashboardGenerationRunORM.id)
        .filter(
            DashboardGenerationRunORM.owner_id == owner_id,
            DashboardGenerationRunORM.status.in_(ACTIVE_RUN_STATUSES),
        )
        .count()
    )
    if active_count >= max(1, max_active_runs):
        raise ActiveGenerationConflictError("Another dashboard generation is already active.")

    row = DashboardGenerationRunORM(
        id=str(uuid.uuid4()),
        owner_id=owner_id,
        connection_id=connection_id,
        client_request_id=client_request_id,
        prompt=prompt,
        requested_widget_count=requested_widget_count,
        default_time_range=default_time_range,
        extra_instructions=extra_instructions or "",
        status="planning",
        current_stage="reading_objective",
        current_stage_label="Reading the dashboard objective",
        started_at=_now(),
        heartbeat_at=_now(),
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ActiveGenerationConflictError("Another dashboard generation is already active.") from exc
    return _map_run(row), True


async def create_planning_run(**kwargs) -> tuple[DashboardGenerationRun, bool]:
    def _run() -> tuple[DashboardGenerationRun, bool]:
        with session_scope() as session:
            return create_planning_run_sync(session, **kwargs)

    return await anyio.to_thread.run_sync(_run)


def get_run_sync(session: Session, owner_id: str, run_id: str) -> DashboardGenerationRun | None:
    row = (
        session.query(DashboardGenerationRunORM)
        .filter(DashboardGenerationRunORM.id == run_id, DashboardGenerationRunORM.owner_id == owner_id)
        .one_or_none()
    )
    return _map_run(row) if row else None


async def get_run(owner_id: str, run_id: str) -> DashboardGenerationRun | None:
    def _run() -> DashboardGenerationRun | None:
        with read_session_scope() as session:
            return get_run_sync(session, owner_id, run_id)

    return await anyio.to_thread.run_sync(_run)


def get_run_by_id_sync(session: Session, run_id: str) -> DashboardGenerationRun | None:
    row = session.query(DashboardGenerationRunORM).filter(DashboardGenerationRunORM.id == run_id).one_or_none()
    return _map_run(row) if row else None


def get_latest_run_for_dashboard_sync(
    session: Session,
    owner_id: str,
    dashboard_id: str,
) -> DashboardGenerationRun | None:
    row = (
        session.query(DashboardGenerationRunORM)
        .filter(
            DashboardGenerationRunORM.owner_id == owner_id,
            DashboardGenerationRunORM.dashboard_id == dashboard_id,
        )
        .order_by(DashboardGenerationRunORM.created_at.desc())
        .first()
    )
    return _map_run(row) if row else None


async def get_latest_run_for_dashboard(owner_id: str, dashboard_id: str) -> DashboardGenerationRun | None:
    def _run() -> DashboardGenerationRun | None:
        with read_session_scope() as session:
            return get_latest_run_for_dashboard_sync(session, owner_id, dashboard_id)

    return await anyio.to_thread.run_sync(_run)


def claim_planning_run_sync(session: Session, run_id: str) -> DashboardGenerationRun | None:
    now = _now()
    changed = (
        session.query(DashboardGenerationRunORM)
        .filter(
            DashboardGenerationRunORM.id == run_id,
            DashboardGenerationRunORM.status == "planning",
            DashboardGenerationRunORM.current_stage == "reading_objective",
        )
        .update(
            {
                "current_stage": "planning",
                "current_stage_label": "Planning dashboard",
                "heartbeat_at": now,
                "updated_at": now,
            },
            synchronize_session=False,
        )
    )
    if not changed:
        return None
    row = session.query(DashboardGenerationRunORM).filter(DashboardGenerationRunORM.id == run_id).one()
    return _map_run(row)


def claim_execution_run_sync(session: Session, run_id: str) -> DashboardGenerationRun | None:
    now = _now()
    changed = (
        session.query(DashboardGenerationRunORM)
        .filter(
            DashboardGenerationRunORM.id == run_id,
            DashboardGenerationRunORM.status == "queued",
        )
        .update(
            {
                "status": "running",
                "current_stage": "running",
                "current_stage_label": "Generating widgets",
                "started_at": now,
                "heartbeat_at": now,
                "updated_at": now,
            },
            synchronize_session=False,
        )
    )
    if not changed:
        return None
    row = session.query(DashboardGenerationRunORM).filter(DashboardGenerationRunORM.id == run_id).one()
    return _map_run(row)


def claim_item_sync(session: Session, item_id: str) -> DashboardGenerationItem | None:
    now = _now()
    changed = (
        session.query(DashboardGenerationItemORM)
        .filter(
            DashboardGenerationItemORM.id == item_id,
            DashboardGenerationItemORM.status.in_(("queued", "regenerating")),
        )
        .update(
            {
                "status": "running",
                "attempt_count": DashboardGenerationItemORM.attempt_count + 1,
                "started_at": now,
                "finished_at": None,
                "last_error_code": None,
                "last_error_message": None,
                "updated_at": now,
            },
            synchronize_session=False,
        )
    )
    if not changed:
        return None
    row = session.query(DashboardGenerationItemORM).filter(DashboardGenerationItemORM.id == item_id).one()
    if row.dashboard_widget_id:
        widget = session.query(DashboardWidgetORM).filter(DashboardWidgetORM.id == row.dashboard_widget_id).one_or_none()
        if widget:
            widget.generation_status = "running"
            widget.generation_error = None
    session.flush()
    return _map_item(row)


def reopen_run_for_item_sync(
    session: Session,
    owner_id: str,
    run_id: str,
    item_id: str,
    *,
    item_status: str,
    allowed_item_statuses: tuple[str, ...],
) -> DashboardGenerationRun:
    row = (
        session.query(DashboardGenerationRunORM)
        .filter(DashboardGenerationRunORM.id == run_id, DashboardGenerationRunORM.owner_id == owner_id)
        .one_or_none()
    )
    if not row:
        raise GenerationNotFoundError(run_id)
    item = (
        session.query(DashboardGenerationItemORM)
        .filter(DashboardGenerationItemORM.id == item_id, DashboardGenerationItemORM.run_id == run_id)
        .one_or_none()
    )
    if not item:
        raise GenerationItemNotFoundError(item_id)
    if item.status not in allowed_item_statuses:
        raise GenerationNotApprovableError(
            f"Widget cannot be queued from status '{item.status}'."
        )
    mark_item_status_sync(session, item_id, status=item_status)
    row.status = "queued"
    row.current_stage = "queued"
    row.current_stage_label = "Widget queued"
    row.finished_at = None
    row.failure_code = None
    row.failure_message = None
    row.cancel_requested_at = None
    row.heartbeat_at = _now()
    session.flush()
    return _map_run(row)


def update_stage_sync(
    session: Session,
    run_id: str,
    *,
    stage: str,
    stage_label: str,
    status: str | None = None,
) -> DashboardGenerationRun | None:
    row = session.query(DashboardGenerationRunORM).filter(DashboardGenerationRunORM.id == run_id).one_or_none()
    if not row:
        return None
    if row.status in TERMINAL_RUN_STATUSES:
        return _map_run(row)
    row.current_stage = stage
    row.current_stage_label = stage_label
    row.heartbeat_at = _now()
    if status is not None and row.status not in TERMINAL_RUN_STATUSES:
        row.status = status
    session.flush()
    return _map_run(row)


def set_task_id_sync(session: Session, run_id: str, celery_task_id: str) -> None:
    row = session.query(DashboardGenerationRunORM).filter(DashboardGenerationRunORM.id == run_id).one_or_none()
    if row and row.status not in TERMINAL_RUN_STATUSES:
        row.celery_task_id = celery_task_id
        row.heartbeat_at = _now()
        session.flush()


def save_plan_sync(
    session: Session,
    owner_id: str,
    run_id: str,
    plan: dict[str, Any],
    *,
    expected_revision: int | None = None,
    mark_awaiting_approval: bool = False,
) -> DashboardGenerationRun:
    row = (
        session.query(DashboardGenerationRunORM)
        .filter(DashboardGenerationRunORM.id == run_id, DashboardGenerationRunORM.owner_id == owner_id)
        .one_or_none()
    )
    if not row:
        raise GenerationNotFoundError(run_id)
    if expected_revision is not None and row.plan_revision != expected_revision:
        raise PlanRevisionConflictError("Plan revision conflict.")
    if expected_revision is not None and row.status != "awaiting_approval":
        raise GenerationNotApprovableError("Plan can only be edited while awaiting approval.")
    if row.status in TERMINAL_RUN_STATUSES:
        raise GenerationNotApprovableError("Terminal generation runs cannot be updated.")

    row.plan_json = plan
    row.plan_revision = (row.plan_revision or 0) + 1
    row.heartbeat_at = _now()
    if mark_awaiting_approval:
        row.status = "awaiting_approval"
        row.current_stage = "plan_ready"
        row.current_stage_label = "Dashboard plan ready"
    session.flush()
    return _map_run(row)


async def save_plan(
    owner_id: str,
    run_id: str,
    plan: dict[str, Any],
    *,
    expected_revision: int | None = None,
    mark_awaiting_approval: bool = False,
) -> DashboardGenerationRun:
    def _run() -> DashboardGenerationRun:
        with session_scope() as session:
            return save_plan_sync(
                session,
                owner_id,
                run_id,
                plan,
                expected_revision=expected_revision,
                mark_awaiting_approval=mark_awaiting_approval,
            )

    return await anyio.to_thread.run_sync(_run)


def approve_plan_sync(
    session: Session,
    owner_id: str,
    run_id: str,
    *,
    expected_revision: int,
) -> tuple[DashboardGenerationRun, Dashboard, list[DashboardWidget], bool]:
    row = (
        session.query(DashboardGenerationRunORM)
        .filter(DashboardGenerationRunORM.id == run_id, DashboardGenerationRunORM.owner_id == owner_id)
        .one_or_none()
    )
    if not row:
        raise GenerationNotFoundError(run_id)

    if row.dashboard_id and row.status in {"queued", "running", "partial", "completed", "failed", "cancelled"}:
        dashboard = (
            session.query(DashboardORM)
            .filter(DashboardORM.id == row.dashboard_id, DashboardORM.owner_id == owner_id)
            .one()
        )
        widgets = (
            session.query(DashboardWidgetORM)
            .filter(DashboardWidgetORM.dashboard_id == dashboard.id, DashboardWidgetORM.owner_id == owner_id)
            .order_by(DashboardWidgetORM.order_index.asc())
            .all()
        )
        return _map_run(row), _map_dashboard(dashboard), [_map_widget(w) for w in widgets], False

    if row.status != "awaiting_approval":
        raise GenerationNotApprovableError("Generation is not awaiting approval.")
    if row.plan_revision != expected_revision:
        raise PlanRevisionConflictError("Plan revision conflict.")
    if not row.plan_json or not isinstance(row.plan_json, dict):
        raise GenerationNotApprovableError("Plan is missing.")

    widgets_plan = list(row.plan_json.get("widgets") or [])
    if not widgets_plan:
        raise GenerationNotApprovableError("Plan has no widgets.")

    layouts = compute_placeholder_layouts(widgets_plan)
    dashboard = DashboardORM(
        id=str(uuid.uuid4()),
        owner_id=owner_id,
        name=str(row.plan_json.get("title") or "AI Dashboard")[:100],
        icon="\U0001f4ca",
        filters={},
        is_public=False,
        creation_mode="ai",
        lifecycle_status="draft",
    )
    session.add(dashboard)
    session.flush()

    created_widgets: list[DashboardWidgetORM] = []
    for index, (plan, layout) in enumerate(zip(widgets_plan, layouts)):
        item = DashboardGenerationItemORM(
            id=str(uuid.uuid4()),
            run_id=row.id,
            client_key=str(plan.get("client_key") or uuid.uuid4()),
            order_index=index,
            plan_json=dict(plan),
            status="queued",
        )
        session.add(item)
        session.flush()

        viz = str(plan.get("visualization") or "auto")
        if viz == "auto":
            viz = "table"
        widget = DashboardWidgetORM(
            id=str(uuid.uuid4()),
            dashboard_id=dashboard.id,
            owner_id=owner_id,
            connection_id=row.connection_id,
            title=str(plan.get("title") or f"Widget {index + 1}")[:100],
            viz_type=viz if viz != "auto" else "table",
            size=str(plan.get("size") or "half"),
            sql=None,
            chart_config={},
            layout_params={
                "x": layout["x"],
                "y": layout["y"],
                "w": layout["w"],
                "h": layout["h"],
                "minW": layout["minW"],
                "minH": layout["minH"],
                "bar_orientation": "horizontal",
            },
            cadence="Manual only",
            order_index=index,
            rows=[],
            columns=[],
            source_type="ai",
            source_prompt=str(plan.get("question") or ""),
            generation_item_id=item.id,
            generation_status="queued",
            generation_error=None,
            assumptions=[],
        )
        session.add(widget)
        session.flush()
        item.dashboard_widget_id = widget.id
        created_widgets.append(widget)

    row.dashboard_id = dashboard.id
    row.status = "queued"
    row.current_stage = "queued"
    row.current_stage_label = "Queued for generation"
    row.heartbeat_at = _now()
    session.flush()
    return (
        _map_run(row),
        _map_dashboard(dashboard),
        [_map_widget(w) for w in created_widgets],
        True,
    )


async def approve_plan(
    owner_id: str,
    run_id: str,
    *,
    expected_revision: int,
) -> tuple[DashboardGenerationRun, Dashboard, list[DashboardWidget], bool]:
    def _run():
        with session_scope() as session:
            return approve_plan_sync(session, owner_id, run_id, expected_revision=expected_revision)

    return await anyio.to_thread.run_sync(_run)


def request_cancel_sync(session: Session, owner_id: str, run_id: str) -> DashboardGenerationRun:
    row = (
        session.query(DashboardGenerationRunORM)
        .filter(DashboardGenerationRunORM.id == run_id, DashboardGenerationRunORM.owner_id == owner_id)
        .one_or_none()
    )
    if not row:
        raise GenerationNotFoundError(run_id)
    if row.status in TERMINAL_RUN_STATUSES:
        return _map_run(row)
    if row.cancel_requested_at is None:
        row.cancel_requested_at = _now()
    row.heartbeat_at = _now()
    session.flush()
    return _map_run(row)


async def request_cancel(owner_id: str, run_id: str) -> DashboardGenerationRun:
    def _run() -> DashboardGenerationRun:
        with session_scope() as session:
            return request_cancel_sync(session, owner_id, run_id)

    return await anyio.to_thread.run_sync(_run)


def finalize_run_sync(
    session: Session,
    run_id: str,
    *,
    status: str,
    failure_code: str | None = None,
    failure_message: str | None = None,
    stage: str | None = None,
    stage_label: str | None = None,
) -> DashboardGenerationRun | None:
    row = session.query(DashboardGenerationRunORM).filter(DashboardGenerationRunORM.id == run_id).one_or_none()
    if not row:
        return None
    if row.status in TERMINAL_RUN_STATUSES:
        return _map_run(row)
    row.status = status
    row.failure_code = failure_code
    row.failure_message = failure_message
    if stage:
        row.current_stage = stage
    if stage_label:
        row.current_stage_label = stage_label
    row.finished_at = _now()
    row.heartbeat_at = _now()
    session.flush()
    return _map_run(row)


def mark_item_status_sync(
    session: Session,
    item_id: str,
    *,
    status: str,
    error_code: str | None = None,
    error_message: str | None = None,
    increment_attempt: bool = False,
) -> DashboardGenerationItem | None:
    row = session.query(DashboardGenerationItemORM).filter(DashboardGenerationItemORM.id == item_id).one_or_none()
    if not row:
        return None
    row.status = status
    if increment_attempt:
        row.attempt_count = (row.attempt_count or 0) + 1
    if status in {"running", "regenerating"} and row.started_at is None:
        row.started_at = _now()
    if status in {"completed", "failed", "cancelled"}:
        row.finished_at = _now()
    row.last_error_code = error_code
    row.last_error_message = error_message
    row.updated_at = _now()

    if row.dashboard_widget_id:
        widget = (
            session.query(DashboardWidgetORM)
            .filter(DashboardWidgetORM.id == row.dashboard_widget_id)
            .one_or_none()
        )
        if widget:
            widget_status = {
                "queued": "queued",
                "running": "running",
                "regenerating": "regenerating",
                "completed": "ready",
                "failed": "failed",
                "cancelled": "cancelled",
                "planned": "queued",
            }.get(status, widget.generation_status)
            widget.generation_status = widget_status
            if error_message is not None:
                widget.generation_error = error_message
            if status == "completed":
                widget.generation_error = None
    session.flush()
    return _map_item(row)


def cancel_pending_items_sync(session: Session, run_id: str) -> int:
    rows = (
        session.query(DashboardGenerationItemORM)
        .filter(
            DashboardGenerationItemORM.run_id == run_id,
            DashboardGenerationItemORM.status.in_(("planned", "queued", "running", "regenerating")),
        )
        .all()
    )
    for row in rows:
        mark_item_status_sync(session, row.id, status="cancelled", error_code="dashboard_generation_cancelled")
    return len(rows)


def fail_pending_items_sync(
    session: Session,
    run_id: str,
    *,
    error_code: str,
    error_message: str,
) -> int:
    rows = (
        session.query(DashboardGenerationItemORM)
        .filter(
            DashboardGenerationItemORM.run_id == run_id,
            DashboardGenerationItemORM.status.in_(("planned", "queued", "running", "regenerating")),
        )
        .all()
    )
    for row in rows:
        mark_item_status_sync(
            session,
            row.id,
            status="failed",
            error_code=error_code,
            error_message=error_message,
        )
    return len(rows)


def fail_stale_runs_sync(session: Session, *, older_than_seconds: int = 1800) -> int:
    cutoff = _now() - timedelta(seconds=older_than_seconds)
    rows = (
        session.query(DashboardGenerationRunORM)
        .filter(
            DashboardGenerationRunORM.status.in_(ACTIVE_RUN_STATUSES),
            DashboardGenerationRunORM.heartbeat_at.is_not(None),
            DashboardGenerationRunORM.heartbeat_at < cutoff,
        )
        .all()
    )
    for row in rows:
        cancel_pending_items_sync(session, row.id)
        finalize_run_sync(
            session,
            row.id,
            status="failed",
            failure_code="dashboard_generation_stale",
            failure_message="Dashboard generation timed out.",
            stage="failed",
            stage_label="Generation timed out",
        )
    return len(rows)


async def fail_stale_runs(*, older_than_seconds: int = 1800) -> int:
    def _run() -> int:
        with session_scope() as session:
            return fail_stale_runs_sync(session, older_than_seconds=older_than_seconds)

    return await anyio.to_thread.run_sync(_run)


def active_run_count_sync(session: Session, owner_id: str) -> int:
    return (
        session.query(DashboardGenerationRunORM.id)
        .filter(
            DashboardGenerationRunORM.owner_id == owner_id,
            DashboardGenerationRunORM.status.in_(ACTIVE_RUN_STATUSES),
        )
        .count()
    )


def run_health_counts_sync(session: Session, *, stale_after_seconds: int) -> dict[str, int]:
    cutoff = _now() - timedelta(seconds=stale_after_seconds)
    active = (
        session.query(DashboardGenerationRunORM.id)
        .filter(DashboardGenerationRunORM.status.in_(ACTIVE_RUN_STATUSES))
        .count()
    )
    stale = (
        session.query(DashboardGenerationRunORM.id)
        .filter(
            DashboardGenerationRunORM.status.in_(ACTIVE_RUN_STATUSES),
            DashboardGenerationRunORM.heartbeat_at.is_not(None),
            DashboardGenerationRunORM.heartbeat_at < cutoff,
        )
        .count()
    )
    return {"active_runs": active, "stale_runs": stale}


def run_health_counts(*, stale_after_seconds: int) -> dict[str, int]:
    with read_session_scope() as session:
        return run_health_counts_sync(session, stale_after_seconds=stale_after_seconds)


__all__ = [
    "ACTIVE_RUN_STATUSES",
    "TERMINAL_RUN_STATUSES",
    "RETRYABLE_ITEM_STATUSES",
    "ActiveGenerationConflictError",
    "PlanRevisionConflictError",
    "GenerationNotApprovableError",
    "GenerationNotFoundError",
    "GenerationItemNotFoundError",
    "compute_placeholder_layouts",
    "create_planning_run",
    "create_planning_run_sync",
    "get_run",
    "get_run_sync",
    "get_run_by_id_sync",
    "get_latest_run_for_dashboard",
    "get_latest_run_for_dashboard_sync",
    "claim_planning_run_sync",
    "claim_execution_run_sync",
    "claim_item_sync",
    "reopen_run_for_item_sync",
    "update_stage_sync",
    "set_task_id_sync",
    "save_plan",
    "save_plan_sync",
    "approve_plan",
    "approve_plan_sync",
    "request_cancel",
    "request_cancel_sync",
    "finalize_run_sync",
    "mark_item_status_sync",
    "cancel_pending_items_sync",
    "fail_pending_items_sync",
    "fail_stale_runs",
    "fail_stale_runs_sync",
    "active_run_count_sync",
    "run_health_counts",
    "run_health_counts_sync",
]
