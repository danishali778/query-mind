from __future__ import annotations

import pytest
import json
import asyncio
from types import SimpleNamespace
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.session as db_session
from app.agents.schema_context.types import CatalogColumn, CatalogTable, SchemaCatalog
from app.db.base import Base
from app.db.orm_models import DatabaseConnectionORM
from app.db.repositories import semantic_repository as repository
from app.query_engine.semantic_validation import validate_metric_expression, validate_structure
from app.services.semantic_drift_service import revalidate_sync
from app.services import semantic_service
from app.agents.schema_context import semantic_suggester


OWNER_ID = "11111111-1111-1111-1111-111111111111"
OTHER_OWNER_ID = "99999999-9999-9999-9999-999999999999"
CONNECTION_ID = "22222222-2222-2222-2222-222222222222"


@pytest.fixture(autouse=True)
def sqlite_app_db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    db_session._engine = engine
    db_session._read_engine = engine
    db_session._session_factory = factory
    db_session._read_session_factory = factory
    Base.metadata.create_all(engine)
    with db_session.session_scope() as session:
        session.add(
            DatabaseConnectionORM(
                id=CONNECTION_ID,
                owner_id=OWNER_ID,
                name="Analytics",
                db_type="postgresql",
                database="analytics",
                readonly=True,
            )
        )
    try:
        yield
    finally:
        Base.metadata.drop_all(engine)
        db_session.reset_engine_for_tests()


@pytest.fixture
def catalog():
    return SchemaCatalog(
        connection_id=CONNECTION_ID,
        db_type="postgresql",
        schema_hash="schema-v1",
        captured_at="2026-07-13T00:00:00Z",
        tables=[
            CatalogTable(
                name="orders",
                columns=[
                    CatalogColumn(name="id", type="integer", primary_key=True),
                    CatalogColumn(name="customer_id", type="integer", fk_referred_table="customers", fk_referred_column="id"),
                    CatalogColumn(name="total_amount", type="numeric", semantic_type="money"),
                    CatalogColumn(name="created_at", type="timestamp", semantic_type="datetime"),
                    CatalogColumn(name="email", type="text", semantic_type="email", is_sensitive=True),
                ],
            ),
            CatalogTable(
                name="customers",
                columns=[CatalogColumn(name="id", type="integer", primary_key=True)],
            ),
        ],
    )


def _create_metric():
    with db_session.session_scope() as session:
        return repository.create_definition_sync(
            session,
            owner_id=OWNER_ID,
            connection_id=CONNECTION_ID,
            kind="metric",
            key="revenue",
            display_name="Revenue",
            description="Paid order value",
            payload={"kind": "metric", "expression": "SUM(orders.total_amount)", "tables": ["orders"]},
        )


def test_lifecycle_versions_and_owner_scope():
    created = _create_metric()
    assert created.versions[0].status == "draft"
    assert created.versions[0].draft_revision == 1

    with db_session.session_scope() as session:
        updated = repository.update_draft_sync(
            session,
            owner_id=OWNER_ID,
            connection_id=CONNECTION_ID,
            definition_id=created.id,
            expected_revision=1,
            display_name="Net revenue",
            description="Validated revenue",
            payload=created.versions[0].payload,
        )
        assert updated.versions[0].draft_revision == 2

    with db_session.session_scope() as session:
        validated = repository.save_validation_sync(
            session,
            owner_id=OWNER_ID,
            connection_id=CONNECTION_ID,
            definition_id=created.id,
            version=1,
            schema_hash="schema-v1",
            validation_status="valid",
            validation_report={"warnings": [], "normalized_payload": created.versions[0].payload},
        )
        assert validated.versions[0].validation_status == "valid"

    with db_session.session_scope() as session:
        verified = repository.verify_version_sync(
            session,
            owner_id=OWNER_ID,
            connection_id=CONNECTION_ID,
            definition_id=created.id,
            version=1,
            expected_schema_hash="schema-v1",
            acknowledged_warning_codes=[],
            change_note="Matched finance report",
        )
        assert verified.versions[0].status == "verified"

    with db_session.read_session_scope() as session:
        assert repository.get_definition_model_sync(session, OTHER_OWNER_ID, CONNECTION_ID, created.id) is None


def test_revision_conflict_is_rejected():
    created = _create_metric()
    with db_session.session_scope() as session:
        with pytest.raises(repository.SemanticRevisionConflictError):
            repository.update_draft_sync(
                session,
                owner_id=OWNER_ID,
                connection_id=CONNECTION_ID,
                definition_id=created.id,
                expected_revision=99,
                display_name="Revenue",
                description="",
                payload=created.versions[0].payload,
            )


def test_metric_expression_requires_qualified_allowed_aggregate(catalog):
    normalized, errors, _warnings = validate_metric_expression(
        "SUM(orders.total_amount)", ["orders"], catalog
    )
    assert normalized == "SUM(orders.total_amount)"
    assert errors == []

    _, errors, _ = validate_metric_expression("pg_sleep(10)", ["orders"], catalog)
    assert {item.code for item in errors} >= {
        "metric_function_not_allowed",
        "metric_aggregation_required",
    }

    _, errors, _ = validate_metric_expression("SUM(total_amount)", ["orders"], catalog)
    assert "metric_column_unqualified" in {item.code for item in errors}


def test_sensitive_classification_cannot_be_weakened(catalog):
    result = validate_structure(
        "column",
        {
            "kind": "column",
            "table_name": "orders",
            "column_name": "email",
            "semantic_type": "email",
            "classification": "public",
            "synonyms": [],
        },
        catalog,
    )
    assert "sensitivity_cannot_be_weakened" in {item.code for item in result.errors}


def test_non_fk_relationship_warns(catalog):
    result = validate_structure(
        "relationship",
        {
            "kind": "relationship",
            "left_table": "orders",
            "left_column": "id",
            "right_table": "customers",
            "right_column": "id",
            "cardinality": "one_to_one",
            "join_type": "inner",
            "canonical": True,
        },
        catalog,
    )
    assert "relationship_not_physical_fk" in {item.code for item in result.warnings}


def test_schema_drift_keeps_compatible_definition_and_marks_broken_one_stale(catalog):
    created = _create_metric()
    with db_session.session_scope() as session:
        repository.save_validation_sync(
            session,
            owner_id=OWNER_ID,
            connection_id=CONNECTION_ID,
            definition_id=created.id,
            version=1,
            schema_hash="schema-v1",
            validation_status="valid",
            validation_report={"warnings": [], "normalized_payload": created.versions[0].payload},
        )
        repository.verify_version_sync(
            session,
            owner_id=OWNER_ID,
            connection_id=CONNECTION_ID,
            definition_id=created.id,
            version=1,
            expected_schema_hash="schema-v1",
            acknowledged_warning_codes=[],
            change_note=None,
        )

    compatible = catalog.model_copy(deep=True)
    compatible.schema_hash = "schema-v2"
    assert revalidate_sync(OWNER_ID, CONNECTION_ID, compatible) == {"valid": 1, "stale": 0}

    broken = compatible.model_copy(deep=True)
    broken.schema_hash = "schema-v3"
    broken.tables[0].columns = [
        column for column in broken.tables[0].columns if column.name != "total_amount"
    ]
    assert revalidate_sync(OWNER_ID, CONNECTION_ID, broken) == {"valid": 0, "stale": 1}

    with db_session.read_session_scope() as session:
        definition = repository.get_definition_model_sync(
            session, OWNER_ID, CONNECTION_ID, created.id
        )
    assert definition is not None
    assert definition.versions[0].status == "verified"
    assert definition.versions[0].validation_status == "stale"
    assert definition.versions[0].schema_hash == "schema-v3"


def test_suggestion_runs_are_idempotent_owner_scoped_and_connection_serialized():
    request_id = "33333333-3333-3333-3333-333333333333"
    with db_session.session_scope() as session:
        first, created = repository.create_suggestion_run_sync(
            session,
            owner_id=OWNER_ID,
            connection_id=CONNECTION_ID,
            client_request_id=request_id,
            schema_hash="schema-v1",
            requested_kinds=["metric"],
            business_context="Finance reporting",
        )
        repeated, repeated_created = repository.create_suggestion_run_sync(
            session,
            owner_id=OWNER_ID,
            connection_id=CONNECTION_ID,
            client_request_id=request_id,
            schema_hash="schema-v1",
            requested_kinds=["metric"],
            business_context="Finance reporting",
        )
        assert created is True
        assert repeated_created is False
        assert repeated.id == first.id
        with pytest.raises(repository.SemanticSuggestionConflictError):
            repository.create_suggestion_run_sync(
                session,
                owner_id=OWNER_ID,
                connection_id=CONNECTION_ID,
                client_request_id="44444444-4444-4444-4444-444444444444",
                schema_hash="schema-v1",
                requested_kinds=["dimension"],
                business_context=None,
            )

    with db_session.read_session_scope() as session:
        assert repository.get_suggestion_run_sync(
            session, OTHER_OWNER_ID, CONNECTION_ID, first.id
        ) is None
    with db_session.session_scope() as session:
        cancelled = repository.cancel_suggestion_run_sync(
            session, OWNER_ID, CONNECTION_ID, first.id
        )
        assert cancelled.status == "cancelled"


def test_semantic_health_counts_are_value_free_and_include_suggestion_metrics():
    metric = _create_metric()
    with db_session.session_scope() as session:
        repository.save_validation_sync(
            session,
            owner_id=OWNER_ID,
            connection_id=CONNECTION_ID,
            definition_id=metric.id,
            version=1,
            schema_hash="schema-v1",
            validation_status="invalid",
            validation_report={
                "errors": [{"code": "semantic_preview_failed", "message": "sanitized"}],
                "preview": {},
            },
        )
        run, _ = repository.create_suggestion_run_sync(
            session,
            owner_id=OWNER_ID,
            connection_id=CONNECTION_ID,
            client_request_id="55555555-5555-5555-5555-555555555555",
            schema_hash="schema-v1",
            requested_kinds=["metric"],
            business_context=None,
        )
        repository.claim_suggestion_run_sync(session, run.id)
        repository.finalize_suggestion_run_sync(
            session,
            run.id,
            status="failed",
            failure_code="semantic_suggestion_failed",
            failure_message="The suggestion could not be generated.",
        )

    diagnostics = repository.semantic_health_counts()
    assert diagnostics["invalid_definitions"] == 1
    assert diagnostics["failed_previews"] == 1
    assert diagnostics["suggestion_failed_runs"] == 1
    assert diagnostics["suggestion_failure_rate"] == 1.0
    assert "validation_report" not in diagnostics


def test_suggestion_generator_returns_structurally_valid_typed_candidates_without_samples(
    catalog, monkeypatch
):
    captured = {}

    class FakeLlm:
        def invoke(self, messages):
            captured["prompt"] = messages[-1].content
            return SimpleNamespace(
                content=json.dumps(
                    {
                        "candidates": [
                            {
                                "kind": "metric",
                                "key": "revenue",
                                "display_name": "Revenue",
                                "description": "Total order value",
                                "payload": {
                                    "kind": "metric",
                                    "expression": "SUM(orders.total_amount)",
                                    "tables": ["orders"],
                                },
                                "rationale": "A monetary order column is available.",
                                "assumptions": [],
                            }
                        ]
                    }
                )
            )

    monkeypatch.setattr(semantic_suggester, "get_chat_llm", lambda **_kwargs: FakeLlm())
    candidates = semantic_suggester.generate_semantic_candidates(
        catalog=catalog,
        requested_kinds=["metric"],
        business_context="Finance reporting",
        verified_definitions=[],
        max_candidates=25,
    )
    assert candidates[0]["kind"] == "metric"
    assert candidates[0]["structural_validation"]["valid"] is True
    assert "sample_values" not in captured["prompt"]


def test_filter_values_must_match_physical_column_type(catalog):
    result = validate_structure(
        "filter",
        {
            "kind": "filter",
            "table_name": "orders",
            "conjunction": "and",
            "conditions": [
                {"column": "total_amount", "operator": "gt", "value": "not-a-number"}
            ],
        },
        catalog,
    )
    assert "filter_value_type_mismatch" in {item.code for item in result.errors}


def test_verified_restricted_column_is_rejected_by_later_dimension_validation(catalog, monkeypatch):
    with db_session.session_scope() as session:
        restricted = repository.create_definition_sync(
            session,
            owner_id=OWNER_ID,
            connection_id=CONNECTION_ID,
            kind="column",
            key="private_email",
            display_name="Private email",
            description="Protected customer email",
            payload={
                "kind": "column",
                "table_name": "orders",
                "column_name": "email",
                "semantic_type": "email",
                "classification": "restricted",
                "synonyms": [],
            },
        )
        repository.save_validation_sync(
            session,
            owner_id=OWNER_ID,
            connection_id=CONNECTION_ID,
            definition_id=restricted.id,
            version=1,
            schema_hash="schema-v1",
            validation_status="valid",
            validation_report={"warnings": [], "normalized_payload": restricted.versions[0].payload},
        )
        repository.verify_version_sync(
            session,
            owner_id=OWNER_ID,
            connection_id=CONNECTION_ID,
            definition_id=restricted.id,
            version=1,
            expected_schema_hash="schema-v1",
            acknowledged_warning_codes=[],
            change_note=None,
        )
        dimension = repository.create_definition_sync(
            session,
            owner_id=OWNER_ID,
            connection_id=CONNECTION_ID,
            kind="dimension",
            key="email_dimension",
            display_name="Email",
            description="Email breakdown",
            payload={
                "kind": "dimension",
                "table_name": "orders",
                "column_name": "email",
                "label": "Email",
                "format": None,
                "synonyms": [],
            },
        )

    async def get_connection(*_args):
        return SimpleNamespace(id=CONNECTION_ID)

    async def get_catalog(*_args, **_kwargs):
        return catalog

    monkeypatch.setattr(semantic_service.connection_service, "get_connection", get_connection)
    monkeypatch.setattr(semantic_service.connection_service, "get_catalog", get_catalog)
    validated = asyncio.run(
        semantic_service.validate_version(
            OWNER_ID, CONNECTION_ID, dimension.id, 1, run_preview=False
        )
    )
    report = validated["versions"][0]["validation_report"]
    assert "column_not_found" in {item["code"] for item in report["errors"]}
