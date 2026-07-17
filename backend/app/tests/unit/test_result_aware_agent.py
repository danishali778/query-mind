import json

from app.agents.db_agent.agent import _policy_rejection_reason, _validated_chart
from app.agents.db_agent.output import ChatAgentOutcome
from app.agents.db_agent.tools import ToolContext, build_tools
from app.agents.db_agent.trace import TraceRecorder
from app.agents.schema_context.types import CatalogColumn, CatalogTable, SchemaCatalog
from app.agents.schema_context.user_semantics import SemanticContext
from app.query_engine.results import QueryExecutionResult


def _context() -> ToolContext:
    catalog = SchemaCatalog(
        connection_id="connection-1",
        db_type="postgresql",
        schema_hash="schema-1",
        captured_at="2026-07-17T00:00:00Z",
        tables=[
            CatalogTable(
                name="orders",
                schema_name="public",
                columns=[CatalogColumn(name="amount", type="numeric", semantic_type="currency")],
            )
        ],
    )
    return ToolContext(
        user_id="user-1",
        connection_id="connection-1",
        catalog=catalog,
        engine=object(),
        trace=TraceRecorder(),
        matched_tables={"orders", "public.orders"},
        enforce_grounding=True,
        semantic_context=SemanticContext(schema_hash="schema-1"),
    )


def test_existing_database_tools_are_preserved_and_execute_sql_is_registered():
    names = {tool.name for tool in build_tools(_context())}
    assert names == {
        "list_tables",
        "search_schema",
        "get_table_schema",
        "get_sample_values",
        "validate_sql",
        "execute_sql",
        "get_relationships",
        "note",
        "preview_table",
        "profile_table",
        "run_count",
        "explain_sql",
    }


def test_execute_sql_returns_stable_result_reference_and_keeps_authoritative_result(monkeypatch):
    ctx = _context()
    monkeypatch.setattr(
        "app.agents.db_agent.tools.execute_query",
        lambda *args, **kwargs: QueryExecutionResult(
            success=True,
            columns=["amount"],
            rows=[{"amount": 42}],
            row_count=1,
            execution_time_ms=3.5,
        ),
    )
    execute_tool = next(tool for tool in build_tools(ctx) if tool.name == "execute_sql")

    payload = json.loads(execute_tool.invoke({"sql": "SELECT amount FROM orders"}))

    assert payload["success"] is True
    assert payload["result_ref"] == "result_1"
    assert ctx.analysis_results["result_1"].sql == "SELECT amount FROM orders"
    assert ctx.analysis_results["result_1"].result.rows == [{"amount": 42}]
    serialized_trace = json.dumps(ctx.trace.to_list())
    assert '"amount": 42' not in serialized_trace
    assert "SELECT amount FROM orders" not in serialized_trace


def test_execute_sql_stops_after_three_attempts(monkeypatch):
    ctx = _context()
    monkeypatch.setattr(
        "app.agents.db_agent.tools.execute_query",
        lambda *args, **kwargs: QueryExecutionResult(
            success=True,
            columns=["amount"],
            rows=[{"amount": 1}],
            row_count=1,
        ),
    )
    execute_tool = next(tool for tool in build_tools(ctx) if tool.name == "execute_sql")

    for _ in range(3):
        assert json.loads(execute_tool.invoke({"sql": "SELECT amount FROM orders"}))["success"] is True
    blocked = json.loads(execute_tool.invoke({"sql": "SELECT amount FROM orders"}))

    assert blocked["success"] is False
    assert blocked["error_class"] == "query_budget_exhausted"


def test_chart_with_non_numeric_y_axis_downgrades_to_table():
    outcome = ChatAgentOutcome.model_validate(
        {
            "response_type": "data_analysis",
            "answer": "The results are listed by customer.",
            "result_ref": "result_1",
            "presentation": {
                "kind": "chart",
                "chart": {
                    "type": "bar",
                    "title": "Customers",
                    "x_column": "customer",
                    "y_columns": ["status"],
                    "tooltip_columns": [],
                },
            },
            "evidence": [
                {
                    "claim": "The first customer is active.",
                    "result_ref": "result_1",
                    "columns": ["customer", "status"],
                    "row_indexes": [0],
                }
            ],
            "method": "Listed the returned records.",
            "relevant_tables": ["customers"],
            "relevant_columns": ["customers.status"],
        }
    )

    kind, chart = _validated_chart(
        outcome,
        ["customer", "status"],
        [{"customer": "Acme", "status": "active"}],
    )

    assert kind == "table"
    assert chart is None


def test_sql_policy_rejection_is_not_eligible_for_emergency_fallback():
    trace = TraceRecorder()
    trace.record(
        "execute_sql",
        "sql_chars=29",
        1.0,
        "refused",
        error_class="connection_scope_violation",
    )

    assert _policy_rejection_reason(trace) == "connection_scope_violation"
