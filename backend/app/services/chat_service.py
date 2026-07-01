"""Chat workflows."""

import functools

import anyio

from app.agents.nl_to_sql.graph import run_chat
from app.agents.visualization.generator import generate_visualization_blueprint
from app.db.models.chat import ChatMessage, SessionSummary
from app.db.repositories.chat_repository import (
    add_message,
    create_session,
    delete_session,
    get_history_for_llm,
    get_latest_user_message_id,
    get_session,
    list_sessions,
    reconstruct_dual_chain,
    rename_session,
    track_connection,
    update_message,
)
from app.services import connection_service, query_execution_service


def _sanitize_chart_recommendation(chart_rec: dict | None) -> dict | None:
    if chart_rec and isinstance(chart_rec, dict):
        if chart_rec.get("y_columns") is None:
            chart_rec["y_columns"] = []
        if chart_rec.get("tooltip_columns") is None:
            chart_rec["tooltip_columns"] = []
    return chart_rec


async def send_message(
    user_id: str,
    connection_id: str,
    message: str,
    session_id: str | None = None,
) -> dict:
    engine = await connection_service.get_engine(user_id, connection_id)
    if not engine:
        raise ValueError("Database connection not found. Connect first.")

    schema_context = await connection_service.get_schema_for_ai(user_id, connection_id)
    if not schema_context:
        schema_context = "No schema available. Please connect to a database first."

    is_new_session = False
    if not session_id:
        session = await create_session(user_id, connection_id)
        session_id = session.id
        is_new_session = True
    else:
        session = await get_session(user_id, session_id)
        if not session:
            raise ValueError("Session not found.")

    await track_connection(user_id, session_id, connection_id)

    if is_new_session:
        title = message[:50].strip()
        if len(message) > 50:
            title += "..."
        await rename_session(user_id, session_id, title)

    prev_query_id = await get_latest_user_message_id(user_id, session_id) if session_id else None
    user_msg = ChatMessage(
        role="user",
        content=message,
        connection_id=connection_id,
        prev_query_id=prev_query_id,
    )
    await add_message(user_id, session_id, user_msg)
    history = await get_history_for_llm(user_id, session_id)

    result = await anyio.to_thread.run_sync(
        functools.partial(
            run_chat,
            user_id=user_id,
            connection_id=connection_id,
            session_id=session_id,
            user_message=message,
            schema_context=schema_context,
            history=history,
            readonly=True,
        )
    )

    assistant_msg_id = ""
    assistant_msg = ChatMessage(
        role="assistant",
        content=result.get("explanation", ""),
        connection_id=connection_id,
        sql=result.get("sql"),
        results={"rows": result.get("rows", [])},
        columns=result.get("columns", []),
        chart_recommendation=result.get("chart_recommendation"),
        error=result.get("error"),
        parent_id=user_msg.id,
    )
    assistant_msg_id = assistant_msg.id
    await add_message(user_id, session_id, assistant_msg)

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
        "execution_time_ms": result.get("execution_time_ms", 0.0),
        "chart_recommendation": chart_rec,
        "error": error if error else None,
        "column_metadata": result.get("column_metadata", {}),
        "is_pinned": False,
        "prev_query_id": prev_query_id,
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
        "results": {"rows": result.rows},
        "columns": result.columns,
    }
    if new_viz is not None:
        updates["chart_recommendation"] = new_viz
    if result.error:
        updates["error"] = result.error

    await update_message(user_id, session_id, message_id, updates)

    return ChatMessage(
        id=message_id,
        role="assistant",
        content="SQL Updated & Re-run",
        sql=sql,
        results={"rows": result.rows},
        columns=result.columns,
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
    "toggle_pin_status",
    "create_session",
    "get_session",
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
