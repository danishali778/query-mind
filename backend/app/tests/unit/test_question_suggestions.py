from types import SimpleNamespace

import pytest

from app.agents.question_suggestions.context import build_generation_context
from app.agents.question_suggestions.deterministic import generate_deterministic_bundle
from app.agents.question_suggestions.generator import _validate_bundle
from app.agents.schema_context.types import CatalogColumn, CatalogTable, SchemaCatalog
from app.db.models.question_suggestions import QuestionSuggestion


def _catalog() -> SchemaCatalog:
    return SchemaCatalog(
        connection_id="connection-1",
        db_type="postgresql",
        schema_hash="schema-v1",
        captured_at="2026-07-13T00:00:00Z",
        tables=[
            CatalogTable(
                name="orders",
                columns=[
                    CatalogColumn(name="created_at", type="timestamp"),
                    CatalogColumn(name="amount", type="numeric"),
                    CatalogColumn(name="status", type="text"),
                    CatalogColumn(name="customer_email", type="text", is_sensitive=True),
                ],
            ),
            CatalogTable(name="private_notes", columns=[CatalogColumn(name="body", type="text")]),
        ],
    )


def _row(kind: str, key: str, display: str, payload: dict, *, version_id: str):
    return (
        SimpleNamespace(id=f"definition-{key}", kind=kind, key=key),
        SimpleNamespace(
            id=version_id,
            version=1,
            display_name=display,
            description="Verified business metadata",
            payload=payload,
            schema_hash="schema-v1",
        ),
    )


def test_context_fingerprint_changes_with_scope_revision():
    first = build_generation_context(
        catalog=_catalog(), scope_revision=1, rows=[], max_characters=12000
    )
    second = build_generation_context(
        catalog=_catalog(), scope_revision=2, rows=[], max_characters=12000
    )
    assert first.context_fingerprint != second.context_fingerprint
    assert first.semantic_fingerprint == second.semantic_fingerprint


def test_hidden_restricted_and_sensitive_objects_are_not_evidence():
    rows = [
        _row("table", "notes", "Private notes", {"table_name": "private_notes", "visibility": "hidden"}, version_id="v-hidden"),
        _row("column", "email", "Customer email", {"table_name": "orders", "column_name": "customer_email", "classification": "restricted"}, version_id="v-restricted"),
        _row("column", "amount", "Order amount", {"table_name": "orders", "column_name": "amount", "classification": "sensitive"}, version_id="v-sensitive"),
    ]
    context = build_generation_context(
        catalog=_catalog(), scope_revision=1, rows=rows, max_characters=12000
    )
    labels = {item.label for item in context.evidence}
    assert all("private_notes" not in label for label in labels)
    assert all("customer_email" not in label for label in labels)
    assert "Order amount" not in labels
    assert [table.name for table in context.catalog.tables] == ["orders"]
    assert all(column.sample_values == [] for table in context.catalog.tables for column in table.columns)


def test_verified_metric_drives_diverse_deterministic_suggestions():
    context = build_generation_context(
        catalog=_catalog(),
        scope_revision=1,
        rows=[
            _row("metric", "revenue", "Revenue", {"formula": "SUM(orders.amount)"}, version_id="v-metric"),
            _row("date_policy", "order_date", "Order date", {"table_name": "orders", "column_name": "created_at"}, version_id="v-date"),
            _row("dimension", "status", "Order status", {"table_name": "orders", "column_name": "status"}, version_id="v-dimension"),
        ],
        max_characters=12000,
    )
    bundle = generate_deterministic_bundle(context)
    assert set(bundle) == {"chat", "dashboard", "connection", "library"}
    assert len(bundle["chat"]) == 6
    assert len({item["category"] for item in bundle["chat"]}) >= 4
    assert any("Revenue" in item["prompt"] for item in bundle["chat"])
    assert all(item["id"].startswith("qs_") for items in bundle.values() for item in items)


@pytest.mark.parametrize(
    "prompt",
    ["Delete old orders", "```sql\nSELECT * FROM orders\n```", "Update every customer record"],
)
def test_public_contract_rejects_write_or_sql_prompts(prompt: str):
    with pytest.raises(ValueError):
        QuestionSuggestion(
            id="qs_1234567890abcdef",
            surface="chat",
            title="Unsafe",
            prompt=prompt,
            category="kpi",
            source="ai",
        )


def test_ai_bundle_rejects_unknown_evidence_reference():
    context = build_generation_context(
        catalog=_catalog(), scope_revision=1, rows=[], max_characters=12000
    )
    payload = {
        "version": 1,
        "chat": [{
            "surface": "chat",
            "title": "Orders",
            "prompt": "Summarize order volume.",
            "rationale": "Orders are available.",
            "category": "kpi",
            "based_on_refs": ["tbl_unknown"],
        }],
        "dashboard": [],
        "connection": [],
        "library": [],
    }
    with pytest.raises(ValueError, match="not supplied"):
        _validate_bundle(payload, context)
