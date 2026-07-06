"""Backward-compatible Groq client exports (delegates to llm_client)."""

from groq import Groq

from app.core.config import settings
from app.integrations.llm_client import get_chat_llm, invoke_chat_llm

_groq_client: Groq | None = None


def get_groq_client() -> Groq:
    if settings.resolved_llm_provider != "groq":
        raise RuntimeError("get_groq_client() is only available when LLM_PROVIDER=groq")
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=settings.require("groq_api_key"))
    return _groq_client


def get_chat_groq():
    return get_chat_llm()


__all__ = ["get_groq_client", "get_chat_groq", "invoke_chat_llm"]
