"""Owner-scoped, metered LLM clients for supported providers."""

from __future__ import annotations

from typing import Any, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from langchain_core.runnables import Runnable, RunnableConfig

from app.db.models.llm import LlmExecutionContext, LlmResolution
from app.services import llm_credential_service


def _build_chat_llm(
    resolution: LlmResolution,
    *,
    temperature: float = 0,
    max_tokens: int = 4096,
) -> BaseChatModel:
    api_key = resolution.api_key.get_secret_value()
    common = {"model": resolution.model, "max_retries": 0}
    if resolution.provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            google_api_key=api_key,
            temperature=temperature,
            max_output_tokens=max_tokens,
            **common,
        )
    if resolution.provider == "openai":
        from langchain_openai import ChatOpenAI

        parameters: dict[str, Any] = {
            "api_key": api_key,
            "max_completion_tokens": max_tokens,
            **common,
        }
        if not resolution.model.startswith("gpt-5"):
            parameters["temperature"] = temperature
        return ChatOpenAI(**parameters)

    from langchain_groq import ChatGroq

    return ChatGroq(
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        **common,
    )


class _MeteredRunnable(Runnable):
    def __init__(self, underlying: Runnable, context: LlmExecutionContext, resolution: LlmResolution) -> None:
        self.underlying = underlying
        self.context = context
        self.resolution = resolution

    def invoke(self, input: Any, config: RunnableConfig | None = None, **kwargs: Any) -> Any:
        return llm_credential_service.invoke_metered(
            self.context,
            self.resolution,
            lambda: self.underlying.invoke(input, config=config, **kwargs),
        )

    async def ainvoke(self, input: Any, config: RunnableConfig | None = None, **kwargs: Any) -> Any:
        return await llm_credential_service.ainvoke_metered(
            self.context,
            self.resolution,
            lambda: self.underlying.ainvoke(input, config=config, **kwargs),
        )


class MeteredChatModel(BaseChatModel):
    """Delegating model that meters every provider invocation, including tool turns."""

    underlying: BaseChatModel
    execution_context: LlmExecutionContext
    resolution: LlmResolution

    @property
    def _llm_type(self) -> str:
        return f"querymind-metered-{self.resolution.provider}"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"provider": self.resolution.provider, "model": self.resolution.model}

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs: Any) -> ChatResult:
        return llm_credential_service.invoke_metered(
            self.execution_context,
            self.resolution,
            lambda: self.underlying._generate(messages, stop=stop, run_manager=run_manager, **kwargs),
        )

    async def _agenerate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs: Any) -> ChatResult:
        return await llm_credential_service.ainvoke_metered(
            self.execution_context,
            self.resolution,
            lambda: self.underlying._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs),
        )

    def bind_tools(self, tools: Sequence, *, tool_choice: str | None = None, **kwargs: Any) -> Runnable:
        bound = self.underlying.bind_tools(tools, tool_choice=tool_choice, **kwargs)
        return _MeteredRunnable(bound, self.execution_context, self.resolution)

    def with_structured_output(self, schema, *, include_raw: bool = False, **kwargs: Any) -> Runnable:
        bound = self.underlying.with_structured_output(schema, include_raw=include_raw, **kwargs)
        return _MeteredRunnable(bound, self.execution_context, self.resolution)


def get_chat_llm(
    context: LlmExecutionContext,
    *,
    temperature: float = 0,
    max_tokens: int = 4096,
) -> MeteredChatModel:
    resolution = llm_credential_service.resolve(context)
    return MeteredChatModel(
        underlying=_build_chat_llm(resolution, temperature=temperature, max_tokens=max_tokens),
        execution_context=context,
        resolution=resolution,
    )


def get_chat_llm_with_tools(context: LlmExecutionContext, tools: list[Any]) -> Runnable:
    return get_chat_llm(context).bind_tools(tools)


def invoke_chat_llm(
    context: LlmExecutionContext,
    messages: list[BaseMessage],
    *,
    temperature: float = 0,
    max_tokens: int = 4096,
) -> str:
    response = get_chat_llm(context, temperature=temperature, max_tokens=max_tokens).invoke(messages)
    content = response.content
    if isinstance(content, str):
        return content.strip()
    return str(content).strip()


__all__ = ["MeteredChatModel", "get_chat_llm", "get_chat_llm_with_tools", "invoke_chat_llm"]
