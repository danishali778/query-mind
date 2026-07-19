"""Chat workflows."""

import functools
import logging

import anyio

from app.agents.visualization.generator import generate_visualization_blueprint
from app.db.models.chat import ChatMessage, SessionSummary
from app.db.models.llm import LlmExecutionContext
from app.db.repositories.chat_repository import (
    add_message,
    create_session,
    delete_session,
    get_history_for_llm,
    get_latest_user_message_id,
    get_message,
    get_session,
    list_sessions,
    record_user_turn,
    reconstruct_dual_chain,
    rename_session,
    track_connection,
    update_message,
)
from app.services import analysis_service, connection_service, query_execution_service
from app.services.chat_intent_orchestrator import prepare_chat_intent


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


async def _execute_chat_turn(
    user_id: str,
    connection_id: str,
    session_id: str,
    message: str,
    schema_context: str | None,
    history: list[dict],
    prior_results: dict | None = None,
    conversation_memory: dict | None = None,
    progress=None,
    llm_workflow_id: str | None = None,
    intent_result=None,
) -> dict:
    return await analysis_service.run_analysis(
        user_id=user_id,
        connection_id=connection_id,
        question=message,
        history=history,
        prior_results=prior_results,
        conversation_memory=conversation_memory,
        progress=progress,
        session_id=session_id,
        schema_context=schema_context,
        allow_schema_shortcuts=True,
        llm_context=LlmExecutionContext(
            owner_id=user_id,
            feature="chat",
            workflow_type="chat_run" if llm_workflow_id else "chat_session",
            workflow_id=llm_workflow_id or session_id,
            interaction_type="explicit",
        ),
        intent_result=intent_result,
        decision_agent=True,
    )


async def send_message(
    user_id: str,
    connection_id: str,
    message: str,
    session_id: str | None = None,
) -> dict:
    prepared = await prepare_chat_intent(
        user_id=user_id,
        connection_id=connection_id,
        message=message,
        session_id=session_id,
    )
    schema_context: str | None = None

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

    if is_new_session:
        title = message[:50].strip()
        if len(message) > 50:
            title += "..."
        try:
            await rename_session(user_id, session_id, title)
        except Exception:
            logger.warning("Failed to rename new chat session %s", session_id, exc_info=True)

    # Track the active connection, resolve prev_query_id, persist the user
    # message, and load LLM history in one atomic transaction/session.
    try:
        user_msg, prev_query_id, _history = await record_user_turn(
            user_id, session_id, connection_id, message
        )
    except Exception as exc:
        logger.exception("Failed to persist chat turn for session %s", session_id)
        raise ChatPersistenceError("Unable to persist chat state for this request.") from exc

    result = await _execute_chat_turn(
        user_id=user_id,
        connection_id=connection_id,
        session_id=session_id,
        message=message,
        schema_context=schema_context,
        history=prepared.history,
        prior_results=getattr(prepared, "prior_results", {}),
        conversation_memory=getattr(prepared, "conversation_memory", {}),
        progress=None,
        intent_result=prepared.intent,
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
            "column_metadata": result.get("column_metadata", {}),
        },
        columns=result.get("columns", []),
        truncated=result.get("truncated", False),
        chart_recommendation=result.get("chart_recommendation"),
        error=result.get("error"),
        parent_id=user_msg.id,
        agent_trace=result.get("trace"),
        agent_tier=result.get("tier"),
        semantic_lineage=result.get("semantic_lineage", []),
        response_kind=result.get("response_kind", "answer"),
        clarification_context=result.get("clarification_context"),
        presentation_kind=result.get("presentation_kind"),
        answer_metadata=result.get("answer_metadata"),
    )
    assistant_msg_id = assistant_msg.id
    try:
        memory_update = result.get("memory_update")
        if memory_update is None:
            await add_message(user_id, session_id, assistant_msg)
        else:
            await add_message(
                user_id,
                session_id,
                assistant_msg,
                memory_update=memory_update,
            )
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
        "semantic_lineage": result.get("semantic_lineage", []),
        "response_kind": result.get("response_kind", "answer"),
        "clarification_context": result.get("clarification_context"),
        "presentation_kind": result.get("presentation_kind"),
        "answer_metadata": result.get("answer_metadata"),
    }


async def execute_prepared_turn(
    *,
    user_id: str,
    connection_id: str,
    session_id: str,
    message: str,
    history: list[dict] | None,
    progress,
    run_id: str | None = None,
) -> dict:
    """Execute an already-persisted durable turn without creating messages."""
    progress.check_cancelled()
    prepared = await prepare_chat_intent(
        user_id=user_id,
        connection_id=connection_id,
        message=message,
        session_id=session_id,
    )
    engine = await connection_service.get_engine(user_id, connection_id)
    if not engine:
        raise ValueError("Database connection not found. Connect first.")
    schema_context: str | None = None
    return await _execute_chat_turn(
        user_id=user_id,
        connection_id=connection_id,
        session_id=session_id,
        message=message,
        schema_context=schema_context,
        history=prepared.history,
        prior_results=getattr(prepared, "prior_results", {}),
        conversation_memory=getattr(prepared, "conversation_memory", {}),
        progress=progress,
        llm_workflow_id=run_id,
        intent_result=prepared.intent,
    )


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
                llm_context=LlmExecutionContext(
                    owner_id=user_id,
                    feature="chat_visualization",
                    workflow_type="chat_session",
                    workflow_id=session_id,
                    interaction_type="explicit",
                ),
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
    "execute_prepared_turn",
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
