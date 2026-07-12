"""Durable progress events for AI dashboard generation runs."""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.db.repositories import dashboard_generation_repository as gen_repo
from app.db.session import session_scope
from app.query_engine.cancellation import AgentRunCancelled, QueryCancellationToken
from app.services import run_stream

NAMESPACE = "dashboard-run"
TERMINAL_EVENTS = {
    "run.completed",
    "run.failed",
    "run.cancelled",
    "run.partial",
}
ALLOWED_METADATA_KEYS = {
    "dashboard_id",
    "item_id",
    "widget_id",
    "plan_revision",
    "reason",
    "failure_code",
}


def ensure_available() -> None:
    run_stream.ensure_stream_available()


def publish_event(
    run_id: str,
    event_type: str,
    label: str,
    *,
    stage: str | None = None,
    duration_ms: float | None = None,
    outcome: str | None = None,
    retry_count: int | None = None,
    row_count: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return run_stream.publish_typed_event(
        namespace=NAMESPACE,
        run_id=run_id,
        event_type=event_type,
        label=label,
        maxlen=settings.dashboard_run_event_maxlen,
        ttl_seconds=settings.dashboard_run_event_ttl_seconds,
        stage=stage,
        duration_ms=duration_ms,
        outcome=outcome,
        retry_count=retry_count,
        row_count=row_count,
        metadata=metadata,
        allowed_metadata_keys=ALLOWED_METADATA_KEYS,
    )


def read_events(run_id: str, last_sequence: int, block_ms: int = 5000) -> list[tuple[str, dict]]:
    return run_stream.read_typed_events(
        namespace=NAMESPACE,
        run_id=run_id,
        last_sequence=last_sequence,
        block_ms=block_ms,
    )


def signal_cancel(run_id: str) -> None:
    run_stream.signal_typed_cancel(
        namespace=NAMESPACE,
        run_id=run_id,
        ttl_seconds=max(settings.agent_wall_clock_seconds * 2, 300),
    )
    publish_event(run_id, "run.cancel_requested", "Stopping dashboard generation")


def cancel_signalled(run_id: str) -> bool:
    if run_stream.cancel_typed_signalled(namespace=NAMESPACE, run_id=run_id):
        return True
    with session_scope() as session:
        run = gen_repo.get_run_by_id_sync(session, run_id)
        return bool(run and run.cancel_requested_at)


def clear_cancel(run_id: str) -> None:
    run_stream.clear_typed_cancel(namespace=NAMESPACE, run_id=run_id)


class DashboardGenerationReporter:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.cancellation_token = QueryCancellationToken()

    def check_cancelled(self) -> None:
        if cancel_signalled(self.run_id):
            self.cancellation_token.cancel()
            raise AgentRunCancelled("Dashboard generation cancellation requested.")

    def stage_started(self, stage: str, label: str) -> None:
        self.check_cancelled()
        with session_scope() as session:
            gen_repo.update_stage_sync(session, self.run_id, stage=stage, stage_label=label)
        publish_event(self.run_id, "stage.started", label, stage=stage)

    def stage_completed(
        self,
        stage: str,
        label: str,
        *,
        duration_ms: float | None = None,
        row_count: int | None = None,
    ) -> None:
        publish_event(
            self.run_id,
            "stage.completed",
            label,
            stage=stage,
            duration_ms=duration_ms,
            row_count=row_count,
        )
        self.check_cancelled()

    def tool_started(self, tool_name: str) -> None:
        labels = {
            "list_tables": ("inspecting_schema", "Inspecting schema"),
            "describe_table": ("inspecting_schema", "Inspecting schema"),
            "validate_sql": ("validating", "Validating"),
            "preview_sql": ("executing", "Executing"),
            "execute_sql": ("executing", "Executing"),
        }
        stage, label = labels.get(tool_name, ("generating_sql", "Generating SQL"))
        self.check_cancelled()
        with session_scope() as session:
            gen_repo.update_stage_sync(session, self.run_id, stage=stage, stage_label=label)
        publish_event(self.run_id, "tool.started", label, stage=stage)

    def tool_completed(self, step) -> None:
        labels = {
            "list_tables": "Schema search completed",
            "describe_table": "Table inspection completed",
            "find_join_path": "Relationship search completed",
            "validate_sql": "SQL validation completed",
            "preview_sql": "Query preview completed",
            "execute_sql": "Query execution completed",
        }
        publish_event(
            self.run_id,
            "tool.completed",
            labels.get(getattr(step, "tool", ""), "Analysis step completed"),
            duration_ms=getattr(step, "duration_ms", None),
            outcome=getattr(step, "outcome", None),
            retry_count=getattr(step, "retry_count", None),
            row_count=getattr(step, "output_row_count", None),
        )
        self.check_cancelled()

    def fallback(self, reason: str | None = None) -> None:
        publish_event(
            self.run_id,
            "stage.started",
            "Switching to the reliable fallback pipeline",
            stage="fallback",
            metadata={"reason": (reason or "agent_unavailable")[:80]},
        )

    def widget_event(
        self,
        event_type: str,
        label: str,
        *,
        item_id: str,
        widget_id: str | None = None,
        stage: str | None = None,
    ) -> None:
        publish_event(
            self.run_id,
            event_type,
            label,
            stage=stage,
            metadata={"item_id": item_id, "widget_id": widget_id} if widget_id else {"item_id": item_id},
        )


__all__ = [
    "AgentRunCancelled",
    "DashboardGenerationReporter",
    "TERMINAL_EVENTS",
    "ensure_available",
    "publish_event",
    "read_events",
    "signal_cancel",
    "cancel_signalled",
    "clear_cancel",
]
