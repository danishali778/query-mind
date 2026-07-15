"""Mechanical salvage when the LLM cannot produce a final JSON proposal."""

from __future__ import annotations

from app.agents.db_agent.output import AnalystProposal
from app.agents.db_agent.tools import ToolContext
from app.agents.db_agent.trace import TraceRecorder


SALVAGE_FINISH_INSTRUCTION = (
    "Tool budget exhausted. Review the scratchpad and tool results above. "
    "Return your best raw JSON proposal with keys response_type, clarification_question, "
    "analysis_summary, relevant_tables, relevant_columns, sql, column_metadata, assumptions, "
    "semantic_refs. If no grounded safe SQL is available, return a clarification proposal."
)


def build_mechanical_salvage(trace: TraceRecorder, ctx: ToolContext) -> AnalystProposal:
    steps = trace.to_list()
    tools_called = [step["tool"] for step in steps]
    tables_touched: list[str] = []
    for step in steps:
        args = step.get("args_summary", "")
        if "table_names" in args or "table" in args:
            tables_touched.append(args[:120])

    lines = [
        "The agent could not finish with a model-generated SQL proposal.",
        f"Tools used ({len(tools_called)}): {', '.join(tools_called) if tools_called else 'none'}.",
    ]
    if ctx.scratchpad:
        lines.append("Findings: " + "; ".join(ctx.scratchpad[:10]))
    if tables_touched:
        lines.append("Tables examined: " + "; ".join(tables_touched[:5]))
    lines.append("No backend-validated SQL proposal was available.")
    return AnalystProposal(
        response_type="clarification",
        clarification_question="Which metric, table, or business outcome should I analyze?",
        analysis_summary=" ".join(lines),
        relevant_tables=[],
        relevant_columns=[],
        sql=None,
        column_metadata={},
        assumptions=[],
    )


__all__ = ["SALVAGE_FINISH_INSTRUCTION", "build_mechanical_salvage"]
