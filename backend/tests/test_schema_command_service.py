"""Tests for deterministic schema and control command routing."""

from app.agents.schema_context.catalog import build_catalog
from app.core.config import settings
from app.db.models.connection import ColumnInfo, TableInfo
from app.services.schema_command_service import handle_schema_or_control_command


def _catalog(table_count: int = 2):
    tables = [
        TableInfo(
            name="products",
            row_count=124,
            columns=[
                ColumnInfo(name="id", type="uuid", nullable=False, primary_key=True),
                ColumnInfo(name="name", type="text", nullable=False, primary_key=False),
                ColumnInfo(name="list_price", type="numeric", nullable=True, primary_key=False),
            ],
        ),
        TableInfo(
            name="orders",
            row_count=3000,
            columns=[
                ColumnInfo(name="id", type="uuid", nullable=False, primary_key=True),
                ColumnInfo(name="status", type="text", nullable=False, primary_key=False),
            ],
        ),
    ]
    for index in range(max(0, table_count - len(tables))):
        tables.append(TableInfo(name=f"extra_{index}", row_count=index, columns=[]))
    return build_catalog("conn-1", "postgresql", tables)


def test_list_tables_returns_schema_catalog_shape(monkeypatch):
    monkeypatch.setattr(settings, "agent_max_tables_listed", 50)
    result = handle_schema_or_control_command("show me all tables", _catalog(table_count=33))

    assert result is not None
    assert result["tier"] == "schema_catalog"
    assert result["sql"] is None
    assert result["row_count"] == 33
    assert result["columns"] == ["table_name", "schema_name", "row_estimate", "column_count"]
    assert result["trace"][0]["output_summary"] == "33 tables returned"


def test_list_tables_truncates_display(monkeypatch):
    monkeypatch.setattr(settings, "agent_max_tables_listed", 1)
    result = handle_schema_or_control_command("what tables exist?", _catalog(table_count=3))

    assert result is not None
    assert result["tier"] == "schema_catalog"
    assert result["row_count"] == 3
    assert len(result["rows"]) == 1
    assert result["truncated"] is True


def test_describe_table_returns_columns():
    result = handle_schema_or_control_command("describe products", _catalog())

    assert result is not None
    assert result["tier"] == "schema_catalog"
    assert result["row_count"] == 3
    assert {row["column_name"] for row in result["rows"]} == {"id", "name", "list_price"}


def test_ambiguous_table_name_returns_suggestions():
    catalog = build_catalog(
        "conn-1",
        "postgresql",
        [
            TableInfo(name="public.orders", columns=[ColumnInfo(name="id", type="uuid", nullable=False, primary_key=True)]),
            TableInfo(name="archive.orders", columns=[ColumnInfo(name="id", type="uuid", nullable=False, primary_key=True)]),
        ],
    )

    result = handle_schema_or_control_command("describe orders", catalog)

    assert result is not None
    assert result["tier"] == "schema_catalog"
    assert result["error"]
    assert {row["table_name"] for row in result["rows"]} == {"public.orders", "archive.orders"}


def test_write_intent_returns_controlled_refusal_without_catalog():
    result = handle_schema_or_control_command("delete all orders", None)

    assert result is not None
    assert result["tier"] == "controlled_refusal"
    assert result["sql"] is None
    assert result["trace"][0]["outcome"] == "refused"


def test_analytical_prompt_passes_through_to_agent():
    result = handle_schema_or_control_command("orders by status", _catalog())
    assert result is None

