from types import SimpleNamespace

from app.agents.schema_context.types import CatalogColumn, CatalogTable, SchemaCatalog
from app.agents.schema_context.user_semantics import (
    apply_semantic_catalog_overlay,
    build_semantic_context,
    render_untrusted_semantic_context,
)
from app.query_engine.semantic_policy import validate_ai_semantic_policy


def _catalog() -> SchemaCatalog:
    return SchemaCatalog(
        connection_id="connection-1",
        db_type="postgresql",
        schema_hash="hash-1",
        captured_at="2026-07-13T00:00:00Z",
        tables=[
            CatalogTable(
                name="orders",
                columns=[
                    CatalogColumn(name="total", type="numeric"),
                    CatalogColumn(name="email", type="text", sample_values=["hidden@example.com"]),
                    CatalogColumn(name="secret", type="text"),
                ],
            ),
            CatalogTable(name="audit_log", columns=[CatalogColumn(name="id", type="integer")]),
        ],
    )


def _row(kind: str, key: str, payload: dict, *, version: int = 1, schema_hash: str = "hash-1"):
    definition = SimpleNamespace(id=f"def-{key}", kind=kind, key=key)
    definition_version = SimpleNamespace(
        id=f"version-{key}",
        version=version,
        display_name=key.replace("_", " ").title(),
        description=f"Business definition for {key}",
        payload=payload,
        schema_hash=schema_hash,
    )
    return definition, definition_version


def test_context_matches_relevant_versions_and_excludes_stale_versions():
    context = build_semantic_context(
        catalog=_catalog(),
        rows=[
            _row(
                "metric",
                "revenue",
                {"kind": "metric", "expression": "SUM(orders.total)", "tables": ["orders"]},
            ),
            _row(
                "metric",
                "old_revenue",
                {"kind": "metric", "expression": "SUM(orders.total)", "tables": ["orders"]},
                schema_hash="old-hash",
            ),
        ],
        question="Show revenue by month",
        max_definitions=20,
        max_characters=12_000,
    )
    assert [entry.key for entry in context.definitions] == ["revenue"]
    assert context.definitions[0].reference == "sem_metric_revenue_v1"


def test_untrusted_metadata_is_serialized_as_data_not_system_instructions():
    context = build_semantic_context(
        catalog=_catalog(),
        rows=[
            _row(
                "metric",
                "revenue",
                {"kind": "metric", "expression": "SUM(orders.total)", "tables": ["orders"]},
            )
        ],
        question="revenue",
        max_definitions=20,
        max_characters=12_000,
    )
    rendered = render_untrusted_semantic_context(context)
    assert rendered.startswith("UNTRUSTED SEMANTIC METADATA")
    assert '"reference":"sem_metric_revenue_v1"' in rendered


def test_overlay_hides_tables_restricts_columns_and_removes_sensitive_samples():
    context = build_semantic_context(
        catalog=_catalog(),
        rows=[
            _row("table", "audit", {"kind": "table", "table_name": "audit_log", "visibility": "hidden"}),
            _row(
                "column",
                "secret",
                {
                    "kind": "column",
                    "table_name": "orders",
                    "column_name": "secret",
                    "classification": "restricted",
                    "semantic_type": "free_text",
                },
            ),
            _row(
                "column",
                "email",
                {
                    "kind": "column",
                    "table_name": "orders",
                    "column_name": "email",
                    "classification": "sensitive",
                    "semantic_type": "email",
                },
            ),
        ],
        question="audit secret email",
        max_definitions=20,
        max_characters=12_000,
    )
    overlaid = apply_semantic_catalog_overlay(_catalog(), context)
    assert [table.name for table in overlaid.tables] == ["orders"]
    assert [column.name for column in overlaid.tables[0].columns] == ["total", "email"]
    assert overlaid.tables[0].columns[1].is_sensitive is True
    assert overlaid.tables[0].columns[1].sample_values == []


def test_sql_policy_rejects_restricted_and_raw_sensitive_projection_but_allows_aggregate():
    context = build_semantic_context(
        catalog=_catalog(),
        rows=[
            _row(
                "column",
                "secret",
                {"kind": "column", "table_name": "orders", "column_name": "secret", "classification": "restricted"},
            ),
            _row(
                "column",
                "total",
                {"kind": "column", "table_name": "orders", "column_name": "total", "classification": "sensitive"},
            ),
        ],
        question="secret total",
        max_definitions=20,
        max_characters=12_000,
    )
    assert not validate_ai_semantic_policy("SELECT orders.secret FROM orders", context).allowed
    assert not validate_ai_semantic_policy("SELECT orders.total FROM orders", context).allowed
    aggregate = validate_ai_semantic_policy("SELECT SUM(orders.total) FROM orders", context)
    assert aggregate.allowed
    assert aggregate.enforced_references == ["sem_column_total_v1"]


def test_unknown_agent_reference_is_rejected():
    context = build_semantic_context(
        catalog=_catalog(),
        rows=[],
        question="revenue",
        max_definitions=20,
        max_characters=12_000,
    )
    try:
        context.lineage_for_references(["sem_metric_invented_v1"])
    except ValueError as exc:
        assert "not supplied" in str(exc)
    else:
        raise AssertionError("Unknown semantic reference was accepted")
