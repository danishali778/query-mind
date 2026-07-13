"""Unit tests for dashboard plan contract and layout helpers."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agents.dashboard_planner.plan import DashboardPlan, parse_dashboard_plan, reject_write_oriented_prompt
from app.db.repositories.dashboard_generation_repository import compute_placeholder_layouts


def test_parse_valid_plan():
    plan = parse_dashboard_plan(
        {
            "version": 1,
            "title": "Sales Overview",
            "description": "Track sales",
            "assumptions": ["Orders are completed"],
            "warnings": [],
            "widgets": [
                {
                    "client_key": "11111111-1111-1111-1111-111111111111",
                    "title": "Monthly Revenue",
                    "question": "What was revenue by month?",
                    "purpose": "Trend",
                    "visualization": "line",
                    "size": "full",
                    "time_range": "12 months",
                }
            ],
        }
    )
    assert isinstance(plan, DashboardPlan)
    assert plan.version == 1
    assert len(plan.widgets) == 1


def test_reject_duplicate_titles():
    with pytest.raises(ValidationError):
        parse_dashboard_plan(
            {
                "version": 1,
                "title": "Sales",
                "widgets": [
                    {
                        "client_key": "11111111-1111-1111-1111-111111111111",
                        "title": "Revenue",
                        "question": "What is revenue?",
                    },
                    {
                        "client_key": "22222222-2222-2222-2222-222222222222",
                        "title": "revenue",
                        "question": "What is profit?",
                    },
                ],
            }
        )


def test_reject_sql_in_question():
    with pytest.raises(ValidationError):
        parse_dashboard_plan(
            {
                "version": 1,
                "title": "Sales",
                "widgets": [
                    {
                        "client_key": "11111111-1111-1111-1111-111111111111",
                        "title": "Revenue",
                        "question": "SELECT amount FROM orders;",
                    }
                ],
            }
        )


def test_reject_write_prompt():
    with pytest.raises(ValueError):
        reject_write_oriented_prompt("Delete old customers and rebuild the dashboard")


def test_reject_unknown_fields():
    with pytest.raises(ValidationError):
        parse_dashboard_plan(
            {
                "version": 1,
                "title": "Sales",
                "sql": "SELECT 1",
                "widgets": [
                    {
                        "client_key": "11111111-1111-1111-1111-111111111111",
                        "title": "Revenue",
                        "question": "What is revenue?",
                    }
                ],
            }
        )


def test_layout_does_not_overlap():
    plans = [
        {"size": "half", "visualization": "kpi"},
        {"size": "half", "visualization": "kpi"},
        {"size": "full", "visualization": "line"},
        {"size": "quarter", "visualization": "kpi"},
    ]
    layouts = compute_placeholder_layouts(plans)
    assert len(layouts) == 4
    occupied = set()
    for layout in layouts:
        for dx in range(layout["w"]):
            for dy in range(layout["h"]):
                cell = (layout["x"] + dx, layout["y"] + dy)
                assert cell not in occupied
                occupied.add(cell)


def test_reject_non_uuid_client_key():
    with pytest.raises(ValidationError, match="valid UUID"):
        parse_dashboard_plan(
            {
                "version": 1,
                "title": "Sales",
                "widgets": [
                    {
                        "client_key": "stable-key",
                        "title": "Revenue",
                        "question": "What is revenue?",
                    }
                ],
            }
        )
