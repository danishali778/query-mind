from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.session as db_session
from app.agents.schema_context.types import CatalogColumn, CatalogTable, SchemaCatalog
from app.db.base import Base
from app.db.orm_models import DatabaseConnectionORM
from app.db.repositories import semantic_repository as repository
from app.query_engine.semantic_validation import validate_metric_expression, validate_structure


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
