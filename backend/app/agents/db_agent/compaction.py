"""Context compaction for long agent runs."""

from __future__ import annotations

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage


def estimate_tokens(messages: list[BaseMessage]) -> int:
    total_chars = 0
    for message in messages:
        content = message.content
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            total_chars += len(str(content))
        if isinstance(message, AIMessage) and message.tool_calls:
            total_chars += len(str(message.tool_calls))
    return max(1, total_chars // 4)


def _identify_tool_rounds(messages: list[BaseMessage]) -> list[tuple[int, int]]:
    """Return inclusive (start, end) indices for each agent tool round."""
    rounds: list[tuple[int, int]] = []
    index = 0
    while index < len(messages):
        message = messages[index]
        if isinstance(message, AIMessage) and message.tool_calls:
            start = index
            index += 1
            while index < len(messages) and isinstance(messages[index], ToolMessage):
                index += 1
            while index < len(messages) and isinstance(messages[index], SystemMessage):
                index += 1
            rounds.append((start, index - 1))
        else:
            index += 1
    return rounds


def _build_summary(
    trace_steps: list[dict],
    scratchpad: list[str],
    prior_summaries: list[str],
) -> str:
    parts: list[str] = []
    if prior_summaries:
        parts.append(" ".join(prior_summaries))
    if trace_steps:
        tool_bits = []
        for step in trace_steps:
            tool_bits.append(f"{step['tool']} ({step['outcome']})")
        parts.append(f"Tools: {', '.join(tool_bits)}")
    if scratchpad:
        parts.append("Notes: " + "; ".join(scratchpad[-10:]))
    body = " ".join(part for part in parts if part).strip()
    return f"[Earlier exploration summary: {body}]" if body else "[Earlier exploration summary: no details captured]"


def compact_messages(
    messages: list[BaseMessage],
    *,
    scratchpad: list[str],
    trace_steps: list[dict],
    keep_rounds: int = 2,
) -> tuple[list[BaseMessage], HumanMessage | None]:
    """Remove older tool rounds and replace them with one summary HumanMessage."""
    rounds = _identify_tool_rounds(messages)
    if len(rounds) <= keep_rounds:
        return messages, None

    compact_rounds = rounds[: -keep_rounds]
    compact_start = compact_rounds[0][0]
    compact_end = compact_rounds[-1][1]

    prior_summaries: list[str] = []
    kept_prefix: list[BaseMessage] = []
    for message in messages[:compact_start]:
        if isinstance(message, HumanMessage) and str(message.content).startswith("[Earlier exploration summary:"):
            prior_summaries.append(str(message.content))
        else:
            kept_prefix.append(message)

    summary = _build_summary(trace_steps, scratchpad, prior_summaries)
    kept_suffix = messages[compact_end + 1 :]
    return [*kept_prefix, HumanMessage(content=summary), *kept_suffix], HumanMessage(content=summary)


__all__ = ["compact_messages", "estimate_tokens"]
