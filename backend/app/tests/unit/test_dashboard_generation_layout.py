"""Unit tests for dashboard generation layout and status helpers."""

from __future__ import annotations

from app.db.repositories.dashboard_generation_repository import (
    ACTIVE_RUN_STATUSES,
    TERMINAL_RUN_STATUSES,
    compute_placeholder_layouts,
)


def test_active_and_terminal_statuses_disjoint():
    assert set(ACTIVE_RUN_STATUSES).isdisjoint(set(TERMINAL_RUN_STATUSES))


def test_three_quarter_and_full_use_twenty_column_grid():
    layouts = compute_placeholder_layouts(
        [
            {"size": "three-quarter", "visualization": "bar"},
            {"size": "full", "visualization": "line"},
        ]
    )
    assert layouts[0]["w"] == 15
    assert layouts[1]["w"] == 20
    assert layouts[1]["y"] >= layouts[0]["y"] + layouts[0]["h"]


def test_kpi_half_row_packing():
    layouts = compute_placeholder_layouts(
        [
            {"size": "half", "visualization": "kpi"},
            {"size": "half", "visualization": "kpi"},
        ]
    )
    assert layouts[0]["x"] == 0
    assert layouts[1]["x"] == 10
    assert layouts[0]["y"] == layouts[1]["y"]
