"""Tests for agent trace logging."""

import logging

from app.agents.db_agent.trace import TraceRecorder


def test_trace_record_emits_tool_log(caplog):
    caplog.set_level(logging.INFO, logger="query-mind.db_agent")
    trace = TraceRecorder()
    trace.record(
        "search_schema",
        "query=revenue",
        12.5,
        "ok",
        output_summary="matched orders, payments",
    )
    assert any("[tool] search_schema" in record.message for record in caplog.records)
    assert any("-> ok" in record.message for record in caplog.records)
