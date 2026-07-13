from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.session as db_session
from app.db.base import Base
from app.db.orm_models import (
    DashboardGenerationItemORM,
    DashboardGenerationRunORM,
    DashboardORM,
    DashboardWidgetORM,
    SemanticDefinitionORM,
    SemanticDefinitionUsageORM,
    SemanticDefinitionVersionORM,
)
from app.db.repositories import dashboard_generation_repository as repository
from app.services import dashboard_generation_service


OWNER_ID = "11111111-1111-1111-1111-111111111111"
CONNECTION_ID = "22222222-2222-2222-2222-222222222222"
RUN_ID = "33333333-3333-3333-3333-333333333333"
DASHBOARD_ID = "44444444-4444-4444-4444-444444444444"
ITEM_ID = "55555555-5555-5555-5555-555555555555"
WIDGET_ID = "66666666-6666-6666-6666-666666666666"


@pytest.fixture(autouse=True)
def sqlite_app_db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)
    db_session._engine = engine
    db_session._read_engine = engine
    db_session._session_factory = factory
    db_session._read_session_factory = factory
    Base.metadata.create_all(engine)
    try:
        yield
    finally:
        Base.metadata.drop_all(engine)
        db_session.reset_engine_for_tests()


def _add_run(*, status: str, stage: str = "queued", dashboard_id: str | None = None) -> None:
    with db_session.session_scope() as session:
        session.add(
            DashboardGenerationRunORM(
                id=RUN_ID,
                owner_id=OWNER_ID,
                connection_id=CONNECTION_ID,
                dashboard_id=dashboard_id,
                client_request_id="77777777-7777-7777-7777-777777777777",
                prompt="Build a revenue dashboard",
                requested_widget_count=1,
                status=status,
                current_stage=stage,
                current_stage_label="Queued",
                heartbeat_at=datetime.now(timezone.utc),
            )
        )


def _add_failed_widget_run() -> None:
    with db_session.session_scope() as session:
        session.add(
            DashboardORM(
                id=DASHBOARD_ID,
                owner_id=OWNER_ID,
                name="Revenue",
                filters={},
                is_public=False,
                creation_mode="ai",
                lifecycle_status="draft",
            )
        )
        session.add(
            DashboardGenerationRunORM(
                id=RUN_ID,
                owner_id=OWNER_ID,
                connection_id=CONNECTION_ID,
                dashboard_id=DASHBOARD_ID,
                client_request_id="77777777-7777-7777-7777-777777777777",
                prompt="Build a revenue dashboard",
                requested_widget_count=1,
                status="partial",
                current_stage="partial",
                current_stage_label="Partially completed",
                cancel_requested_at=datetime.now(timezone.utc),
            )
        )
        session.add(
            DashboardGenerationItemORM(
                id=ITEM_ID,
                run_id=RUN_ID,
                client_key="88888888-8888-8888-8888-888888888888",
                dashboard_widget_id=WIDGET_ID,
                order_index=0,
                plan_json={"title": "Revenue", "question": "Revenue?"},
                status="failed",
            )
        )
        session.add(
            DashboardWidgetORM(
                id=WIDGET_ID,
                dashboard_id=DASHBOARD_ID,
                owner_id=OWNER_ID,
                connection_id=CONNECTION_ID,
                title="Revenue",
                viz_type="table",
                generation_item_id=ITEM_ID,
                generation_status="failed",
            )
        )


def test_execution_run_and_item_are_claimed_once():
    _add_run(status="queued")
    with db_session.session_scope() as session:
        session.add(
            DashboardGenerationItemORM(
                id=ITEM_ID,
                run_id=RUN_ID,
                client_key="88888888-8888-8888-8888-888888888888",
                plan_json={"title": "Revenue"},
                status="queued",
            )
        )

    with db_session.session_scope() as session:
        assert repository.claim_execution_run_sync(session, RUN_ID).status == "running"
    with db_session.session_scope() as session:
        assert repository.claim_execution_run_sync(session, RUN_ID) is None
        assert repository.claim_item_sync(session, ITEM_ID).status == "running"
    with db_session.session_scope() as session:
        assert repository.claim_item_sync(session, ITEM_ID) is None


def test_reopen_terminal_run_clears_cancellation_and_requeues_widget():
    _add_failed_widget_run()
    with db_session.session_scope() as session:
        reopened = repository.reopen_run_for_item_sync(
            session,
            OWNER_ID,
            RUN_ID,
            ITEM_ID,
            item_status="queued",
            allowed_item_statuses=("failed", "cancelled"),
        )
        assert reopened.status == "queued"
        assert reopened.cancel_requested_at is None

    with db_session.read_session_scope() as session:
        item = session.get(DashboardGenerationItemORM, ITEM_ID)
        widget = session.get(DashboardWidgetORM, WIDGET_ID)
        assert item.status == "queued"
        assert widget.generation_status == "queued"


def test_latest_run_lookup_is_dashboard_and_owner_scoped():
    _add_failed_widget_run()
    found = asyncio.run(repository.get_latest_run_for_dashboard(OWNER_ID, DASHBOARD_ID))
    assert found and found.id == RUN_ID
    assert asyncio.run(repository.get_latest_run_for_dashboard("99999999-9999-9999-9999-999999999999", DASHBOARD_ID)) is None


def test_cancel_awaiting_approval_finalizes_immediately(monkeypatch):
    _add_run(status="awaiting_approval", stage="plan_ready")
    monkeypatch.setattr(dashboard_generation_service, "signal_cancel", lambda _run_id: None)
    monkeypatch.setattr(dashboard_generation_service, "publish_event", lambda *_args, **_kwargs: {})

    snapshot = asyncio.run(dashboard_generation_service.cancel(OWNER_ID, RUN_ID))

    assert snapshot["status"] == "cancelled"
    assert snapshot["failure_code"] == "dashboard_generation_cancelled"


def _semantic_context() -> dict:
    return {
        "schema_hash": "schema-v1",
        "policy": {"hidden_tables": {}, "restricted_columns": {}, "sensitive_columns": {}},
        "definitions": [
            {
                "definition_id": "99999999-1111-1111-1111-111111111111",
                "version_id": "99999999-2222-2222-2222-222222222222",
                "reference": "sem_metric_revenue_v1",
                "kind": "metric",
                "key": "revenue",
                "display_name": "Revenue",
                "description": "Completed order value",
                "version": 1,
                "payload": {
                    "kind": "metric",
                    "expression": "SUM(orders.total)",
                    "tables": ["orders"],
                },
            }
        ],
    }


def _add_verified_metric() -> None:
    with db_session.session_scope() as session:
        definition = SemanticDefinitionORM(
            id="99999999-1111-1111-1111-111111111111",
            owner_id=OWNER_ID,
            connection_id=CONNECTION_ID,
            kind="metric",
            key="revenue",
        )
        definition.versions.append(
            SemanticDefinitionVersionORM(
                id="99999999-2222-2222-2222-222222222222",
                definition_id=definition.id,
                version=1,
                status="verified",
                display_name="Revenue",
                description="Completed order value",
                payload={"kind": "metric", "expression": "SUM(orders.total)", "tables": ["orders"]},
                schema_hash="schema-v1",
                validation_status="valid",
                validation_report={},
                created_by=OWNER_ID,
                verified_by=OWNER_ID,
            )
        )
        session.add(definition)


def _semantic_plan(reference: str) -> dict:
    return {
        "version": 1,
        "title": "Revenue",
        "description": "Revenue dashboard",
        "assumptions": [],
        "warnings": [],
        "widgets": [
            {
                "client_key": "88888888-8888-8888-8888-888888888888",
                "title": "Revenue",
                "question": "What is revenue?",
                "purpose": "Track revenue",
                "visualization": "kpi",
                "size": "quarter",
                "time_range": None,
                "semantic_refs": [reference],
            }
        ],
    }


def test_plan_rejects_refs_outside_frozen_context():
    _add_run(status="awaiting_approval", stage="plan_ready")
    with db_session.session_scope() as session:
        with pytest.raises(repository.GenerationNotApprovableError):
            repository.save_plan_sync(
                session,
                OWNER_ID,
                RUN_ID,
                _semantic_plan("sem_metric_invented_v1"),
                expected_revision=0,
                semantic_context_json=_semantic_context(),
            )


def test_approval_pins_widget_lineage_and_indexes_run_and_widget_usage():
    _add_verified_metric()
    _add_run(status="awaiting_approval", stage="plan_ready")
    with db_session.session_scope() as session:
        saved = repository.save_plan_sync(
            session,
            OWNER_ID,
            RUN_ID,
            _semantic_plan("sem_metric_revenue_v1"),
            expected_revision=0,
            semantic_context_json=_semantic_context(),
        )
        assert saved.semantic_context_json["schema_hash"] == "schema-v1"
    with db_session.session_scope() as session:
        run, _dashboard, widgets, created = repository.approve_plan_sync(
            session, OWNER_ID, RUN_ID, expected_revision=1
        )
        assert created is True
        assert run.semantic_context_json["definitions"][0]["version"] == 1
        assert widgets[0].semantic_lineage[0]["reference"] == "sem_metric_revenue_v1"

    with db_session.read_session_scope() as session:
        usages = session.query(SemanticDefinitionUsageORM).all()
    assert {(usage.consumer_type, usage.usage_role) for usage in usages} == {
        ("dashboard_generation", "applied"),
        ("dashboard_widget", "applied"),
    }
