"""Tests for schema namespace exclusions during introspection."""

from types import SimpleNamespace

from app.core.config import settings
from app.query_engine.schema_exclusions import (
    DEFAULT_EXCLUDED_SCHEMAS,
    is_schema_excluded,
    merge_excluded_schemas,
)
from app.query_engine.schema_inspector import _get_user_schema_names


def test_default_excluded_schemas_include_supabase_platform():
    assert "auth" in DEFAULT_EXCLUDED_SCHEMAS
    assert "realtime" in DEFAULT_EXCLUDED_SCHEMAS
    assert "storage" in DEFAULT_EXCLUDED_SCHEMAS
    assert "information_schema" in DEFAULT_EXCLUDED_SCHEMAS


def test_merge_excluded_schemas_adds_config_extra():
    merged = merge_excluded_schemas(["staging_internal", "auth"])
    assert "auth" in merged
    assert "staging_internal" in merged
    assert "public" not in merged


def test_is_schema_excluded_handles_pg_toast():
    excluded = merge_excluded_schemas()
    assert is_schema_excluded("pg_toast", excluded) is True
    assert is_schema_excluded("public", excluded) is False
    assert is_schema_excluded(None, excluded) is False


def test_get_user_schema_names_filters_excluded_namespaces():
    inspector = SimpleNamespace(
        get_schema_names=lambda: [
            "public",
            "auth",
            "realtime",
            "information_schema",
            "pg_catalog",
            "pg_toast_temp",
            "custom_app",
        ]
    )
    names = _get_user_schema_names(inspector)
    assert names == ["public", "custom_app"]


def test_get_user_schema_names_respects_config_extra(monkeypatch):
    monkeypatch.setattr(settings, "catalog_excluded_schemas_raw", "custom_app")
    inspector = SimpleNamespace(get_schema_names=lambda: ["public", "custom_app", "auth"])
    names = _get_user_schema_names(inspector)
    assert names == ["public"]
