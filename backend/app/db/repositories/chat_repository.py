import logging
import uuid
from datetime import datetime
from typing import Optional

import anyio
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, aliased

from app.db.models.chat import ChatMessage, ChatSession, SessionSummary
from app.db.orm_models import ChatAgentRunORM, ChatMessageORM, ChatSessionORM
from app.db.session import read_session_scope, session_scope
from app.db.repositories import semantic_repository
from app.core.config import settings
from app.core.secret_detection import detect_secret


logger = logging.getLogger(__name__)


def _iso(value) -> str:
    if value is None:
        return datetime.now().isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _map_message(row: ChatMessageORM, run: ChatAgentRunORM | None = None) -> ChatMessage:
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
        agent_run_id=row.agent_run_id,
        agent_run_status=run.status if run else None,
        agent_run_stage=run.current_stage if run else None,
        agent_run_stage_label=run.current_stage_label if run else None,
        semantic_lineage=row.semantic_lineage or [],
        response_kind=row.response_kind or "answer",
        clarification_context=row.clarification_context,
        presentation_kind=row.presentation_kind,
        answer_metadata=row.answer_metadata,
        created_at=_iso(row.created_at),
    )


def _map_session(row: ChatSessionORM, messages: list[ChatMessage] | None = None) -> ChatSession:
    return ChatSession(
        id=row.id,
        owner_id=row.owner_id,
        connection_ids=row.connection_ids or [],
        last_connection_id=row.last_connection_id,
        title=row.title,
        memory_state=row.memory_state or {},
        memory_revision=row.memory_revision or 1,
        memory_updated_at=_iso(row.memory_updated_at) if row.memory_updated_at else None,
        messages=messages or [],
        created_at=_iso(row.created_at),
    )


async def create_session(user_id: str, connection_id: str | None = None) -> ChatSession:
    def _run() -> ChatSession:
        with session_scope() as session:
            return _create_session_sync(session, user_id, connection_id)
    return await anyio.to_thread.run_sync(_run)


def _create_session_sync(session: Session, user_id: str, connection_id: str | None = None) -> ChatSession:
    session_id = str(uuid.uuid4())
    row = ChatSessionORM(
        id=session_id,
        owner_id=user_id,
        connection_ids=[connection_id] if connection_id else [],
        last_connection_id=connection_id,
        title="New Chat",
    )
    session.add(row)
    session.flush()
    return _map_session(row)


def _record_semantic_message_usages(
    session: Session, user_id: str, message: ChatMessage
) -> None:
    if not message.connection_id or not message.semantic_lineage:
        return
    for usage_role in ("applied", "policy_enforced"):
        version_ids = [
            item.get("version_id")
            for item in message.semantic_lineage
            if item.get("usage_role", "applied") == usage_role and item.get("version_id")
        ]
        semantic_repository.record_usages_sync(
            session,
            owner_id=user_id,
            connection_id=message.connection_id,
            version_ids=version_ids,
            consumer_type="chat_message",
            consumer_id=message.id,
            usage_role=usage_role,
        )
async def get_session(user_id: str, session_id: str) -> Optional[ChatSession]:
    def _run() -> Optional[ChatSession]:
        with read_session_scope() as session:
            return _get_session_sync(session, user_id, session_id)
    return await anyio.to_thread.run_sync(_run)


def _get_session_sync(session: Session, user_id: str, session_id: str) -> Optional[ChatSession]:
    row = (
        session.query(ChatSessionORM)
        .filter(ChatSessionORM.id == session_id, ChatSessionORM.owner_id == user_id)
        .one_or_none()
    )
    if not row:
        return None
    message_rows = (
        session.query(ChatMessageORM)
        .filter(ChatMessageORM.session_id == session_id, ChatMessageORM.owner_id == user_id)
        .order_by(ChatMessageORM.created_at.asc())
        .all()
    )
    run_ids = [row.agent_run_id for row in message_rows if row.agent_run_id]
    run_rows = (
        session.query(ChatAgentRunORM).filter(ChatAgentRunORM.id.in_(run_ids)).all()
        if run_ids
        else []
    )
    runs = {row.id: row for row in run_rows}
    messages = [_map_message(message_row, runs.get(message_row.agent_run_id)) for message_row in message_rows]
    return _map_session(row, reconstruct_dual_chain(messages))


async def get_message(user_id: str, session_id: str, message_id: str) -> Optional[ChatMessage]:
    def _run() -> Optional[ChatMessage]:
        with read_session_scope() as session:
            return _get_message_sync(session, user_id, session_id, message_id)
    return await anyio.to_thread.run_sync(_run)


def _get_message_sync(session: Session, user_id: str, session_id: str, message_id: str) -> Optional[ChatMessage]:
    row = (
        session.query(ChatMessageORM)
        .filter(
            ChatMessageORM.id == message_id,
            ChatMessageORM.session_id == session_id,
            ChatMessageORM.owner_id == user_id,
        )
        .one_or_none()
    )
    return _map_message(row) if row else None


async def delete_session(user_id: str, session_id: str) -> bool:
    def _run() -> bool:
        with session_scope() as session:
            return _delete_session_sync(session, user_id, session_id)
    return await anyio.to_thread.run_sync(_run)


def _delete_session_sync(session: Session, user_id: str, session_id: str) -> bool:
    row = (
        session.query(ChatSessionORM)
        .filter(ChatSessionORM.id == session_id, ChatSessionORM.owner_id == user_id)
        .one_or_none()
    )
    if not row:
        return False
    session.delete(row)
    return True


async def list_sessions(user_id: str) -> list[SessionSummary]:
    def _run() -> list[SessionSummary]:
        with read_session_scope() as session:
            return _list_sessions_sync(session, user_id)
    return await anyio.to_thread.run_sync(_run)


def _list_sessions_sync(session: Session, user_id: str) -> list[SessionSummary]:
    rows = (
        session.query(ChatSessionORM, func.count(ChatMessageORM.id).label("message_count"))
        .outerjoin(
            ChatMessageORM,
            and_(
                ChatMessageORM.session_id == ChatSessionORM.id,
                ChatMessageORM.owner_id == user_id,
            ),
        )
        .filter(ChatSessionORM.owner_id == user_id)
        .group_by(ChatSessionORM.id)
        .order_by(ChatSessionORM.created_at.desc())
        .all()
    )
    return [
        SessionSummary(
            id=row.id,
            owner_id=row.owner_id,
            connection_ids=row.connection_ids or [],
            last_connection_id=row.last_connection_id,
            title=row.title,
            message_count=int(message_count or 0),
            created_at=_iso(row.created_at),
        )
        for row, message_count in rows
    ]


async def track_connection(user_id: str, session_id: str, connection_id: str | None) -> None:
    """Best-effort standalone connection tracking.

    The composite ``record_user_turn`` flow calls the strict sync helper
    directly so a tracking failure rolls back the entire user-turn write.
    """
    def _run() -> None:
        with session_scope() as session:
            _track_connection_sync(session, user_id, session_id, connection_id)
    try:
        await anyio.to_thread.run_sync(_run)
    except Exception as exc:
        logger.warning("Error tracking connection for session %s: %s", session_id, exc)


def _track_connection_sync(session: Session, user_id: str, session_id: str, connection_id: str | None) -> None:
    if not connection_id:
        return
    row = (
        session.query(ChatSessionORM)
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


async def rename_session(user_id: str, session_id: str, title: str) -> bool:
    def _run() -> bool:
        with session_scope() as session:
            return _rename_session_sync(session, user_id, session_id, title)
    return await anyio.to_thread.run_sync(_run)


def _rename_session_sync(session: Session, user_id: str, session_id: str, title: str) -> bool:
    row = (
        session.query(ChatSessionORM)
        .filter(ChatSessionORM.id == session_id, ChatSessionORM.owner_id == user_id)
        .one_or_none()
    )
    if not row:
        return False
    row.title = title
    return True


def _sanitize_memory_update(update: dict | None) -> dict | None:
    if not isinstance(update, dict):
        return None
    summary = str(update.get("summary") or "").strip()[
        : settings.agent_memory_summary_max_characters
    ]
    active_topic = str(update.get("active_topic") or "").strip()[:240] or None
    entities = [
        str(value).strip()[:160]
        for value in (update.get("entities") or [])[:30]
        if str(value).strip()
    ]
    unresolved = update.get("unresolved_choice")
    clean_unresolved = None
    if isinstance(unresolved, dict):
        prompt = str(unresolved.get("prompt") or "").strip()[:500]
        options = [
            str(value).strip()[:200]
            for value in (unresolved.get("options") or [])[:12]
            if str(value).strip()
        ]
        if prompt and options:
            clean_unresolved = {
                "kind": str(unresolved.get("kind") or "other")[:32],
                "prompt": prompt,
                "options": options,
            }
    sensitive_values = [summary, active_topic or "", *entities]
    if clean_unresolved:
        sensitive_values.extend(
            [clean_unresolved["prompt"], *clean_unresolved["options"]]
        )
    if any(detect_secret(value) for value in sensitive_values):
        return None
    return {
        "version": 1,
        "summary": summary,
        "active_topic": active_topic,
        "entities": list(dict.fromkeys(entities)),
        "unresolved_choice": clean_unresolved,
    }


def apply_conversation_memory_sync(
    session: Session,
    *,
    user_id: str,
    session_id: str,
    update: dict | None,
) -> bool:
    clean = _sanitize_memory_update(update)
    if clean is None:
        return False
    row = (
        session.query(ChatSessionORM)
        .filter(ChatSessionORM.id == session_id, ChatSessionORM.owner_id == user_id)
        .one_or_none()
    )
    if row is None:
        return False
    row.memory_state = clean
    row.memory_revision = int(row.memory_revision or 1) + 1
    row.memory_updated_at = datetime.now().astimezone()
    return True


async def get_conversation_memory(user_id: str, session_id: str) -> dict:
    def _run() -> dict:
        with read_session_scope() as session:
            row = (
                session.query(ChatSessionORM)
                .filter(
                    ChatSessionORM.id == session_id,
                    ChatSessionORM.owner_id == user_id,
                )
                .one_or_none()
            )
            if row is None:
                return {}
            return {
                "state": row.memory_state or {},
                "revision": int(row.memory_revision or 1),
                "updated_at": _iso(row.memory_updated_at) if row.memory_updated_at else None,
            }
    return await anyio.to_thread.run_sync(_run)


async def add_message(
    user_id: str,
    session_id: str,
    message: ChatMessage,
    *,
    memory_update: dict | None = None,
) -> None:
    def _run() -> None:
        with session_scope() as session:
            _add_message_sync(session, user_id, session_id, message)
            apply_conversation_memory_sync(
                session,
                user_id=user_id,
                session_id=session_id,
                update=memory_update,
            )
    await anyio.to_thread.run_sync(_run)


def _add_message_sync(session: Session, user_id: str, session_id: str, message: ChatMessage) -> None:
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
        agent_run_id=message.agent_run_id,
        semantic_lineage=message.semantic_lineage or [],
        response_kind=message.response_kind,
        clarification_context=message.clarification_context,
        presentation_kind=message.presentation_kind,
        answer_metadata=message.answer_metadata,
    )
    session.add(row)
    _record_semantic_message_usages(session, user_id, message)


async def update_message(user_id: str, session_id: str, message_id: str, updates: dict) -> bool:
    def _run() -> bool:
        with session_scope() as session:
            return _update_message_sync(session, user_id, session_id, message_id, updates)
    return await anyio.to_thread.run_sync(_run)


def _update_message_sync(
    session: Session, user_id: str, session_id: str, message_id: str, updates: dict
) -> bool:
    row = (
        session.query(ChatMessageORM)
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
    def _run() -> list[dict]:
        with read_session_scope() as session:
            return _get_history_for_llm_sync(session, user_id, session_id)
    return await anyio.to_thread.run_sync(_run)


def _get_history_for_llm_sync(session: Session, user_id: str, session_id: str) -> list[dict]:
    rows = (
        session.query(ChatMessageORM)
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


async def get_intent_history(user_id: str, session_id: str) -> list[dict]:
    """Return a bounded lookback; token selection happens in the context builder."""
    def _run() -> list[dict]:
        with read_session_scope() as session:
            user_message = aliased(ChatMessageORM)
            pairs = (
                session.query(ChatMessageORM, user_message, ChatAgentRunORM.status)
                .join(
                    user_message,
                    and_(
                        ChatMessageORM.parent_id == user_message.id,
                        user_message.owner_id == user_id,
                        user_message.session_id == session_id,
                        user_message.role == "user",
                    ),
                )
                .outerjoin(ChatAgentRunORM, ChatAgentRunORM.id == ChatMessageORM.agent_run_id)
                .filter(
                    ChatMessageORM.session_id == session_id,
                    ChatMessageORM.owner_id == user_id,
                    ChatMessageORM.role == "assistant",
                    ChatMessageORM.content != "",
                    or_(ChatMessageORM.error.is_(None), ChatMessageORM.error == ""),
                    or_(
                        ChatAgentRunORM.id.is_(None),
                        ChatAgentRunORM.status == "completed",
                    ),
                )
                .order_by(ChatMessageORM.created_at.desc())
                .limit(settings.agent_history_lookback_pairs)
                .all()
            )
            history: list[dict] = []
            for assistant, parent, run_status in reversed(pairs):
                history.append(
                    {
                        "id": parent.id,
                        "role": parent.role,
                        "content": parent.content,
                        "connection_id": parent.connection_id,
                        "created_at": _iso(parent.created_at),
                    }
                )
                history.append(
                    {
                        "id": assistant.id,
                        "role": assistant.role,
                        "content": assistant.content,
                        "sql": assistant.sql,
                        "results": assistant.results,
                        "columns": assistant.columns or [],
                        "error": assistant.error,
                        "connection_id": assistant.connection_id,
                        "parent_id": assistant.parent_id,
                        "response_kind": assistant.response_kind or "answer",
                        "clarification_context": assistant.clarification_context,
                        "presentation_kind": assistant.presentation_kind,
                        "chart_recommendation": assistant.chart_recommendation,
                        "answer_metadata": assistant.answer_metadata,
                        "agent_tier": assistant.agent_tier,
                        "created_at": _iso(assistant.created_at),
                        "run_status": run_status,
                    }
                )
            return history
    return await anyio.to_thread.run_sync(_run)


async def get_latest_user_message_id(user_id: str, session_id: str) -> Optional[str]:
    def _run() -> Optional[str]:
        with read_session_scope() as session:
            return _get_latest_user_message_id_sync(session, user_id, session_id)
    return await anyio.to_thread.run_sync(_run)


def _get_latest_user_message_id_sync(session: Session, user_id: str, session_id: str) -> Optional[str]:
    row = (
        session.query(ChatMessageORM.id)
        .filter(
            ChatMessageORM.session_id == session_id,
            ChatMessageORM.owner_id == user_id,
            ChatMessageORM.role == "user",
        )
        .order_by(ChatMessageORM.created_at.desc())
        .first()
    )
    return row.id if row else None


async def record_user_turn(
    user_id: str,
    session_id: str,
    connection_id: str | None,
    message: str,
) -> tuple[ChatMessage, Optional[str], list[dict]]:
    """Track the active connection, resolve the previous user message id,
    persist the new user message, and load LLM history — all in one session.

    Atomicity note: this flow commits atomically. Connection tracking, the
    prev-query-id lookup, the user-message insert, and the history read all
    happen in a single session/transaction, so a mid-flow failure can no
    longer leave connection tracking updated without the matching message
    (or vice versa), and this replaces what used to be four separate pool
    checkouts with one.
    """
    def _run() -> tuple[ChatMessage, Optional[str], list[dict]]:
        with session_scope() as session:
            _track_connection_sync(session, user_id, session_id, connection_id)
            prev_query_id = _get_latest_user_message_id_sync(session, user_id, session_id)
            user_msg = ChatMessage(
                role="user",
                content=message,
                connection_id=connection_id,
                prev_query_id=prev_query_id,
            )
            _add_message_sync(session, user_id, session_id, user_msg)
            # Session factories disable autoflush. Flush explicitly so the
            # history query below includes the message from this turn.
            session.flush()
            history = _get_history_for_llm_sync(session, user_id, session_id)
            return user_msg, prev_query_id, history
    return await anyio.to_thread.run_sync(_run)


async def record_clarification_turn(
    *,
    user_id: str,
    connection_id: str,
    message: str,
    clarification: str,
    clarification_context: dict,
    session_id: str | None,
) -> tuple[str, ChatMessage, ChatMessage, Optional[str]]:
    """Atomically persist a blocking user turn and deterministic clarification."""
    def _run() -> tuple[str, ChatMessage, ChatMessage, Optional[str]]:
        with session_scope() as session:
            nonlocal session_id
            created_session = False
            if session_id:
                row = session.query(ChatSessionORM).filter(
                    ChatSessionORM.id == session_id,
                    ChatSessionORM.owner_id == user_id,
                ).one_or_none()
                if not row:
                    raise ValueError("Session not found.")
            else:
                session_id = _create_session_sync(session, user_id, connection_id).id
                created_session = True
            _track_connection_sync(session, user_id, session_id, connection_id)
            previous_user_id = _get_latest_user_message_id_sync(session, user_id, session_id)
            user_message = ChatMessage(
                role="user",
                content=message,
                connection_id=connection_id,
                prev_query_id=previous_user_id,
            )
            _add_message_sync(session, user_id, session_id, user_message)
            session.flush()
            assistant_message = ChatMessage(
                role="assistant",
                content=clarification,
                connection_id=connection_id,
                parent_id=user_message.id,
                response_kind="clarification",
                clarification_context=clarification_context,
                agent_tier="deterministic",
            )
            _add_message_sync(session, user_id, session_id, assistant_message)
            if created_session:
                title = message[:50].strip() + ("..." if len(message) > 50 else "")
                session.query(ChatSessionORM).filter(ChatSessionORM.id == session_id).update({"title": title})
            session.flush()
            return session_id, user_message, assistant_message, previous_user_id
    return await anyio.to_thread.run_sync(_run)


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
    "get_intent_history",
    "get_latest_user_message_id",
    "record_user_turn",
    "record_clarification_turn",
    "reconstruct_dual_chain",
]
