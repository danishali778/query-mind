from sqlalchemy import create_engine

from app.query_engine.executor import execute_query


def test_execute_query_allows_safe_select_on_sqlite():
    engine = create_engine("sqlite:///:memory:")

    result = execute_query("user-1", engine, "SELECT 1 AS value", row_limit=10, readonly=True)

    assert result.success is True
    assert result.rows == [{"value": 1}]


def test_execute_query_rejects_multiple_statements_before_execution():
    engine = create_engine("sqlite:///:memory:")

    result = execute_query("user-1", engine, "SELECT 1; SELECT 2", row_limit=10, readonly=True)

    assert result.success is False
    assert "Multiple SQL statements" in (result.error or "")


def test_execute_query_sanitizes_missing_table_errors():
    engine = create_engine("sqlite:///:memory:")

    result = execute_query("user-1", engine, "SELECT * FROM missing_table", row_limit=10, readonly=True)

    assert result.success is False
    assert result.error is not None
    assert "Table or column not found." in result.error
