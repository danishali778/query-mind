"""Tests for agent message compaction."""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.agents.db_agent.compaction import compact_messages, estimate_tokens


def test_estimate_tokens_counts_content():
    messages = [
        SystemMessage(content="x" * 400),
        HumanMessage(content="y" * 400),
    ]
    assert estimate_tokens(messages) >= 200


def test_compact_preserves_recent_tool_rounds():
    messages = [
        SystemMessage(content="system"),
        HumanMessage(content="question"),
        AIMessage(content="", tool_calls=[{"name": "list_tables", "args": {}, "id": "1"}]),
        ToolMessage(content="old", tool_call_id="1"),
        AIMessage(content="", tool_calls=[{"name": "search_schema", "args": {"query": "x"}, "id": "2"}]),
        ToolMessage(content="new", tool_call_id="2"),
    ]
    compacted, summary = compact_messages(
        messages,
        scratchpad=["found customers"],
        trace_steps=[
            {"tool": "list_tables", "outcome": "ok"},
            {"tool": "search_schema", "outcome": "ok"},
        ],
        keep_rounds=1,
    )
    assert summary is not None
    assert any(isinstance(m, HumanMessage) and "Earlier exploration summary" in str(m.content) for m in compacted)
    assert isinstance(compacted[-2], AIMessage)
    assert isinstance(compacted[-1], ToolMessage)
    assert compacted[-1].content == "new"


def test_compact_keeps_pairing_invariant():
    messages = [
        SystemMessage(content="system"),
        HumanMessage(content="question"),
        AIMessage(content="", tool_calls=[{"name": "list_tables", "args": {}, "id": "1"}]),
        ToolMessage(content="a", tool_call_id="1"),
        AIMessage(content="", tool_calls=[{"name": "search_schema", "args": {"query": "x"}, "id": "2"}]),
        ToolMessage(content="b", tool_call_id="2"),
    ]
    compacted, _ = compact_messages(messages, scratchpad=[], trace_steps=[], keep_rounds=1)
    for index, message in enumerate(compacted):
        if isinstance(message, AIMessage) and message.tool_calls:
            assert index + 1 < len(compacted)
            assert isinstance(compacted[index + 1], ToolMessage)


def test_compact_noop_when_few_rounds():
    messages = [
        HumanMessage(content="question"),
        AIMessage(content="", tool_calls=[{"name": "list_tables", "args": {}, "id": "1"}]),
        ToolMessage(content="a", tool_call_id="1"),
    ]
    compacted, summary = compact_messages(messages, scratchpad=[], trace_steps=[], keep_rounds=2)
    assert summary is None
    assert compacted == messages
