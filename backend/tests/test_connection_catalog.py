"""Tests for eager catalog lifecycle on connection flows."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.schema_context.types import CatalogColumn, CatalogTable, SchemaCatalog
from app.db import connection_manager
from app.db.models.connection import TableInfo


def _sample_catalog() -> SchemaCatalog:
    return SchemaCatalog(
        connection_id="conn-1",
        db_type="postgresql",
        schema_hash="abc123",
        captured_at="2026-07-05T00:00:00+00:00",
        tables=[
            CatalogTable(
                name="customers",
                row_estimate=100,
                columns=[
                    CatalogColumn(name="id", type="uuid", primary_key=True),
                    CatalogColumn(
                        name="account_id",
                        type="uuid",
                        fk_referred_table="accounts",
                        fk_referred_column="id",
                    ),
                ],
            )
        ],
    )

def test_connect_builds_catalog_on_success():
    config = MagicMock()
    engine = MagicMock()

    async def run():
        with (
            patch.object(connection_manager, "_preflight_connection_attempt"),
            patch.object(connection_manager.connection_pool, "open_connection", return_value=(engine, None)),
            patch.object(connection_manager.connection_repository, "create_connection", AsyncMock(return_value="conn-1")),
            patch.object(connection_manager.connection_repository, "record_connection_health", AsyncMock()),
            patch.object(connection_manager.connection_pool, "cache_connection"),
            patch.object(connection_manager, "_persist_catalog_for_connection", AsyncMock()) as mock_persist,
            patch.object(connection_manager, "_log_attempt"),
        ):
            connection_id, _, _ = await connection_manager.connect("user-1", config)

        assert connection_id == "conn-1"
        mock_persist.assert_awaited_once_with("user-1", "conn-1")

    asyncio.run(run())


def test_connect_catalog_failure_does_not_fail_connection():
    config = MagicMock()
    engine = MagicMock()

    async def run():
        with (
            patch.object(connection_manager, "_preflight_connection_attempt"),
            patch.object(connection_manager.connection_pool, "open_connection", return_value=(engine, None)),
            patch.object(connection_manager.connection_repository, "create_connection", AsyncMock(return_value="conn-1")),
            patch.object(connection_manager.connection_repository, "record_connection_health", AsyncMock()),
            patch.object(connection_manager.connection_pool, "cache_connection"),
            patch.object(
                connection_manager,
                "_persist_catalog_for_connection",
                AsyncMock(side_effect=RuntimeError("catalog failed")),
            ),
            patch.object(connection_manager, "_log_attempt"),
        ):
            connection_id, _, _ = await connection_manager.connect("user-1", config)

        assert connection_id == "conn-1"

    asyncio.run(run())


def test_refresh_schema_persists_catalog():
    schema = [TableInfo(name="customers", row_count=1, columns=[])]

    async def run():
        with (
            patch.object(connection_manager, "invalidate_catalog", AsyncMock()),
            patch.object(connection_manager, "get_cached_schema", AsyncMock(return_value=schema)),
            patch.object(connection_manager.connection_repository, "record_health_and_schema_sync", AsyncMock()),
            patch.object(connection_manager, "_persist_catalog_from_schema", AsyncMock()) as mock_persist,
        ):
            result = await connection_manager.refresh_schema("user-1", "conn-1")

        assert result == schema
        mock_persist.assert_awaited_once_with("user-1", "conn-1", schema)

    asyncio.run(run())


def test_catalog_to_table_info_maps_columns_and_foreign_keys():
    tables = connection_manager.catalog_to_table_info(_sample_catalog())

    assert len(tables) == 1
    assert tables[0].name == "customers"
    assert tables[0].row_count == 100
    assert tables[0].columns[0].name == "id"
    assert tables[0].foreign_keys[0].column == "account_id"
    assert tables[0].foreign_keys[0].referred_table == "accounts"


def test_get_connection_schema_reads_persisted_catalog_without_refresh():
    catalog = _sample_catalog()

    async def run():
        with (
            patch.object(connection_manager, "get_connection", AsyncMock(return_value=MagicMock())),
            patch.object(connection_manager.connection_pool, "peek_cached_schema", return_value=None),
            patch.object(connection_manager.connection_pool, "get_cached_catalog_entry", return_value=None),
            patch.object(connection_manager.schema_snapshot_repository, "get", return_value=catalog),
            patch.object(connection_manager.connection_pool, "cache_schema") as mock_cache_schema,
            patch.object(connection_manager.connection_pool, "cache_catalog") as mock_cache_catalog,
            patch.object(connection_manager, "get_cached_schema", AsyncMock()) as mock_get_cached_schema,
            patch.object(connection_manager, "refresh_schema", AsyncMock()) as mock_refresh,
        ):
            tables = await connection_manager.get_connection_schema("user-1", "conn-1")

        assert len(tables) == 1
        assert tables[0].name == "customers"
        mock_cache_schema.assert_called_once()
        mock_cache_catalog.assert_called_once()
        mock_get_cached_schema.assert_not_called()
        mock_refresh.assert_not_called()

    asyncio.run(run())
