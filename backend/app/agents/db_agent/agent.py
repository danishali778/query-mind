"""LangGraph tool-calling database analyst agent."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from numbers import Number
from pathlib import Path
from typing import TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph

from app.agents._llm_content import content_to_text, log_llm_output
from app.agents._prompt_loader import load_prompt
from app.agents.db_agent.budget import BudgetDecision, BudgetGuard
from app.agents.db_agent.compaction import compact_messages, estimate_tokens
from app.agents.db_agent.output import AgentFinishError, ChatAgentOutcome, parse_agent_outcome
from app.agents.db_agent.salvage import SALVAGE_FINISH_INSTRUCTION, build_mechanical_salvage
from app.agents.db_agent.tools import ToolContext, build_tools
from app.agents.db_agent.trace import TraceRecorder, log_agent_event
from app.agents.schema_context.scoring import tokenize
from app.agents.schema_context.semantics import render_semantics_prompt, resolve_semantics
from app.agents.schema_context.types import SchemaCatalog
from app.agents.schema_context.user_semantics import (
    SemanticContext,
    apply_semantic_catalog_overlay,
    render_untrusted_semantic_context,
)
from app.core.config import settings
from app.db.models.llm import LlmExecutionContext
from app.integrations.llm_client import get_chat_llm_with_tools

logger = logging.getLogger("query-mind.db_agent")

_PROMPT_PATH = Path(__file__).with_name("prompts") / "agent_system_prompt.md"
_PROPOSAL_KEYS = (
    "response_type, answer, clarification_context, result_ref, presentation, evidence, method, "
    "limitations, relevant_tables, relevant_columns, column_metadata, semantic_refs"
)


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
    chart_recommendation: dict | None = None
    error: str | None = None
    trace: list[dict] = field(default_factory=list)
    tool_calls: int = 0
    wall_ms: float = 0.0
    fallback_reason: str | None = None
    semantic_lineage: list[dict] = field(default_factory=list)
    response_kind: str = "answer"
    clarification_context: dict | None = None
    presentation_kind: str | None = None
    answer_metadata: dict | None = None

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
            "chart_recommendation": self.chart_recommendation,
            "error": self.error,
            "trace": self.trace,
            "tier": self.tier,
            "tool_calls": self.tool_calls,
            "wall_ms": self.wall_ms,
            "fallback_reason": self.fallback_reason,
            "semantic_lineage": self.semantic_lineage,
            "response_kind": self.response_kind,
            "clarification_context": self.clarification_context,
            "presentation_kind": self.presentation_kind,
            "answer_metadata": self.answer_metadata,
        }


class AgentState(TypedDict):
    messages: list[BaseMessage]
    force_finish: bool
    finish_retry_used: bool
    tool_retry_used: bool
    proposal: ChatAgentOutcome | None
    finish_error: str | None


def _build_system_prompt(catalog: SchemaCatalog) -> str:
    base = load_prompt(str(_PROMPT_PATH))
    dialect = f"DATABASE DIALECT\n{catalog.db_type}\n"
    return "\n\n".join([base.strip(), dialect])


def _build_context_messages(
    catalog: SchemaCatalog, question: str, semantic_context: SemanticContext
) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    built_in = render_semantics_prompt(resolve_semantics(question, catalog))
    if built_in:
        messages.append(HumanMessage(content=f"QUERYMIND DEFAULT SEMANTIC CONTEXT\n{built_in}"))
    user_context = render_untrusted_semantic_context(semantic_context)
    if user_context:
        messages.append(HumanMessage(content=user_context))
    return messages


def _get_llm(llm_context: LlmExecutionContext, tools):
    return get_chat_llm_with_tools(llm_context, tools)


def _is_tool_use_failed(exc: Exception) -> bool:
    text = str(exc).lower()
    return "tool_use_failed" in text or "failed to call a function" in text or "failed_generation" in text


_NON_FALLBACK_TOOL_REJECTIONS = {
    "connection_scope_violation",
    "live_query_cap_reached",
    "schema_relevance_rejected",
    "semantic_policy_rejected",
    "unsafe_query",
    "query_budget_exhausted",
}


def _policy_rejection_reason(trace: TraceRecorder) -> str | None:
    for step in reversed(trace.steps):
        if step.error_class in _NON_FALLBACK_TOOL_REJECTIONS:
            return step.error_class
    return None


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


def build_agent_graph(
    llm,
    tool_map: dict,
    budget: BudgetGuard,
    ctx: ToolContext,
    trace: TraceRecorder,
    progress=None,
):
    """Compile the tool-calling analyst loop as a LangGraph StateGraph."""

    def agent_node(state: AgentState) -> dict:
        if progress:
            progress.check_cancelled()
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
        if progress:
            progress.check_cancelled()
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
            return {"proposal": parse_agent_outcome(proposal_text)}
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
            if progress:
                progress.tool_started(name)
            tool = tool_map.get(name)
            if not tool:
                log_agent_event("[tool] %s -> error unknown tool", name)
            result = tool.invoke(args) if tool else f"Unknown tool: {name}"
            if progress:
                progress.check_cancelled()
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
            return {"proposal": parse_agent_outcome(finish_text)}
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


def _is_numeric_result_column(
    column: str,
    *,
    metadata: dict[str, str],
    rows: list[dict],
) -> bool:
    semantic_type = metadata.get(column, "").casefold()
    if semantic_type in {"numeric", "currency", "percent", "percentage", "duration"}:
        return True

    observed = [row.get(column) for row in rows if row.get(column) is not None]
    if not observed:
        return False
    for value in observed:
        if isinstance(value, bool):
            return False
        if isinstance(value, Number):
            continue
        if isinstance(value, str):
            try:
                float(value.replace(",", ""))
                continue
            except ValueError:
                pass
        return False
    return True


def _is_identifier_result_column(column: str, metadata: dict[str, str]) -> bool:
    semantic_type = metadata.get(column, "").casefold()
    normalized = column.casefold()
    return semantic_type == "identifier" or normalized == "id" or normalized.endswith("_id")


def _is_temporal_result_column(column: str, metadata: dict[str, str]) -> bool:
    semantic_type = metadata.get(column, "").casefold()
    if semantic_type in {"date", "datetime", "temporal"}:
        return True
    normalized = column.casefold()
    return any(
        token in normalized
        for token in ("date", "time", "month", "year", "week", "quarter", "day")
    )


def _display_column_name(column: str) -> str:
    return " ".join(part.capitalize() for part in column.replace("-", "_").split("_") if part)


def infer_chart_from_result(
    columns: list[str],
    rows: list[dict],
    metadata: dict[str, str] | None = None,
) -> dict | None:
    """Create a conservative chart for an obviously chartable executed result."""
    if not rows or not columns:
        return None

    metadata = metadata or {}
    numeric_columns = [
        column
        for column in columns
        if not _is_identifier_result_column(column, metadata)
        and _is_numeric_result_column(column, metadata=metadata, rows=rows)
    ]
    if not numeric_columns:
        return None

    if len(rows) == 1:
        return {
            "type": "kpi",
            "title": "Key result",
            "x_column": None,
            "y_columns": numeric_columns[:4],
            "color_column": None,
            "tooltip_columns": [],
            "is_grouped": False,
            "is_dual_axis": False,
            "x_label": None,
            "y_label": None,
        }

    dimension_columns = [
        column
        for column in columns
        if column not in numeric_columns and not _is_identifier_result_column(column, metadata)
    ]
    if not dimension_columns:
        return None

    x_column = next(
        (column for column in dimension_columns if _is_temporal_result_column(column, metadata)),
        dimension_columns[0],
    )
    y_columns = numeric_columns[:4]
    chart_type = "line" if _is_temporal_result_column(x_column, metadata) else "bar"
    tooltip_columns = [
        column for column in columns if column != x_column and column not in y_columns
    ][:8]
    return {
        "type": chart_type,
        "title": f"{_display_column_name(y_columns[0])} by {_display_column_name(x_column)}",
        "x_column": x_column,
        "y_columns": y_columns,
        "color_column": None,
        "tooltip_columns": tooltip_columns,
        "is_grouped": len(y_columns) > 1,
        "is_dual_axis": False,
        "x_label": _display_column_name(x_column),
        "y_label": _display_column_name(y_columns[0]),
    }


def _validated_chart(outcome: ChatAgentOutcome, columns: list[str], rows: list[dict]) -> tuple[str, dict | None]:
    """Validate a model chart and fill obvious chartable result shapes deterministically."""
    kind = outcome.presentation.kind
    chart = outcome.presentation.chart
    if kind == "kpi":
        inferred = infer_chart_from_result(columns, rows, outcome.column_metadata)
        if inferred and inferred["type"] == "kpi":
            return "kpi", inferred
    elif kind == "chart" and chart is not None:
        referenced = [*(chart.y_columns or []), *(chart.tooltip_columns or [])]
        if chart.x_column:
            referenced.append(chart.x_column)
        if chart.color_column:
            referenced.append(chart.color_column)
        is_valid = bool(chart.x_column and chart.y_columns) and not any(
            column not in columns for column in referenced
        )
        is_valid = is_valid and not any(
            not _is_numeric_result_column(column, metadata=outcome.column_metadata, rows=rows)
            for column in chart.y_columns
        )
        if chart.type == "pie" and len(rows) > 7:
            is_valid = False
        if chart.type in {"line", "area"}:
            x_type = outcome.column_metadata.get(chart.x_column or "", "").casefold()
            if x_type != "numeric" and not _is_temporal_result_column(
                chart.x_column or "", outcome.column_metadata
            ):
                is_valid = False
        if is_valid:
            return "chart", chart.model_dump()

    inferred = infer_chart_from_result(columns, rows, outcome.column_metadata)
    if inferred:
        return ("kpi" if inferred["type"] == "kpi" else "chart"), inferred
    return "table", None


def _outcome_to_result(
    outcome: ChatAgentOutcome,
    *,
    question: str,
    ctx: ToolContext,
    semantic_context: SemanticContext,
    trace: TraceRecorder,
    budget: BudgetGuard,
    wall_ms: float,
    progress=None,
) -> AgentRunResult:
    if outcome.response_type != "data_analysis":
        presentation_kind = "none" if outcome.presentation.kind == "table" else outcome.presentation.kind
        semantic_lineage = semantic_context.lineage_for_references(outcome.semantic_refs)
        return AgentRunResult(
            success=True,
            tier="agent",
            explanation=outcome.answer,
            relevant_tables=outcome.relevant_tables,
            relevant_columns=outcome.relevant_columns,
            trace=trace.to_list(),
            tool_calls=budget.call_count,
            wall_ms=wall_ms,
            response_kind=outcome.response_type,
            clarification_context=(
                outcome.clarification_context.model_dump() if outcome.clarification_context else None
            ),
            presentation_kind=presentation_kind,
            answer_metadata={
                "method": outcome.method,
                "limitations": outcome.limitations,
                "evidence": [],
            },
            semantic_lineage=semantic_lineage,
        )

    selected = ctx.analysis_results.get(outcome.result_ref or "")
    if selected is None:
        raise AgentFinishError("data_analysis selected an unknown or unsuccessful result_ref")

    result = selected.result
    for evidence in outcome.evidence:
        evidence_result = ctx.analysis_results.get(evidence.result_ref)
        if evidence_result is None:
            raise AgentFinishError("evidence selected an unknown result_ref")
        if any(column not in evidence_result.result.columns for column in evidence.columns):
            raise AgentFinishError("evidence referenced a column absent from its result")
        if any(index >= len(evidence_result.result.rows) for index in evidence.row_indexes):
            raise AgentFinishError("evidence referenced a row absent from its result")

    analytical_terms = {"outlier", "outliers", "anomaly", "anomalies", "unusual"}
    if analytical_terms & set(tokenize(question)) and not outcome.method:
        raise AgentFinishError("outlier and anomaly analyses require an explicit method")

    if progress:
        progress.stage_started("result_analysis", "Interpreting the query results")
        progress.stage_completed("result_analysis", "Result findings verified")
        progress.stage_started("presentation", "Preparing the response")
    presentation_kind, chart = _validated_chart(outcome, result.columns, result.rows)
    if progress:
        progress.stage_completed("presentation", "Response presentation ready")

    applied_lineage = semantic_context.lineage_for_references(outcome.semantic_refs)
    policy_lineage = semantic_context.lineage_for_references(
        selected.semantic_policy_refs, usage_role="policy_enforced"
    )
    return AgentRunResult(
        success=True,
        tier="agent",
        explanation=outcome.answer,
        sql=selected.sql,
        column_metadata=outcome.column_metadata,
        relevant_tables=outcome.relevant_tables,
        relevant_columns=outcome.relevant_columns,
        columns=result.columns,
        rows=result.rows,
        row_count=result.row_count,
        truncated=result.truncated,
        execution_time_ms=result.execution_time_ms,
        trace=trace.to_list(),
        tool_calls=budget.call_count,
        wall_ms=wall_ms,
        semantic_lineage=[*applied_lineage, *policy_lineage],
        response_kind="data_analysis",
        presentation_kind=presentation_kind,
        answer_metadata={
            "method": outcome.method,
            "limitations": outcome.limitations,
            "evidence": [item.model_dump() for item in outcome.evidence],
        },
        chart_recommendation=chart,
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
    progress=None,
    semantic_context: SemanticContext | None = None,
    llm_context: LlmExecutionContext | None = None,
    intent_result=None,
) -> AgentRunResult:
    started = time.monotonic()
    semantic_context = semantic_context or SemanticContext(schema_hash=catalog.schema_hash)
    catalog = apply_semantic_catalog_overlay(catalog, semantic_context)
    trace = TraceRecorder(on_step=progress.tool_completed if progress else None)
    ctx = ToolContext(
        user_id=user_id,
        connection_id=connection_id,
        catalog=catalog,
        engine=engine,
        trace=trace,
        invalidate_catalog=invalidate_catalog,
        rebuild_catalog=rebuild_catalog,
        cancellation_token=getattr(progress, "cancellation_token", None),
        grounded_terms=(
            set(tokenize(question))
            | {
                token
                for entry in semantic_context.definitions
                for token in tokenize(
                    " ".join(
                        [
                            entry.key,
                            entry.display_name,
                            entry.description,
                            str(entry.payload.get("table_name") or ""),
                            str(entry.payload.get("source_table") or ""),
                            str(entry.payload.get("column_name") or ""),
                        ]
                    )
                )
            }
        ),
        matched_tables=set(getattr(intent_result, "matched_tables", []) or []),
        allow_broad_discovery=bool(getattr(intent_result, "broad_discovery", False)),
        enforce_grounding=intent_result is not None,
        semantic_context=semantic_context,
    )
    tools = build_tools(ctx)
    tool_map = {tool.name: tool for tool in tools}
    budget = BudgetGuard(settings.agent_max_tool_calls, settings.agent_wall_clock_seconds)

    log_agent_event(
        "[agent] run start model=%s connection=%s question_chars=%d",
        settings.resolved_llm_model,
        connection_id,
        len(question),
    )

    try:
        if progress:
            progress.stage_started("interpreting", "Understanding how to help")
        llm_context = llm_context or LlmExecutionContext(
            owner_id=user_id,
            feature="chat",
            workflow_type="chat_session",
            workflow_id=connection_id,
        )
        llm = _get_llm(llm_context, tools)
        agent_graph = build_agent_graph(llm, tool_map, budget, ctx, trace, progress)

        messages: list[BaseMessage] = [SystemMessage(content=_build_system_prompt(catalog))]
        messages.extend(_build_context_messages(catalog, question, semantic_context))
        if history:
            messages.append(SystemMessage(content="CONVERSATION HISTORY — CONTEXT ONLY"))
            for msg in history[-10:]:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))
        messages.append(SystemMessage(content="CURRENT USER REQUEST — AUTHORITATIVE"))
        messages.append(HumanMessage(content=question))

        recursion_limit = settings.agent_max_tool_calls * 2 + 10
        final_state = _invoke_graph(agent_graph, messages, recursion_limit)
        if progress:
            progress.check_cancelled()
            progress.stage_completed("interpreting", "Request interpretation complete")

        proposal: ChatAgentOutcome | None = final_state["proposal"]
        finish_error: str | None = final_state["finish_error"]
        if proposal is None:
            wall_ms = round((time.monotonic() - started) * 1000, 2)
            failure_reason = _policy_rejection_reason(trace) or finish_error or "no_valid_proposal"
            log_agent_event(
                "[agent] run finish success=false tool_calls=%d wall_ms=%.0f reason=%s",
                budget.call_count,
                wall_ms,
                failure_reason,
            )
            return AgentRunResult(
                success=False,
                tier="agent",
                explanation="The agent could not produce a valid final response.",
                error=finish_error or "Agent run failed.",
                trace=trace.to_list(),
                tool_calls=budget.call_count,
                wall_ms=wall_ms,
                fallback_reason=failure_reason,
            )

        wall_ms = round((time.monotonic() - started) * 1000, 2)
        try:
            result = _outcome_to_result(
                proposal,
                question=question,
                ctx=ctx,
                semantic_context=semantic_context,
                trace=trace,
                budget=budget,
                wall_ms=wall_ms,
                progress=progress,
            )
        except (AgentFinishError, ValueError) as exc:
            log_agent_event("[agent] final outcome validation failed: %s", exc)
            failure_reason = _policy_rejection_reason(trace) or "agent_outcome_invalid"
            return AgentRunResult(
                success=False,
                tier="agent",
                explanation="The agent could not produce a grounded final response.",
                error=failure_reason,
                trace=trace.to_list(),
                tool_calls=budget.call_count,
                wall_ms=wall_ms,
                fallback_reason=failure_reason,
            )
        log_agent_event(
            "[agent] run finish success=true type=%s tool_calls=%d wall_ms=%.0f rows=%d",
            proposal.response_type,
            budget.call_count,
            wall_ms,
            result.row_count,
        )
        return result
    except Exception as exc:
        if exc.__class__.__name__ == "AgentRunCancelled":
            raise
        fallback_reason = _policy_rejection_reason(trace) or (
            "tool_use_failed" if _is_tool_use_failed(exc) else "agent_exception"
        )
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
            explanation="The agent could not produce a valid final response.",
            error=fallback_reason,
            trace=trace.to_list(),
            tool_calls=budget.call_count,
            wall_ms=wall_ms,
            fallback_reason=fallback_reason,
        )


__all__ = ["AgentRunResult", "AgentState", "build_agent_graph", "run_agent"]
