"""Reusable analytical execution shared by chat and dashboard generation."""

from __future__ import annotations

import functools
import logging
from typing import Any

import anyio

from app.agents.db_agent.agent import infer_chart_from_result, run_agent
from app.agents.db_agent.trace import combine_failed_agent_trace
from app.agents.nl_to_sql.graph import run_chat
from app.core.config import settings
from app.core.errors import AppError
from app.core import chat_guard_metrics
from app.db.models.llm import LlmExecutionContext
from app.services import connection_service
from app.services import semantic_context_service
from app.services.schema_command_service import handle_schema_or_control_command

logger = logging.getLogger(__name__)

_NON_FALLBACK_LLM_ERRORS = {
    "llm_credential_required",
    "llm_credential_invalid",
    "llm_provider_permission_denied",
    "llm_provider_rate_limited",
    "llm_provider_unavailable",
    "llm_background_usage_disabled",
    "deployment_llm_unavailable",
    "deployment_llm_trial_exhausted",
}
_EMERGENCY_FALLBACK_REASONS = {
    "agent_exception",
    "agent_outcome_invalid",
    "no_valid_proposal",
    "tool_use_failed",
}


def _raise_if_llm_access_error(exc: Exception) -> None:
    if isinstance(exc, AppError) and exc.code in _NON_FALLBACK_LLM_ERRORS:
        raise exc


def _run_pipeline_sync(
    user_id: str,
    connection_id: str,
    session_id: str,
    message: str,
    schema_context: str,
    history: list[dict],
    progress=None,
    llm_context: LlmExecutionContext | None = None,
    intent_result=None,
    decision_agent: bool = False,
) -> dict:
    result = run_chat(
        user_id=user_id,
        connection_id=connection_id,
        session_id=session_id,
        user_message=message,
        schema_context=schema_context,
        history=history,
        readonly=True,
        cancellation_token=getattr(progress, "cancellation_token", None),
        progress=progress,
        llm_context=llm_context,
        grounded_tables=list(getattr(intent_result, "matched_tables", []) or []),
        enforce_grounding=intent_result is not None,
        broad_discovery=bool(getattr(intent_result, "broad_discovery", False)),
        select_visualization=not decision_agent,
    )
    result["tier"] = "pipeline"
    result["trace"] = []
    result["tool_calls"] = 0
    result["wall_ms"] = 0.0
    return result


def _run_agent_sync(
    user_id: str,
    connection_id: str,
    message: str,
    history: list[dict],
    catalog,
    engine,
    progress=None,
    semantic_context=None,
    llm_context: LlmExecutionContext | None = None,
    intent_result=None,
) -> dict:
    from app.agents.schema_context.catalog import build_catalog
    from app.db.repositories import schema_snapshot_repository
    from app.query_engine import schema_inspector
    import app.query_engine.connection_pool as connection_pool

    def invalidate_sync() -> None:
        connection_pool.invalidate_schema_cache(user_id, connection_id)
        schema_snapshot_repository.delete(user_id, connection_id)

    def rebuild_sync():
        try:
            schema = schema_inspector.get_schema(engine)
            rebuilt = build_catalog(connection_id, catalog.db_type, schema)
            schema_snapshot_repository.upsert(rebuilt, user_id)
            connection_pool.cache_catalog(user_id, connection_id, rebuilt)
            from app.services.semantic_drift_service import revalidate_sync

            revalidate_sync(user_id, connection_id, rebuilt)
            return rebuilt
        except Exception:
            logger.warning("Catalog rebuild after drift failed", exc_info=True)
            return None

    agent_result = run_agent(
        user_id=user_id,
        connection_id=connection_id,
        question=message,
        catalog=catalog,
        engine=engine,
        history=history,
        invalidate_catalog=invalidate_sync,
        rebuild_catalog=rebuild_sync,
        progress=progress,
        semantic_context=semantic_context,
        llm_context=llm_context,
        intent_result=intent_result,
    )
    return agent_result.as_chat_dict()


async def _load_pipeline_schema_context(user_id: str, connection_id: str) -> str:
    schema_context = await connection_service.get_schema_for_ai(user_id, connection_id)
    return schema_context or "No schema available. Please connect to a database first."


def _normalize_requested_visualization(
    result: dict[str, Any],
    *,
    requested_visualization: str | None,
) -> dict[str, Any]:
    assumptions = list(result.get("assumptions") or [])
    chart = result.get("chart_recommendation")
    if not requested_visualization or requested_visualization in {"auto", None}:
        result["assumptions"] = assumptions
        return result

    requested = requested_visualization.lower()
    chart_type = None
    if isinstance(chart, dict):
        chart_type = (chart.get("chart_type") or chart.get("type") or "").lower()

    if chart_type and chart_type != requested and requested not in {"table", "kpi"}:
        assumptions.append(
            f"Requested visualization '{requested}' was incompatible with the result shape; "
            f"used '{chart_type or 'auto'}' instead."
        )
    elif requested in {"table", "kpi"} and not chart_type:
        result["preferred_viz_type"] = requested
    elif requested and not chart:
        result["preferred_viz_type"] = requested
    result["assumptions"] = assumptions
    return result


async def run_analysis(
    *,
    user_id: str,
    connection_id: str,
    question: str,
    history: list[dict] | None = None,
    context_instructions: str | None = None,
    progress=None,
    session_id: str | None = None,
    schema_context: str | None = None,
    requested_visualization: str | None = None,
    allow_schema_shortcuts: bool = True,
    semantic_context=None,
    llm_context: LlmExecutionContext | None = None,
    intent_result=None,
    decision_agent: bool = False,
) -> dict[str, Any]:
    """Execute a business question through the shared agent/pipeline path.

    Returns explanation, SQL, rows, visualization recommendation, assumptions,
    trace, and error fields without persisting chat messages.
    """
    history = list(history or [])
    message = question.strip()
    if context_instructions and context_instructions.strip():
        message = f"{message}\n\nAdditional instructions: {context_instructions.strip()}"

    if progress:
        progress.check_cancelled()

    failed_agent_trace: list = []
    fallback_reason: str | None = None
    agent_error: str | None = None
    analysis_session_id = session_id or f"analysis-{connection_id}"
    llm_context = llm_context or LlmExecutionContext(
        owner_id=user_id,
        feature="analysis",
        workflow_type="chat_session",
        workflow_id=analysis_session_id,
        interaction_type="explicit",
    )

    use_tools = decision_agent or settings.agent_mode == "tools"
    if use_tools:
        try:
            if progress:
                progress.stage_started("schema_search", "Searching the database schema")
            if allow_schema_shortcuts and message.lstrip().startswith("/"):
                control_result = handle_schema_or_control_command(message, None)
                if control_result:
                    return _normalize_requested_visualization(
                        {**control_result, "assumptions": []},
                        requested_visualization=requested_visualization,
                    )

            catalog = await connection_service.get_catalog(user_id, connection_id)
            if progress:
                progress.stage_completed("schema_search", "Schema context ready")
            if allow_schema_shortcuts and message.lstrip().startswith("/"):
                schema_result = handle_schema_or_control_command(message, catalog)
                if schema_result:
                    return _normalize_requested_visualization(
                        {**schema_result, "assumptions": []},
                        requested_visualization=requested_visualization,
                    )

            engine = await connection_service.get_engine(user_id, connection_id)
            if catalog and engine:
                if semantic_context is None:
                    semantic_context = await semantic_context_service.load_context(
                        user_id, connection_id, catalog, message
                    )
                try:
                    agent_out = await anyio.to_thread.run_sync(
                        functools.partial(
                            _run_agent_sync,
                            user_id,
                            connection_id,
                            message,
                            history,
                            catalog,
                            engine,
                            progress,
                            semantic_context,
                            llm_context,
                            intent_result,
                        )
                    )
                except Exception as exc:
                    _raise_if_llm_access_error(exc)
                    logger.exception("Agent path raised; falling back to pipeline")
                    agent_error = "agent_exception"
                else:
                    if agent_out.get("success"):
                        return _normalize_requested_visualization(
                            {
                                "explanation": agent_out.get("explanation", ""),
                                "sql": agent_out.get("sql"),
                                "column_metadata": agent_out.get("column_metadata", {}),
                                "columns": agent_out.get("columns", []),
                                "rows": agent_out.get("rows", []),
                                "row_count": agent_out.get("row_count", 0),
                                "truncated": agent_out.get("truncated", False),
                                "execution_time_ms": agent_out.get("execution_time_ms", 0.0),
                                "chart_recommendation": agent_out.get("chart_recommendation"),
                                "error": agent_out.get("error"),
                                "trace": agent_out.get("trace", []),
                                "tier": agent_out.get("tier", "agent"),
                                "tool_calls": agent_out.get("tool_calls", 0),
                                "wall_ms": agent_out.get("wall_ms", 0.0),
                                "assumptions": [],
                                "semantic_lineage": agent_out.get("semantic_lineage", []),
                                "response_kind": agent_out.get("response_kind", "answer"),
                                "clarification_context": agent_out.get("clarification_context"),
                                "presentation_kind": agent_out.get("presentation_kind"),
                                "answer_metadata": agent_out.get("answer_metadata"),
                            },
                            requested_visualization=requested_visualization,
                        )
                    failed_agent_trace = agent_out.get("trace", []) or []
                    fallback_reason = agent_out.get("fallback_reason") or "agent_failed"
                    if fallback_reason not in _EMERGENCY_FALLBACK_REASONS:
                        chat_guard_metrics.increment("schema_relevance_rejections")
                        chat_guard_metrics.increment("prevented_sql_executions")
                        return {
                            "explanation": "I couldn't safely complete that analysis. Please clarify the metric, table, or business outcome you want to examine.",
                            "sql": None,
                            "columns": [],
                            "rows": [],
                            "row_count": 0,
                            "truncated": False,
                            "execution_time_ms": 0.0,
                            "chart_recommendation": None,
                            "error": None,
                            "trace": failed_agent_trace,
                            "tier": "agent",
                            "response_kind": "clarification",
                            "clarification_context": {
                                "reason_code": fallback_reason,
                                "expected_input": "metric_table_or_outcome",
                            },
                            "presentation_kind": "none",
                            "answer_metadata": None,
                            "semantic_lineage": [],
                        }
                    if progress and hasattr(progress, "fallback"):
                        progress.fallback(fallback_reason)
            else:
                fallback_reason = "missing_catalog_or_engine"
        except Exception as exc:
            _raise_if_llm_access_error(exc)
            logger.exception("Agent path raised; falling back to pipeline")
            agent_error = "agent_exception"

    if schema_context is None:
        if progress:
            progress.stage_started("schema_search", "Loading schema context")
        schema_context = await _load_pipeline_schema_context(user_id, connection_id)
        if progress:
            progress.stage_completed("schema_search", "Schema context ready")

    pipeline_result = await anyio.to_thread.run_sync(
        functools.partial(
            _run_pipeline_sync,
            user_id,
            connection_id,
            analysis_session_id,
            message,
            schema_context,
            history,
            progress,
            llm_context,
            intent_result,
            decision_agent,
        )
    )
    if pipeline_result.get("relevance_rejected") and pipeline_result.get("error"):
        chat_guard_metrics.increment("schema_relevance_rejections")
        chat_guard_metrics.increment("prevented_sql_executions")
        return {
            "explanation": "I couldn't verify that the proposed analysis matched your request. Tell me which metric, table, or business outcome you want to analyze.",
            "sql": None,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "truncated": False,
            "execution_time_ms": 0.0,
            "chart_recommendation": None,
            "error": None,
            "trace": [],
            "tier": "pipeline",
            "response_kind": "clarification",
            "clarification_context": {
                "reason_code": "schema_relevance_rejected",
                "expected_input": "metric_table_or_outcome",
            },
            "semantic_lineage": [],
            "assumptions": [],
        }
    tier = "fallback" if use_tools else "pipeline"
    pipeline_result["tier"] = tier
    pipeline_result["assumptions"] = []
    if decision_agent:
        fallback_chart = infer_chart_from_result(
            list(pipeline_result.get("columns") or []),
            list(pipeline_result.get("rows") or []),
            dict(pipeline_result.get("column_metadata") or {}),
        )
        pipeline_result["chart_recommendation"] = fallback_chart
        pipeline_result["presentation_kind"] = (
            "kpi" if fallback_chart and fallback_chart.get("type") == "kpi"
            else "chart" if fallback_chart
            else "table" if pipeline_result.get("rows")
            else "none"
        )
        pipeline_result["answer_metadata"] = {
            "method": None,
            "limitations": ["The decision agent was unavailable, so detailed result interpretation was not completed."],
            "evidence": [],
        }
        pipeline_result["response_kind"] = "data_analysis" if pipeline_result.get("rows") else "answer"
        if pipeline_result.get("rows"):
            pipeline_result["explanation"] = (
                "The fallback read-only query completed. Review the verified result table; detailed "
                "agent interpretation was unavailable for this response."
            )
    if use_tools and (failed_agent_trace or agent_error or fallback_reason):
        pipeline_result["trace"] = combine_failed_agent_trace(
            failed_agent_trace,
            fallback_reason,
            agent_error,
        )
    return _normalize_requested_visualization(
        pipeline_result,
        requested_visualization=requested_visualization,
    )


__all__ = ["run_analysis"]
