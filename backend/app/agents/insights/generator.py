import json
from pathlib import Path
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents._prompt_loader import load_prompt
from app.integrations.llm_client import invoke_chat_llm
from app.db.models.llm import LlmExecutionContext

_PROMPT_PATH = Path(__file__).with_name("prompts") / "widget_insight_prompt.md"


def generate_widget_insight(
    llm_context: LlmExecutionContext,
    title: str,
    viz_type: str,
    data: List[Dict[str, Any]],
    filters: Dict[str, Any],
) -> str:
    if not data:
        return "Not enough data to generate insights yet."

    prompt = (
        load_prompt(str(_PROMPT_PATH))
        .replace("__TITLE__", title)
        .replace("__VIZ_TYPE__", viz_type)
        .replace("__FILTERS__", json.dumps(filters))
        .replace("__DATA__", json.dumps(data[:10], indent=2))
    )

    try:
        return invoke_chat_llm(
            llm_context,
            [
                SystemMessage(content="You provide short, professional data insights."),
                HumanMessage(content=prompt),
            ],
            temperature=0.3,
            max_tokens=150,
        )
    except Exception:
        return "Analysis momentarily unavailable. Please try again shortly."
