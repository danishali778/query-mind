import json
import re
import uuid
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.nl_to_sql.llm import get_llm
from app.agents.nl_to_sql.prompts import build_template_recommender_prompt

CATEGORY_COLORS: dict[str, str] = {
    "Sales": "#22d3a5",
    "Marketing": "#00e5ff",
    "Finance": "#f59e0b",
    "Operations": "#f87171",
    "Analytics": "#c084fc",
    "Users": "#60a5fa",
}

CATEGORY_ICON_BG: dict[str, str] = {
    "Sales": "#1a3a2a",
    "Marketing": "#1a1a3a",
    "Finance": "#2a1a1a",
    "Operations": "#2a2a1a",
    "Analytics": "#1a2a3a",
    "Users": "#1a1a2a",
}

VALID_CATEGORIES = set(CATEGORY_COLORS.keys())
VALID_DIFFICULTIES = {"beginner", "intermediate", "advanced"}


@dataclass
class DynamicTemplate:
    id: str
    connection_id: str
    title: str
    description: str
    sql: str
    category: str
    category_color: str
    tags: list[str]
    icon: str
    icon_bg: str
    difficulty: str


def generate_templates(connection_id: str, schema_text: str, db_type: str) -> list[DynamicTemplate]:
    response = get_llm().invoke(
        [
            SystemMessage(
                content=(
                    "You are a SQL expert. Output only raw JSON arrays with no "
                    "surrounding text or markdown."
                )
            ),
            HumanMessage(
                content=build_template_recommender_prompt(
                    schema_text=schema_text,
                    db_type=db_type,
                )
            ),
        ]
    )
    return _parse_response(connection_id, response.content.strip())


def _parse_response(connection_id: str, raw: str) -> list[DynamicTemplate]:
    raw = re.sub(r"```json\s*", "", raw)
    raw = re.sub(r"```\s*", "", raw)

    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1:
        if end == -1 or end < start:
            last_brace = raw.rfind("}")
            if last_brace != -1:
                raw = raw[start : last_brace + 1] + "]"
        else:
            raw = raw[start : end + 1]

    raw = raw.strip()
    if not raw:
        return []

    data = json.loads(raw)
    templates: list[DynamicTemplate] = []

    for item in data:
        sql = str(item.get("sql", "")).strip()
        if not sql:
            continue

        category = item.get("category", "Analytics")
        if category not in VALID_CATEGORIES:
            category = "Analytics"

        difficulty = item.get("difficulty", "beginner")
        if difficulty not in VALID_DIFFICULTIES:
            difficulty = "beginner"

        templates.append(
            DynamicTemplate(
                id=str(uuid.uuid4()),
                connection_id=connection_id,
                title=str(item.get("title", "Query"))[:60],
                description=str(item.get("description", ""))[:200],
                sql=sql,
                category=category,
                category_color=CATEGORY_COLORS[category],
                tags=[str(tag).lower() for tag in item.get("tags", [])[:4]],
                icon=str(item.get("icon", "chart")),
                icon_bg=CATEGORY_ICON_BG.get(category, "#1a2a3a"),
                difficulty=difficulty,
            )
        )

    return templates
