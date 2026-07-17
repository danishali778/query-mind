"""Mechanical salvage when the decision agent cannot finish its typed outcome."""

from __future__ import annotations

from app.agents.db_agent.output import ChatAgentOutcome, ClarificationContext
from app.agents.db_agent.tools import ToolContext
from app.agents.db_agent.trace import TraceRecorder


SALVAGE_FINISH_INSTRUCTION = (
    "Tool budget exhausted. Return the best final raw JSON outcome now. If a successful execute_sql "
    "result exists, return data_analysis and cite its result_ref. Otherwise return a direct answer, "
    "clarification, schema answer, or refusal. Do not invent query results."
)


def build_mechanical_salvage(trace: TraceRecorder, ctx: ToolContext) -> ChatAgentOutcome:
    if ctx.analysis_results:
        result_ref, stored = next(reversed(ctx.analysis_results.items()))
        columns = stored.result.columns
        return ChatAgentOutcome(
            response_type="data_analysis",
            answer=(
                "The read-only query completed, but the agent reached its reasoning budget before it "
                "could produce a detailed interpretation. Review the result table for the verified data."
            ),
            result_ref=result_ref,
            presentation={"kind": "table", "chart": None},
            evidence=[
                {
                    "claim": "The selected query completed successfully.",
                    "result_ref": result_ref,
                    "columns": columns[:5],
                    "row_indexes": [0] if stored.result.rows else [],
                }
            ],
            method="Read-only query execution; detailed analytical synthesis did not complete.",
            limitations=["Detailed result interpretation was not completed within the agent budget."],
            relevant_tables=[],
            relevant_columns=[],
            column_metadata={},
            semantic_refs=[],
        )
    return ChatAgentOutcome(
        response_type="clarification",
        answer="Which metric, table, or business outcome would you like me to analyze?",
        clarification_context=ClarificationContext(
            reason_code="agent_budget_exhausted",
            expected_input="metric_table_or_outcome",
        ),
        presentation={"kind": "none", "chart": None},
    )


__all__ = ["SALVAGE_FINISH_INSTRUCTION", "build_mechanical_salvage"]
