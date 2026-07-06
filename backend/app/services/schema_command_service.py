"""Deterministic schema command handling for chat turns."""

from __future__ import annotations

import re
from difflib import get_close_matches

from app.agents.schema_context.types import CatalogTable, SchemaCatalog
from app.core.config import settings

_WRITE_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|merge|replace|upsert)\b",
    re.IGNORECASE,
)
_LIST_TABLES_RE = re.compile(
    r"(?:\b(show|list|display)\b.*\b(tables|schema)\b)|"
    r"(?:\bwhat\b.*\btables\b.*\b(exist|available|have)\b)|"
    r"(?:\b(describe|inspect)\b.*\b(database|schema)\b)",
    re.IGNORECASE,
)
_COLUMNS_IN_RE = re.compile(
    r"\b(?:show|list|display|what\s+are|what're)\b\s+(?:the\s+)?(?:columns|fields)\s+(?:in|of|for)\s+(?P<table>.+)$",
    re.IGNORECASE,
)
_DESCRIBE_TABLE_RE = re.compile(
    r"\b(?:describe|inspect)\b\s+(?:the\s+)?(?P<table>.+)$",
    re.IGNORECASE,
)


def _base_response(*, explanation: str, tier: str, trace: list[dict]) -> dict:
    return {
        "success": True,
        "explanation": explanation,
        "sql": None,
        "column_metadata": {},
        "columns": [],
        "rows": [],
        "row_count": 0,
        "truncated": False,
        "execution_time_ms": 0.0,
        "chart_recommendation": None,
        "error": None,
        "trace": trace,
        "tier": tier,
        "tool_calls": 0,
        "wall_ms": 0.0,
    }


def _trace(args_summary: str, outcome: str = "ok", output_summary: str | None = None) -> list[dict]:
    step = {
        "tool": "schema_catalog",
        "args_summary": args_summary[:500],
        "duration_ms": 0.0,
        "outcome": outcome,
    }
    if output_summary:
        step["output_summary"] = output_summary[:500]
    return [step]


def _table_sort_key(table: CatalogTable) -> tuple[bool, float, str]:
    return (table.is_internal, -table.importance_score, table.name.lower())


def _all_table_names(catalog: SchemaCatalog) -> list[str]:
    names: list[str] = []
    for table in catalog.tables:
        names.append(table.name)
        short = table.name.split(".")[-1]
        if short != table.name:
            names.append(short)
    return names


def _matching_tables(catalog: SchemaCatalog, raw_name: str) -> list[CatalogTable]:
    cleaned = raw_name.strip().strip("`\"'").rstrip("?.")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return []
    lowered = cleaned.lower()
    exact = [table for table in catalog.tables if table.name.lower() == lowered]
    if exact:
        return exact
    return [table for table in catalog.tables if table.name.split(".")[-1].lower() == lowered]


def _suggestions(catalog: SchemaCatalog, raw_name: str) -> list[str]:
    return get_close_matches(raw_name.strip().strip("`\"'"), _all_table_names(catalog), n=5, cutoff=0.45)


def _list_tables_response(catalog: SchemaCatalog) -> dict:
    sorted_tables = sorted(catalog.tables, key=_table_sort_key)
    max_rows = max(1, settings.agent_max_tables_listed)
    shown = sorted_tables[:max_rows]
    rows = [
        {
            "table_name": table.name,
            "schema_name": table.schema_name,
            "row_estimate": table.row_estimate,
            "column_count": len(table.columns),
        }
        for table in shown
    ]
    total = len(sorted_tables)
    truncated = len(shown) < total
    explanation = f"This database has {total} table{'s' if total != 1 else ''}."
    if truncated:
        explanation += f" Showing {len(shown)} because the table list is capped."
    response = _base_response(
        explanation=explanation,
        tier="schema_catalog",
        trace=_trace("list_tables", output_summary=f"{total} tables returned"),
    )
    response.update(
        {
            "columns": ["table_name", "schema_name", "row_estimate", "column_count"],
            "rows": rows,
            "row_count": total,
            "truncated": truncated,
        }
    )
    return response


def _describe_table_response(catalog: SchemaCatalog, raw_name: str) -> dict:
    matches = _matching_tables(catalog, raw_name)
    if not matches:
        suggestions = _suggestions(catalog, raw_name)
        explanation = f"I could not find a table named '{raw_name.strip()}'."
        if suggestions:
            explanation += " Did you mean: " + ", ".join(suggestions) + "?"
        response = _base_response(
            explanation=explanation,
            tier="schema_catalog",
            trace=_trace(f"describe_table:{raw_name}", "error", "unknown table"),
        )
        response["error"] = explanation
        return response
    if len(matches) > 1:
        names = [table.name for table in matches]
        explanation = "That table name is ambiguous. Please use one of: " + ", ".join(names)
        response = _base_response(
            explanation=explanation,
            tier="schema_catalog",
            trace=_trace(f"describe_table:{raw_name}", "error", "ambiguous table"),
        )
        response.update(
            {
                "columns": ["table_name"],
                "rows": [{"table_name": name} for name in names],
                "row_count": len(names),
                "error": explanation,
            }
        )
        return response

    table = matches[0]
    rows = []
    for col in table.columns:
        fk = f"{col.fk_referred_table}.{col.fk_referred_column}" if col.fk_referred_table else None
        rows.append(
            {
                "column_name": col.name,
                "type": col.type,
                "nullable": col.nullable,
                "primary_key": col.primary_key,
                "foreign_key": fk,
                "semantic_type": col.semantic_type,
                "sensitive": col.is_sensitive,
            }
        )
    explanation = (
        f"Table {table.name} has {len(table.columns)} column{'s' if len(table.columns) != 1 else ''}."
    )
    if table.row_estimate is not None:
        explanation += f" Estimated rows: {table.row_estimate}."
    response = _base_response(
        explanation=explanation,
        tier="schema_catalog",
        trace=_trace(f"describe_table:{table.name}", output_summary=f"{len(table.columns)} columns returned"),
    )
    response.update(
        {
            "columns": [
                "column_name",
                "type",
                "nullable",
                "primary_key",
                "foreign_key",
                "semantic_type",
                "sensitive",
            ],
            "rows": rows,
            "row_count": len(rows),
        }
    )
    return response


def _read_only_refusal() -> dict:
    return _base_response(
        explanation=(
            "I can only help with read-only database analysis. I cannot modify data, "
            "but I can help write a SELECT query to inspect the affected rows."
        ),
        tier="controlled_refusal",
        trace=_trace("read_only_refusal", "refused", "write intent detected"),
    )


def handle_schema_or_control_command(message: str, catalog: SchemaCatalog | None) -> dict | None:
    text = message.strip()
    if _WRITE_RE.search(text):
        return _read_only_refusal()
    if not catalog:
        return None
    if _LIST_TABLES_RE.search(text):
        return _list_tables_response(catalog)

    columns_match = _COLUMNS_IN_RE.search(text)
    if columns_match:
        return _describe_table_response(catalog, columns_match.group("table"))

    describe_match = _DESCRIBE_TABLE_RE.search(text)
    if describe_match:
        raw_table = describe_match.group("table").strip()
        if raw_table.lower() not in {"database", "schema", "db"}:
            return _describe_table_response(catalog, raw_table)
    return None


__all__ = ["handle_schema_or_control_command"]
