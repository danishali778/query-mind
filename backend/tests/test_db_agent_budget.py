"""Tests for agent budget warnings and repeat ladder."""

from app.agents.db_agent.budget import BudgetDecision, BudgetGuard


def test_budget_warning_fires_once_at_threshold():
    guard = BudgetGuard(max_calls=10, wall_clock_seconds=100)
    guard.call_count = 5
    first = guard.pending_warning()
    second = guard.pending_warning()
    assert first is not None
    assert "50%" in first or "5 of 10" in first
    assert second is None


def test_budget_warning_at_eighty_percent():
    guard = BudgetGuard(max_calls=10, wall_clock_seconds=100)
    guard.call_count = 8
    guard.warnings_issued.add(0.5)
    warning = guard.pending_warning()
    assert warning is not None
    assert "8 of 10" in warning


def test_repeat_ladder_warns_then_forces_after_two_identical_calls():
    guard = BudgetGuard(max_calls=20, wall_clock_seconds=120)
    args = {"query": "customers"}

    first = guard.check_before_call("search_schema", args)
    guard.record_call("search_schema", args)
    second = guard.check_before_call("search_schema", args)
    guard.record_call("search_schema", args)
    third = guard.check_before_call("search_schema", args)
    assert first == BudgetDecision.ALLOW
    assert second == BudgetDecision.WARN_REPEAT
    assert third == BudgetDecision.FORCE_FINISH


def test_skip_repeat_guard_message():
    guard = BudgetGuard(max_calls=20, wall_clock_seconds=120)
    guard.repeat_counts["abc"] = 3
    message = guard.guard_message(BudgetDecision.SKIP_REPEAT, "list_tables")
    assert message is not None
    assert "identical arguments" in message
