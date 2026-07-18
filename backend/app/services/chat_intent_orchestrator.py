"""Coordinates pre-persistence chat validation and intent preparation."""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.db_agent.tools import PriorAnalysisExecution
from app.services import connection_service, llm_credential_service, semantic_context_service
from app.services.chat_input_guard import ChatInputGuard
from app.services.conversation_evidence_service import build_conversation_evidence_context
from app.services.question_intent_service import (
    QuestionIntentResult,
    build_grounding_context,
    latest_clarification_context,
)
from app.db.repositories.chat_repository import get_intent_history
from app.core import chat_guard_metrics


@dataclass(frozen=True)
class PreparedChatIntent:
    intent: QuestionIntentResult
    history: list[dict]
    prior_results: dict[str, PriorAnalysisExecution]


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
    intent = build_grounding_context(
        message,
        catalog=catalog,
        semantic_context=semantic_context,
        history=intent_history,
    )
    conversation = (
        build_conversation_evidence_context(
            intent_history,
            connection_id=connection_id,
            catalog=catalog,
            semantic_context=semantic_context,
        )
        if catalog is not None and semantic_context is not None
        else None
    )
    history = conversation.messages if conversation else []
    prior_results = conversation.prior_results if conversation else {}
    if history or prior_results:
        chat_guard_metrics.increment("explicit_history_inclusions")
    if not message.lstrip().startswith("/"):
        llm_credential_service.preflight(user_id, "chat", interaction_type="explicit")
    return PreparedChatIntent(
        intent=intent,
        history=history,
        prior_results=prior_results,
    )


__all__ = ["PreparedChatIntent", "prepare_chat_intent"]
