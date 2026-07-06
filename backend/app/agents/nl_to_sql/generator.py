import json
import logging
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents._llm_content import content_to_text, log_llm_output
from app.agents.nl_to_sql.llm import get_llm

logger = logging.getLogger("query-mind.nl_to_sql")


def generate_sql(messages: list[dict]) -> tuple[str, dict, str]:
    llm = get_llm()

    lc_messages = []
    for msg in messages:
        if msg["role"] == "system":
            lc_messages.append(SystemMessage(content=msg["content"]))
        elif msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            lc_messages.append(AIMessage(content=msg["content"]))

    response = llm.invoke(lc_messages)
    response_text = log_llm_output(logger, "pipeline generate_sql", response.content)

    return (
        extract_explanation(response_text),
        extract_metadata(response_text),
        extract_sql(response_text),
    )


def extract_sql(text: str) -> str:
    for pattern in (
        r"```sql\s*\n?(.*?)\n?\s*```",
        r"```\s*\n?(.*?)\n?\s*```",
    ):
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            sql = match.group(1).strip()
            if sql:
                return sql

    lines = text.split("\n")
    sql_lines: list[str] = []
    in_sql = False
    for line in lines:
        stripped = line.strip().upper()
        if stripped.startswith(("SELECT", "WITH")):
            in_sql = True
        if in_sql:
            sql_lines.append(line)
            if stripped.endswith(";"):
                break

    return "\n".join(sql_lines).strip() if sql_lines else ""


def extract_explanation(text: str) -> str:
    match = re.search(r"EXPLANATION:\s*(.+?)(?=```|$)", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    parts = text.split("```")
    if parts:
        explanation = parts[0].strip()
        explanation = re.sub(r"^EXPLANATION:\s*", "", explanation, flags=re.IGNORECASE)
        if explanation:
            return explanation

    return "Here's the SQL query for your question."


def extract_metadata(text: str) -> dict:
    match = re.search(
        r"METADATA:\s*```json\s*(.*?)\s*```",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    match = re.search(r"METADATA:.*?({.*?})", text, re.DOTALL | re.IGNORECASE)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    return {}


def generate_error_correction(
    messages: list[dict],
    sql: str,
    error: str,
) -> tuple[str, dict, str]:
    error_message = {
        "role": "user",
        "content": (
            "The SQL query you generated had an error when executed:\n\n"
            f"Query:\n```sql\n{sql}\n```\n\n"
            f"Error: {error}\n\n"
            "Please fix the SQL query and try again. Return the corrected query in the same format."
        ),
    }
    return generate_sql(messages + [error_message])
