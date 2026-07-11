"""Tests for schema catalog, sensitivity, and scoring."""

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.db.session as db_session
from app.agents.schema_context.catalog import build_catalog, compute_schema_hash, catalog_table_by_name
from app.agents.schema_context.scoring import score_tables, tokenize
from app.agents.schema_context.semantics import resolve_semantics, render_semantics_prompt
from app.agents.schema_context.sensitivity import filter_sample_values, is_sensitive_column
from app.db.base import Base
from app.db.models.connection import ColumnInfo, ForeignKeyInfo, TableInfo
from app.db.repositories import schema_snapshot_repository


@pytest.fixture(autouse=True)
def sqlite_app_db():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)
    db_session._engine = engine
    db_session._read_engine = engine
    db_session._session_factory = SessionLocal
    db_session._read_session_factory = SessionLocal
    Base.metadata.create_all(engine)
    try:
        yield
    finally:
        Base.metadata.drop_all(engine)
        db_session.reset_engine_for_tests()


def _sample_tables() -> list[TableInfo]:
    return [
        TableInfo(
            name="customers",
            row_count=100,
            columns=[
                ColumnInfo(name="id", type="uuid", nullable=False, primary_key=True),
                ColumnInfo(name="email", type="text", nullable=False, primary_key=False, sample_values=[]),
                ColumnInfo(name="status", type="text", nullable=True, primary_key=False, sample_values=["active", "inactive"]),
            ],
            foreign_keys=[],
        ),
        TableInfo(
            name="orders",
            row_count=500,
            columns=[
                ColumnInfo(name="id", type="uuid", nullable=False, primary_key=True),
                ColumnInfo(name="customer_id", type="uuid", nullable=False, primary_key=False),
                ColumnInfo(name="total_amount", type="numeric", nullable=False, primary_key=False),
                ColumnInfo(name="created_at", type="timestamp", nullable=False, primary_key=False),
            ],
            foreign_keys=[
                ForeignKeyInfo(column="customer_id", referred_table="customers", referred_column="id"),
            ],
        ),
        TableInfo(
            name="audit_logs",
            row_count=9999,
            columns=[ColumnInfo(name="id", type="bigint", nullable=False, primary_key=True)],
            foreign_keys=[],
        ),
    ]


def test_tokenize_splits_snake_case():
    tokens = tokenize("top_customers_by_revenue")
    assert "customer" in tokens or "customers" in tokens
    assert "revenue" in tokens


def test_build_catalog_marks_internal_and_sensitive():
    catalog = build_catalog("conn-1", "postgresql", _sample_tables())
    audit = catalog_table_by_name(catalog, "audit_logs")
    assert audit is not None
    assert audit.is_internal is True

    customers = catalog_table_by_name(catalog, "customers")
    assert customers is not None
    email_col = next(c for c in customers.columns if c.name == "email")
    assert email_col.is_sensitive is True
    assert email_col.sample_values == []

    status_col = next(c for c in customers.columns if c.name == "status")
    assert status_col.sample_values == ["active", "inactive"]


def test_is_sensitive_column_detects_email():
    assert is_sensitive_column("customer_email", "unknown") is True
    assert filter_sample_values("status", "category", ["paid", "pending"])[0] == ["paid", "pending"]


def test_score_tables_prefers_relevant_tables():
    catalog = build_catalog("conn-1", "postgresql", _sample_tables())
    scored = score_tables("top customers by revenue", catalog)
    names = [item.name for item in scored]
    assert "customers" in names
    assert "orders" in names
    assert "audit_logs" not in names


def test_schema_hash_changes_when_schema_changes():
    tables_a = _sample_tables()
    tables_b = _sample_tables()
    assert compute_schema_hash(tables_a) == compute_schema_hash(tables_b)
    tables_b[0].columns.append(
        ColumnInfo(name="phone", type="text", nullable=True, primary_key=False)
    )
    assert compute_schema_hash(tables_a) != compute_schema_hash(tables_b)


def test_snapshot_repository_round_trip():
    owner_id = str(uuid.uuid4())
    connection_id = str(uuid.uuid4())
    catalog = build_catalog(connection_id, "postgresql", _sample_tables())
    schema_snapshot_repository.upsert(catalog, owner_id)
    loaded = schema_snapshot_repository.get(owner_id, connection_id)
    assert loaded is not None
    assert loaded.schema_hash == catalog.schema_hash
    assert len(loaded.tables) == 3


def test_snapshot_repository_owner_isolation():
    owner_a = str(uuid.uuid4())
    owner_b = str(uuid.uuid4())
    connection_id = str(uuid.uuid4())
    catalog = build_catalog(connection_id, "postgresql", _sample_tables())
    schema_snapshot_repository.upsert(catalog, owner_a)
    assert schema_snapshot_repository.get(owner_b, connection_id) is None


def test_semantics_resolve_matches_customer_entity():
    catalog = build_catalog("conn-1", "postgresql", _sample_tables())
    matched = resolve_semantics("show top customers by revenue", catalog)
    assert any(entity.name == "customer" for entity in matched.entities)
    prompt = render_semantics_prompt(matched)
    assert "BUSINESS DEFINITIONS" in prompt
    assert "customers" in prompt
