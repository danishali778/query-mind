"""AI dashboard generation orchestration."""

from __future__ import annotations

import logging
from typing import Any

import anyio

from app.agents.dashboard_planner import (
    DashboardPlanningError,
    parse_dashboard_plan,
    plan_dashboard,
    reject_write_oriented_prompt,
)
from app.core.config import settings
from app.core.errors import BadRequestError, ConflictError, NotFoundError, ServiceUnavailableError
from app.db.models.dashboard import ChartConfig, UpdateWidgetInput
from app.db.repositories import dashboard_generation_repository as gen_repo
from app.db.repositories import dashboard_repository
from app.db.session import session_scope
from app.query_engine.cancellation import AgentRunCancelled
from app.services import analysis_service, connection_service
from app.services.dashboard_generation_progress import (
    TERMINAL_EVENTS,
    DashboardGenerationReporter,
    cancel_signalled,
    clear_cancel,
    ensure_available,
    publish_event,
    read_events,
    signal_cancel,
)

logger = logging.getLogger(__name__)


def _events_url(run_id: str) -> str:
    return f"/api/dashboard/generations/{run_id}/events"


def _snapshot_dict(run) -> dict[str, Any]:
    return {
        **run.model_dump(),
        "events_url": _events_url(run.id),
    }


def _finalize_idle_run_sync(session, run_id: str):
    run = gen_repo.get_run_by_id_sync(session, run_id)
    if not run:
        return None, None, None
    statuses = [item.status for item in run.items]
    if any(status in {"queued", "running", "regenerating"} for status in statuses):
        return None, None, None
    completed = sum(1 for status in statuses if status == "completed")
    failed = sum(1 for status in statuses if status in {"failed", "cancelled"})
    if failed and completed:
        status, event, label = "partial", "run.partial", "Dashboard generation partially completed"
    elif failed and not completed:
        status, event, label = "failed", "run.failed", "Dashboard generation failed"
    else:
        status, event, label = "completed", "run.completed", "Dashboard generation completed"
    finalized = gen_repo.finalize_run_sync(
        session,
        run_id,
        status=status,
        stage=status,
        stage_label=label,
    )
    return finalized, event, label


def _mark_item_dispatch_failed(run_id: str, item_id: str) -> tuple[str | None, str | None]:
    message = "The widget generation worker could not be started."
    with session_scope() as session:
        gen_repo.mark_item_status_sync(
            session,
            item_id,
            status="failed",
            error_code="dispatch_failed",
            error_message=message,
        )
        _finalized, event, label = _finalize_idle_run_sync(session, run_id)
    publish_event(
        run_id,
        "widget.failed",
        "Widget generation worker unavailable",
        stage="failed",
        metadata={"item_id": item_id, "failure_code": "dispatch_failed"},
    )
    if event and label:
        publish_event(run_id, event, label, stage=event.removeprefix("run."))
    return event, label


async def start_planning(
    *,
    owner_id: str,
    connection_id: str,
    prompt: str,
    client_request_id: str,
    requested_widget_count: int | None = None,
    default_time_range: str | None = None,
    extra_instructions: str | None = None,
) -> dict[str, Any]:
    if not settings.dashboard_ai_enabled:
        raise BadRequestError("AI dashboard generation is disabled.", code="dashboard_ai_disabled")
    prompt = (prompt or "").strip()
    if not prompt:
        raise BadRequestError("Prompt is required.")
    if len(prompt) > settings.dashboard_ai_max_prompt_chars:
        raise BadRequestError("Prompt exceeds the maximum length.")
    try:
        reject_write_oriented_prompt(prompt)
        if extra_instructions:
            reject_write_oriented_prompt(extra_instructions)
    except ValueError as exc:
        raise BadRequestError(str(exc), code="invalid_dashboard_plan") from exc

    count = requested_widget_count or settings.dashboard_ai_default_widgets
    count = max(1, min(settings.dashboard_ai_max_widgets, int(count)))

    engine = await connection_service.get_engine(owner_id, connection_id)
    if not engine:
        raise NotFoundError("Database connection not found.")

    try:
        ensure_available()
    except RuntimeError as exc:
        raise ServiceUnavailableError(str(exc), code="streaming_unavailable") from exc

    try:
        run, created = await gen_repo.create_planning_run(
            owner_id=owner_id,
            connection_id=connection_id,
            prompt=prompt,
            client_request_id=client_request_id,
            requested_widget_count=count,
            default_time_range=default_time_range,
            extra_instructions=extra_instructions,
            max_active_runs=settings.dashboard_ai_max_active_per_user,
        )
    except gen_repo.ActiveGenerationConflictError as exc:
        raise ConflictError(str(exc), code="dashboard_generation_limit_reached") from exc

    if created:
        from app.workers.jobs.plan_dashboard import plan_dashboard_task

        try:
            async_result = plan_dashboard_task.apply_async(args=[run.id], queue=settings.celery_dashboards_queue)
            with session_scope() as session:
                gen_repo.set_task_id_sync(session, run.id, async_result.id)
            publish_event(run.id, "run.queued", "Planning queued", stage="planning")
        except Exception as exc:
            with session_scope() as session:
                gen_repo.finalize_run_sync(
                    session,
                    run.id,
                    status="failed",
                    failure_code="dispatch_failed",
                    failure_message="The dashboard planning worker could not be started.",
                    stage="failed",
                    stage_label="Planning worker unavailable",
                )
            publish_event(run.id, "run.failed", "Planning worker unavailable", stage="failed")
            raise ServiceUnavailableError(
                "The dashboard planning worker could not be started.",
                code="dispatch_failed",
            ) from exc

    return {
        "run_id": run.id,
        "status": run.status,
        "events_url": _events_url(run.id),
    }


async def get_generation(owner_id: str, run_id: str) -> dict[str, Any]:
    run = await gen_repo.get_run(owner_id, run_id)
    if not run:
        raise NotFoundError("Generation run not found.")
    return _snapshot_dict(run)


async def get_generation_for_dashboard(owner_id: str, dashboard_id: str) -> dict[str, Any]:
    run = await gen_repo.get_latest_run_for_dashboard(owner_id, dashboard_id)
    if not run:
        raise NotFoundError("Generation run not found.")
    return _snapshot_dict(run)


async def update_plan(owner_id: str, run_id: str, *, expected_revision: int, plan: dict[str, Any]) -> dict[str, Any]:
    try:
        validated = parse_dashboard_plan(plan)
    except Exception as exc:
        raise BadRequestError(str(exc), code="invalid_dashboard_plan") from exc
    try:
        run = await gen_repo.save_plan(
            owner_id,
            run_id,
            validated.model_dump(),
            expected_revision=expected_revision,
        )
    except gen_repo.GenerationNotFoundError as exc:
        raise NotFoundError("Generation run not found.") from exc
    except gen_repo.PlanRevisionConflictError as exc:
        raise ConflictError(str(exc), code="dashboard_plan_revision_conflict") from exc
    except gen_repo.GenerationNotApprovableError as exc:
        raise BadRequestError(str(exc), code="dashboard_generation_not_approvable") from exc
    publish_event(
        run.id,
        "plan.updated",
        "Dashboard plan updated",
        stage="awaiting_approval",
        metadata={"plan_revision": run.plan_revision},
    )
    return _snapshot_dict(run)


async def approve(owner_id: str, run_id: str, *, expected_revision: int) -> dict[str, Any]:
    try:
        run, dashboard, _widgets, created = await gen_repo.approve_plan(
            owner_id,
            run_id,
            expected_revision=expected_revision,
        )
    except gen_repo.GenerationNotFoundError as exc:
        raise NotFoundError("Generation run not found.") from exc
    except gen_repo.PlanRevisionConflictError as exc:
        raise ConflictError(str(exc), code="dashboard_plan_revision_conflict") from exc
    except gen_repo.GenerationNotApprovableError as exc:
        raise BadRequestError(str(exc), code="dashboard_generation_not_approvable") from exc

    if created:
        publish_event(
            run.id,
            "dashboard.created",
            "Draft dashboard created",
            stage="queued",
            metadata={"dashboard_id": dashboard.id},
        )
        from app.workers.jobs.execute_dashboard_generation import execute_dashboard_generation_task

        try:
            async_result = execute_dashboard_generation_task.apply_async(
                args=[run.id],
                queue=settings.celery_dashboards_queue,
            )
            with session_scope() as session:
                gen_repo.set_task_id_sync(session, run.id, async_result.id)
            publish_event(run.id, "run.queued", "Generation queued", stage="queued")
        except Exception as exc:
            message = "The dashboard generation worker could not be started."
            with session_scope() as session:
                gen_repo.fail_pending_items_sync(
                    session,
                    run.id,
                    error_code="dispatch_failed",
                    error_message=message,
                )
                gen_repo.finalize_run_sync(
                    session,
                    run.id,
                    status="failed",
                    failure_code="dispatch_failed",
                    failure_message=message,
                    stage="failed",
                    stage_label="Generation worker unavailable",
                )
            publish_event(run.id, "run.failed", "Generation worker unavailable", stage="failed")
            raise ServiceUnavailableError(message, code="dispatch_failed") from exc

    return {
        "run_id": run.id,
        "dashboard_id": run.dashboard_id,
        "status": run.status,
        "events_url": _events_url(run.id),
    }


async def cancel(owner_id: str, run_id: str) -> dict[str, Any]:
    try:
        run = await gen_repo.request_cancel(owner_id, run_id)
    except gen_repo.GenerationNotFoundError as exc:
        raise NotFoundError("Generation run not found.") from exc
    try:
        signal_cancel(run_id)
    except Exception:
        logger.warning("Failed to publish dashboard cancel signal for %s", run_id, exc_info=True)

    if run.status in {"planning", "awaiting_approval"} and not run.dashboard_id:
        with session_scope() as session:
            gen_repo.cancel_pending_items_sync(session, run_id)
            finalized = gen_repo.finalize_run_sync(
                session,
                run_id,
                status="cancelled",
                failure_code="dashboard_generation_cancelled",
                failure_message="Cancelled before approval.",
                stage="cancelled",
                stage_label="Cancelled",
            )
            if finalized:
                run = finalized
        publish_event(run_id, "run.cancelled", "Dashboard generation cancelled", stage="cancelled")
    return _snapshot_dict(run)


async def retry_item(owner_id: str, run_id: str, item_id: str) -> dict[str, Any]:
    run = await gen_repo.get_run(owner_id, run_id)
    if not run:
        raise NotFoundError("Generation run not found.")
    item = next((entry for entry in run.items if entry.id == item_id), None)
    if not item:
        raise NotFoundError("Generation item not found.")
    if item.status not in gen_repo.RETRYABLE_ITEM_STATUSES:
        raise BadRequestError("Only failed or cancelled widgets can be retried.")
    if run.status not in gen_repo.TERMINAL_RUN_STATUSES and run.status != "queued":
        raise ConflictError("Wait for the active dashboard generation to finish before retrying a widget.")

    try:
        with session_scope() as session:
            gen_repo.reopen_run_for_item_sync(
                session,
                owner_id,
                run_id,
                item_id,
                item_status="queued",
                allowed_item_statuses=gen_repo.RETRYABLE_ITEM_STATUSES,
            )
    except gen_repo.GenerationNotApprovableError as exc:
        raise ConflictError(str(exc), code="dashboard_widget_already_queued") from exc
    clear_cancel(run_id)

    from app.workers.jobs.execute_dashboard_generation import regenerate_dashboard_widget_task

    try:
        task = regenerate_dashboard_widget_task.apply_async(
            args=[run_id, item_id, None],
            queue=settings.celery_dashboards_queue,
        )
        with session_scope() as session:
            gen_repo.set_task_id_sync(session, run_id, task.id)
    except Exception as exc:
        _mark_item_dispatch_failed(run_id, item_id)
        raise ServiceUnavailableError(
            "The widget generation worker could not be started.",
            code="dispatch_failed",
        ) from exc
    publish_event(run_id, "widget.queued", "Widget queued for retry", metadata={"item_id": item_id})
    return await get_generation(owner_id, run_id)


async def regenerate_item(
    owner_id: str,
    run_id: str,
    item_id: str,
    *,
    instruction: str | None = None,
) -> dict[str, Any]:
    run = await gen_repo.get_run(owner_id, run_id)
    if not run:
        raise NotFoundError("Generation run not found.")
    item = next((entry for entry in run.items if entry.id == item_id), None)
    if not item:
        raise NotFoundError("Generation item not found.")

    if item.status not in {"completed", "failed", "cancelled"}:
        raise BadRequestError("Only completed, failed, or cancelled widgets can be regenerated.")
    if run.status not in gen_repo.TERMINAL_RUN_STATUSES:
        raise ConflictError("Wait for the active dashboard generation to finish before regenerating a widget.")

    try:
        with session_scope() as session:
            gen_repo.reopen_run_for_item_sync(
                session,
                owner_id,
                run_id,
                item_id,
                item_status="regenerating",
                allowed_item_statuses=("completed", "failed", "cancelled"),
            )
    except gen_repo.GenerationNotApprovableError as exc:
        raise ConflictError(str(exc), code="dashboard_widget_already_queued") from exc
    clear_cancel(run_id)

    from app.workers.jobs.execute_dashboard_generation import regenerate_dashboard_widget_task

    try:
        task = regenerate_dashboard_widget_task.apply_async(
            args=[run_id, item_id, instruction],
            queue=settings.celery_dashboards_queue,
        )
        with session_scope() as session:
            gen_repo.set_task_id_sync(session, run_id, task.id)
    except Exception as exc:
        _mark_item_dispatch_failed(run_id, item_id)
        raise ServiceUnavailableError(
            "The widget generation worker could not be started.",
            code="dispatch_failed",
        ) from exc
    publish_event(
        run_id,
        "widget.regenerating",
        "Regenerating widget",
        metadata={"item_id": item_id},
    )
    return await get_generation(owner_id, run_id)


async def stream_events(owner_id: str, run_id: str, last_event_id: str | None = None):
    run = await gen_repo.get_run(owner_id, run_id)
    if not run:
        raise NotFoundError("Generation run not found.")

    last_sequence = 0
    if last_event_id:
        try:
            last_sequence = int(str(last_event_id).split("-", 1)[0])
        except ValueError:
            last_sequence = 0

    try:
        ensure_available()
        redis_ok = True
    except RuntimeError:
        redis_ok = False

    if not redis_ok:
        snapshot = _snapshot_dict(run)
        yield _sse("snapshot", snapshot, event_id="0")
        return

    idle_rounds = 0
    heartbeat_rounds = max(1, (settings.dashboard_run_heartbeat_seconds + 3) // 4)
    while True:
        try:
            events = await anyio.to_thread.run_sync(read_events, run_id, last_sequence, 4000)
        except Exception:
            snapshot = await get_generation(owner_id, run_id)
            yield _sse("snapshot", snapshot, event_id=str(last_sequence))
            return

        if not events:
            idle_rounds += 1
            if idle_rounds >= heartbeat_rounds:
                current = await get_generation(owner_id, run_id)
                yield _sse("heartbeat", {"run_id": run_id, "status": current["status"]}, event_id=str(last_sequence))
                if current["status"] in gen_repo.TERMINAL_RUN_STATUSES:
                    return
                idle_rounds = 0
            continue

        idle_rounds = 0
        for seq, event in events:
            last_sequence = int(seq)
            yield _sse(event.get("type") or "message", event, event_id=str(seq))
            if event.get("type") in TERMINAL_EVENTS:
                return


def _sse(event_type: str, payload: dict[str, Any], *, event_id: str) -> str:
    import json

    return f"id: {event_id}\nevent: {event_type}\ndata: {json.dumps(payload)}\n\n"


def _chart_config_from_result(result: dict[str, Any]) -> ChartConfig | None:
    chart = result.get("chart_recommendation")
    if not isinstance(chart, dict):
        return None
    try:
        return ChartConfig.model_validate(chart)
    except Exception:
        return ChartConfig(
            x_column=chart.get("x_column"),
            y_columns=list(chart.get("y_columns") or []),
            color_column=chart.get("color_column"),
            is_grouped=bool(chart.get("is_grouped", False)),
            title=chart.get("title"),
            x_label=chart.get("x_label"),
            y_label=chart.get("y_label"),
        )


def _viz_type_from_result(result: dict[str, Any], planned: str | None) -> str:
    preferred = result.get("preferred_viz_type")
    if preferred:
        return str(preferred)
    chart = result.get("chart_recommendation")
    if isinstance(chart, dict):
        chart_type = chart.get("chart_type") or chart.get("type")
        if chart_type:
            return str(chart_type)
    if planned and planned != "auto":
        return planned
    return "table"


async def execute_run(
    run_id: str,
    *,
    reporter: DashboardGenerationReporter | None = None,
) -> None:
    reporter = reporter or DashboardGenerationReporter(run_id)
    with session_scope() as session:
        run = gen_repo.claim_execution_run_sync(session, run_id)
        if not run:
            return
    publish_event(run_id, "run.started", "Generating dashboard widgets", stage="running")

    with session_scope() as session:
        run = gen_repo.get_run_by_id_sync(session, run_id)
        items = list(run.items) if run else []

    completed = 0
    failed = 0
    for item in sorted(items, key=lambda entry: entry.order_index):
        if cancel_signalled(run_id):
            with session_scope() as session:
                gen_repo.cancel_pending_items_sync(session, run_id)
                status = "partial" if completed else "cancelled"
                gen_repo.finalize_run_sync(
                    session,
                    run_id,
                    status=status,
                    failure_code="dashboard_generation_cancelled",
                    failure_message="Cancelled during generation.",
                    stage="cancelled",
                    stage_label="Cancelled",
                )
            publish_event(
                run_id,
                "run.partial" if completed else "run.cancelled",
                "Dashboard generation cancelled",
                stage="cancelled",
            )
            return

        if item.status in {"completed"}:
            completed += 1
            continue

        try:
            ok = await _execute_item(run_id, item.id, reporter=reporter)
        except AgentRunCancelled:
            with session_scope() as session:
                gen_repo.cancel_pending_items_sync(session, run_id)
                status = "partial" if completed else "cancelled"
                gen_repo.finalize_run_sync(
                    session,
                    run_id,
                    status=status,
                    failure_code="dashboard_generation_cancelled",
                    failure_message="Cancelled during generation.",
                    stage="cancelled",
                    stage_label="Cancelled",
                )
            publish_event(
                run_id,
                "run.partial" if completed else "run.cancelled",
                "Dashboard generation cancelled",
                stage="cancelled",
            )
            return
        if ok:
            completed += 1
        else:
            failed += 1

    with session_scope() as session:
        if failed and completed:
            status = "partial"
            event = "run.partial"
            label = "Dashboard generation partially completed"
        elif failed and not completed:
            status = "failed"
            event = "run.failed"
            label = "Dashboard generation failed"
        else:
            status = "completed"
            event = "run.completed"
            label = "Dashboard generation completed"
        gen_repo.finalize_run_sync(
            session,
            run_id,
            status=status,
            failure_code="dashboard_widget_generation_failed" if failed and not completed else None,
            failure_message="All widgets failed." if failed and not completed else None,
            stage=status,
            stage_label=label,
        )
    publish_event(run_id, event, label, stage=status)


async def _execute_item(
    run_id: str,
    item_id: str,
    *,
    reporter: DashboardGenerationReporter,
    instruction: str | None = None,
    regenerating: bool = False,
) -> bool:
    with session_scope() as session:
        run = gen_repo.get_run_by_id_sync(session, run_id)
        if not run:
            return False
        item = next((entry for entry in run.items if entry.id == item_id), None)
        if not item:
            return False
        owner_id = run.owner_id
        connection_id = run.connection_id
        plan = dict(item.plan_json or {})
        widget_id = item.dashboard_widget_id
        default_time_range = run.default_time_range
        plan_assumptions = list((run.plan_json or {}).get("assumptions") or [])[:5] if run.plan_json else []

    previous_sql = None
    previous_rows = None
    previous_columns = None
    previous_chart = None
    previous_viz = None
    if regenerating and widget_id:
        widget = await dashboard_repository.get_widget(owner_id, widget_id)
        if widget and widget.generation_status == "ready":
            previous_sql = widget.sql
            previous_rows = widget.rows
            previous_columns = widget.columns
            previous_chart = widget.chart_config
            previous_viz = widget.viz_type

    with session_scope() as session:
        claimed = gen_repo.claim_item_sync(session, item_id)
    if not claimed:
        return False
    reporter.widget_event(
        "widget.regenerating" if regenerating else "widget.started",
        "Regenerating widget" if regenerating else "Generating widget",
        item_id=item_id,
        widget_id=widget_id,
        stage="regenerating" if regenerating else "running",
    )

    question = str(plan.get("question") or "")
    if instruction:
        question = f"{question}\n\nRegeneration instruction: {instruction.strip()}"
    time_range = plan.get("time_range") or default_time_range
    context = []
    if time_range:
        context.append(f"Prefer the time range: {time_range}")
    if plan.get("purpose"):
        context.append(f"Widget purpose: {plan['purpose']}")

    try:
        reporter.stage_started("generating_sql", "Generating SQL")
        result = await analysis_service.run_analysis(
            user_id=owner_id,
            connection_id=connection_id,
            question=question,
            context_instructions="\n".join(context) if context else None,
            progress=reporter,
            session_id=f"dashboard-gen-{run_id}-{item_id}",
            requested_visualization=str(plan.get("visualization") or "auto"),
            allow_schema_shortcuts=False,
        )
        if result.get("error") or not result.get("sql"):
            raise RuntimeError(result.get("error") or "Widget generation produced no SQL.")

        viz_type = _viz_type_from_result(result, plan.get("visualization"))
        chart_config = _chart_config_from_result(result)
        assumptions = list(result.get("assumptions") or [])
        assumptions.extend(plan_assumptions)

        if widget_id:
            await dashboard_repository.update_widget(
                owner_id,
                widget_id,
                UpdateWidgetInput(
                    sql=result.get("sql"),
                    columns=list(result.get("columns") or []),
                    rows=list(result.get("rows") or []),
                    viz_type=viz_type,
                    chart_config=chart_config,
                    source_prompt=str(plan.get("question") or ""),
                    generation_status="ready",
                    generation_error="",
                    assumptions=[str(item) for item in assumptions if item],
                ),
            )
        with session_scope() as session:
            gen_repo.mark_item_status_sync(session, item_id, status="completed")
        reporter.widget_event(
            "widget.completed",
            "Widget ready",
            item_id=item_id,
            widget_id=widget_id,
            stage="ready",
        )
        return True
    except AgentRunCancelled:
        with session_scope() as session:
            gen_repo.mark_item_status_sync(
                session,
                item_id,
                status="cancelled",
                error_code="dashboard_generation_cancelled",
                error_message="Cancelled",
            )
        if regenerating and widget_id and previous_sql is not None:
            await dashboard_repository.update_widget(
                owner_id,
                widget_id,
                UpdateWidgetInput(
                    sql=previous_sql,
                    columns=previous_columns or [],
                    rows=previous_rows or [],
                    viz_type=previous_viz,
                    chart_config=previous_chart,
                    generation_status="ready",
                    generation_error="",
                ),
            )
        reporter.widget_event("widget.cancelled", "Widget cancelled", item_id=item_id, widget_id=widget_id)
        raise
    except Exception as exc:
        logger.warning("Dashboard widget generation failed item=%s", item_id, exc_info=True)
        message = "Unable to generate this widget."
        with session_scope() as session:
            gen_repo.mark_item_status_sync(
                session,
                item_id,
                status="failed",
                error_code="dashboard_widget_generation_failed",
                error_message=message,
            )
        if regenerating and widget_id and previous_sql is not None:
            await dashboard_repository.update_widget(
                owner_id,
                widget_id,
                UpdateWidgetInput(
                    sql=previous_sql,
                    columns=previous_columns or [],
                    rows=previous_rows or [],
                    viz_type=previous_viz,
                    chart_config=previous_chart,
                    generation_status="ready",
                    generation_error=message,
                ),
            )
        else:
            if widget_id:
                await dashboard_repository.update_widget(
                    owner_id,
                    widget_id,
                    UpdateWidgetInput(generation_status="failed", generation_error=message),
                )
        reporter.widget_event(
            "widget.failed",
            "Widget generation failed",
            item_id=item_id,
            widget_id=widget_id,
            stage="failed",
        )
        return False


async def execute_planning(
    run_id: str,
    *,
    reporter: DashboardGenerationReporter | None = None,
) -> None:
    reporter = reporter or DashboardGenerationReporter(run_id)
    with session_scope() as session:
        run = gen_repo.claim_planning_run_sync(session, run_id)
        if not run:
            return
        owner_id = run.owner_id
        connection_id = run.connection_id
        prompt = run.prompt
        count = run.requested_widget_count
        default_time_range = run.default_time_range
        extra_instructions = run.extra_instructions

    publish_event(run_id, "run.started", "Planning dashboard", stage="planning")
    try:
        if cancel_signalled(run_id):
            raise AgentRunCancelled("Cancelled")

        reporter.stage_started("schema_search", "Searching the database schema")
        catalog = await connection_service.get_catalog(owner_id, connection_id)
        reporter.stage_completed("schema_search", "Schema context ready")

        def progress(stage: str, label: str) -> None:
            reporter.stage_started(stage, label)

        plan = await anyio.to_thread.run_sync(
            lambda: plan_dashboard(
                objective=prompt,
                widget_count=count,
                catalog=catalog,
                default_time_range=default_time_range,
                extra_instructions=extra_instructions,
                progress=progress,
            )
        )
        with session_scope() as session:
            saved = gen_repo.save_plan_sync(
                session,
                owner_id,
                run_id,
                plan.model_dump(),
                mark_awaiting_approval=True,
            )
        publish_event(
            run_id,
            "plan.ready",
            "Dashboard plan ready",
            stage="awaiting_approval",
            metadata={"plan_revision": saved.plan_revision},
        )
    except AgentRunCancelled:
        with session_scope() as session:
            gen_repo.finalize_run_sync(
                session,
                run_id,
                status="cancelled",
                failure_code="dashboard_generation_cancelled",
                failure_message="Cancelled during planning.",
                stage="cancelled",
                stage_label="Cancelled",
            )
        publish_event(run_id, "run.cancelled", "Planning cancelled", stage="cancelled")
    except DashboardPlanningError as exc:
        with session_scope() as session:
            gen_repo.finalize_run_sync(
                session,
                run_id,
                status="failed",
                failure_code=exc.code,
                failure_message=str(exc),
                stage="failed",
                stage_label="Planning failed",
            )
        publish_event(run_id, "run.failed", "Planning failed", stage="failed", metadata={"failure_code": exc.code})
    except Exception as exc:
        logger.exception("Dashboard planning failed for %s", run_id)
        with session_scope() as session:
            finalized = gen_repo.finalize_run_sync(
                session,
                run_id,
                status="failed",
                failure_code="dashboard_planning_failed",
                failure_message="Unable to plan this dashboard.",
                stage="failed",
                stage_label="Planning failed",
            )
        if finalized and finalized.status == "failed":
            publish_event(
                run_id,
                "run.failed",
                "Planning failed",
                stage="failed",
                metadata={"failure_code": "dashboard_planning_failed"},
            )


async def execute_single_item(
    run_id: str,
    item_id: str,
    instruction: str | None = None,
    *,
    reporter: DashboardGenerationReporter | None = None,
) -> None:
    reporter = reporter or DashboardGenerationReporter(run_id)
    regenerating = True
    try:
        await _execute_item(
            run_id,
            item_id,
            reporter=reporter,
            instruction=instruction,
            regenerating=regenerating,
        )
    except AgentRunCancelled:
        completed = 0
        with session_scope() as session:
            run = gen_repo.get_run_by_id_sync(session, run_id)
            if run:
                completed = sum(1 for entry in run.items if entry.status == "completed")
                gen_repo.cancel_pending_items_sync(session, run_id)
                status = "partial" if completed else "cancelled"
                gen_repo.finalize_run_sync(
                    session,
                    run_id,
                    status=status,
                    failure_code="dashboard_generation_cancelled",
                    failure_message="Cancelled during widget generation.",
                    stage="cancelled",
                    stage_label="Cancelled",
                )
        publish_event(
            run_id,
            "run.partial" if completed else "run.cancelled",
            "Dashboard generation cancelled",
            stage="cancelled",
        )
        return

    with session_scope() as session:
        _finalized, event, label = _finalize_idle_run_sync(session, run_id)
    if event and label:
        publish_event(run_id, event, label, stage=event.removeprefix("run."))


__all__ = [
    "start_planning",
    "get_generation",
    "update_plan",
    "approve",
    "cancel",
    "retry_item",
    "regenerate_item",
    "stream_events",
    "execute_run",
    "execute_planning",
    "execute_single_item",
]
