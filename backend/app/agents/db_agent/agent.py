"""LangGraph tool-calling database analyst agent."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph

from app.agents._llm_content import content_to_text, log_llm_output
from app.agents._prompt_loader import load_prompt
from app.agents.db_agent.budget import BudgetDecision, BudgetGuard
from app.agents.db_agent.compaction import compact_messages, estimate_tokens
from app.agents.db_agent.output import AgentFinishError, AnalystProposal, parse_agent_proposal
from app.agents.db_agent.salvage import SALVAGE_FINISH_INSTRUCTION, build_mechanical_salvage
from app.agents.db_agent.tools import ToolContext, build_tools
from app.agents.db_agent.trace import TraceRecorder, log_agent_event
from app.agents.schema_context.semantics import render_semantics_prompt, resolve_semantics
from app.agents.schema_context.types import SchemaCatalog
from app.core.config import settings
from app.integrations.llm_client import get_chat_llm_with_tools
from app.query_engine.results import QueryExecutionResult
from app.query_engine.safety import validate_query
from app.services.query_execution_service import execute_query

logger = logging.getLogger("query-mind.db_agent")

_PROMPT_PATH = Path(__file__).with_name("prompts") / "agent_system_prompt.md"
_PROPOSAL_KEYS = "analysis_summary, relevant_tables, relevant_columns, sql, column_metadata, assumptions"
_VALIDATION_REPAIR_LIMIT = 1
_EXECUTION_REPAIR_LIMIT = 2


@dataclass
class AgentRunResult:
    success: bool
    tier: str = "agent"
    explanation: str = ""
    sql: str | None = None
    column_metadata: dict[str, str] = field(default_factory=dict)
    relevant_tables: list[str] = field(default_factory=list)
    relevant_columns: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    execution_time_ms: float = 0.0
    error: str | None = None
    trace: list[dict] = field(default_factory=list)
    tool_calls: int = 0
    wall_ms: float = 0.0
    fallback_reason: str | None = None

    def as_chat_dict(self) -> dict:
        return {
            "success": self.success,
            "explanation": self.explanation,
            "sql": self.sql,
            "column_metadata": self.column_metadata,
            "relevant_tables": self.relevant_tables,
            "relevant_columns": self.relevant_columns,
            "assumptions": self.assumptions,
            "columns": self.columns,
            "rows": self.rows,
            "row_count": self.row_count,
            "truncated": self.truncated,
            "execution_time_ms": self.execution_time_ms,
            "error": self.error,
            "trace": self.trace,
            "tier": self.tier,
            "tool_calls": self.tool_calls,
            "wall_ms": self.wall_ms,
            "fallback_reason": self.fallback_reason,
        }


class AgentState(TypedDict):
    messages: list[BaseMessage]
    force_finish: bool
    finish_retry_used: bool
    tool_retry_used: bool
    proposal: AnalystProposal | None
    finish_error: str | None


def _build_system_prompt(catalog: SchemaCatalog, question: str) -> str:
    base = load_prompt(str(_PROMPT_PATH))
    semantics = resolve_semantics(question, catalog)
    semantics_block = render_semantics_prompt(semantics)
    dialect = f"DATABASE DIALECT\n{catalog.db_type}\n"
    parts = [base.strip(), dialect]
    if semantics_block:
        parts.append(semantics_block)
    return "\n\n".join(parts)


def _get_llm(tools):
    return get_chat_llm_with_tools(tools)


def _is_tool_use_failed(exc: Exception) -> bool:
    text = str(exc).lower()
    return "tool_use_failed" in text or "failed to call a function" in text or "failed_generation" in text


def _proposal_retry_message(error: Exception) -> str:
    return (
        "Your response must be ONLY a raw JSON object with keys "
        f"{_PROPOSAL_KEYS}. Do not use markdown fences, prose, or tool-call syntax. "
        f"Parser error: {error}"
    )


def _native_tool_retry_message() -> str:
    return (
        "Your previous response attempted to write a tool call as text. "
        "Call tools only through the native tool interface. Never write XML, HTML, "
        "<function=...>, or any tool-call syntax in the message body. Continue from the same question."
    )


def _repair_message(stage: str, error_message: str, failed_sql: str | None) -> str:
    return (
        "The backend rejected the SQL proposal. Return a corrected raw JSON proposal with keys "
        f"{_PROPOSAL_KEYS}. "
        f"Stage: {stage}. Error: {error_message}. "
        f"Failed SQL: {failed_sql or 'null'}. "
        "You may inspect schema again if needed. Do not include prose outside JSON."
    )


def _classify_execution_error(error: str) -> str:
    lower = error.lower()
    if "does not exist" in lower and "relation" in lower:
        return "missing_table"
    if "column" in lower and "does not exist" in lower:
        return "missing_column"
    if "syntax error" in lower:
        return "syntax_error"
    if "timeout" in lower or "timed out" in lower or "cancel" in lower:
        return "timeout"
    if "permission" in lower or "denied" in lower:
        return "permission_denied"
    return "unknown"


def _finalize_execution(
    ctx: ToolContext,
    proposal: AnalystProposal,
) -> tuple[QueryExecutionResult | None, str | None, str | None]:
    if not proposal.sql:
        return None, "Agent did not propose SQL for this analytical question.", "validation"
    is_safe, reason = validate_query(proposal.sql)
    if not is_safe:
        return None, reason or "Final SQL failed validation.", "validation"

    result = execute_query(
        ctx.user_id,
        ctx.engine,
        proposal.sql,
        row_limit=500,
        connection_id=ctx.connection_id,
        readonly=True,
        timeout_seconds=settings.agent_query_timeout_seconds,
    )
    if not result.success:
        return None, result.error or "Final SQL execution failed.", "execution"
    return result, None, None


def build_agent_graph(
    llm,
    tool_map: dict,
    budget: BudgetGuard,
    ctx: ToolContext,
    trace: TraceRecorder,
):
    """Compile the tool-calling analyst loop as a LangGraph StateGraph."""

    def agent_node(state: AgentState) -> dict:
        if budget.elapsed_seconds() >= budget.wall_clock_seconds:
            log_agent_event(
                "[agent] wall-clock budget reached (%.0fs/%ss); forcing finish",
                budget.elapsed_seconds(),
                budget.wall_clock_seconds,
            )
            return {"force_finish": True}

        log_agent_event(
            "[agent] llm turn start messages=%d tool_calls=%d/%d elapsed=%.0fs",
            len(state["messages"]),
            budget.call_count,
            budget.max_calls,
            budget.elapsed_seconds(),
        )
        llm_started = time.monotonic()
        try:
            response = llm.invoke(state["messages"])
        except Exception as exc:
            llm_ms = (time.monotonic() - llm_started) * 1000
            log_agent_event("[agent] llm turn failed (%.0fms): %s", llm_ms, exc)
            if _is_tool_use_failed(exc) and not state["tool_retry_used"]:
                trace.record(
                    "model_tool_call_retry",
                    "tool_use_failed",
                    0,
                    "error",
                    error_class="tool_use_failed",
                    retry_count=1,
                )
                return {
                    "tool_retry_used": True,
                    "messages": [*state["messages"], HumanMessage(content=_native_tool_retry_message())],
                }
            raise

        llm_ms = (time.monotonic() - llm_started) * 1000
        tool_calls = getattr(response, "tool_calls", None) or []
        if tool_calls:
            tool_names = [call["name"] for call in tool_calls]
            log_agent_event(
                "[agent] llm turn done (%.0fms) requesting tools: %s",
                llm_ms,
                ", ".join(tool_names),
            )
            return {"messages": [*state["messages"], response]}

        log_agent_event("[agent] llm turn done (%.0fms) returned proposal text", llm_ms)
        proposal_text = content_to_text(response.content)
        log_llm_output(logger, "agent proposal", proposal_text)
        try:
            return {"proposal": parse_agent_proposal(proposal_text)}
        except AgentFinishError as exc:
            log_agent_event("[agent] proposal parse failed: %s", exc)
            if not state["finish_retry_used"]:
                return {
                    "finish_retry_used": True,
                    "messages": [*state["messages"], response, HumanMessage(content=_proposal_retry_message(exc))],
                }
            return {"finish_error": str(exc)}

    def route_after_agent(state: AgentState) -> str:
        if state["force_finish"]:
            return "finish"
        if state["proposal"] is not None or state["finish_error"] is not None:
            return "done"
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return "agent"

    def tools_node(state: AgentState) -> dict:
        last = state["messages"][-1]
        new_messages: list[BaseMessage] = []
        guard_notes: list[str] = []
        force_finish = False

        for tool_call in last.tool_calls:
            name = tool_call["name"]
            args = tool_call.get("args", {})
            decision = budget.check_before_call(name, args)
            guard_msg = budget.guard_message(decision, name)
            if guard_msg:
                guard_notes.append(guard_msg)
            if decision == BudgetDecision.FORCE_FINISH:
                log_agent_event(
                    "[agent] tool budget exhausted at %s; forcing finish (calls=%d/%d elapsed=%.0fs)",
                    name,
                    budget.call_count,
                    budget.max_calls,
                    budget.elapsed_seconds(),
                )
                force_finish = True
                break
            if decision == BudgetDecision.SKIP_REPEAT:
                log_agent_event("[tool] %s skipped (duplicate call)", name)
                new_messages.append(
                    ToolMessage(content=guard_msg or "Duplicate tool call skipped.", tool_call_id=tool_call["id"])
                )
                continue

            log_agent_event("[tool] %s start %s", name, args)
            tool = tool_map.get(name)
            if not tool:
                log_agent_event("[tool] %s -> error unknown tool", name)
            result = tool.invoke(args) if tool else f"Unknown tool: {name}"
            budget.record_call(name, args)
            new_messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))

        warning = budget.pending_warning()
        if warning:
            guard_notes.append(warning)
        if guard_notes:
            new_messages.append(SystemMessage(content="\n".join(guard_notes)))

        messages = [*state["messages"], *new_messages]
        if estimate_tokens(messages) > settings.agent_compaction_token_threshold:
            before_tokens = estimate_tokens(messages)
            messages, _ = compact_messages(
                messages,
                scratchpad=ctx.scratchpad,
                trace_steps=trace.to_list(),
            )
            after_tokens = estimate_tokens(messages)
            log_agent_event(
                "[agent] compacted context tokens %d -> %d (threshold=%d)",
                before_tokens,
                after_tokens,
                settings.agent_compaction_token_threshold,
            )

        return {"messages": messages, "force_finish": force_finish}

    def route_after_tools(state: AgentState) -> str:
        return "finish" if state["force_finish"] else "agent"

    def force_finish_node(state: AgentState) -> dict:
        log_agent_event(
            "[agent] force-finish start calls=%d/%d elapsed=%.0fs",
            budget.call_count,
            budget.max_calls,
            budget.elapsed_seconds(),
        )
        finish_started = time.monotonic()
        finish_text = ""
        try:
            force_response = llm.invoke([*state["messages"], HumanMessage(content=SALVAGE_FINISH_INSTRUCTION)])
            log_agent_event("[agent] force-finish llm done (%.0fms)", (time.monotonic() - finish_started) * 1000)
            finish_text = log_llm_output(logger, "agent force-finish", force_response.content)
            return {"proposal": parse_agent_proposal(finish_text)}
        except AgentFinishError as exc:
            logger.warning("Force-finish JSON parse failed; using mechanical salvage: %s", exc)
            return {"proposal": build_mechanical_salvage(trace, ctx)}
        except Exception as exc:
            logger.warning("Force-finish LLM call failed; using mechanical salvage: %s", exc)
            return {"proposal": build_mechanical_salvage(trace, ctx)}

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.add_node("finish", force_finish_node)

    graph.set_entry_point("agent")
    graph.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tools": "tools", "finish": "finish", "agent": "agent", "done": END},
    )
    graph.add_conditional_edges(
        "tools",
        route_after_tools,
        {"agent": "agent", "finish": "finish"},
    )
    graph.add_edge("finish", END)
    return graph.compile()


def _initial_state(messages: list[BaseMessage]) -> AgentState:
    return {
        "messages": messages,
        "force_finish": False,
        "finish_retry_used": False,
        "tool_retry_used": False,
        "proposal": None,
        "finish_error": None,
    }


def _invoke_graph(agent_graph, messages: list[BaseMessage], recursion_limit: int) -> AgentState:
    return agent_graph.invoke(_initial_state(messages), config={"recursion_limit": recursion_limit})


def _result_from_success(
    proposal: AnalystProposal,
    execution: QueryExecutionResult,
    trace: TraceRecorder,
    budget: BudgetGuard,
    wall_ms: float,
) -> AgentRunResult:
    return AgentRunResult(
        success=True,
        tier="agent",
        explanation=proposal.analysis_summary,
        sql=proposal.sql,
        column_metadata=proposal.column_metadata,
        relevant_tables=proposal.relevant_tables,
        relevant_columns=proposal.relevant_columns,
        assumptions=proposal.assumptions,
        columns=execution.columns,
        rows=execution.rows,
        row_count=execution.row_count,
        truncated=execution.truncated,
        execution_time_ms=execution.execution_time_ms,
        trace=trace.to_list(),
        tool_calls=budget.call_count,
        wall_ms=wall_ms,
    )


def run_agent(
    *,
    user_id: str,
    connection_id: str,
    question: str,
    catalog: SchemaCatalog,
    engine,
    history: list[dict] | None = None,
    invalidate_catalog=None,
    rebuild_catalog=None,
) -> AgentRunResult:
    started = time.monotonic()
    trace = TraceRecorder()
    ctx = ToolContext(
        user_id=user_id,
        connection_id=connection_id,
        catalog=catalog,
        engine=engine,
        trace=trace,
        invalidate_catalog=invalidate_catalog,
        rebuild_catalog=rebuild_catalog,
    )
    tools = build_tools(ctx)
    tool_map = {tool.name: tool for tool in tools}
    budget = BudgetGuard(settings.agent_max_tool_calls, settings.agent_wall_clock_seconds)

    log_agent_event(
        "[agent] run start model=%s connection=%s question=%r",
        settings.resolved_llm_model,
        connection_id,
        question[:160],
    )

    try:
        llm = _get_llm(tools)
        agent_graph = build_agent_graph(llm, tool_map, budget, ctx, trace)

        messages: list[BaseMessage] = [SystemMessage(content=_build_system_prompt(catalog, question))]
        if history:
            for msg in history[-10:]:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))
        messages.append(HumanMessage(content=question))

        recursion_limit = settings.agent_max_tool_calls * 2 + 10
        final_state = _invoke_graph(agent_graph, messages, recursion_limit)

        proposal: AnalystProposal | None = final_state["proposal"]
        finish_error: str | None = final_state["finish_error"]
        if proposal is None:
            wall_ms = round((time.monotonic() - started) * 1000, 2)
            log_agent_event(
                "[agent] run finish success=false tool_calls=%d wall_ms=%.0f reason=%s",
                budget.call_count,
                wall_ms,
                finish_error or "no_valid_proposal",
            )
            return AgentRunResult(
                success=False,
                tier="agent",
                explanation="The agent could not produce a valid SQL proposal.",
                error=finish_error or "Agent run failed.",
                trace=trace.to_list(),
                tool_calls=budget.call_count,
                wall_ms=wall_ms,
                fallback_reason=finish_error or "no_valid_proposal",
            )

        validation_repairs = 0
        execution_repairs = 0
        repair_messages = final_state["messages"]
        last_error: str | None = None
        last_stage: str | None = None

        while True:
            execution, exec_error, stage = _finalize_execution(ctx, proposal)
            if execution is not None and exec_error is None:
                wall_ms = round((time.monotonic() - started) * 1000, 2)
                log_agent_event(
                    "[agent] run finish success=true tool_calls=%d wall_ms=%.0f rows=%d",
                    budget.call_count,
                    wall_ms,
                    execution.row_count,
                )
                return _result_from_success(proposal, execution, trace, budget, wall_ms)

            last_error = exec_error or "SQL proposal failed."
            last_stage = stage or "execution"
            error_class = _classify_execution_error(last_error) if last_stage == "execution" else "validation_error"
            trace.record(
                f"backend_{last_stage}",
                f"sql={proposal.sql or 'null'}",
                0,
                "error",
                output_summary=last_error,
                error_class=error_class,
            )

            can_repair_validation = last_stage == "validation" and validation_repairs < _VALIDATION_REPAIR_LIMIT
            can_repair_execution = last_stage == "execution" and execution_repairs < _EXECUTION_REPAIR_LIMIT
            if not (can_repair_validation or can_repair_execution):
                fallback_reason = (
                    "validation_repair_exhausted" if last_stage == "validation" else "execution_repair_exhausted"
                )
                wall_ms = round((time.monotonic() - started) * 1000, 2)
                return AgentRunResult(
                    success=False,
                    tier="agent",
                    explanation=proposal.analysis_summary,
                    sql=proposal.sql,
                    column_metadata=proposal.column_metadata,
                    relevant_tables=proposal.relevant_tables,
                    relevant_columns=proposal.relevant_columns,
                    assumptions=proposal.assumptions,
                    error=last_error,
                    trace=trace.to_list(),
                    tool_calls=budget.call_count,
                    wall_ms=wall_ms,
                    fallback_reason=fallback_reason,
                )

            if last_stage == "validation":
                validation_repairs += 1
                retry_count = validation_repairs
            else:
                execution_repairs += 1
                retry_count = execution_repairs
            trace.record(
                "agent_repair",
                last_stage,
                0,
                "ok",
                output_summary="Requesting corrected SQL proposal from analyst agent.",
                retry_count=retry_count,
            )
            repair_state = _invoke_graph(
                agent_graph,
                [*repair_messages, HumanMessage(content=_repair_message(last_stage, last_error, proposal.sql))],
                recursion_limit,
            )
            if repair_state["proposal"] is None:
                wall_ms = round((time.monotonic() - started) * 1000, 2)
                return AgentRunResult(
                    success=False,
                    tier="agent",
                    explanation="The agent could not repair the SQL proposal.",
                    sql=proposal.sql,
                    column_metadata=proposal.column_metadata,
                    error=repair_state["finish_error"] or last_error,
                    trace=trace.to_list(),
                    tool_calls=budget.call_count,
                    wall_ms=wall_ms,
                    fallback_reason=f"{last_stage}_repair_failed",
                )
            proposal = repair_state["proposal"]
            repair_messages = repair_state["messages"]
    except Exception as exc:
        fallback_reason = "tool_use_failed" if _is_tool_use_failed(exc) else "agent_exception"
        wall_ms = round((time.monotonic() - started) * 1000, 2)
        log_agent_event(
            "[agent] run finish success=false tool_calls=%d wall_ms=%.0f reason=%s error=%s",
            budget.call_count,
            wall_ms,
            fallback_reason,
            exc,
        )
        logger.exception("Agent run failed with exception")
        return AgentRunResult(
            success=False,
            tier="agent",
            explanation="The agent could not produce a valid SQL proposal.",
            error=fallback_reason,
            trace=trace.to_list(),
            tool_calls=budget.call_count,
            wall_ms=wall_ms,
            fallback_reason=fallback_reason,
        )


__all__ = ["AgentRunResult", "AgentState", "build_agent_graph", "run_agent"]
