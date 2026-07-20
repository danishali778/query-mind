import json

from app.agents.db_agent.agent import _outcome_to_result, _policy_rejection_reason, _validated_chart
from app.agents.db_agent.budget import BudgetGuard
from app.agents.db_agent.output import ChatAgentOutcome
from app.agents.db_agent.tools import PriorAnalysisExecution, ToolContext, build_tools
from app.agents.db_agent.trace import TraceRecorder
from app.agents.schema_context.types import CatalogColumn, CatalogTable, SchemaCatalog
from app.agents.schema_context.user_semantics import SemanticContext
from app.query_engine.results import QueryExecutionResult
from app.services.conversation_evidence_service import build_conversation_evidence_context


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
        "inspect_previous_result",
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


def _prior_result(*, rows=None) -> PriorAnalysisExecution:
    return PriorAnalysisExecution(
        result_ref="prior_result_1",
        source_message_id="assistant-1",
        question="Which companies have the most employees?",
        answer="CreativeHub has 50 active employees.",
        sql="SELECT company_name, active_employee_count FROM orders",
        result=QueryExecutionResult(
            success=True,
            columns=["company_name", "active_employee_count"],
            rows=rows or [{"company_name": "CreativeHub", "active_employee_count": 50}],
            row_count=1,
        ),
        captured_at="2026-07-17T12:00:00Z",
        presentation_kind="chart",
        column_metadata={
            "company_name": "categorical",
            "active_employee_count": "numeric",
        },
        evidence=[
            {
                "claim": "CreativeHub has 50 active employees.",
                "result_ref": "prior_result_1",
                "columns": ["company_name", "active_employee_count"],
                "row_indexes": [0],
            }
        ],
        method="Counted active employees by company.",
        limitations=["Historical snapshot."],
        relevant_tables=["public.orders"],
    )


def test_inspect_previous_result_is_bounded_and_seeds_verified_tables():
    ctx = _context()
    ctx.prior_results = {"prior_result_1": _prior_result()}
    tool = next(tool for tool in build_tools(ctx) if tool.name == "inspect_previous_result")

    payload = json.loads(tool.invoke({"result_ref": "prior_result_1", "offset": 0, "limit": 20}))

    assert payload["success"] is True
    assert payload["preview_rows"][0]["active_employee_count"] == "50"
    assert "sql" not in payload
    assert "public.orders" in ctx.inspected_tables
    assert "CreativeHub" not in json.dumps(ctx.trace.to_list())

    with_sql = json.loads(
        tool.invoke(
            {
                "result_ref": "prior_result_1",
                "offset": 0,
                "limit": 1,
                "include_sql": True,
            }
        )
    )
    assert with_sql["sql"] == "SELECT company_name, active_employee_count FROM orders"


def test_result_follow_up_can_answer_from_prior_evidence_without_attaching_rows():
    ctx = _context()
    ctx.prior_results = {"prior_result_1": _prior_result()}
    outcome = ChatAgentOutcome.model_validate(
        {
            "response_type": "result_follow_up",
            "answer": "CreativeHub had the highest active employee count at 50.",
            "result_ref": "prior_result_1",
            "presentation": {"kind": "none", "chart": None},
            "evidence": ctx.prior_results["prior_result_1"].evidence,
            "relevant_tables": ["orders"],
        }
    )

    result = _outcome_to_result(
        outcome,
        question="What was the highest result?",
        ctx=ctx,
        semantic_context=SemanticContext(schema_hash="schema-1"),
        trace=ctx.trace,
        budget=BudgetGuard(20, 120),
        wall_ms=5,
    )

    assert result.response_kind == "result_follow_up"
    assert result.sql is None
    assert result.rows == []
    assert result.answer_metadata["provenance"]["source_message_id"] == "assistant-1"


def test_result_follow_up_chart_attaches_the_verified_prior_result():
    ctx = _context()
    ctx.prior_results = {"prior_result_1": _prior_result()}
    outcome = ChatAgentOutcome.model_validate(
        {
            "response_type": "result_follow_up",
            "answer": "Here is the same employee comparison as a bar chart.",
            "result_ref": "prior_result_1",
            "presentation": {
                "kind": "chart",
                "chart": {
                    "type": "bar",
                    "title": "Active employees by company",
                    "x_column": "company_name",
                    "y_columns": ["active_employee_count"],
                    "tooltip_columns": ["active_employee_count"],
                },
            },
            "evidence": ctx.prior_results["prior_result_1"].evidence,
            "relevant_tables": ["orders"],
        }
    )

    result = _outcome_to_result(
        outcome,
        question="Make a bar chart for it.",
        ctx=ctx,
        semantic_context=SemanticContext(schema_hash="schema-1"),
        trace=ctx.trace,
        budget=BudgetGuard(20, 120),
        wall_ms=5,
    )

    assert result.response_kind == "result_follow_up"
    assert result.sql == "SELECT company_name, active_employee_count FROM orders"
    assert result.rows == [{"company_name": "CreativeHub", "active_employee_count": 50}]
    assert result.chart_recommendation["type"] == "bar"
    assert result.answer_metadata["method"] == "Counted active employees by company."
    assert result.answer_metadata["provenance"]["reused_without_execution"] is True


def test_conversation_context_uses_token_budget_and_exposes_only_a_manifest():
    history = []
    for index in range(6):
        user_id = f"user-{index}"
        history.extend(
            [
                {"id": user_id, "role": "user", "content": f"question {index}"},
                {
                    "id": f"assistant-{index}",
                    "role": "assistant",
                    "parent_id": user_id,
                    "content": f"answer {index}",
                    "connection_id": "connection-1",
                    "sql": "SELECT amount FROM orders",
                    "results": {"rows": [{"amount": index}], "row_count": 1},
                    "columns": ["amount"],
                    "agent_tier": "agent",
                    "run_status": "completed",
                    "response_kind": "data_analysis",
                    "created_at": f"2026-07-17T12:00:0{index}Z",
                    "answer_metadata": {
                        "evidence": [
                            {
                                "claim": f"amount was {index}",
                                "columns": ["amount"],
                                "row_indexes": [0],
                            }
                        ]
                    },
                },
            ]
        )

    context = build_conversation_evidence_context(
        history,
        connection_id="connection-1",
        catalog=_context().catalog,
        semantic_context=SemanticContext(schema_hash="schema-1"),
    )

    assert len(context.messages) == 12
    assert context.messages[0]["content"] == "question 0"
    assert context.prior_results["prior_result_1"].answer == "answer 5"
    manifest = json.dumps(context.manifest())
    assert '"rows"' not in manifest
    assert "SELECT amount" not in manifest


def test_agent_memory_update_is_strict_and_secret_safe():
    outcome = ChatAgentOutcome.model_validate(
        {
            "response_type": "schema_answer",
            "answer": "I found support_tickets and ticket_messages.",
            "presentation": {"kind": "none", "chart": None},
            "memory_update": {
                "summary": "The user is exploring support data.",
                "active_topic": "support tickets",
                "entities": ["support_tickets", "ticket_messages"],
                "unresolved_choice": {
                    "kind": "table",
                    "prompt": "Which support table should be explored?",
                    "options": ["support_tickets", "ticket_messages"],
                },
            },
        }
    )

    assert outcome.memory_update.unresolved_choice.options == [
        "support_tickets",
        "ticket_messages",
    ]
