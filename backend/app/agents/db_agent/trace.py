"""Tool trace capture for agent runs."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from app.core.secret_detection import redact_secrets

logger = logging.getLogger("query-mind.db_agent")


def _truncate(text: str | None, limit: int = 160) -> str:
    if not text:
        return ""
    trimmed = text.strip().replace("\n", " ")
    if len(trimmed) <= limit:
        return trimmed
    return f"{trimmed[: limit - 3]}..."


def log_agent_event(message: str, *args) -> None:
    logger.info(message, *args)


@dataclass
class TraceStep:
    tool: str
    args_summary: str
    duration_ms: float
    outcome: str  # ok | error | refused | truncated
    output_summary: str | None = None
    output_row_count: int | None = None
    error_class: str | None = None
    retry_count: int | None = None


@dataclass
class TraceRecorder:
    steps: list[TraceStep] = field(default_factory=list)
    on_step: Callable[[TraceStep], None] | None = None

    def record(
        self,
        tool: str,
        args_summary: str,
        duration_ms: float,
        outcome: str,
        *,
        output_summary: str | None = None,
        output_row_count: int | None = None,
        error_class: str | None = None,
        retry_count: int | None = None,
    ) -> None:
        step = TraceStep(
            tool=tool,
            args_summary=redact_secrets(args_summary)[:500],
            duration_ms=round(duration_ms, 2),
            outcome=outcome,
            output_summary=redact_secrets(output_summary)[:500] if output_summary else None,
            output_row_count=output_row_count,
            error_class=error_class,
            retry_count=retry_count,
        )
        self.steps.append(step)
        self._log_step(step)
        if self.on_step:
            self.on_step(step)

    def _log_step(self, step: TraceStep) -> None:
        detail_parts = [f"[tool] {step.tool}", step.args_summary, f"-> {step.outcome}", f"({step.duration_ms:.0f}ms)"]
        if step.output_row_count is not None:
            detail_parts.append(f"rows={step.output_row_count}")
        if step.output_summary:
            detail_parts.append(f"| {_truncate(step.output_summary)}")
        if step.error_class:
            detail_parts.append(f"[{step.error_class}]")
        if step.retry_count is not None:
            detail_parts.append(f"retry={step.retry_count}")
        logger.info(" ".join(part for part in detail_parts if part))

    def to_list(self) -> list[dict]:
        rows: list[dict] = []
        for step in self.steps:
            item = {
                "tool": step.tool,
                "args_summary": step.args_summary,
                "duration_ms": step.duration_ms,
                "outcome": step.outcome,
            }
            if step.output_summary:
                item["output_summary"] = step.output_summary
            if step.output_row_count is not None:
                item["output_row_count"] = step.output_row_count
            if step.error_class:
                item["error_class"] = step.error_class
            if step.retry_count is not None:
                item["retry_count"] = step.retry_count
            rows.append(item)
        return rows


def summarize_args(tool_name: str, args: dict) -> str:
    if tool_name in {"execute_sql", "preview_sql", "validate_sql", "explain_sql"}:
        sql = str(args.get("sql", ""))
        return f"sql={sql[:200]}{'...' if len(sql) > 200 else ''}"
    return str(args)[:300]


def synthetic_trace_step(
    tool: str,
    args_summary: str,
    outcome: str,
    *,
    output_summary: str | None = None,
    error_class: str | None = None,
    retry_count: int | None = None,
) -> dict:
    step = {
        "tool": tool,
        "args_summary": args_summary[:500],
        "duration_ms": 0.0,
        "outcome": outcome,
    }
    if output_summary:
        step["output_summary"] = output_summary[:500]
    if error_class:
        step["error_class"] = error_class
    if retry_count is not None:
        step["retry_count"] = retry_count
    return step


def combine_failed_agent_trace(
    failed_trace: list | None,
    fallback_reason: str | None,
    agent_error: str | None = None,
) -> list:
    trace = list(failed_trace or [])
    if agent_error and not trace:
        trace.append(
            synthetic_trace_step(
                "agent_exception",
                "Agent path raised before trace was available.",
                "error",
                error_class="agent_exception",
            )
        )
    reason = fallback_reason or ("agent_exception" if agent_error else None)
    if reason:
        trace.append(
            synthetic_trace_step(
                "fallback_pipeline",
                f"Agent failed: {reason}",
                "ok",
                output_summary="Fallback pipeline answered after the agent path failed.",
            )
        )
    return trace


__all__ = [
    "TraceStep",
    "TraceRecorder",
    "log_agent_event",
    "summarize_args",
    "synthetic_trace_step",
    "combine_failed_agent_trace",
]
