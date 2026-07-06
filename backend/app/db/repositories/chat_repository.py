import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from app.db.models.chat import ChatMessage, ChatSession, SessionSummary
from app.db.orm_models import ChatMessageORM, ChatSessionORM
from app.db.session import session_scope


logger = logging.getLogger(__name__)


def _iso(value) -> str:
    if value is None:
        return datetime.now().isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _map_message(row: ChatMessageORM) -> ChatMessage:
    return ChatMessage(
        id=row.id,
        role=row.role,
        content=row.content,
        connection_id=row.connection_id,
        sql=row.sql,
        results=row.results,
        columns=row.columns or [],
        truncated=bool((row.results or {}).get("truncated", False)),
        chart_recommendation=row.chart_recommendation,
        is_pinned=bool(row.is_pinned),
        error=row.error,
        parent_id=row.parent_id,
        prev_query_id=row.prev_query_id,
        agent_trace=row.agent_trace if isinstance(row.agent_trace, list) else None,
        agent_tier=row.agent_tier,
        created_at=_iso(row.created_at),
    )


def _map_session(row: ChatSessionORM, messages: list[ChatMessage] | None = None) -> ChatSession:
    return ChatSession(
        id=row.id,
        owner_id=row.owner_id,
        connection_ids=row.connection_ids or [],
        last_connection_id=row.last_connection_id,
        title=row.title,
        messages=messages or [],
        created_at=_iso(row.created_at),
    )


async def create_session(user_id: str, connection_id: str | None = None) -> ChatSession:
    session_id = str(uuid.uuid4())
    with session_scope() as db:
        row = ChatSessionORM(
            id=session_id,
            owner_id=user_id,
            connection_ids=[connection_id] if connection_id else [],
            last_connection_id=connection_id,
            title="New Chat",
        )
        db.add(row)
        db.flush()
        return _map_session(row)


async def get_session(user_id: str, session_id: str) -> Optional[ChatSession]:
    with session_scope() as db:
        row = (
            db.query(ChatSessionORM)
            .filter(ChatSessionORM.id == session_id, ChatSessionORM.owner_id == user_id)
            .one_or_none()
        )
        if not row:
            return None
        message_rows = (
            db.query(ChatMessageORM)
            .filter(ChatMessageORM.session_id == session_id, ChatMessageORM.owner_id == user_id)
            .order_by(ChatMessageORM.created_at.asc())
            .all()
        )
        messages = [_map_message(message_row) for message_row in message_rows]
        return _map_session(row, reconstruct_dual_chain(messages))

async def get_message(user_id: str, session_id: str, message_id: str) -> Optional[ChatMessage]:
    with session_scope() as db:
        row = (
            db.query(ChatMessageORM)
            .filter(
                ChatMessageORM.id == message_id,
                ChatMessageORM.session_id == session_id,
                ChatMessageORM.owner_id == user_id,
            )
            .one_or_none()
        )
        return _map_message(row) if row else None

async def delete_session(user_id: str, session_id: str) -> bool:
    with session_scope() as db:
        row = (
            db.query(ChatSessionORM)
            .filter(ChatSessionORM.id == session_id, ChatSessionORM.owner_id == user_id)
            .one_or_none()
        )
        if not row:
            return False
        db.delete(row)
        return True


async def list_sessions(user_id: str) -> list[SessionSummary]:
    with session_scope() as db:
        rows = (
            db.query(ChatSessionORM)
            .filter(ChatSessionORM.owner_id == user_id)
            .order_by(ChatSessionORM.created_at.desc())
            .all()
        )
        summaries: list[SessionSummary] = []
        for row in rows:
            msg_count = (
                db.query(ChatMessageORM)
                .filter(ChatMessageORM.session_id == row.id, ChatMessageORM.owner_id == user_id)
                .count()
            )
            summaries.append(
                SessionSummary(
                    id=row.id,
                    owner_id=row.owner_id,
                    connection_ids=row.connection_ids or [],
                    last_connection_id=row.last_connection_id,
                    title=row.title,
                    message_count=msg_count,
                    created_at=_iso(row.created_at),
                )
            )
        return summaries


async def track_connection(user_id: str, session_id: str, connection_id: str | None) -> None:
    if not connection_id:
        return
    try:
        with session_scope() as db:
            row = (
                db.query(ChatSessionORM)
                .filter(ChatSessionORM.id == session_id, ChatSessionORM.owner_id == user_id)
                .one_or_none()
            )
            if not row:
                return
            conn_ids = list(row.connection_ids or [])
            if connection_id not in conn_ids:
                conn_ids.append(connection_id)
            row.connection_ids = conn_ids
            row.last_connection_id = connection_id
    except Exception as exc:
        logger.warning("Error tracking connection for session %s: %s", session_id, exc)


async def rename_session(user_id: str, session_id: str, title: str) -> bool:
    with session_scope() as db:
        row = (
            db.query(ChatSessionORM)
            .filter(ChatSessionORM.id == session_id, ChatSessionORM.owner_id == user_id)
            .one_or_none()
        )
        if not row:
            return False
        row.title = title
        return True

async def add_message(user_id: str, session_id: str, message: ChatMessage) -> None:
    with session_scope() as db:
        row = ChatMessageORM(
            id=message.id,
            session_id=session_id,
            owner_id=user_id,
            role=message.role,
            content=message.content,
            connection_id=message.connection_id,
            sql=message.sql,
            results=message.results,
            columns=message.columns or [],
            chart_recommendation=message.chart_recommendation,
            is_pinned=message.is_pinned,
            error=message.error,
            parent_id=message.parent_id,
            prev_query_id=message.prev_query_id,
            agent_trace=message.agent_trace,
            agent_tier=message.agent_tier,
        )
        db.add(row)

async def update_message(user_id: str, session_id: str, message_id: str, updates: dict) -> bool:
    with session_scope() as db:
        row = (
            db.query(ChatMessageORM)
            .filter(
                ChatMessageORM.id == message_id,
                ChatMessageORM.session_id == session_id,
                ChatMessageORM.owner_id == user_id,
            )
            .one_or_none()
        )
        if not row:
            return False
        clean_updates = {key: value for key, value in updates.items() if value is not None}
        for key, value in clean_updates.items():
            if hasattr(row, key):
                setattr(row, key, value)
        return True

async def get_history_for_llm(user_id: str, session_id: str) -> list[dict]:
    with session_scope() as db:
        rows = (
            db.query(ChatMessageORM)
            .filter(ChatMessageORM.session_id == session_id, ChatMessageORM.owner_id == user_id)
            .order_by(ChatMessageORM.created_at.asc())
            .all()
        )
        history: list[dict] = []
        for row in rows:
            content = row.content
            if row.role == "assistant" and row.sql:
                content = f"{content}\n```sql\n{row.sql}\n```"
            history.append({"role": row.role, "content": content})
        return history

async def get_latest_user_message_id(user_id: str, session_id: str) -> Optional[str]:
    with session_scope() as db:
        row = (
            db.query(ChatMessageORM.id)
            .filter(
                ChatMessageORM.session_id == session_id,
                ChatMessageORM.owner_id == user_id,
                ChatMessageORM.role == "user",
            )
            .order_by(ChatMessageORM.created_at.desc())
            .first()
        )
        return row.id if row else None

def reconstruct_dual_chain(messages: list[ChatMessage]) -> list[ChatMessage]:
    """Reconstruct conversation order using prev_query_id and parent_id links."""
    if not messages:
        return []

    user_msgs_by_prev: dict[str | None, ChatMessage] = {}
    assistant_msgs_by_parent: dict[str | None, list[ChatMessage]] = {}

    for msg in messages:
        if msg.role == "user":
            user_msgs_by_prev[msg.prev_query_id] = msg
        elif msg.role == "assistant":
            assistant_msgs_by_parent.setdefault(msg.parent_id, []).append(msg)

    chain: list[ChatMessage] = []
    current_user_msg = user_msgs_by_prev.get(None)
    while current_user_msg:
        chain.append(current_user_msg)
        responses = assistant_msgs_by_parent.get(current_user_msg.id, [])
        responses.sort(key=lambda item: item.created_at)
        chain.extend(responses)
        current_user_msg = user_msgs_by_prev.get(current_user_msg.id)

    if not chain and messages:
        return sorted(messages, key=lambda item: item.created_at)

    if len(chain) < len(messages):
        chain_ids = {msg.id for msg in chain}
        orphans = [msg for msg in messages if msg.id not in chain_ids]
        chain.extend(sorted(orphans, key=lambda item: item.created_at))

    return chain


__all__ = [
    "create_session",
    "get_session",
    "get_message",
    "delete_session",
    "list_sessions",
    "track_connection",
    "rename_session",
    "add_message",
    "update_message",
    "get_history_for_llm",
    "get_latest_user_message_id",
    "reconstruct_dual_chain",
]