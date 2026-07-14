from langchain_core.language_models.chat_models import BaseChatModel

from app.db.models.llm import LlmExecutionContext
from app.integrations.llm_client import get_chat_llm


def get_llm(context: LlmExecutionContext) -> BaseChatModel:
    return get_chat_llm(context)
