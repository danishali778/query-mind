"""Reusable analytical execution shared by chat and dashboard generation."""

from __future__ import annotations

import functools
import logging
from typing import Any

import anyio

from app.agents.db_agent.agent import run_agent
from app.agents.db_agent.trace import combine_failed_agent_trace
from app.agents.nl_to_sql.graph import run_chat
from app.agents.visualization.generator import generate_visualization_blueprint
from app.core.config import settings
from app.services import connection_service
from app.services import semantic_context_service
from app.services.schema_command_service import handle_schema_or_control_command

logger = logging.getLogger(__name__)


def _run_pipeline_sync(
    user_id: str,
    connection_id: str,
    session_id: str,
    message: str,
    schema_context: str,
    history: list[dict],
    progress=None,
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

    if settings.agent_mode == "tools":
        try:
            if progress:
                progress.stage_started("schema_search", "Searching the database schema")
            if allow_schema_shortcuts:
                control_result = handle_schema_or_control_command(message, None)
                if control_result:
                    return _normalize_requested_visualization(
                        {**control_result, "assumptions": []},
                        requested_visualization=requested_visualization,
                    )

            catalog = await connection_service.get_catalog(user_id, connection_id)
            if progress:
                progress.stage_completed("schema_search", "Schema context ready")
            if allow_schema_shortcuts:
                schema_result = handle_schema_or_control_command(message, catalog)
                if schema_result:
                    return _normalize_requested_visualization(
                        {**schema_result, "assumptions": []},
                        requested_visualization=requested_visualization,
                    )

            engine = await connection_service.get_engine(user_id, connection_id)
            if catalog and engine:
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
                        )
                    )
                except Exception:
                    logger.exception("Agent path raised; falling back to pipeline")
                    agent_error = "agent_exception"
                else:
                    if agent_out.get("success"):
                        try:
                            if agent_out.get("columns") and agent_out.get("rows"):
                                if progress:
                                    progress.stage_started("visualization", "Selecting the best visualization")
                                chart = await anyio.to_thread.run_sync(
                                    functools.partial(
                                        generate_visualization_blueprint,
                                        user_message=message,
                                        sql=agent_out.get("sql") or "",
                                        preview_rows=agent_out.get("rows", [])[:5],
                                        column_metadata=agent_out.get("column_metadata", {}),
                                    )
                                )
                                agent_out["chart_recommendation"] = chart
                                if progress:
                                    progress.stage_completed("visualization", "Visualization ready")
                        except Exception:
                            logger.warning("Visualization generation failed after agent success", exc_info=True)
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
                            },
                            requested_visualization=requested_visualization,
                        )
                    failed_agent_trace = agent_out.get("trace", []) or []
                    fallback_reason = agent_out.get("fallback_reason") or "agent_failed"
                    if progress and hasattr(progress, "fallback"):
                        progress.fallback(fallback_reason)
            else:
                fallback_reason = "missing_catalog_or_engine"
        except Exception:
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
        )
    )
    tier = "fallback" if settings.agent_mode == "tools" else "pipeline"
    pipeline_result["tier"] = tier
    pipeline_result["assumptions"] = []
    if settings.agent_mode == "tools" and (failed_agent_trace or agent_error or fallback_reason):
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
