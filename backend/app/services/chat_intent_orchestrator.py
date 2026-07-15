"""Coordinates pre-persistence chat validation and intent preparation."""

from __future__ import annotations

from dataclasses import dataclass

from app.services import connection_service, llm_credential_service, semantic_context_service
from app.services.chat_input_guard import ChatInputGuard
from app.services.question_intent_service import (
    QuestionIntentResult,
    analyze_question_intent,
    bounded_follow_up_history,
    latest_clarification_context,
)
from app.db.repositories.chat_repository import get_intent_history
from app.core import chat_guard_metrics


@dataclass(frozen=True)
class PreparedChatIntent:
    intent: QuestionIntentResult
    history: list[dict]


async def prepare_chat_intent(
    *,
    user_id: str,
    connection_id: str,
    message: str,
    session_id: str | None,
) -> PreparedChatIntent:
    # Credential detection is history-independent and must happen before any
    # connection, catalog, Redis, or LLM work.
    ChatInputGuard.enforce_sensitive(message)

    intent_history = await get_intent_history(user_id, session_id) if session_id else []
    clarification_context = latest_clarification_context(intent_history)
    expects_identifier = bool(
        clarification_context and clarification_context.get("expected_input") == "identifier"
    )
    ChatInputGuard.enforce(message, expects_identifier=expects_identifier)

    engine = await connection_service.get_engine(user_id, connection_id)
    if not engine:
        raise ValueError("Database connection not found. Connect first.")
    catalog = await connection_service.get_catalog(user_id, connection_id)
    semantic_context = None
    if catalog:
        semantic_context = await semantic_context_service.load_context(
            user_id, connection_id, catalog, message
        )
    intent = analyze_question_intent(
        message,
        catalog=catalog,
        semantic_context=semantic_context,
        history=intent_history,
    )
    history = bounded_follow_up_history(
        intent_history,
        include=intent.history_mode == "explicit_follow_up",
    )
    if history:
        chat_guard_metrics.increment("explicit_history_inclusions")
    if intent.decision == "clarify":
        chat_guard_metrics.increment("clarifications_returned")
        chat_guard_metrics.increment("prevented_llm_calls")
        chat_guard_metrics.increment("prevented_sql_executions")
    if intent.decision == "analyze":
        if intent.reason_code != "schema_command":
            llm_credential_service.preflight(user_id, "chat", interaction_type="explicit")
    return PreparedChatIntent(intent=intent, history=history)


__all__ = ["PreparedChatIntent", "prepare_chat_intent"]
