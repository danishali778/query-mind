"""Agent evaluation harness (unit smoke + env-gated integration)."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
import yaml

from app.agents.schema_context.catalog import build_catalog
from app.agents.schema_context.scoring import score_tables
from app.db.models.connection import ColumnInfo, TableInfo


FIXTURES = Path(__file__).with_name("fixtures")


def _demo_catalog():
    tables = [
        TableInfo(
            name="customers",
            row_count=100,
            columns=[ColumnInfo(name="id", type="uuid", nullable=False, primary_key=True)],
        ),
        TableInfo(
            name="orders",
            row_count=500,
            columns=[ColumnInfo(name="customer_id", type="uuid", nullable=False, primary_key=False)],
        ),
        TableInfo(
            name="payments",
            row_count=400,
            columns=[ColumnInfo(name="amount", type="numeric", nullable=False, primary_key=False)],
        ),
        TableInfo(
            name="products",
            row_count=50,
            columns=[ColumnInfo(name="name", type="text", nullable=False, primary_key=False)],
        ),
        TableInfo(
            name="order_items",
            row_count=800,
            columns=[ColumnInfo(name="quantity", type="integer", nullable=False, primary_key=False)],
        ),
        TableInfo(
            name="audit_logs",
            row_count=10000,
            columns=[ColumnInfo(name="event", type="text", nullable=False, primary_key=False)],
        ),
        TableInfo(
            name="schema_migrations",
            row_count=1,
            columns=[ColumnInfo(name="name", type="text", nullable=False, primary_key=False)],
        ),
    ]
    return build_catalog("demo", "postgresql", tables)


def test_demo_schema_fixture_exists():
    sql = (FIXTURES / "demo_schema.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE" in sql
    assert re.search(r"customers", sql)


def test_agent_questions_fixture_loads():
    questions = yaml.safe_load((FIXTURES / "agent_questions.yml").read_text(encoding="utf-8"))
    assert isinstance(questions, list)
    assert questions[0]["question"]


def test_golden_questions_retriever_recall():
    catalog = _demo_catalog()
    questions = yaml.safe_load((FIXTURES / "agent_questions.yml").read_text(encoding="utf-8"))
    failures: list[str] = []

    for item in questions:
        scored = score_tables(item["question"], catalog)
        selected = {name.split(".")[-1] for name in (row.name for row in scored)}
        for expected in item.get("expected_tables", []):
            if expected not in selected:
                failures.append(f"{item['question']}: missing expected table {expected}")
        for forbidden in item.get("forbidden_tables", []):
            if forbidden in selected:
                failures.append(f"{item['question']}: included forbidden table {forbidden}")

    assert not failures, "\n".join(failures)


@pytest.mark.integration
def test_agent_golden_questions_on_demo_database():
    if os.environ.get("RUN_AGENT_EVAL") != "1":
        pytest.skip("Set RUN_AGENT_EVAL=1 to run agent evaluation harness")
    if not os.environ.get("AGENT_EVAL_DATABASE_URL"):
        pytest.skip("Set AGENT_EVAL_DATABASE_URL to run real agent evaluation")
    if not (os.environ.get("GROQ_API_KEY") or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        pytest.skip("Set GROQ_API_KEY or GEMINI_API_KEY to run real agent evaluation")

    from sqlalchemy import create_engine, text

    from app.agents.db_agent.agent import run_agent
    from app.core.config import settings
    from app.query_engine import schema_inspector
    from app.query_engine.safety import validate_query

    engine = create_engine(os.environ["AGENT_EVAL_DATABASE_URL"])
    demo_sql = (FIXTURES / "demo_schema.sql").read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.execute(text(demo_sql))

    schema = schema_inspector.get_schema(engine)
    catalog = build_catalog("eval-demo", "postgresql", schema)
    questions = yaml.safe_load((FIXTURES / "agent_questions.yml").read_text(encoding="utf-8"))

    for item in questions:
        result = run_agent(
            user_id="eval-user",
            connection_id="eval-demo",
            question=item["question"],
            catalog=catalog,
            engine=engine,
            history=[],
        )
        assert result.success, f"{item['question']}: {result.error}"
        assert result.tool_calls <= settings.agent_max_tool_calls
        assert result.wall_ms <= (settings.agent_wall_clock_seconds * 1000) + 5000
        if result.sql:
            is_safe, reason = validate_query(result.sql)
            assert is_safe, reason
            sql_lower = result.sql.lower()
            for forbidden in item.get("forbidden_tables", []):
                assert forbidden not in sql_lower
            referenced = any(table in sql_lower for table in item.get("expected_tables", []))
            trace_text = " ".join(step.get("tool", "") for step in result.trace).lower()
            assert referenced or "search_schema" in trace_text or "get_table_schema" in trace_text
