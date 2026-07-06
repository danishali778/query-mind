"""Unified LLM client for Groq and Gemini providers."""

from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage

from app.core.config import settings

_default_chat_llm: BaseChatModel | None = None


def _build_chat_llm(*, temperature: float = 0, max_tokens: int = 4096) -> BaseChatModel:
    provider = settings.resolved_llm_provider
    model = settings.resolved_llm_model

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        api_key = settings.resolved_google_api_key
        if not api_key:
            raise RuntimeError("Required configuration value is missing: google_api_key or gemini_api_key")
        return ChatGoogleGenerativeAI(
            google_api_key=api_key,
            model=model,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

    from langchain_groq import ChatGroq

    return ChatGroq(
        api_key=settings.require("groq_api_key"),
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def get_chat_llm(*, temperature: float = 0, max_tokens: int = 4096) -> BaseChatModel:
    global _default_chat_llm
    if _default_chat_llm is None:
        _default_chat_llm = _build_chat_llm(temperature=temperature, max_tokens=max_tokens)
    return _default_chat_llm


def get_chat_llm_with_tools(tools: list[Any]) -> BaseChatModel:
    return _build_chat_llm().bind_tools(tools)


def invoke_chat_llm(messages: list[BaseMessage], *, temperature: float = 0, max_tokens: int = 4096) -> str:
    response = _build_chat_llm(temperature=temperature, max_tokens=max_tokens).invoke(messages)
    content = response.content
    if isinstance(content, str):
        return content.strip()
    return str(content).strip()


__all__ = ["get_chat_llm", "get_chat_llm_with_tools", "invoke_chat_llm"]
