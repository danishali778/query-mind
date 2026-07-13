"""Dashboard planner agent — produces a versioned plan without executing SQL."""

from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any, Callable

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from app.agents._llm_content import content_to_text
from app.agents._prompt_loader import load_prompt
from app.agents.dashboard_planner.plan import (
    ALLOWED_SIZES,
    ALLOWED_VISUALIZATIONS,
    DashboardPlan,
    parse_dashboard_plan,
    reject_write_oriented_prompt,
)
from app.integrations.llm_client import get_chat_llm
from app.agents.schema_context.user_semantics import SemanticContext, render_untrusted_semantic_context

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).with_name("prompts") / "planner_system_prompt.md"
_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


class DashboardPlanningError(RuntimeError):
    def __init__(self, message: str, *, code: str = "dashboard_planning_failed"):
        super().__init__(message)
        self.code = code


def _extract_json_object(text: str) -> dict[str, Any]:
    cleaned = (text or "").strip()
    fence = _JSON_FENCE.search(cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise DashboardPlanningError("Planner did not return JSON.", code="invalid_dashboard_plan")
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise DashboardPlanningError("Planner returned malformed JSON.", code="invalid_dashboard_plan") from exc
    if not isinstance(payload, dict):
        raise DashboardPlanningError("Planner JSON must be an object.", code="invalid_dashboard_plan")
    return payload


def _ensure_client_keys(payload: dict[str, Any]) -> dict[str, Any]:
    widgets = payload.get("widgets")
    if isinstance(widgets, list):
        for widget in widgets:
            if not isinstance(widget, dict):
                continue
            try:
                widget["client_key"] = str(uuid.UUID(str(widget.get("client_key") or "")))
            except (ValueError, AttributeError):
                widget["client_key"] = str(uuid.uuid4())
    return payload


def _sanitize_catalog_for_planner(catalog: Any) -> str:
    if catalog is None:
        return "No schema catalog available."
    if hasattr(catalog, "model_dump"):
        data = catalog.model_dump()
    elif isinstance(catalog, dict):
        data = catalog
    else:
        data = {"repr": str(catalog)[:4000]}

    # Keep only structural metadata — never dump sample rows.
    tables = []
    raw_tables = data.get("tables") or data.get("catalog") or []
    if isinstance(raw_tables, dict):
        raw_tables = list(raw_tables.values())
    for table in list(raw_tables)[:80]:
        if not isinstance(table, dict):
            continue
        columns = []
        for column in list(table.get("columns") or [])[:40]:
            if isinstance(column, dict):
                columns.append(
                    {
                        "name": column.get("name"),
                        "type": column.get("type") or column.get("data_type"),
                        "nullable": column.get("nullable"),
                    }
                )
            else:
                columns.append({"name": str(column)})
        tables.append(
            {
                "name": table.get("name") or table.get("table"),
                "schema": table.get("schema"),
                "columns": columns,
            }
        )
    relationships = data.get("relationships") or data.get("foreign_keys") or []
    semantics = data.get("semantics") or data.get("semantic_definitions") or []
    return json.dumps(
        {
            "db_type": data.get("db_type"),
            "tables": tables,
            "relationships": relationships[:100] if isinstance(relationships, list) else relationships,
            "semantics": semantics[:50] if isinstance(semantics, list) else semantics,
        },
        default=str,
    )[:20000]


def _build_messages(
    *,
    objective: str,
    widget_count: int,
    default_time_range: str | None,
    extra_instructions: str | None,
    catalog_text: str,
    semantic_context_text: str = "",
    repair_feedback: str | None = None,
) -> list:
    system = (
        load_prompt(str(_PROMPT_PATH))
        .replace("__WIDGET_COUNT__", str(widget_count))
    )
    human_parts = [
        f"Dashboard objective:\n{objective.strip()}",
        f"Requested widget count: {widget_count}",
        f"Default time period: {default_time_range or 'not specified'}",
        f"Extra instructions: {(extra_instructions or '').strip() or 'none'}",
        f"Supported visualizations: {', '.join(ALLOWED_VISUALIZATIONS)}",
        f"Supported sizes: {', '.join(ALLOWED_SIZES)}",
        f"Sanitized schema catalog:\n{catalog_text}",
    ]
    if semantic_context_text:
        human_parts.append(semantic_context_text)
    if repair_feedback:
        human_parts.append(f"Previous plan was invalid. Fix these issues and return JSON only:\n{repair_feedback}")
    return [
        SystemMessage(content=system),
        HumanMessage(content="\n\n".join(human_parts)),
    ]


def plan_dashboard(
    *,
    objective: str,
    widget_count: int,
    catalog: Any,
    default_time_range: str | None = None,
    extra_instructions: str | None = None,
    progress: Callable[[str, str], None] | None = None,
    semantic_context: SemanticContext | None = None,
) -> DashboardPlan:
    """Produce a validated dashboard plan. Never executes SQL."""

    reject_write_oriented_prompt(objective)
    if extra_instructions:
        reject_write_oriented_prompt(extra_instructions)

    widget_count = max(1, min(8, int(widget_count)))
    catalog_text = _sanitize_catalog_for_planner(catalog)
    semantic_context = semantic_context or SemanticContext(
        schema_hash=getattr(catalog, "schema_hash", "")
    )
    semantic_context_text = render_untrusted_semantic_context(semantic_context)

    def _stage(stage: str, label: str) -> None:
        if progress:
            progress(stage, label)

    _stage("reading_objective", "Reading the dashboard objective")
    _stage("designing_widgets", "Designing dashboard widgets")

    llm = get_chat_llm(temperature=0.2, max_tokens=4096)
    messages = _build_messages(
        objective=objective,
        widget_count=widget_count,
        default_time_range=default_time_range,
        extra_instructions=extra_instructions,
        catalog_text=catalog_text,
        semantic_context_text=semantic_context_text,
    )

    try:
        response = llm.invoke(messages)
        raw = content_to_text(response.content)
        payload = _ensure_client_keys(_extract_json_object(raw))
        plan = parse_dashboard_plan(payload)
    except (DashboardPlanningError, ValidationError, ValueError) as first_error:
        feedback = str(first_error)
        logger.warning("Dashboard planner first pass invalid: %s", feedback)
        _stage("checking_plan", "Checking the dashboard plan")
        repair_messages = _build_messages(
            objective=objective,
            widget_count=widget_count,
            default_time_range=default_time_range,
            extra_instructions=extra_instructions,
            catalog_text=catalog_text,
            semantic_context_text=semantic_context_text,
            repair_feedback=feedback,
        )
        try:
            response = llm.invoke(repair_messages)
            raw = content_to_text(response.content)
            payload = _ensure_client_keys(_extract_json_object(raw))
            plan = parse_dashboard_plan(payload)
        except (DashboardPlanningError, ValidationError, ValueError) as second_error:
            raise DashboardPlanningError(
                "Unable to produce a valid dashboard plan.",
                code="invalid_dashboard_plan",
            ) from second_error

    _stage("checking_plan", "Checking the dashboard plan")
    if len(plan.widgets) > widget_count:
        plan = plan.model_copy(update={"widgets": plan.widgets[:widget_count]})
    unknown_refs = {
        reference
        for widget in plan.widgets
        for reference in widget.semantic_refs
        if reference not in semantic_context.allowed_references
    }
    if unknown_refs:
        raise DashboardPlanningError(
            "Planner used semantic references that were not supplied.",
            code="invalid_dashboard_plan",
        )
    _stage("plan_ready", "Dashboard plan ready")
    return plan


__all__ = ["DashboardPlanningError", "plan_dashboard"]
