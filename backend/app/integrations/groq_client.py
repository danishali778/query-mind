"""Backward-compatible owner-scoped LLM exports."""

from app.db.models.llm import LlmExecutionContext
from app.integrations.llm_client import get_chat_llm, invoke_chat_llm

def get_groq_client(*_args, **_kwargs):
    raise RuntimeError("Direct provider clients are disabled; use the owner-scoped LLM gateway.")


def get_chat_groq(context: LlmExecutionContext):
    return get_chat_llm(context)


__all__ = ["get_groq_client", "get_chat_groq", "invoke_chat_llm"]
