"""Deterministic grounding facts and bounded history for the decision agent."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from app.agents.schema_context.scoring import tokenize
from app.agents.schema_context.types import SchemaCatalog
from app.agents.schema_context.user_semantics import SemanticContext
from app.core.secret_detection import detect_secret
from app.core.config import settings


CLARIFICATION_MESSAGE = (
    "I couldn't identify a database question yet. Tell me which metric, table, "
    "or business outcome you want to analyze."
)

@dataclass(frozen=True)
class QuestionIntentResult:
    decision: Literal["analyze", "clarify"]
    history_mode: Literal["none"] = "none"
    broad_discovery: bool = False
    matched_tables: list[str] = field(default_factory=list)
    matched_columns: list[str] = field(default_factory=list)
    matched_semantic_refs: list[str] = field(default_factory=list)
    reason_code: str = ""
    clarification_message: str | None = None
    clarification_context: dict | None = None


def _completed_pairs(history: list[dict]) -> list[tuple[dict, dict]]:
    users = {item.get("id"): item for item in history if item.get("role") == "user"}
    pairs: list[tuple[dict, dict]] = []
    for assistant in history:
        if assistant.get("role") != "assistant":
            continue
        parent = users.get(assistant.get("parent_id"))
        if not parent or not assistant.get("content") or assistant.get("error"):
            continue
        if assistant.get("run_status") not in {None, "completed"}:
            continue
        pairs.append((parent, assistant))
    return pairs


def latest_clarification_context(history: list[dict]) -> dict | None:
    pairs = _completed_pairs(history)
    if not pairs:
        return None
    assistant = pairs[-1][1]
    if assistant.get("response_kind") != "clarification":
        return None
    context = assistant.get("clarification_context")
    return context if isinstance(context, dict) else None


def bounded_follow_up_history(history: list[dict], *, include: bool = True) -> list[dict]:
    if not include:
        return []
    result: list[dict] = []
    selected: list[tuple[dict, dict]] = []
    used_tokens = 0
    for user, assistant in reversed(_completed_pairs(history)):
        pair_tokens = max(
            1,
            (
                len(str(user.get("content") or ""))
                + len(str(assistant.get("content") or ""))
                + 3
            )
            // 4,
        ) + 32
        if selected and used_tokens + pair_tokens > settings.agent_recent_history_token_budget:
            break
        selected.append((user, assistant))
        used_tokens += pair_tokens
    for user, assistant in reversed(selected):
        if detect_secret(str(user.get("content") or "")) or detect_secret(str(assistant.get("content") or "")):
            continue
        assistant_content = str(assistant.get("content") or "")
        metadata = assistant.get("answer_metadata")
        if isinstance(metadata, dict):
            method = metadata.get("method")
            evidence = metadata.get("evidence") or []
            limitations = metadata.get("limitations") or []
            if method:
                assistant_content += f"\nMethod: {method}"
            if evidence:
                safe_claims = [str(item.get("claim")) for item in evidence[:5] if isinstance(item, dict) and item.get("claim")]
                if safe_claims:
                    assistant_content += "\nEvidence: " + "; ".join(safe_claims)
            if limitations:
                assistant_content += "\nLimitations: " + "; ".join(str(item) for item in limitations[:5])
        if detect_secret(assistant_content):
            continue
        result.append({"role": "user", "content": str(user.get("content") or "")})
        result.append(
            {
                "role": "assistant",
                "content": assistant_content,
                "response_kind": assistant.get("response_kind") or "answer",
            }
        )
    return result


def _phrase_present(question_lower: str, value: str) -> bool:
    return bool(
        value
        and re.search(
            rf"(?<![a-z0-9_]){re.escape(value.casefold())}(?![a-z0-9_])",
            question_lower,
        )
    )


def _matched_semantic_definitions(question: str, semantic_context: SemanticContext | None):
    if not semantic_context:
        return []
    lowered = question.casefold()
    matched = []
    for item in semantic_context.definitions:
        phrases = {
            item.key.replace("_", " "),
            item.display_name,
        }
        phrases.update(str(value) for value in item.payload.get("synonyms", []) if value)
        if item.kind == "synonym":
            phrases.add(str(item.payload.get("phrase") or ""))
        if any(_phrase_present(lowered, phrase) for phrase in phrases if phrase):
            matched.append(item)
    return matched


def _physical_matches(question: str, catalog: SchemaCatalog | None) -> tuple[list[str], list[str]]:
    if not catalog:
        return [], []
    lowered = question.casefold()
    terms = set(tokenize(question))
    tables: list[str] = []
    columns: list[str] = []

    for table in catalog.tables:
        names = {table.name.casefold(), table.name.split(".")[-1].casefold()}
        table_tokens = set(tokenize(table.name))
        if any(_phrase_present(lowered, name) for name in names) or terms & table_tokens:
            tables.append(table.name)
        for column in table.columns:
            column_tokens = set(tokenize(column.name))
            if _phrase_present(lowered, column.name) or terms & column_tokens:
                columns.append(f"{table.name}.{column.name}")
    return list(dict.fromkeys(tables)), list(dict.fromkeys(columns))


def build_grounding_context(
    question: str,
    *,
    catalog: SchemaCatalog | None,
    semantic_context: SemanticContext | None,
    history: list[dict],
) -> QuestionIntentResult:
    tables, columns = _physical_matches(question, catalog)
    semantic_definitions = _matched_semantic_definitions(question, semantic_context)
    semantic_refs = [item.reference for item in semantic_definitions]
    for item in semantic_definitions:
        payload = item.payload
        for table_name in [payload.get("table_name"), payload.get("source_table"), payload.get("primary_table")]:
            if table_name:
                tables.append(str(table_name))
        tables.extend(str(name) for name in payload.get("required_tables", []) if name)
        column_name = payload.get("column_name") or payload.get("source_column")
        table_name = payload.get("table_name") or payload.get("source_table")
        if table_name and column_name:
            columns.append(f"{table_name}.{column_name}")
    tables = list(dict.fromkeys(tables))
    columns = list(dict.fromkeys(columns))
    if semantic_refs:
        reason = "verified_semantic_match"
    elif tables or columns:
        reason = "physical_schema_match"
    else:
        reason = "agent_decision_required"

    return QuestionIntentResult(
        decision="analyze",
        history_mode="none",
        broad_discovery=False,
        matched_tables=tables,
        matched_columns=columns,
        matched_semantic_refs=semantic_refs,
        reason_code=reason,
    )


def analyze_question_intent(
    question: str,
    *,
    catalog: SchemaCatalog | None,
    semantic_context: SemanticContext | None,
    history: list[dict],
) -> QuestionIntentResult:
    """Backward-compatible alias for the non-decision-making grounding builder."""
    return build_grounding_context(
        question,
        catalog=catalog,
        semantic_context=semantic_context,
        history=history,
    )


__all__ = [
    "CLARIFICATION_MESSAGE",
    "QuestionIntentResult",
    "analyze_question_intent",
    "build_grounding_context",
    "bounded_follow_up_history",
    "latest_clarification_context",
]
