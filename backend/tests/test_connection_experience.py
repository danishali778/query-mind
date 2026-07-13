from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.errors import BadRequestError
from app.db.models.connection import ConnectionRequest
from app.query_engine.connection_scope import (
    normalize_scope,
    referenced_tables,
    validate_connection_scope_sql,
)
from app.query_engine.connection_tls import validate_tls_configuration
from app.query_engine.executor import execute_query
from app.services.connection_input import normalize_connection_input


def test_uri_normalization_decodes_credentials_without_retaining_uri():
    request = normalize_connection_input(
        {
            "input_mode": "uri",
            "connection_uri": "postgresql://reader%40team:p%40ss%3Aword@db.example.com:5433/analytics?sslmode=require",
        }
    )

    assert request.host == "db.example.com"
    assert request.port == 5433
    assert request.database == "analytics"
    assert request.username == "reader@team"
    assert request.password == "p@ss:word"
    assert request.ssl_mode == "require"
    assert "connection_uri" not in request.model_fields


@pytest.mark.parametrize(
    "uri",
    [
        "mysql://reader:secret@db.example.com/demo",
        "postgresql://reader:secret@db.example.com/demo#fragment",
        "postgresql://reader:secret@db.example.com/demo?sslrootcert=/tmp/ca.pem",
        "postgresql://reader:secret@db.example.com/demo?options=-c%20search_path%3Dprivate",
    ],
)
def test_uri_normalization_rejects_unsafe_inputs(uri: str):
    with pytest.raises(BadRequestError):
        normalize_connection_input({"input_mode": "uri", "connection_uri": uri})


def test_uri_and_field_credentials_conflict():
    with pytest.raises(BadRequestError) as exc:
        normalize_connection_input(
            {
                "input_mode": "uri",
                "connection_uri": "postgresql://reader:secret@db.example.com/demo",
                "host": "other.example.com",
            }
        )
    assert exc.value.code == "connection_uri_conflict"


def test_allowlist_scope_is_normalized_and_system_schemas_are_rejected():
    assert normalize_scope("allowlist", ["analytics", "analytics"], ["public.orders"]) == {
        "mode": "allowlist",
        "included_schemas": ["analytics"],
        "included_tables": ["public.orders"],
    }
    with pytest.raises(ValueError):
        normalize_scope("allowlist", ["pg_catalog"], [])


def test_scope_parser_ignores_cte_aliases_and_keeps_physical_tables():
    tables = referenced_tables(
        "WITH recent AS (SELECT id FROM analytics.orders) SELECT * FROM recent JOIN public.customers c ON c.id = recent.id"
    )
    assert tables == {"analytics.orders", "public.customers"}


def test_scope_validator_blocks_unknown_and_excluded_objects():
    scope = {
        "mode": "allowlist",
        "included_schemas": [],
        "included_tables": ["public.orders"],
        "known_tables": ["public.orders"],
    }
    with patch("app.query_engine.connection_scope._load_scope", return_value=scope):
        assert validate_connection_scope_sql("owner", "connection", "SELECT * FROM orders")[0]
        allowed, error = validate_connection_scope_sql("owner", "connection", "SELECT * FROM customers")
        assert not allowed and "unknown" in str(error).lower()
        allowed, _ = validate_connection_scope_sql("owner", "connection", "SELECT * FROM pg_catalog.pg_tables")
        assert not allowed


def test_executor_returns_stable_scope_violation_code():
    with patch(
        "app.query_engine.executor.validate_connection_scope_sql",
        return_value=(False, "Object is outside this connection scope."),
    ):
        result = execute_query(
            "owner", object(), "SELECT * FROM customers", connection_id="connection"
        )
    assert result.success is False
    assert result.error_code == "connection_scope_violation"


def test_tls_verification_requires_root_ca_and_mtls_pair():
    base = dict(
        db_type="postgresql", host="db.example.com", port=5432,
        database="analytics", username="reader", password="secret",
    )
    with pytest.raises(BadRequestError):
        validate_tls_configuration(ConnectionRequest(**base, ssl_mode="verify-full"))
    with pytest.raises(BadRequestError):
        validate_tls_configuration(
            ConnectionRequest(
                **base,
                ssl_mode="require",
                ssl_client_certificate="-----BEGIN CERTIFICATE-----\ninvalid\n-----END CERTIFICATE-----",
            )
        )
