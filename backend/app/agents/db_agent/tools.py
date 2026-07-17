"""Read-only tools for the database agent."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from difflib import get_close_matches
from typing import Callable

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine

from app.agents.db_agent.trace import TraceRecorder, summarize_args
from app.agents.schema_context.catalog import catalog_table_by_name
from app.agents.schema_context.scoring import expand_terms, score_tables, tokenize
from app.agents.schema_context.types import CatalogColumn, CatalogTable, SchemaCatalog
from app.agents.schema_context.user_semantics import SemanticContext
from app.core.config import settings
from app.query_engine.connection_scope import referenced_tables
from app.query_engine.executor import execute_query as guarded_execute_query
from app.query_engine.results import QueryExecutionResult
from app.query_engine.safety import validate_query
from app.query_engine.semantic_policy import validate_ai_semantic_policy
from app.query_engine.cancellation import QueryCancellationToken
from app.services.query_execution_service import execute_query

SAMPLE_MAX_VALUES = 15
SAMPLE_QUERY_LIMIT = SAMPLE_MAX_VALUES + 1


@dataclass(frozen=True)
class AnalysisExecution:
    result_ref: str
    sql: str
    result: QueryExecutionResult
    semantic_policy_refs: list[str] = field(default_factory=list)


@dataclass
class ToolContext:
    user_id: str
    connection_id: str
    catalog: SchemaCatalog
    engine: Engine
    trace: TraceRecorder
    invalidate_catalog: Callable[[], None] | None = None
    rebuild_catalog: Callable[[], SchemaCatalog | None] | None = None
    last_execution: QueryExecutionResult | None = None
    last_executed_sql: str | None = None
    drift_refresh_used: bool = False
    scratchpad: list[str] = field(default_factory=list)
    live_query_count: int = 0
    cancellation_token: QueryCancellationToken | None = None
    grounded_terms: set[str] = field(default_factory=set)
    matched_tables: set[str] = field(default_factory=set)
    inspected_tables: set[str] = field(default_factory=set)
    allow_broad_discovery: bool = False
    enforce_grounding: bool = False
    semantic_context: SemanticContext | None = None
    analysis_query_count: int = 0
    analysis_results: dict[str, AnalysisExecution] = field(default_factory=dict)


class SearchSchemaInput(BaseModel):
    query: str = Field(description="Natural-language search query for tables and columns")


class GetTableSchemaInput(BaseModel):
    table_names: list[str] = Field(description="List of table names to inspect")


class TableColumnInput(BaseModel):
    table: str = Field(description="Table name")
    column: str = Field(description="Column name")


class SqlInput(BaseModel):
    sql: str = Field(description="SQL query string")


class TableNameInput(BaseModel):
    table: str = Field(description="Table name")


class NoteInput(BaseModel):
    text: str = Field(description="Finding or observation to remember for this run")


class RunCountFilterInput(BaseModel):
    column: str = Field(description="Column name to filter on")
    operator: str = Field(default="=", description="One of =, !=, >, >=, <, <=, like, ilike, is_null, is_not_null")
    value: str | int | float | bool | None = Field(default=None, description="Filter value; omitted for is_null/is_not_null")


class RunCountInput(BaseModel):
    table: str = Field(description="Table name")
    filters: list[RunCountFilterInput] = Field(default_factory=list, description="Structured filters combined by conjunction")
    conjunction: str = Field(default="AND", description="AND or OR")


def _suggest_similar(name: str, candidates: list[str], limit: int = 5) -> list[str]:
    if not candidates:
        return []
    return get_close_matches(name, candidates, n=limit, cutoff=0.5)


def _catalog_table_names(catalog: SchemaCatalog) -> list[str]:
    return [table.name for table in catalog.tables]


def _catalog_column_names(catalog: SchemaCatalog, table_name: str | None = None) -> list[str]:
    if table_name:
        table = catalog_table_by_name(catalog, table_name)
        if not table:
            return []
        return [column.name for column in table.columns]
    names: list[str] = []
    for table in catalog.tables:
        names.extend(column.name for column in table.columns)
    return names


def _canonical_table_name(catalog: SchemaCatalog, name: str) -> str | None:
    table = catalog_table_by_name(catalog, name)
    if not table:
        return None
    if "." in table.name:
        return table.name
    return f"{table.schema_name or 'public'}.{table.name}"


def _table_is_grounded(ctx: ToolContext, name: str) -> bool:
    if not ctx.enforce_grounding or ctx.allow_broad_discovery:
        return True
    canonical = _canonical_table_name(ctx.catalog, name)
    if not canonical:
        return False
    candidates = {canonical.casefold(), canonical.split(".")[-1].casefold()}
    allowed = {item.casefold() for item in ctx.matched_tables | ctx.inspected_tables}
    allowed |= {item.split(".")[-1] for item in allowed}
    return bool(candidates & allowed)


def _grounding_refusal(ctx: ToolContext, tool: str, table: str) -> str | None:
    if _table_is_grounded(ctx, table):
        return None
    message = "Tool request refused because the table was not grounded in the current user request."
    ctx.trace.record(tool, "table=[REDACTED]", 0, "refused", output_summary=message)
    return message


def _append_suggestions(payload: dict, suggestions: list[str]) -> dict:
    if suggestions:
        payload["suggestions"] = suggestions
    return payload


def _check_live_query_cap(ctx: ToolContext) -> str | None:
    if ctx.live_query_count >= settings.agent_max_live_queries:
        return (
            f"Live query cap reached ({settings.agent_max_live_queries} queries per run). "
            "Use catalog tools or answer with what you have."
        )
    return None


def _run_live_query(ctx: ToolContext, sql: str, *, row_limit: int = 500, skip_row_limit_wrap: bool = False):
    cap_msg = _check_live_query_cap(ctx)
    if cap_msg:
        return None, cap_msg
    is_safe, reason = validate_query(sql)
    if not is_safe:
        return None, reason or "SQL validation failed."
    ctx.live_query_count += 1
    result = guarded_execute_query(
        ctx.user_id,
        ctx.engine,
        sql,
        row_limit=row_limit,
        connection_id=ctx.connection_id,
        readonly=True,
        skip_row_limit_wrap=skip_row_limit_wrap,
        timeout_seconds=settings.agent_query_timeout_seconds,
        cancellation_token=ctx.cancellation_token,
    )
    return result, None


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _qualified_table_name(table: CatalogTable) -> str:
    base = table.name.split(".")[-1]
    if table.schema_name:
        return f"{_quote_identifier(table.schema_name)}.{_quote_identifier(base)}"
    if "." in table.name:
        schema_part, table_part = table.name.rsplit(".", 1)
        return f"{_quote_identifier(schema_part)}.{_quote_identifier(table_part)}"
    return _quote_identifier(base)


def _sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _resolve_filter_column(table: CatalogTable, column_name: str) -> CatalogColumn | None:
    lowered = column_name.strip().lower()
    for col in table.columns:
        if col.name.lower() == lowered:
            return col
    return None


def _build_run_count_where(table: CatalogTable, filters: list | None, conjunction: str) -> tuple[str, str | None]:
    if not filters:
        return "", None
    if len(filters) > 5:
        return "", "run_count accepts at most 5 structured filters."
    joiner = conjunction.strip().upper() if conjunction else "AND"
    if joiner not in {"AND", "OR"}:
        return "", "run_count conjunction must be AND or OR."

    allowed_ops = {"=", "!=", ">", ">=", "<", "<=", "like", "ilike", "is_null", "is_not_null"}
    clauses: list[str] = []
    for raw_filter in filters:
        if isinstance(raw_filter, BaseModel):
            item = raw_filter.model_dump()
        else:
            item = dict(raw_filter or {})
        col = _resolve_filter_column(table, str(item.get("column", "")))
        if not col:
            return "", f"Unknown filter column: {item.get('column')}"
        if col.is_sensitive:
            return "", f"Column {table.name}.{col.name} is marked sensitive and cannot be used in run_count filters."
        op = str(item.get("operator", "=")).strip().lower()
        if op not in allowed_ops:
            return "", f"Unsupported run_count operator: {op}"
        quoted = _quote_identifier(col.name)
        if op == "is_null":
            clauses.append(f"{quoted} IS NULL")
            continue
        if op == "is_not_null":
            clauses.append(f"{quoted} IS NOT NULL")
            continue
        value = item.get("value")
        if value is None:
            return "", f"Operator {op} requires a non-null value."
        sql_op = "<>" if op == "!=" else op.upper() if op in {"like", "ilike"} else op
        clauses.append(f"{quoted} {sql_op} {_sql_literal(value)}")
    return " WHERE " + f" {joiner} ".join(clauses), None


def _build_sample_values_sql(table: CatalogTable, column: CatalogColumn, limit: int = SAMPLE_QUERY_LIMIT) -> str:
    qualified = _qualified_table_name(table)
    quoted_col = _quote_identifier(column.name)
    return (
        f"SELECT DISTINCT {quoted_col} FROM {qualified} "
        f"WHERE {quoted_col} IS NOT NULL ORDER BY {quoted_col} LIMIT {limit}"
    )


def _truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    marker = "\n[truncated]"
    keep = max(0, max_chars - len(marker))
    return text[:keep] + marker, True


def _truncate_value(value: object, max_chars: int) -> object:
    if value is None:
        return None
    text = str(value)
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 3)] + "..."


def _compact_rows(rows: list[dict], max_cell_chars: int) -> list[dict]:
    compact: list[dict] = []
    for row in rows:
        compact.append({key: _truncate_value(val, max_cell_chars) for key, val in row.items()})
    return compact


def _cap_tool_output(text: str, max_chars: int) -> tuple[str, bool]:
    return _truncate_text(text, max_chars)


def _json_tool_response(payload: dict, max_chars: int) -> tuple[str, bool]:
    text = json.dumps(payload)
    if len(text) <= max_chars:
        return text, False

    shrunk = dict(payload)
    if "preview_rows" in shrunk:
        preview = shrunk.get("preview_rows") or []
        while preview and len(json.dumps(shrunk)) > max_chars:
            preview = preview[:-1]
            shrunk["preview_rows"] = preview
            shrunk["truncated"] = True
        if len(json.dumps(shrunk)) > max_chars:
            shrunk = {
                "success": payload.get("success"),
                "message": "Output truncated due to size limit.",
                "truncated": True,
            }
    elif "values" in shrunk:
        values = shrunk.get("values") or []
        while values and len(json.dumps(shrunk)) > max_chars:
            values = values[:-1]
            shrunk["values"] = values
            shrunk["truncated"] = True
        if len(json.dumps(shrunk)) > max_chars:
            shrunk = {"message": "Output truncated due to size limit.", "truncated": True}
    else:
        shrunk = {"message": "Output truncated due to size limit.", "truncated": True}

    return json.dumps(shrunk), True


def _sort_tables_for_listing(tables: list[CatalogTable]) -> list[CatalogTable]:
    return sorted(tables, key=lambda table: (table.is_internal, -table.importance_score, table.name.lower()))


def _classify_execution_error(error: str) -> str:
    lower = error.lower()
    if "does not exist" in lower and "relation" in lower:
        return "missing_table"
    if "column" in lower and "does not exist" in lower:
        return "missing_column"
    if "syntax error" in lower:
        return "syntax_error"
    if "timeout" in lower or "timed out" in lower:
        return "timeout"
    if "permission denied" in lower:
        return "permission_denied"
    return "unknown"


def _maybe_refresh_on_drift(ctx: ToolContext, error: str, sql: str) -> str | None:
    if ctx.drift_refresh_used or not ctx.invalidate_catalog or not ctx.rebuild_catalog:
        return None
    error_class = _classify_execution_error(error)
    if error_class not in {"missing_table", "missing_column"}:
        return None
    identifiers = set(re.findall(r'"([^"]+)"', error)) | set(re.findall(r"'([^']+)'", error))
    catalog_names = {t.name for t in ctx.catalog.tables} | {
        t.name.split(".")[-1] for t in ctx.catalog.tables
    }
    if not identifiers & catalog_names:
        return None
    ctx.drift_refresh_used = True
    ctx.invalidate_catalog()
    rebuilt = ctx.rebuild_catalog()
    if rebuilt:
        ctx.catalog = rebuilt
        return "Schema catalog was refreshed due to a possible schema drift. Retry with updated table names."
    return None


def build_tools(ctx: ToolContext) -> list[StructuredTool]:
    preview_rows = settings.agent_preview_rows
    max_tables = settings.agent_max_tables_per_call
    max_output_chars = settings.agent_tool_output_chars
    max_tables_listed = settings.agent_max_tables_listed
    max_columns = settings.agent_max_columns_per_table
    max_cell_chars = settings.agent_max_cell_chars

    def list_tables() -> str:
        started = time.monotonic()
        if ctx.enforce_grounding and not ctx.allow_broad_discovery:
            message = "Table listing is allowed only for explicit schema or broad analytical discovery."
            ctx.trace.record("list_tables", "{}", (time.monotonic() - started) * 1000, "refused", output_summary=message)
            return message
        sorted_tables = _sort_tables_for_listing(ctx.catalog.tables)
        total = len(sorted_tables)
        shown = sorted_tables[:max_tables_listed]
        lines = []
        for table in shown:
            flag = " [internal]" if table.is_internal else ""
            estimate = table.row_estimate if table.row_estimate is not None else "?"
            lines.append(f"- {table.name} (~{estimate} rows){flag}")
        if total > len(shown):
            lines.append(
                f"Output truncated. Showing {len(shown)} of {total} tables. "
                "Use search_schema for targeted lookup."
            )
        body = "\n".join(lines) if lines else "No tables in catalog."
        output, truncated = _cap_tool_output(body, max_output_chars)
        outcome = "truncated" if truncated or total > len(shown) else "ok"
        ctx.trace.record("list_tables", "{}", (time.monotonic() - started) * 1000, outcome)
        return output

    def search_schema(query: str) -> str:
        started = time.monotonic()
        if ctx.enforce_grounding:
            allowed_terms = expand_terms(list(ctx.grounded_terms))
            query_terms = set(tokenize(query))
            if not query_terms or not (query_terms & allowed_terms):
                message = "Schema search terms must be grounded in the current user request."
                ctx.trace.record("search_schema", "query=[REDACTED]", (time.monotonic() - started) * 1000, "refused", output_summary=message)
                return message
        scored = score_tables(query, ctx.catalog, top_k=8)
        if not scored:
            ctx.trace.record(
                "search_schema",
                summarize_args("search_schema", {"query": query}),
                (time.monotonic() - started) * 1000,
                "ok",
            )
            return "No matching tables found."
        lines = []
        for item in scored:
            ctx.matched_tables.add(item.name)
            cols = f" columns={item.matched_columns}" if item.matched_columns else ""
            lines.append(f"- {item.name} (score={item.score}): {item.reason}{cols}")
        body = "\n".join(lines)
        output, truncated = _cap_tool_output(body, max_output_chars)
        ctx.trace.record(
            "search_schema",
            summarize_args("search_schema", {"query": query}),
            (time.monotonic() - started) * 1000,
            "truncated" if truncated else "ok",
        )
        return output

    def get_table_schema(table_names: list[str]) -> str:
        started = time.monotonic()
        parts: list[str] = []
        unknown: list[str] = []
        ignored: list[str] = []
        truncated_tables = len(table_names) > max_tables
        selected_names = table_names[:max_tables]
        if truncated_tables:
            ignored = table_names[max_tables:]
        column_cap_hit = False
        for name in selected_names:
            refusal = _grounding_refusal(ctx, "get_table_schema", name)
            if refusal:
                parts.append(refusal)
                continue
            table = catalog_table_by_name(ctx.catalog, name)
            if not table:
                unknown.append(name)
                continue
            ctx.inspected_tables.add(table.name)
            lines = [f"Table: {table.name}"]
            if table.row_estimate is not None:
                lines.append(f"  row_estimate: {table.row_estimate}")
            columns = table.columns[:max_columns]
            truncated_columns = len(table.columns) > max_columns
            if truncated_columns:
                column_cap_hit = True
            for col in columns:
                tags = []
                if col.primary_key:
                    tags.append("PK")
                if col.fk_referred_table:
                    tags.append(f"FK->{col.fk_referred_table}.{col.fk_referred_column}")
                if col.is_sensitive:
                    tags.append("sensitive")
                sample_str = f" values={col.sample_values}" if col.sample_values else ""
                tag_str = f" ({', '.join(tags)})" if tags else ""
                lines.append(f"  - {col.name}: {col.type} [{col.semantic_type}]{tag_str}{sample_str}")
            if truncated_columns:
                lines.append(
                    f"  ... {len(table.columns) - max_columns} more columns omitted. "
                    "Use get_sample_values for enum-like columns."
                )
            parts.append("\n".join(lines))
        if ignored:
            parts.append(f"Ignored extra requested tables: {', '.join(ignored)}")
        if unknown:
            suggestions = _suggest_similar(unknown[0], _catalog_table_names(ctx.catalog)) if len(unknown) == 1 else []
            unknown_line = f"Unknown tables: {', '.join(unknown)}"
            if suggestions:
                unknown_line += f". Did you mean: {', '.join(suggestions)}?"
            parts.append(unknown_line)
        body = "\n\n".join(parts) if parts else "No tables found."
        output, truncated = _cap_tool_output(body, max_output_chars)
        outcome = "error" if not parts else "truncated" if truncated or truncated_tables or column_cap_hit else "ok"
        ctx.trace.record(
            "get_table_schema",
            summarize_args("get_table_schema", {"table_names": table_names}),
            (time.monotonic() - started) * 1000,
            outcome,
        )
        return output

    def get_sample_values(table: str, column: str) -> str:
        started = time.monotonic()
        refusal = _grounding_refusal(ctx, "get_sample_values", table)
        if refusal:
            return refusal
        table_obj = catalog_table_by_name(ctx.catalog, table)
        if not table_obj:
            ctx.trace.record(
                "get_sample_values",
                summarize_args("get_sample_values", {"table": table, "column": column}),
                (time.monotonic() - started) * 1000,
                "error",
            )
            return f"Unknown table: {table}"
        col_obj = next((c for c in table_obj.columns if c.name.lower() == column.lower()), None)
        if not col_obj:
            ctx.trace.record(
                "get_sample_values",
                summarize_args("get_sample_values", {"table": table, "column": column}),
                (time.monotonic() - started) * 1000,
                "error",
            )
            return f"Unknown column: {table}.{column}"
        if col_obj.is_sensitive:
            ctx.trace.record(
                "get_sample_values",
                summarize_args("get_sample_values", {"table": table, "column": column}),
                (time.monotonic() - started) * 1000,
                "refused",
            )
            return f"Column {table_obj.name}.{col_obj.name} is marked sensitive; sample values are not available."
        if col_obj.sample_values:
            values = [
                _truncate_value(value, max_cell_chars)
                for value in col_obj.sample_values[:SAMPLE_MAX_VALUES]
            ]
            payload = {"values": values}
            output, truncated = _json_tool_response(payload, max_output_chars)
            ctx.trace.record(
                "get_sample_values",
                summarize_args("get_sample_values", {"table": table, "column": column}),
                (time.monotonic() - started) * 1000,
                "truncated" if truncated else "ok",
            )
            return output
        if col_obj.semantic_type not in {"category", "boolean"}:
            ctx.trace.record(
                "get_sample_values",
                summarize_args("get_sample_values", {"table": table, "column": column}),
                (time.monotonic() - started) * 1000,
                "refused",
            )
            return f"Column {table_obj.name}.{col_obj.name} is not eligible for live sampling (not enum-like)."
        sql = _build_sample_values_sql(table_obj, col_obj)
        result, error = _run_live_query(ctx, sql, row_limit=SAMPLE_QUERY_LIMIT)
        if error:
            ctx.trace.record(
                "get_sample_values",
                summarize_args("get_sample_values", {"table": table, "column": column}),
                (time.monotonic() - started) * 1000,
                "error",
            )
            return f"Could not fetch sample values: {error}"
        assert result is not None
        if not result.success:
            ctx.trace.record(
                "get_sample_values",
                summarize_args("get_sample_values", {"table": table, "column": column}),
                (time.monotonic() - started) * 1000,
                "error",
            )
            return f"Could not fetch sample values: {result.error or 'query failed'}"
        if not result.columns:
            ctx.trace.record(
                "get_sample_values",
                summarize_args("get_sample_values", {"table": table, "column": column}),
                (time.monotonic() - started) * 1000,
                "error",
            )
            return "Could not fetch sample values: no columns returned."
        column_name = result.columns[0]
        raw_values = [row.get(column_name) for row in result.rows if row.get(column_name) is not None]
        if len(raw_values) > SAMPLE_MAX_VALUES:
            ctx.trace.record(
                "get_sample_values",
                summarize_args("get_sample_values", {"table": table, "column": column}),
                (time.monotonic() - started) * 1000,
                "refused",
            )
            return (
                f"Column {table_obj.name}.{col_obj.name} appears high-cardinality; "
                "live sample values are not available."
            )
        values = [_truncate_value(value, max_cell_chars) for value in raw_values[:SAMPLE_MAX_VALUES]]
        payload = {"values": values}
        output, truncated = _json_tool_response(payload, max_output_chars)
        ctx.trace.record(
            "get_sample_values",
            summarize_args("get_sample_values", {"table": table, "column": column}),
            (time.monotonic() - started) * 1000,
            "truncated" if truncated else "ok",
        )
        return output

    def validate_sql_tool(sql: str) -> str:
        started = time.monotonic()
        is_safe, reason = validate_query(sql)
        outcome = "ok" if is_safe else "error"
        ctx.trace.record(
            "validate_sql",
            summarize_args("validate_sql", {"sql": sql}),
            (time.monotonic() - started) * 1000,
            outcome,
        )
        return json.dumps({"valid": is_safe, "reason": reason or "OK"})

    def execute_sql_tool(sql: str) -> str:
        started = time.monotonic()
        if ctx.analysis_query_count >= settings.agent_max_analysis_queries:
            message = (
                f"Analysis-query cap reached ({settings.agent_max_analysis_queries} per run). "
                "Finish with a successful result already available or explain the limitation."
            )
            ctx.trace.record(
                "execute_sql",
                summarize_args("execute_sql", {"sql": sql}),
                (time.monotonic() - started) * 1000,
                "refused",
                output_summary=message,
                error_class="query_budget_exhausted",
            )
            return json.dumps({"success": False, "error": message, "error_class": "query_budget_exhausted"})
        ctx.analysis_query_count += 1
        cap_msg = _check_live_query_cap(ctx)
        if cap_msg:
            ctx.trace.record(
                "execute_sql",
                summarize_args("execute_sql", {"sql": sql}),
                (time.monotonic() - started) * 1000,
                "error",
                error_class="live_query_cap_reached",
            )
            return json.dumps({"success": False, "error": cap_msg})
        is_safe, reason = validate_query(sql)
        if not is_safe:
            ctx.trace.record(
                "execute_sql",
                summarize_args("execute_sql", {"sql": sql}),
                (time.monotonic() - started) * 1000,
                "refused",
                output_summary=reason or "SQL did not pass read-only validation.",
                error_class="unsafe_query",
            )
            return json.dumps({"success": False, "error": reason})
        semantic_policy_refs: list[str] = []
        if ctx.semantic_context is not None:
            semantic_policy = validate_ai_semantic_policy(sql, ctx.semantic_context)
            if not semantic_policy.allowed:
                message = semantic_policy.reason or "SQL violated the semantic data policy."
                ctx.trace.record(
                    "execute_sql",
                    summarize_args("execute_sql", {"sql": sql}),
                    (time.monotonic() - started) * 1000,
                    "refused",
                    output_summary=message,
                    error_class="semantic_policy_rejected",
                )
                return json.dumps({"success": False, "error": message, "error_class": "semantic_policy_rejected"})
            semantic_policy_refs = list(semantic_policy.enforced_references)
        if ctx.enforce_grounding and not ctx.allow_broad_discovery:
            try:
                sql_tables = referenced_tables(sql)
            except Exception:
                message = "SQL relevance could not be verified."
                ctx.trace.record(
                    "execute_sql",
                    summarize_args("execute_sql", {"sql": sql}),
                    (time.monotonic() - started) * 1000,
                    "refused",
                    output_summary=message,
                    error_class="schema_relevance_rejected",
                )
                return json.dumps({"success": False, "error": message, "error_class": "schema_relevance_rejected"})
            allowed = {item.casefold() for item in ctx.matched_tables | ctx.inspected_tables}
            allowed |= {f"public.{item}" for item in allowed if "." not in item}
            if any(table.casefold() not in allowed for table in sql_tables):
                message = "SQL references a table unsupported by the current request."
                ctx.trace.record(
                    "execute_sql",
                    summarize_args("execute_sql", {"sql": sql}),
                    (time.monotonic() - started) * 1000,
                    "refused",
                    output_summary=message,
                    error_class="schema_relevance_rejected",
                )
                return json.dumps({"success": False, "error": message, "error_class": "schema_relevance_rejected"})
        ctx.live_query_count += 1
        result = execute_query(
            ctx.user_id,
            ctx.engine,
            sql,
            row_limit=500,
            connection_id=ctx.connection_id,
            readonly=True,
            timeout_seconds=settings.agent_query_timeout_seconds,
            cancellation_token=ctx.cancellation_token,
        )
        if not result.success:
            drift_note = _maybe_refresh_on_drift(ctx, result.error or "", sql)
            error_class = _classify_execution_error(result.error or "")
            ctx.trace.record(
                "execute_sql",
                summarize_args("execute_sql", {"sql": sql}),
                (time.monotonic() - started) * 1000,
                "error",
                error_class=error_class,
            )
            payload = {
                "success": False,
                "error": result.error,
                "error_class": error_class,
            }
            if error_class == "missing_table":
                identifiers = re.findall(r'"([^"]+)"', result.error or "")
                suggestions: list[str] = []
                for ident in identifiers:
                    suggestions.extend(_suggest_similar(ident, _catalog_table_names(ctx.catalog)))
                payload = _append_suggestions(payload, list(dict.fromkeys(suggestions))[:5])
            elif error_class == "missing_column":
                identifiers = re.findall(r'"([^"]+)"', result.error or "")
                suggestions = []
                for ident in identifiers:
                    suggestions.extend(_suggest_similar(ident, _catalog_column_names(ctx.catalog)))
                payload = _append_suggestions(payload, list(dict.fromkeys(suggestions))[:5])
            if drift_note:
                payload["note"] = drift_note
            return json.dumps(payload)
        ctx.last_execution = result
        ctx.last_executed_sql = sql
        result_ref = f"result_{len(ctx.analysis_results) + 1}"
        ctx.analysis_results[result_ref] = AnalysisExecution(
            result_ref=result_ref,
            sql=sql,
            result=result,
            semantic_policy_refs=semantic_policy_refs,
        )
        preview = _compact_rows(result.rows[: settings.agent_result_preview_rows], max_cell_chars)
        truncated_flag = (
            result.truncated
            or result.row_count > len(preview)
            or any(len(str(value)) > max_cell_chars for row in result.rows[:preview_rows] for value in row.values())
        )
        payload = {
            "success": True,
            "result_ref": result_ref,
            "columns": result.columns,
            "preview_rows": preview,
            "row_count": result.row_count,
            "truncated": truncated_flag,
            "execution_time_ms": result.execution_time_ms,
        }
        output, json_truncated = _json_tool_response(payload, max_output_chars)
        if json_truncated:
            truncated_flag = True
        ctx.trace.record(
            "execute_sql",
            summarize_args("execute_sql", {"sql": sql}),
            (time.monotonic() - started) * 1000,
            "truncated" if truncated_flag else "ok",
            output_summary=f"Stored bounded result as {result_ref}.",
            output_row_count=result.row_count,
        )
        return output

    def get_relationships(table_names: list[str]) -> str:
        started = time.monotonic()
        selected = table_names[:max_tables]
        lines: list[str] = []
        unknown: list[str] = []
        for name in selected:
            refusal = _grounding_refusal(ctx, "get_relationships", name)
            if refusal:
                lines.append(refusal)
                continue
            table = catalog_table_by_name(ctx.catalog, name)
            if not table:
                unknown.append(name)
                continue
            ctx.inspected_tables.add(table.name)
            lines.append(f"Table: {table.name}")
            for col in table.columns:
                if col.fk_referred_table:
                    ctx.matched_tables.add(col.fk_referred_table)
                    lines.append(
                        f"  outbound: {col.name} -> {col.fk_referred_table}.{col.fk_referred_column}"
                    )
            for other in ctx.catalog.tables:
                for col in other.columns:
                    if col.fk_referred_table and col.fk_referred_table.lower() in {
                        table.name.lower(),
                        table.name.split(".")[-1].lower(),
                    }:
                        ctx.matched_tables.add(other.name)
                        lines.append(f"  inbound: {other.name}.{col.name} -> {table.name}.{col.fk_referred_column}")
        if unknown:
            lines.append(f"Unknown tables: {', '.join(unknown)}")
        body = "\n".join(lines) if lines else "No relationships found."
        output, truncated = _cap_tool_output(body, max_output_chars)
        ctx.trace.record(
            "get_relationships",
            summarize_args("get_relationships", {"table_names": table_names}),
            (time.monotonic() - started) * 1000,
            "truncated" if truncated else "ok",
        )
        return output

    def note(text: str) -> str:
        started = time.monotonic()
        trimmed = text.strip()[:500]
        if not trimmed:
            ctx.trace.record("note", summarize_args("note", {"text": text}), (time.monotonic() - started) * 1000, "error")
            return "Note text cannot be empty."
        if len(ctx.scratchpad) >= settings.agent_max_notes:
            ctx.trace.record("note", summarize_args("note", {"text": text}), (time.monotonic() - started) * 1000, "error")
            return "Scratchpad is full for this run."
        ctx.scratchpad.append(trimmed)
        ctx.trace.record("note", summarize_args("note", {"text": trimmed}), (time.monotonic() - started) * 1000, "ok")
        return json.dumps({"saved": True, "notes_count": len(ctx.scratchpad)})

    def preview_table(table: str) -> str:
        started = time.monotonic()
        refusal = _grounding_refusal(ctx, "preview_table", table)
        if refusal:
            return json.dumps({"success": False, "error": refusal})
        table_obj = catalog_table_by_name(ctx.catalog, table)
        if not table_obj:
            suggestions = _suggest_similar(table, _catalog_table_names(ctx.catalog))
            payload = {"success": False, "error": f"Unknown table: {table}"}
            payload = _append_suggestions(payload, suggestions)
            ctx.trace.record("preview_table", summarize_args("preview_table", {"table": table}), (time.monotonic() - started) * 1000, "error")
            return json.dumps(payload)
        safe_columns = [col for col in table_obj.columns if not col.is_sensitive]
        if not safe_columns:
            ctx.trace.record("preview_table", summarize_args("preview_table", {"table": table}), (time.monotonic() - started) * 1000, "refused")
            return json.dumps({"success": False, "error": f"Table {table_obj.name} has no non-sensitive columns available to preview."})
        select_list = ", ".join(_quote_identifier(col.name) for col in safe_columns[:max_columns])
        sql = f"SELECT {select_list} FROM {_qualified_table_name(table_obj)} LIMIT 5"
        result, error = _run_live_query(ctx, sql, row_limit=5)
        if error:
            ctx.trace.record("preview_table", summarize_args("preview_table", {"table": table}), (time.monotonic() - started) * 1000, "error")
            return json.dumps({"success": False, "error": error})
        assert result is not None
        if not result.success:
            ctx.trace.record("preview_table", summarize_args("preview_table", {"table": table}), (time.monotonic() - started) * 1000, "error")
            return json.dumps({"success": False, "error": result.error})
        sensitive = {col.name.lower() for col in table_obj.columns if col.is_sensitive}
        preview = []
        for row in result.rows:
            masked = {}
            for key, value in row.items():
                masked[key] = "[redacted]" if key.lower() in sensitive else _truncate_value(value, max_cell_chars)
            preview.append(masked)
        payload = {"success": True, "columns": result.columns, "preview_rows": preview}
        output, truncated = _json_tool_response(payload, max_output_chars)
        ctx.trace.record(
            "preview_table",
            summarize_args("preview_table", {"table": table}),
            (time.monotonic() - started) * 1000,
            "truncated" if truncated else "ok",
        )
        return output

    def profile_table(table: str) -> str:
        started = time.monotonic()
        refusal = _grounding_refusal(ctx, "profile_table", table)
        if refusal:
            return json.dumps({"success": False, "error": refusal})
        table_obj = catalog_table_by_name(ctx.catalog, table)
        if not table_obj:
            ctx.trace.record("profile_table", summarize_args("profile_table", {"table": table}), (time.monotonic() - started) * 1000, "error")
            return json.dumps({"success": False, "error": f"Unknown table: {table}"})
        if table_obj.row_estimate and table_obj.row_estimate > settings.agent_profile_row_estimate_cap:
            ctx.trace.record("profile_table", summarize_args("profile_table", {"table": table}), (time.monotonic() - started) * 1000, "refused")
            return json.dumps(
                {
                    "success": False,
                    "error": (
                        f"Table {table_obj.name} is too large to profile live "
                        f"(~{table_obj.row_estimate} rows). Use catalog row_estimate instead."
                    ),
                }
            )
        profile_columns = [
            col for col in table_obj.columns if not col.is_sensitive
        ][: settings.agent_profile_max_columns]
        select_parts = ["COUNT(*) AS total_rows"]
        for col in profile_columns:
            quoted = _quote_identifier(col.name)
            select_parts.append(f"COUNT({quoted}) AS {col.name}__non_null")
            select_parts.append(f"COUNT(DISTINCT {quoted}) AS {col.name}__distinct")
        sql = f"SELECT {', '.join(select_parts)} FROM {_qualified_table_name(table_obj)}"
        result, error = _run_live_query(ctx, sql, row_limit=1, skip_row_limit_wrap=True)
        if error:
            ctx.trace.record("profile_table", summarize_args("profile_table", {"table": table}), (time.monotonic() - started) * 1000, "error")
            return json.dumps({"success": False, "error": error})
        assert result is not None
        if not result.success:
            ctx.trace.record("profile_table", summarize_args("profile_table", {"table": table}), (time.monotonic() - started) * 1000, "error")
            return json.dumps({"success": False, "error": result.error})
        payload = {"success": True, "table": table_obj.name, "profile": result.rows[0] if result.rows else {}}
        output, truncated = _json_tool_response(payload, max_output_chars)
        ctx.trace.record(
            "profile_table",
            summarize_args("profile_table", {"table": table}),
            (time.monotonic() - started) * 1000,
            "truncated" if truncated else "ok",
        )
        return output

    def run_count(table: str, filters: list[RunCountFilterInput] | None = None, conjunction: str = "AND") -> str:
        started = time.monotonic()
        args_summary = summarize_args("run_count", {"table": table, "filters": filters or [], "conjunction": conjunction})
        refusal = _grounding_refusal(ctx, "run_count", table)
        if refusal:
            return json.dumps({"success": False, "error": refusal})
        table_obj = catalog_table_by_name(ctx.catalog, table)
        if not table_obj:
            ctx.trace.record("run_count", args_summary, (time.monotonic() - started) * 1000, "error")
            return json.dumps({"success": False, "error": f"Unknown table: {table}"})
        where_sql, filter_error = _build_run_count_where(table_obj, filters, conjunction)
        if filter_error:
            ctx.trace.record("run_count", args_summary, (time.monotonic() - started) * 1000, "refused")
            return json.dumps({"success": False, "error": filter_error})
        sql = f"SELECT COUNT(*) AS row_count FROM {_qualified_table_name(table_obj)}{where_sql}"
        result, error = _run_live_query(ctx, sql, row_limit=1, skip_row_limit_wrap=True)
        if error:
            ctx.trace.record("run_count", args_summary, (time.monotonic() - started) * 1000, "error")
            return json.dumps({"success": False, "error": error})
        assert result is not None
        if not result.success:
            ctx.trace.record("run_count", args_summary, (time.monotonic() - started) * 1000, "error")
            return json.dumps({"success": False, "error": result.error})
        payload = {"success": True, "row_count": result.rows[0].get("row_count") if result.rows else 0}
        ctx.trace.record("run_count", args_summary, (time.monotonic() - started) * 1000, "ok")
        return json.dumps(payload)

    def explain_sql_tool(sql: str) -> str:
        started = time.monotonic()
        if ctx.catalog.db_type != "postgresql":
            ctx.trace.record("explain_sql", summarize_args("explain_sql", {"sql": sql}), (time.monotonic() - started) * 1000, "error")
            return json.dumps({"success": False, "error": "EXPLAIN is only supported for PostgreSQL connections."})
        explain_sql = f"EXPLAIN {sql.rstrip(';').strip()}"
        result, error = _run_live_query(ctx, explain_sql, row_limit=100, skip_row_limit_wrap=True)
        if error:
            ctx.trace.record("explain_sql", summarize_args("explain_sql", {"sql": sql}), (time.monotonic() - started) * 1000, "error")
            return json.dumps({"success": False, "error": error})
        assert result is not None
        if not result.success:
            ctx.trace.record("explain_sql", summarize_args("explain_sql", {"sql": sql}), (time.monotonic() - started) * 1000, "error")
            return json.dumps({"success": False, "error": result.error})
        payload = {"success": True, "plan": result.rows[:20], "columns": result.columns}
        output, truncated = _json_tool_response(payload, max_output_chars)
        ctx.trace.record(
            "explain_sql",
            summarize_args("explain_sql", {"sql": sql}),
            (time.monotonic() - started) * 1000,
            "truncated" if truncated else "ok",
        )
        return output

    return [
        StructuredTool.from_function(list_tables, name="list_tables", description="List all tables with row estimates."),
        StructuredTool.from_function(
            search_schema,
            name="search_schema",
            description="Search schema catalog for relevant tables and columns.",
            args_schema=SearchSchemaInput,
        ),
        StructuredTool.from_function(
            get_table_schema,
            name="get_table_schema",
            description="Get detailed schema for one or more tables.",
            args_schema=GetTableSchemaInput,
        ),
        StructuredTool.from_function(
            get_sample_values,
            name="get_sample_values",
            description="Get distinct sample values for an enum-like column.",
            args_schema=TableColumnInput,
        ),
        StructuredTool.from_function(
            validate_sql_tool,
            name="validate_sql",
            description="Validate SQL is safe and read-only.",
            args_schema=SqlInput,
        ),
        StructuredTool.from_function(
            execute_sql_tool,
            name="execute_sql",
            description=(
                "Execute one grounded, validated, read-only analytical SQL query and return a bounded result preview. "
                "Use the returned result_ref in the final data_analysis outcome."
            ),
            args_schema=SqlInput,
        ),
        StructuredTool.from_function(
            get_relationships,
            name="get_relationships",
            description="Show foreign-key relationships for up to N tables.",
            args_schema=GetTableSchemaInput,
        ),
        StructuredTool.from_function(
            note,
            name="note",
            description="Save a finding to the run scratchpad for later steps.",
            args_schema=NoteInput,
        ),
        StructuredTool.from_function(
            preview_table,
            name="preview_table",
            description="Preview up to 5 rows from a table with sensitive columns redacted.",
            args_schema=TableNameInput,
        ),
        StructuredTool.from_function(
            profile_table,
            name="profile_table",
            description="Profile null and distinct counts for a table.",
            args_schema=TableNameInput,
        ),
        StructuredTool.from_function(
            run_count,
            name="run_count",
            description="Count rows in a table using structured filters only; raw SQL WHERE clauses are not accepted.",
            args_schema=RunCountInput,
        ),
        StructuredTool.from_function(
            explain_sql_tool,
            name="explain_sql",
            description="Run EXPLAIN on validated SQL without executing it.",
            args_schema=SqlInput,
        ),
    ]


__all__ = [
    "AnalysisExecution",
    "ToolContext",
    "SAMPLE_MAX_VALUES",
    "SAMPLE_QUERY_LIMIT",
    "_build_sample_values_sql",
    "_qualified_table_name",
    "_quote_identifier",
    "_compact_rows",
    "_truncate_text",
    "_truncate_value",
    "_json_tool_response",
    "_suggest_similar",
    "_check_live_query_cap",
    "_run_live_query",
    "build_tools",
]
