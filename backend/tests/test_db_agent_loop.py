"""Tests for budget guard, proposal parsing, and the LangGraph analyst loop."""

import json
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.agents.db_agent.agent import _validated_chart, build_agent_graph, infer_chart_from_result
from app.agents.db_agent.budget import BudgetDecision, BudgetGuard
from app.agents.db_agent.output import AgentFinishError, parse_agent_proposal
from app.agents.db_agent.tools import ToolContext
from app.agents.db_agent.trace import TraceRecorder
from app.agents.schema_context.catalog import build_catalog
from app.db.models.connection import ColumnInfo, TableInfo


def _catalog():
    return build_catalog(
        "conn-1",
        "postgresql",
        [
            TableInfo(
                name="customers",
                row_count=10,
                columns=[ColumnInfo(name="id", type="uuid", nullable=False, primary_key=True)],
            )
        ],
    )


def _ctx(trace: TraceRecorder | None = None) -> ToolContext:
    return ToolContext(
        user_id="user-1",
        connection_id="conn-1",
        catalog=_catalog(),
        engine=MagicMock(),
        trace=trace or TraceRecorder(),
    )


def _build_graph(llm, tool_map, budget, ctx=None, trace=None):
    trace = trace or TraceRecorder()
    ctx = ctx or _ctx(trace)
    return build_agent_graph(llm, tool_map, budget, ctx, trace)


def test_budget_guard_warns_on_repeat():
    guard = BudgetGuard(max_calls=8, wall_clock_seconds=60)
    first = guard.check_before_call("search_schema", {"query": "customers"})
    guard.record_call("search_schema", {"query": "customers"})
    second = guard.check_before_call("search_schema", {"query": "customers"})
    assert first == BudgetDecision.ALLOW
    assert second == BudgetDecision.WARN_REPEAT


def test_budget_guard_forces_finish_on_cap():
    guard = BudgetGuard(max_calls=1, wall_clock_seconds=60)
    guard.record_call("list_tables", {})
    decision = guard.check_before_call("list_tables", {})
    assert decision == BudgetDecision.FORCE_FINISH


def test_parse_agent_outcome_accepts_json():
    proposal = parse_agent_proposal(
        json.dumps(
            {
                "response_type": "direct_answer",
                "answer": "I can explain database concepts without running SQL.",
                "presentation": {"kind": "none", "chart": None},
            }
        )
    )
    assert proposal.response_type == "direct_answer"
    assert proposal.result_ref is None


def test_parse_agent_proposal_rejects_invalid_json():
    with pytest.raises(AgentFinishError):
        parse_agent_proposal("not json")


def test_parse_agent_outcome_rejects_analysis_without_result_reference():
    with pytest.raises(AgentFinishError):
        parse_agent_proposal(
            json.dumps(
                {
                    "response_type": "data_analysis",
                    "answer": "Analysis complete.",
                    "presentation": {"kind": "table", "chart": None},
                    "evidence": [],
                }
            )
        )


def test_chartable_categorical_result_gets_deterministic_bar_fallback():
    outcome = parse_agent_proposal(
        json.dumps(
            {
                "response_type": "data_analysis",
                "answer": "CreativeHub has 50 active employees.",
                "result_ref": "result_1",
                "presentation": {"kind": "table", "chart": None},
                "evidence": [
                    {
                        "claim": "CreativeHub has 50 active employees.",
                        "result_ref": "result_1",
                        "columns": ["company_name", "active_employee_count"],
                        "row_indexes": [0],
                    }
                ],
                "column_metadata": {
                    "company_name": "categorical",
                    "active_employee_count": "numeric",
                },
            }
        )
    )

    kind, chart = _validated_chart(
        outcome,
        ["company_name", "active_employee_count"],
        [
            {"company_name": "CreativeHub", "active_employee_count": 50},
            {"company_name": "SkyBuild Group", "active_employee_count": 50},
        ],
    )

    assert kind == "chart"
    assert chart is not None
    assert chart["type"] == "bar"
    assert chart["x_column"] == "company_name"
    assert chart["y_columns"] == ["active_employee_count"]


def test_identifier_only_result_remains_table_only():
    outcome = parse_agent_proposal(
        json.dumps(
            {
                "response_type": "data_analysis",
                "answer": "The matching identifiers are listed.",
                "result_ref": "result_1",
                "presentation": {"kind": "none", "chart": None},
                "evidence": [
                    {
                        "claim": "A matching identifier was returned.",
                        "result_ref": "result_1",
                        "columns": ["id", "company_id"],
                        "row_indexes": [0],
                    }
                ],
                "column_metadata": {"id": "identifier", "company_id": "identifier"},
            }
        )
    )

    kind, chart = _validated_chart(
        outcome,
        ["id", "company_id"],
        [{"id": 1, "company_id": 10}, {"id": 2, "company_id": 10}],
    )

    assert kind == "table"
    assert chart is None


def test_pipeline_compatible_chart_inference_uses_metadata_without_an_agent_outcome():
    chart = infer_chart_from_result(
        ["payment_month", "average_payment"],
        [
            {"payment_month": "2026-01-01", "average_payment": 1000},
            {"payment_month": "2026-02-01", "average_payment": 1200},
        ],
        {"payment_month": "date", "average_payment": "currency"},
    )

    assert chart is not None
    assert chart["type"] == "line"
    assert chart["x_column"] == "payment_month"
    assert chart["y_columns"] == ["average_payment"]


class ScriptedLLM:
    """Fake LLM that returns pre-scripted responses in order."""

    def __init__(self, responses: list[AIMessage]):
        self._responses = list(responses)
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        return self._responses.pop(0)


class FakeTool:
    def __init__(self, name: str, result: str = "ok"):
        self.name = name
        self.result = result
        self.invocations: list[dict] = []

    def invoke(self, args):
        self.invocations.append(args)
        return self.result


PROPOSAL_JSON = json.dumps(
    {
        "response_type": "direct_answer",
        "answer": "Done without querying data.",
        "presentation": {"kind": "none", "chart": None},
        "evidence": [],
        "limitations": [],
        "relevant_tables": [],
        "relevant_columns": [],
        "column_metadata": {},
        "semantic_refs": [],
    }
)


def _initial_state():
    return {
        "messages": [SystemMessage(content="system"), HumanMessage(content="question")],
        "force_finish": False,
        "finish_retry_used": False,
        "tool_retry_used": False,
        "proposal": None,
        "finish_error": None,
    }


def _tool_call_msg(name: str, args: dict, call_id: str = "call-1") -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def test_graph_happy_path_tool_then_finish():
    llm = ScriptedLLM(
        [
            _tool_call_msg("search_schema", {"query": "customers"}),
            AIMessage(content=PROPOSAL_JSON),
        ]
    )
    tool = FakeTool("search_schema", result="- customers (score=5)")
    budget = BudgetGuard(max_calls=8, wall_clock_seconds=60)
    graph = _build_graph(llm, {"search_schema": tool}, budget)

    final = graph.invoke(_initial_state())

    assert final["proposal"] is not None
    assert final["proposal"].response_type == "direct_answer"
    assert tool.invocations == [{"query": "customers"}]
    assert budget.call_count == 1
    assert any(isinstance(m, ToolMessage) for m in final["messages"])


def test_graph_retries_malformed_finish_once():
    llm = ScriptedLLM(
        [
            AIMessage(content="here is your answer, not json"),
            AIMessage(content=PROPOSAL_JSON),
        ]
    )
    budget = BudgetGuard(max_calls=8, wall_clock_seconds=60)
    graph = _build_graph(llm, {}, budget)

    final = graph.invoke(_initial_state())

    assert final["finish_retry_used"] is True
    assert final["proposal"] is not None
    assert final["finish_error"] is None
    assert llm.calls == 2


def test_graph_retries_native_tool_call_failure_once():
    class ToolUseFailedLLM:
        def __init__(self):
            self.calls = 0

        def invoke(self, messages):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("tool_use_failed: <function=search_schema{} </function>")
            assert "native tool interface" in messages[-1].content
            return AIMessage(content=PROPOSAL_JSON)

    llm = ToolUseFailedLLM()
    budget = BudgetGuard(max_calls=8, wall_clock_seconds=60)
    graph = _build_graph(llm, {}, budget)

    final = graph.invoke(_initial_state())

    assert final["tool_retry_used"] is True
    assert final["proposal"] is not None
    assert llm.calls == 2


def test_graph_fails_after_second_malformed_finish():
    llm = ScriptedLLM(
        [
            AIMessage(content="still not json"),
            AIMessage(content="definitely not json"),
        ]
    )
    budget = BudgetGuard(max_calls=8, wall_clock_seconds=60)
    graph = _build_graph(llm, {}, budget)

    final = graph.invoke(_initial_state())

    assert final["proposal"] is None
    assert final["finish_error"]


def test_graph_budget_cap_forces_finish():
    llm = ScriptedLLM(
        [
            _tool_call_msg("list_tables", {}, "call-1"),
            _tool_call_msg("list_tables", {"x": 1}, "call-2"),
            AIMessage(content=PROPOSAL_JSON),
        ]
    )
    tool = FakeTool("list_tables")
    budget = BudgetGuard(max_calls=1, wall_clock_seconds=60)
    graph = _build_graph(llm, {"list_tables": tool}, budget)

    final = graph.invoke(_initial_state())

    assert budget.call_count == 1
    assert final["force_finish"] is True
    assert final["proposal"] is not None
    assert final["proposal"].response_type == "direct_answer"


def test_graph_wall_clock_forces_finish():
    llm = ScriptedLLM([AIMessage(content=PROPOSAL_JSON)])
    budget = BudgetGuard(max_calls=8, wall_clock_seconds=0)
    graph = _build_graph(llm, {}, budget)

    final = graph.invoke(_initial_state())

    assert final["force_finish"] is True
    assert final["proposal"] is not None
    assert llm.calls == 1


def test_graph_mechanical_salvage_when_force_finish_llm_fails():
    llm = ScriptedLLM([AIMessage(content="not json at all")])
    trace = TraceRecorder()
    trace.record("list_tables", "{}", 0, "ok")
    ctx = _ctx(trace)
    budget = BudgetGuard(max_calls=1, wall_clock_seconds=60)
    graph = _build_graph(llm, {}, budget, ctx=ctx, trace=trace)

    state = _initial_state()
    state["force_finish"] = True
    final = graph.invoke(state)

    assert final["proposal"] is not None
    assert final["proposal"].result_ref is None
    assert final["proposal"].response_type == "clarification"


def test_graph_skip_repeat_returns_tool_message_without_executing():
    llm = ScriptedLLM(
        [
            _tool_call_msg("search_schema", {"query": "customers"}, "c1"),
            _tool_call_msg("search_schema", {"query": "customers"}, "c2"),
            _tool_call_msg("search_schema", {"query": "customers"}, "c3"),
            AIMessage(content=PROPOSAL_JSON),
        ]
    )
    tool = FakeTool("search_schema")
    budget = BudgetGuard(max_calls=20, wall_clock_seconds=120)
    graph = _build_graph(llm, {"search_schema": tool}, budget)

    final = graph.invoke(_initial_state())

    assert tool.invocations == [{"query": "customers"}, {"query": "customers"}]
    assert any(
        isinstance(m, ToolMessage) and "identical call" in m.content for m in final["messages"]
    )
