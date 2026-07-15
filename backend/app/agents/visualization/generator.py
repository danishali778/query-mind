import json
import logging
import re
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents._llm_content import log_llm_output
from app.agents._prompt_loader import load_prompt
from app.agents.nl_to_sql.llm import get_llm
from app.db.models.llm import LlmExecutionContext

logger = logging.getLogger("query-mind.visualization")

_PROMPT_PATH = Path(__file__).with_name("prompts") / "blueprint_prompt.md"


def _json_serializable(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date, time)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def generate_visualization_blueprint(
    llm_context: LlmExecutionContext,
    user_message: str,
    sql: str,
    preview_rows: list[dict],
    column_metadata: dict,
    is_edited: bool = False,
) -> dict | None:
    if not preview_rows:
        return None

    human_message = (
        "Here is the query context.\n\n"
        f"User's Original Question: {user_message}\n\n"
        f"Generated SQL:\n{sql}\n\n"
        "Column Metadata:\n"
        f"{json.dumps(column_metadata, indent=2, default=_json_serializable)}\n\n"
        "Data Preview (first 5 rows):\n"
        f"{json.dumps(preview_rows, indent=2, default=_json_serializable)}"
    )

    if is_edited:
        human_message += (
            "\n\nCRITICAL: The user has manually edited the SQL. The provided SQL is "
            "now the source of truth. Ensure your visualization matches the columns "
            "and data structure of the SQL exactly, even if it deviates from the "
            "original question."
        )

    human_message += "\n\nBased on this, generate the optimal chart visualization JSON blueprint."

    response = get_llm(llm_context).invoke(
        [
            SystemMessage(content=load_prompt(str(_PROMPT_PATH))),
            HumanMessage(content=human_message),
        ]
    )
    content = log_llm_output(logger, "visualization blueprint", response.content)

    match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL | re.IGNORECASE)
    if match:
        json_str = match.group(1).strip()
    else:
        match = re.search(r"({.*})", content, re.DOTALL)
        if not match:
            return None
        json_str = match.group(1).strip()

    try:
        blueprint = json.loads(json_str)
    except json.JSONDecodeError:
        return None

    chart_type = blueprint.get("type")
    if chart_type == "table":
        return blueprint
    if chart_type == "kpi" and blueprint.get("y_columns"):
        return blueprint
    if chart_type and blueprint.get("x_column") and blueprint.get("y_columns"):
        return blueprint
    return None
