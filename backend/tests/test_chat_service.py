"""Tests for shared analysis execution used by chat and dashboard generation."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.schema_context.catalog import build_catalog
from app.agents.schema_context.user_semantics import SemanticContext
from app.core.config import settings
from app.db.models.connection import ColumnInfo, TableInfo
from app.services import analysis_service, chat_service


@pytest.fixture(autouse=True)
def _empty_semantic_context(monkeypatch):
    """Keep shared analysis tests independent from the application database."""

    async def load_context(_user_id, _connection_id, catalog, _question):
        return SemanticContext(schema_hash=catalog.schema_hash)

    monkeypatch.setattr(
        analysis_service.semantic_context_service,
        "load_context",
        load_context,
    )


def _catalog():
    return build_catalog(
        "conn-1",
        "postgresql",
        [
            TableInfo(
                name="products",
                row_count=124,
                columns=[
                    ColumnInfo(name="id", type="uuid", nullable=False, primary_key=True),
                    ColumnInfo(name="name", type="text", nullable=False, primary_key=False),
                ],
            )
        ],
    )


def test_run_agent_sync_passes_grounding_through_intent_result():
    catalog = _catalog()
    semantic_context = SemanticContext(schema_hash=catalog.schema_hash)
    intent_result = SimpleNamespace(
        matched_tables=["products"],
        broad_discovery=False,
    )
    agent_result = MagicMock()
    agent_result.as_chat_dict.return_value = {"success": True, "tier": "agent"}

    with patch.object(
        analysis_service,
        "run_agent",
        autospec=True,
        return_value=agent_result,
    ) as mock_run_agent:
        result = analysis_service._run_agent_sync(
            "user-1",
            "conn-1",
            "show active products",
            [],
            catalog,
            MagicMock(),
            semantic_context=semantic_context,
            intent_result=intent_result,
        )

    assert result == {"success": True, "tier": "agent"}
    call_kwargs = mock_run_agent.call_args.kwargs
    assert call_kwargs["intent_result"] is intent_result
    assert "grounded_tables" not in call_kwargs
    assert "enforce_grounding" not in call_kwargs
    assert "broad_discovery" not in call_kwargs


def test_chat_turn_delegates_to_analysis_service():
    async def run():
        with patch.object(
            chat_service.analysis_service,
            "run_analysis",
            AsyncMock(return_value={"tier": "agent", "explanation": "ok"}),
        ) as mock_analysis:
            result = await chat_service._execute_chat_turn(
                user_id="user-1",
                connection_id="conn-1",
                session_id="session-1",
                message="show active products",
                schema_context=None,
                history=[],
            )
        assert result["tier"] == "agent"
        mock_analysis.assert_awaited_once()

    asyncio.run(run())


def test_tools_mode_success_does_not_load_pipeline_schema(monkeypatch):
    monkeypatch.setattr(settings, "agent_mode", "tools")

    async def run():
        with (
            patch.object(analysis_service.connection_service, "get_catalog", AsyncMock(return_value=_catalog())),
            patch.object(analysis_service.connection_service, "get_engine", AsyncMock(return_value=MagicMock())),
            patch.object(analysis_service.connection_service, "get_schema_for_ai", AsyncMock()) as mock_schema,
            patch.object(
                analysis_service,
                "_run_agent_sync",
                return_value={
                    "success": True,
                    "explanation": "ok",
                    "sql": "SELECT 1",
                    "columns": [],
                    "rows": [],
                    "trace": [{"tool": "search_schema", "args_summary": "{}", "duration_ms": 1.0, "outcome": "ok"}],
                    "tier": "agent",
                },
            ),
            patch.object(analysis_service, "_run_pipeline_sync") as mock_pipeline,
        ):
            result = await analysis_service.run_analysis(
                user_id="user-1",
                connection_id="conn-1",
                question="show active products",
                session_id="session-1",
                schema_context=None,
                history=[],
            )

        assert result["tier"] == "agent"
        mock_schema.assert_not_called()
        mock_pipeline.assert_not_called()

    asyncio.run(run())


def test_tools_mode_schema_command_skips_agent_and_engine(monkeypatch):
    monkeypatch.setattr(settings, "agent_mode", "tools")

    async def run():
        with (
            patch.object(analysis_service.connection_service, "get_catalog", AsyncMock(return_value=_catalog())) as mock_catalog,
            patch.object(analysis_service.connection_service, "get_engine", AsyncMock()) as mock_engine,
            patch.object(analysis_service, "_run_agent_sync") as mock_agent,
            patch.object(analysis_service, "_run_pipeline_sync") as mock_pipeline,
        ):
            result = await analysis_service.run_analysis(
                user_id="user-1",
                connection_id="conn-1",
                question="show me all tables",
                session_id="session-1",
                schema_context=None,
                history=[],
            )

        assert result["tier"] == "schema_catalog"
        assert result["sql"] is None
        assert result["row_count"] == 1
        mock_catalog.assert_awaited_once()
        mock_engine.assert_not_called()
        mock_agent.assert_not_called()
        mock_pipeline.assert_not_called()

    asyncio.run(run())


def test_tools_mode_write_intent_skips_catalog_and_agent(monkeypatch):
    monkeypatch.setattr(settings, "agent_mode", "tools")

    async def run():
        with (
            patch.object(analysis_service.connection_service, "get_catalog", AsyncMock()) as mock_catalog,
            patch.object(analysis_service.connection_service, "get_engine", AsyncMock()) as mock_engine,
            patch.object(analysis_service, "_run_agent_sync") as mock_agent,
        ):
            result = await analysis_service.run_analysis(
                user_id="user-1",
                connection_id="conn-1",
                question="drop table orders",
                session_id="session-1",
                schema_context=None,
                history=[],
            )

        assert result["tier"] == "controlled_refusal"
        assert result["sql"] is None
        mock_catalog.assert_not_called()
        mock_engine.assert_not_called()
        mock_agent.assert_not_called()

    asyncio.run(run())


def test_tools_mode_agent_failure_falls_back_and_preserves_trace(monkeypatch):
    monkeypatch.setattr(settings, "agent_mode", "tools")

    async def run():
        with (
            patch.object(analysis_service.connection_service, "get_catalog", AsyncMock(return_value=_catalog())),
            patch.object(analysis_service.connection_service, "get_engine", AsyncMock(return_value=MagicMock())),
            patch.object(
                analysis_service.connection_service,
                "get_schema_for_ai",
                AsyncMock(return_value="Table: customers"),
            ),
            patch.object(
                analysis_service,
                "_run_agent_sync",
                return_value={
                    "success": False,
                    "error": "raw provider boom",
                    "fallback_reason": "tool_use_failed",
                    "trace": [{"tool": "search_schema", "args_summary": "{}", "duration_ms": 1.0, "outcome": "ok"}],
                },
            ),
            patch.object(
                analysis_service,
                "_run_pipeline_sync",
                return_value={"explanation": "pipeline answer", "sql": "SELECT 1"},
            ),
        ):
            result = await analysis_service.run_analysis(
                user_id="user-1",
                connection_id="conn-1",
                question="hello",
                session_id="session-1",
                schema_context=None,
                history=[],
            )

        assert result["tier"] == "fallback"
        assert result["trace"][0]["tool"] == "search_schema"
        assert result["trace"][-1]["tool"] == "fallback_pipeline"
        assert "tool_use_failed" in result["trace"][-1]["args_summary"]
        assert "raw provider boom" not in result["trace"][-1]["args_summary"]

    asyncio.run(run())


def test_tools_mode_agent_exception_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "agent_mode", "tools")

    async def run():
        with (
            patch.object(analysis_service.connection_service, "get_catalog", AsyncMock(return_value=_catalog())),
            patch.object(analysis_service.connection_service, "get_engine", AsyncMock(return_value=MagicMock())),
            patch.object(
                analysis_service.connection_service,
                "get_schema_for_ai",
                AsyncMock(return_value="Table: customers"),
            ),
            patch.object(analysis_service, "_run_agent_sync", side_effect=RuntimeError("boom")),
            patch.object(
                analysis_service,
                "_run_pipeline_sync",
                return_value={"explanation": "pipeline answer"},
            ),
        ):
            result = await analysis_service.run_analysis(
                user_id="user-1",
                connection_id="conn-1",
                question="hello",
                session_id="session-1",
                schema_context=None,
                history=[],
            )

        assert result["tier"] == "fallback"
        assert any(step["tool"] == "agent_exception" for step in result["trace"])
        assert result["trace"][-1]["tool"] == "fallback_pipeline"

    asyncio.run(run())


def test_pipeline_mode_loads_schema_and_sets_tier(monkeypatch):
    monkeypatch.setattr(settings, "agent_mode", "pipeline")

    async def run():
        with patch.object(
            analysis_service,
            "_run_pipeline_sync",
            return_value={"explanation": "pipeline answer"},
        ) as mock_pipeline:
            result = await analysis_service.run_analysis(
                user_id="user-1",
                connection_id="conn-1",
                question="hello",
                session_id="session-1",
                schema_context="Table: customers",
                history=[],
            )

        assert result["tier"] == "pipeline"
        mock_pipeline.assert_called_once()

    asyncio.run(run())
