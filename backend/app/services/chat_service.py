"""Chat workflows."""

import functools
import logging

import anyio

from app.agents.db_agent.agent import run_agent
from app.agents.db_agent.trace import combine_failed_agent_trace
from app.agents.nl_to_sql.graph import run_chat
from app.agents.visualization.generator import generate_visualization_blueprint
from app.core.config import settings
from app.db.models.chat import ChatMessage, SessionSummary
from app.db.repositories.chat_repository import (
    add_message,
    create_session,
    delete_session,
    get_history_for_llm,
    get_latest_user_message_id,
    get_message,
    get_session,
    list_sessions,
    reconstruct_dual_chain,
    rename_session,
    track_connection,
    update_message,
)
from app.services import connection_service, query_execution_service
from app.services.schema_command_service import handle_schema_or_control_command


logger = logging.getLogger(__name__)


class ChatEditNotFoundError(ValueError):
    pass


class ChatEditValidationError(ValueError):
    pass


class ChatPersistenceError(RuntimeError):
    pass


def _sanitize_chart_recommendation(chart_rec: dict | None) -> dict | None:
    if chart_rec and isinstance(chart_rec, dict):
        if chart_rec.get("y_columns") is None:
            chart_rec["y_columns"] = []
        if chart_rec.get("tooltip_columns") is None:
            chart_rec["tooltip_columns"] = []
    return chart_rec


def _run_pipeline_sync(
    user_id: str,
    connection_id: str,
    session_id: str,
    message: str,
    schema_context: str,
    history: list[dict],
) -> dict:
    result = run_chat(
        user_id=user_id,
        connection_id=connection_id,
        session_id=session_id,
        user_message=message,
        schema_context=schema_context,
        history=history,
        readonly=True,
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
) -> dict:
    from app.agents.schema_context.catalog import build_catalog
    from app.db.repositories import schema_snapshot_repository
    from app.query_engine import schema_inspector
    import app.query_engine.connection_pool as connection_pool

    def invalidate_sync() -> None:
        connection_pool.invalidate_schema_cache(user_id, connection_id)
        schema_snapshot_repository.delete(user_id, connection_id)

    def rebuild_sync():
        # Runs on the agent worker thread; re-introspect live and rebuild the catalog
        # so the agent can recover from schema drift within the same run.
        try:
            schema = schema_inspector.get_schema(engine)
            rebuilt = build_catalog(connection_id, catalog.db_type, schema)
            schema_snapshot_repository.upsert(rebuilt, user_id)
            connection_pool.cache_catalog(user_id, connection_id, rebuilt)
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
    )
    return agent_result.as_chat_dict()


async def _load_pipeline_schema_context(user_id: str, connection_id: str) -> str:
    schema_context = await connection_service.get_schema_for_ai(user_id, connection_id)
    return schema_context or "No schema available. Please connect to a database first."


async def _execute_chat_turn(
    user_id: str,
    connection_id: str,
    session_id: str,
    message: str,
    schema_context: str | None,
    history: list[dict],
) -> dict:
    failed_agent_trace: list = []
    fallback_reason: str | None = None
    agent_error: str | None = None

    if settings.agent_mode == "tools":
        try:
            control_result = handle_schema_or_control_command(message, None)
            if control_result:
                return control_result

            catalog = await connection_service.get_catalog(user_id, connection_id)
            schema_result = handle_schema_or_control_command(message, catalog)
            if schema_result:
                return schema_result

            engine = await connection_service.get_engine(user_id, connection_id)
            if catalog and engine:
                logger.info(
                    "[chat] agent path start connection=%s message=%r",
                    connection_id,
                    message[:120],
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
                        )
                    )
                except Exception:
                    logger.exception("Agent path raised; falling back to pipeline")
                    agent_error = "agent_exception"
                else:
                    if agent_out.get("success"):
                        try:
                            if agent_out.get("columns") and agent_out.get("rows"):
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
                        except Exception:
                            logger.warning("Visualization generation failed after agent success", exc_info=True)
                        logger.info(
                            "chat agent tier=%s tool_calls=%s wall_ms=%s",
                            agent_out.get("tier"),
                            agent_out.get("tool_calls"),
                            agent_out.get("wall_ms"),
                        )
                        return {
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
                        }
                    failed_agent_trace = agent_out.get("trace", []) or []
                    fallback_reason = agent_out.get("fallback_reason") or "agent_failed"
                    logger.warning(
                        "Agent run failed (%s); falling back to pipeline",
                        fallback_reason,
                    )
            else:
                logger.warning("[chat] agent path skipped: missing catalog or engine")
                fallback_reason = "missing_catalog_or_engine"
        except Exception:
            logger.exception("Agent path raised; falling back to pipeline")
            agent_error = "agent_exception"

    if schema_context is None:
        schema_context = await _load_pipeline_schema_context(user_id, connection_id)

    pipeline_result = await anyio.to_thread.run_sync(
        functools.partial(
            _run_pipeline_sync,
            user_id,
            connection_id,
            session_id,
            message,
            schema_context,
            history,
        )
    )
    tier = "fallback" if settings.agent_mode == "tools" else "pipeline"
    pipeline_result["tier"] = tier
    if settings.agent_mode == "tools" and (failed_agent_trace or agent_error or fallback_reason):
        pipeline_result["trace"] = combine_failed_agent_trace(
            failed_agent_trace,
            fallback_reason,
            agent_error,
        )
    return pipeline_result


async def send_message(
    user_id: str,
    connection_id: str,
    message: str,
    session_id: str | None = None,
) -> dict:
    engine = await connection_service.get_engine(user_id, connection_id)
    if not engine:
        raise ValueError("Database connection not found. Connect first.")

    schema_context: str | None = None
    if settings.agent_mode != "tools":
        schema_context = await connection_service.get_schema_for_ai(user_id, connection_id)
        if not schema_context:
            schema_context = "No schema available. Please connect to a database first."

    is_new_session = False
    try:
        if not session_id:
            session = await create_session(user_id, connection_id)
            session_id = session.id
            is_new_session = True
        else:
            session = await get_session(user_id, session_id)
            if not session:
                raise ValueError("Session not found.")
    except ValueError:
        raise
    except Exception as exc:
        logger.exception("Failed to load or create chat session %s", session_id)
        raise ChatPersistenceError("Unable to persist chat state for this request.") from exc

    await track_connection(user_id, session_id, connection_id)

    if is_new_session:
        title = message[:50].strip()
        if len(message) > 50:
            title += "..."
        try:
            await rename_session(user_id, session_id, title)
        except Exception:
            logger.warning("Failed to rename new chat session %s", session_id, exc_info=True)

    try:
        prev_query_id = await get_latest_user_message_id(user_id, session_id) if session_id else None
    except Exception as exc:
        logger.exception("Failed to load latest user message for session %s", session_id)
        raise ChatPersistenceError("Unable to persist chat state for this request.") from exc

    user_msg = ChatMessage(
        role="user",
        content=message,
        connection_id=connection_id,
        prev_query_id=prev_query_id,
    )
    try:
        await add_message(user_id, session_id, user_msg)
    except Exception as exc:
        logger.exception("Failed to persist user chat message %s", user_msg.id)
        raise ChatPersistenceError("Unable to persist chat state for this request.") from exc

    try:
        history = await get_history_for_llm(user_id, session_id)
    except Exception as exc:
        logger.exception("Failed to load LLM history for session %s", session_id)
        raise ChatPersistenceError("Unable to persist chat state for this request.") from exc

    result = await _execute_chat_turn(
        user_id=user_id,
        connection_id=connection_id,
        session_id=session_id,
        message=message,
        schema_context=schema_context,
        history=history,
    )

    assistant_msg_id = ""
    assistant_msg = ChatMessage(
        role="assistant",
        content=result.get("explanation", ""),
        connection_id=connection_id,
        sql=result.get("sql"),
        results={
            "rows": result.get("rows", []),
            "row_count": result.get("row_count", 0),
            "execution_time_ms": result.get("execution_time_ms", 0.0),
            "truncated": result.get("truncated", False),
        },
        columns=result.get("columns", []),
        truncated=result.get("truncated", False),
        chart_recommendation=result.get("chart_recommendation"),
        error=result.get("error"),
        parent_id=user_msg.id,
        agent_trace=result.get("trace"),
        agent_tier=result.get("tier"),
    )
    assistant_msg_id = assistant_msg.id
    try:
        await add_message(user_id, session_id, assistant_msg)
    except Exception as exc:
        logger.exception("Failed to persist assistant chat message %s", assistant_msg.id)
        raise ChatPersistenceError("Unable to persist chat state for this request.") from exc

    chart_rec = _sanitize_chart_recommendation(result.get("chart_recommendation"))
    error = result.get("error", "")
    return {
        "session_id": session_id,
        "message_id": assistant_msg_id,
        "user_message_id": user_msg.id,
        "message": result.get("explanation", ""),
        "sql": result.get("sql"),
        "columns": result.get("columns", []),
        "rows": result.get("rows", []),
        "row_count": result.get("row_count", 0),
        "truncated": result.get("truncated", False),
        "execution_time_ms": result.get("execution_time_ms", 0.0),
        "chart_recommendation": chart_rec,
        "error": error if error else None,
        "column_metadata": result.get("column_metadata", {}),
        "is_pinned": False,
        "prev_query_id": prev_query_id,
        "agent_trace": result.get("trace"),
        "agent_tier": result.get("tier"),
    }


async def create_session_summary(user_id: str, connection_id: str | None = None) -> SessionSummary:
    if connection_id:
        engine = await connection_service.get_engine(user_id, connection_id)
        if not engine:
            raise ValueError("Database connection not found.")

    session = await create_session(user_id, connection_id)
    return SessionSummary(
        id=session.id,
        owner_id=session.owner_id,
        connection_ids=session.connection_ids,
        last_connection_id=session.last_connection_id,
        title=session.title,
        message_count=0,
        created_at=session.created_at,
    )


async def update_session_summary(user_id: str, session_id: str, title: str | None = None) -> SessionSummary:
    session = await get_session(user_id, session_id)
    if not session:
        raise ValueError("Session not found.")

    if title is not None:
        await rename_session(user_id, session_id, title)

    session = await get_session(user_id, session_id)
    if not session:
        raise ValueError("Session not found after update.")

    return SessionSummary(
        id=session.id,
        owner_id=session.owner_id,
        connection_ids=session.connection_ids,
        last_connection_id=session.last_connection_id,
        title=session.title,
        message_count=len(session.messages),
        created_at=session.created_at,
    )


async def get_session_messages_response(user_id: str, session_id: str) -> dict:
    session = await get_session(user_id, session_id)
    if not session:
        raise ValueError("Session not found.")

    return {
        "session_id": session_id,
        "owner_id": user_id,
        "connection_ids": session.connection_ids,
        "last_connection_id": session.last_connection_id,
        "messages": session.messages,
    }


async def edit_message_sql(
    user_id: str,
    session_id: str,
    message_id: str,
    sql: str,
    connection_id: str,
) -> ChatMessage:
    session = await get_session(user_id, session_id)
    if not session:
        raise ChatEditNotFoundError("Session not found.")

    message = await get_message(user_id, session_id, message_id)
    if not message:
        raise ChatEditNotFoundError("Message not found.")
    if message.role != "assistant":
        raise ChatEditValidationError("Only assistant SQL messages can be edited.")
    if not message.sql:
        raise ChatEditValidationError("This message does not contain editable SQL.")

    engine = await connection_service.get_engine(user_id, connection_id)
    if not engine:
        raise ChatEditNotFoundError("Database connection not found.")

    result = await query_execution_service.execute_for_connection(
        user_id=user_id,
        connection_id=connection_id,
        sql=sql,
        row_limit=500,
    )

    history = await get_history_for_llm(user_id, session_id)
    user_msg_context = "Custom SQL query"
    for history_message in history:
        if history_message["role"] == "user":
            user_msg_context = history_message["content"]

    new_viz = None
    if result.success and result.rows:
        new_viz = await anyio.to_thread.run_sync(
            functools.partial(
                generate_visualization_blueprint,
                user_message=user_msg_context,
                sql=sql,
                preview_rows=result.rows[:5],
                column_metadata={},
                is_edited=True,
            )
        )

    updates = {
        "sql": sql,
        "results": {
            "rows": result.rows,
            "row_count": result.row_count,
            "execution_time_ms": result.execution_time_ms,
            "truncated": result.truncated,
        },
        "columns": result.columns,
        "truncated": result.truncated,
    }
    if new_viz is not None:
        updates["chart_recommendation"] = new_viz
    if result.error:
        updates["error"] = result.error

    updated = await update_message(user_id, session_id, message_id, updates)
    if not updated:
        raise ChatPersistenceError("Edited SQL executed, but the chat message could not be updated.")

    return ChatMessage(
        id=message_id,
        role="assistant",
        content="SQL Updated & Re-run",
        sql=sql,
        results={
            "rows": result.rows,
            "row_count": result.row_count,
            "execution_time_ms": result.execution_time_ms,
            "truncated": result.truncated,
        },
        columns=result.columns,
        truncated=result.truncated,
        chart_recommendation=new_viz,
        error=result.error,
        connection_id=connection_id,
    )

async def toggle_pin_status(
    user_id: str,
    session_id: str,
    message_id: str,
    is_pinned: bool,
) -> bool:
    return await update_message(
        user_id,
        session_id,
        message_id,
        {"is_pinned": is_pinned},
    )


__all__ = [
    "send_message",
    "create_session_summary",
    "update_session_summary",
    "get_session_messages_response",
    "edit_message_sql",
    "ChatEditNotFoundError",
    "ChatEditValidationError",
    "ChatPersistenceError",
    "toggle_pin_status",
    "create_session",
    "get_session",
    "get_message",
    "delete_session",
    "list_sessions",
    "rename_session",
    "track_connection",
    "add_message",
    "update_message",
    "get_history_for_llm",
    "get_latest_user_message_id",
    "reconstruct_dual_chain",
]
