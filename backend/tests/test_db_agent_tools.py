"""Tests for database agent tools."""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.agents.db_agent.tools import (
    SAMPLE_MAX_VALUES,
    ToolContext,
    _build_sample_values_sql,
    _qualified_table_name,
    _quote_identifier,
    build_tools,
)
from app.agents.schema_context.catalog import build_catalog
from app.agents.schema_context.types import CatalogColumn, CatalogTable, SchemaCatalog
from app.core.config import settings
from app.db.models.connection import ColumnInfo, TableInfo
from app.query_engine.results import QueryExecutionResult


def _catalog() -> SchemaCatalog:
    tables = [
        TableInfo(
            name="customers",
            row_count=10,
            columns=[
                ColumnInfo(name="id", type="uuid", nullable=False, primary_key=True),
                ColumnInfo(name="email", type="text", nullable=False, primary_key=False),
                ColumnInfo(name="status", type="text", nullable=True, primary_key=False, sample_values=["paid"]),
            ],
        )
    ]
    return build_catalog("conn-1", "postgresql", tables)


def _ctx(catalog: SchemaCatalog | None = None) -> ToolContext:
    engine = MagicMock()
    return ToolContext(
        user_id="user-1",
        connection_id="conn-1",
        catalog=catalog or _catalog(),
        engine=engine,
        trace=MagicMock(),
    )


def test_tool_list_registers_guarded_execute_sql():
    tools = {tool.name: tool for tool in build_tools(_ctx())}
    assert "execute_sql" in tools
    assert "validate_sql" in tools


def test_list_tables_returns_catalog_tables():
    tools = {tool.name: tool for tool in build_tools(_ctx())}
    output = tools["list_tables"].invoke({})
    assert "customers" in output


def test_search_schema_returns_matches():
    tools = {tool.name: tool for tool in build_tools(_ctx())}
    output = tools["search_schema"].invoke({"query": "customers email"})
    assert "customers" in output


def test_get_sample_values_refuses_sensitive_column():
    tools = {tool.name: tool for tool in build_tools(_ctx())}
    output = tools["get_sample_values"].invoke({"table": "customers", "column": "email"})
    assert "sensitive" in output.lower()


def test_get_sample_values_returns_catalog_samples_without_executor():
    tools = {tool.name: tool for tool in build_tools(_ctx())}
    with patch("app.agents.db_agent.tools.guarded_execute_query") as mock_execute:
        output = json.loads(tools["get_sample_values"].invoke({"table": "customers", "column": "status"}))
        mock_execute.assert_not_called()
    assert output["values"] == ["paid"]


@patch("app.agents.db_agent.tools.guarded_execute_query")
def test_get_sample_values_live_sampling_uses_guarded_executor(mock_execute):
    mock_execute.return_value = QueryExecutionResult(
        success=True,
        columns=["status"],
        rows=[{"status": "paid"}, {"status": "pending"}],
        row_count=2,
    )
    catalog = SchemaCatalog(
        connection_id="conn-1",
        db_type="postgresql",
        schema_hash="abc",
        captured_at="2026-01-01T00:00:00Z",
        tables=[
            CatalogTable(
                name="analytics.orders",
                schema_name="analytics",
                columns=[
                    CatalogColumn(name="status", type="text", semantic_type="category"),
                ],
            )
        ],
    )
    tools = {tool.name: tool for tool in build_tools(_ctx(catalog))}
    output = json.loads(tools["get_sample_values"].invoke({"table": "analytics.orders", "column": "status"}))
    mock_execute.assert_called_once()
    assert mock_execute.call_args.kwargs["connection_id"] == "conn-1"
    assert output["values"] == ["paid", "pending"]
    sql = mock_execute.call_args.args[2]
    assert '"analytics"."orders"' in sql
    assert '"status"' in sql


def test_build_sample_values_sql_quotes_identifiers():
    table = CatalogTable(name='weird"table', schema_name="public", columns=[])
    column = CatalogColumn(name='weird"col', type="text")
    sql = _build_sample_values_sql(table, column)
    assert sql.startswith("SELECT DISTINCT")
    assert _quote_identifier('weird"col') in sql
    assert _qualified_table_name(table) in sql


@patch("app.agents.db_agent.tools.guarded_execute_query")
def test_get_sample_values_refuses_high_cardinality(mock_execute):
    rows = [{"status": f"value-{index}"} for index in range(SAMPLE_MAX_VALUES + 1)]
    mock_execute.return_value = QueryExecutionResult(
        success=True,
        columns=["status"],
        rows=rows,
        row_count=len(rows),
    )
    catalog = SchemaCatalog(
        connection_id="conn-1",
        db_type="postgresql",
        schema_hash="abc",
        captured_at="2026-01-01T00:00:00Z",
        tables=[
            CatalogTable(
                name="orders",
                columns=[CatalogColumn(name="status", type="text", semantic_type="category")],
            )
        ],
    )
    tools = {tool.name: tool for tool in build_tools(_ctx(catalog))}
    output = tools["get_sample_values"].invoke({"table": "orders", "column": "status"})
    assert "high-cardinality" in output.lower()


@patch("app.agents.db_agent.tools.guarded_execute_query")
def test_get_sample_values_executor_failure_traces_error(mock_execute):
    mock_execute.return_value = QueryExecutionResult(success=False, error="permission denied")
    catalog = SchemaCatalog(
        connection_id="conn-1",
        db_type="postgresql",
        schema_hash="abc",
        captured_at="2026-01-01T00:00:00Z",
        tables=[
            CatalogTable(
                name="orders",
                columns=[CatalogColumn(name="status", type="text", semantic_type="category")],
            )
        ],
    )
    ctx = _ctx(catalog)
    tools = {tool.name: tool for tool in build_tools(ctx)}
    output = tools["get_sample_values"].invoke({"table": "orders", "column": "status"})
    assert "Could not fetch sample values" in output
    ctx.trace.record.assert_called()
    assert ctx.trace.record.call_args.args[3] == "error"


def test_validate_sql_blocks_destructive_query():
    tools = {tool.name: tool for tool in build_tools(_ctx())}
    output = json.loads(tools["validate_sql"].invoke({"sql": "DELETE FROM customers"}))
    assert output["valid"] is False


def test_list_tables_truncates_and_traces(monkeypatch):
    monkeypatch.setattr(settings, "agent_max_tables_listed", 1)
    tables = [
        TableInfo(name=f"table_{index}", row_count=index, columns=[])
        for index in range(3)
    ]
    catalog = build_catalog("conn-1", "postgresql", tables)
    ctx = _ctx(catalog)
    tools = {tool.name: tool for tool in build_tools(ctx)}
    output = tools["list_tables"].invoke({})
    assert "Output truncated" in output
    assert ctx.trace.record.call_args.args[3] == "truncated"


def test_get_table_schema_truncates_columns(monkeypatch):
    monkeypatch.setattr(settings, "agent_max_columns_per_table", 1)
    columns = [
        ColumnInfo(name=f"col_{index}", type="text", nullable=True, primary_key=False)
        for index in range(3)
    ]
    catalog = build_catalog(
        "conn-1",
        "postgresql",
        [TableInfo(name="wide", row_count=1, columns=columns)],
    )
    ctx = _ctx(catalog)
    tools = {tool.name: tool for tool in build_tools(ctx)}
    output = tools["get_table_schema"].invoke({"table_names": ["wide"]})
    assert "more columns omitted" in output
    assert ctx.trace.record.call_args.args[3] == "truncated"


def test_note_tool_saves_scratchpad():
    ctx = _ctx()
    tools = {tool.name: tool for tool in build_tools(ctx)}
    payload = json.loads(tools["note"].invoke({"text": "customers has status column"}))
    assert payload["saved"] is True
    assert ctx.scratchpad == ["customers has status column"]


def test_note_tool_refuses_when_scratchpad_full(monkeypatch):
    monkeypatch.setattr(settings, "agent_max_notes", 1)
    ctx = _ctx()
    tools = {tool.name: tool for tool in build_tools(ctx)}
    tools["note"].invoke({"text": "first"})
    output = tools["note"].invoke({"text": "second"})
    assert "full" in output.lower()


def test_get_relationships_returns_outbound_and_inbound_fk_info():
    from app.db.models.connection import ForeignKeyInfo

    catalog = build_catalog(
        "conn-1",
        "postgresql",
        [
            TableInfo(
                name="orders",
                columns=[
                    ColumnInfo(name="id", type="uuid", nullable=False, primary_key=True),
                    ColumnInfo(name="customer_id", type="uuid", nullable=False, primary_key=False),
                ],
                foreign_keys=[
                    ForeignKeyInfo(column="customer_id", referred_table="customers", referred_column="id"),
                ],
            ),
            TableInfo(
                name="customers",
                columns=[ColumnInfo(name="id", type="uuid", nullable=False, primary_key=True)],
            ),
        ],
    )
    tools = {tool.name: tool for tool in build_tools(_ctx(catalog))}
    outbound = tools["get_relationships"].invoke({"table_names": ["orders"]})
    inbound = tools["get_relationships"].invoke({"table_names": ["customers"]})
    assert "outbound" in outbound
    assert "customer_id -> customers.id" in outbound
    assert "inbound" in inbound
    assert "orders.customer_id -> customers.id" in inbound


@patch("app.agents.db_agent.tools.guarded_execute_query")
def test_preview_table_selects_non_sensitive_columns(mock_execute):
    mock_execute.return_value = QueryExecutionResult(
        success=True,
        columns=["status"],
        rows=[{"status": "paid"}],
        row_count=1,
    )
    ctx = _ctx()
    tools = {tool.name: tool for tool in build_tools(ctx)}
    payload = json.loads(tools["preview_table"].invoke({"table": "customers"}))
    sql = mock_execute.call_args.args[2]
    assert '"email"' not in sql
    assert '"status"' in sql
    assert payload["preview_rows"] == [{"status": "paid"}]


@patch("app.agents.db_agent.tools.guarded_execute_query")
def test_live_query_cap_blocks_preview_table(mock_execute, monkeypatch):
    monkeypatch.setattr(settings, "agent_max_live_queries", 0)
    ctx = _ctx()
    tools = {tool.name: tool for tool in build_tools(ctx)}
    payload = json.loads(tools["preview_table"].invoke({"table": "customers"}))
    assert payload["success"] is False
    mock_execute.assert_not_called()


def test_profile_table_refuses_huge_table(monkeypatch):
    monkeypatch.setattr(settings, "agent_profile_row_estimate_cap", 100)
    catalog = build_catalog(
        "conn-1",
        "postgresql",
        [TableInfo(name="events", row_count=1_000_000, columns=[ColumnInfo(name="id", type="bigint", nullable=False, primary_key=True)])],
    )
    tools = {tool.name: tool for tool in build_tools(_ctx(catalog))}
    payload = json.loads(tools["profile_table"].invoke({"table": "events"}))
    assert payload["success"] is False


def test_explain_sql_refuses_non_postgres():
    catalog = build_catalog("conn-1", "sqlite", [TableInfo(name="customers", columns=[])])
    tools = {tool.name: tool for tool in build_tools(_ctx(catalog))}
    payload = json.loads(tools["explain_sql"].invoke({"sql": "SELECT 1"}))
    assert payload["success"] is False


def test_get_table_schema_suggests_unknown_table():
    tools = {tool.name: tool for tool in build_tools(_ctx())}
    output = tools["get_table_schema"].invoke({"table_names": ["custmers"]})
    assert "Did you mean" in output or "Unknown tables" in output


@patch("app.agents.db_agent.tools.guarded_execute_query")
def test_run_count_uses_structured_filters(mock_execute):
    mock_execute.return_value = QueryExecutionResult(
        success=True,
        columns=["row_count"],
        rows=[{"row_count": 7}],
        row_count=1,
    )
    ctx = _ctx()
    tools = {tool.name: tool for tool in build_tools(ctx)}
    payload = json.loads(
        tools["run_count"].invoke(
            {
                "table": "customers",
                "filters": [{"column": "status", "operator": "=", "value": "paid"}],
            }
        )
    )
    sql = mock_execute.call_args.args[2]
    assert payload["row_count"] == 7
    assert 'WHERE "status" = ' in sql
    assert "paid" in sql


@patch("app.agents.db_agent.tools.guarded_execute_query")
def test_run_count_refuses_sensitive_filter(mock_execute):
    ctx = _ctx()
    tools = {tool.name: tool for tool in build_tools(ctx)}
    payload = json.loads(
        tools["run_count"].invoke(
            {
                "table": "customers",
                "filters": [{"column": "email", "operator": "=", "value": "secret@example.com"}],
            }
        )
    )
    assert payload["success"] is False
    assert "sensitive" in payload["error"].lower()
    mock_execute.assert_not_called()


