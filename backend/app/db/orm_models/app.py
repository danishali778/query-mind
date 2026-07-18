"""SQLAlchemy ORM models for query-mind app-owned tables."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, Text, UniqueConstraint, desc, false, func, text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.orm_models.types import GUID, JsonType, StringArray, UuidArray


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DatabaseConnectionORM(Base):
    __tablename__ = "database_connections"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    db_type: Mapped[str] = mapped_column(Text, nullable=False)
    host: Mapped[str | None] = mapped_column(Text)
    port: Mapped[int | None] = mapped_column(Integer)
    database: Mapped[str] = mapped_column(Text, nullable=False)
    username: Mapped[str | None] = mapped_column(Text)
    password: Mapped[str | None] = mapped_column(Text)
    ssl_mode: Mapped[str | None] = mapped_column(Text, default="disable", nullable=True)
    readonly: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=True)
    use_ssh: Mapped[bool | None] = mapped_column(Boolean, default=False, nullable=True)
    ssh_host: Mapped[str | None] = mapped_column(Text)
    ssh_port: Mapped[int | None] = mapped_column(Integer)
    ssh_username: Mapped[str | None] = mapped_column(Text)
    ssh_password: Mapped[str | None] = mapped_column(Text)
    ssh_private_key: Mapped[str | None] = mapped_column(Text)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str] = mapped_column(Text, default="unknown", server_default=text("'unknown'"), nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    last_schema_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    credential_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    credentials_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ssl_root_certificate: Mapped[str | None] = mapped_column(Text)
    ssl_client_certificate: Mapped[str | None] = mapped_column(Text)
    ssl_client_private_key: Mapped[str | None] = mapped_column(Text)
    scope_mode: Mapped[str] = mapped_column(Text, nullable=False, default="all", server_default=text("'all'"))
    included_schemas: Mapped[list] = mapped_column(JsonType, nullable=False, default=list, server_default=text("'[]'"))
    included_tables: Mapped[list] = mapped_column(JsonType, nullable=False, default=list, server_default=text("'[]'"))
    scope_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    scope_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    health_check_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    health_check_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60, server_default=text("60"))
    next_health_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    schema_refresh_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    schema_refresh_interval_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24, server_default=text("24"))
    next_schema_refresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("readonly = true", name="database_connections_readonly_true"),
        CheckConstraint("db_type = 'postgresql'", name="database_connections_db_type_postgresql"),
        CheckConstraint("last_status IN ('unknown', 'healthy', 'failed')", name="database_connections_last_status_valid"),
        CheckConstraint("ssl_mode IN ('disable', 'require', 'verify-ca', 'verify-full')", name="database_connections_ssl_mode_valid"),
        CheckConstraint("scope_mode IN ('all', 'allowlist')", name="database_connections_scope_mode_valid"),
        CheckConstraint(
            "scope_mode = 'all' OR included_schemas <> '[]' OR included_tables <> '[]'",
            name="database_connections_allowlist_nonempty",
        ),
        CheckConstraint("credential_revision >= 1", name="database_connections_credential_revision_positive"),
        CheckConstraint("scope_revision >= 1", name="database_connections_scope_revision_positive"),
        CheckConstraint("health_check_interval_minutes IN (15, 60, 360, 1440)", name="database_connections_health_interval_valid"),
        CheckConstraint("schema_refresh_interval_hours IN (6, 12, 24, 168)", name="database_connections_schema_interval_valid"),
        Index("idx_database_connections_owner_id_created_at", "owner_id", desc("created_at")),
        Index("idx_database_connections_due_health", "health_check_enabled", "next_health_check_at"),
        Index("idx_database_connections_due_schema", "schema_refresh_enabled", "next_schema_refresh_at"),
    )


class ConnectionHealthEventORM(Base):
    __tablename__ = "connection_health_events"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    connection_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("database_connections.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    diagnostic_code: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "source IN ('initial_connect', 'manual_test', 'scheduled_check', 'credential_rotation', 'schema_refresh')",
            name="connection_health_events_source_valid",
        ),
        CheckConstraint("status IN ('healthy', 'failed')", name="connection_health_events_status_valid"),
        Index("idx_connection_health_owner_connection_created", "owner_id", "connection_id", desc("created_at")),
        Index("idx_connection_health_connection_status_created", "connection_id", "status", desc("created_at")),
    )

class SchemaSnapshotORM(Base):
    __tablename__ = "schema_snapshots"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=_uuid)
    connection_id: Mapped[str] = mapped_column(
        GUID(),
        ForeignKey("database_connections.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    owner_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    schema_hash: Mapped[str] = mapped_column(Text, nullable=False)
    db_type: Mapped[str] = mapped_column(Text, nullable=False)
    catalog_json: Mapped[dict] = mapped_column(JsonType, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now(), nullable=True)

    __table_args__ = (
        Index("idx_schema_snapshots_connection_id", "connection_id", unique=True),
        Index("idx_schema_snapshots_owner_id", "owner_id"),
    )


class ConnectionAttemptORM(Base):
    __tablename__ = "connection_attempts"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    db_type: Mapped[str | None] = mapped_column(Text)
    host: Mapped[str | None] = mapped_column(Text)
    port: Mapped[int | None] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_code: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=True)

    __table_args__ = (
        Index("idx_connection_attempts_owner_id_created_at", "owner_id", desc("created_at")),
        Index("idx_connection_attempts_action_created_at", "action", desc("created_at")),
        Index("idx_connection_attempts_decision_created_at", "decision", desc("created_at")),
    )

class DashboardORM(Base):
    __tablename__ = "dashboards"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    icon: Mapped[str | None] = mapped_column(Text, default="\U0001f4ca", nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=True)
    filters: Mapped[dict | None] = mapped_column(JsonType, default=dict, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    share_token: Mapped[str | None] = mapped_column(GUID(), default=_uuid)
    creation_mode: Mapped[str] = mapped_column(Text, nullable=False, default="manual", server_default=text("'manual'"))
    lifecycle_status: Mapped[str] = mapped_column(Text, nullable=False, default="ready", server_default=text("'ready'"))

    widgets: Mapped[list["DashboardWidgetORM"]] = relationship(
        back_populates="dashboard",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint("is_public = false", name="dashboards_private_only"),
        CheckConstraint("creation_mode IN ('manual', 'ai')", name="dashboards_creation_mode_valid"),
        CheckConstraint("lifecycle_status IN ('draft', 'ready')", name="dashboards_lifecycle_status_valid"),
        Index("idx_dashboards_owner_id_created_at", "owner_id", desc("created_at")),
        Index("idx_dashboards_share_token", "share_token", unique=True),
    )


class DashboardWidgetORM(Base):
    __tablename__ = "dashboard_widgets"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=_uuid)
    dashboard_id: Mapped[str] = mapped_column(GUID(), ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False)
    owner_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    connection_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("database_connections.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    viz_type: Mapped[str] = mapped_column(Text, nullable=False)
    size: Mapped[str | None] = mapped_column(Text, default="half", nullable=True)
    sql: Mapped[str | None] = mapped_column(Text)
    chart_config: Mapped[dict | None] = mapped_column(JsonType, default=dict, nullable=True)
    layout_params: Mapped[dict | None] = mapped_column(JsonType, default=dict, nullable=True)
    cadence: Mapped[str | None] = mapped_column(Text, default="Manual only", nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_run_status: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=True)
    rows: Mapped[list | None] = mapped_column(
        JsonType,
        default=list,
        nullable=True,
        comment="Stores the serialized query results (rows) for the widget.",
    )
    columns: Mapped[list[str] | None] = mapped_column(
        StringArray,
        default=list,
        nullable=True,
        comment="Stores the column names for the query results.",
    )
    order_index: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)
    source_type: Mapped[str] = mapped_column(Text, nullable=False, default="manual", server_default=text("'manual'"))
    source_prompt: Mapped[str | None] = mapped_column(Text)
    generation_item_id: Mapped[str | None] = mapped_column(
        GUID(),
        ForeignKey(
            "dashboard_generation_items.id",
            ondelete="SET NULL",
            name="fk_dashboard_widgets_generation_item_id",
            use_alter=True,
        ),
    )
    generation_status: Mapped[str] = mapped_column(
        Text, nullable=False, default="ready", server_default=text("'ready'")
    )
    generation_error: Mapped[str | None] = mapped_column(Text)
    assumptions: Mapped[list | None] = mapped_column(JsonType, default=list, nullable=True)
    semantic_lineage: Mapped[list | None] = mapped_column(JsonType, default=list, nullable=True)

    dashboard: Mapped[DashboardORM] = relationship(back_populates="widgets")

    __table_args__ = (
        CheckConstraint("source_type IN ('manual', 'chat', 'ai')", name="dashboard_widgets_source_type_valid"),
        CheckConstraint(
            "generation_status IN ('ready', 'queued', 'running', 'failed', 'cancelled', 'regenerating')",
            name="dashboard_widgets_generation_status_valid",
        ),
        Index("idx_dashboard_widgets_dashboard_id_order_index", "dashboard_id", "order_index"),
        Index("idx_dashboard_widgets_owner_id", "owner_id"),
        Index("idx_dashboard_widgets_connection_id", "connection_id"),
        Index("idx_dashboard_widgets_next_run_at", "next_run_at"),
        Index(
            "idx_dashboard_widgets_generation_item_id",
            "generation_item_id",
            unique=True,
            postgresql_where=text("generation_item_id IS NOT NULL"),
            sqlite_where=text("generation_item_id IS NOT NULL"),
        ),
    )


class DashboardGenerationRunORM(Base):
    __tablename__ = "dashboard_generation_runs"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    connection_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("database_connections.id", ondelete="CASCADE"), nullable=False
    )
    dashboard_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("dashboards.id", ondelete="SET NULL")
    )
    client_request_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    requested_widget_count: Mapped[int] = mapped_column(Integer, nullable=False, default=6, server_default=text("6"))
    default_time_range: Mapped[str | None] = mapped_column(Text)
    extra_instructions: Mapped[str | None] = mapped_column(Text)
    plan_json: Mapped[dict | None] = mapped_column(JsonType)
    semantic_context_json: Mapped[dict | None] = mapped_column(JsonType)
    plan_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    status: Mapped[str] = mapped_column(Text, nullable=False, default="planning", server_default=text("'planning'"))
    current_stage: Mapped[str] = mapped_column(
        Text, nullable=False, default="reading_objective", server_default=text("'reading_objective'")
    )
    current_stage_label: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="Reading the dashboard objective",
        server_default=text("'Reading the dashboard objective'"),
    )
    celery_task_id: Mapped[str | None] = mapped_column(Text)
    failure_code: Mapped[str | None] = mapped_column(Text)
    failure_message: Mapped[str | None] = mapped_column(Text)
    llm_provider: Mapped[str | None] = mapped_column(Text)
    llm_model: Mapped[str | None] = mapped_column(Text)
    llm_credential_source: Mapped[str | None] = mapped_column(Text)
    llm_credential_revision: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), onupdate=_utcnow
    )

    items: Mapped[list["DashboardGenerationItemORM"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'planning', 'awaiting_approval', 'queued', 'running', "
            "'partial', 'completed', 'failed', 'cancelled')",
            name="dashboard_generation_runs_status_valid",
        ),
        CheckConstraint(
            "requested_widget_count >= 1 AND requested_widget_count <= 8",
            name="dashboard_generation_runs_widget_count_valid",
        ),
        UniqueConstraint("owner_id", "client_request_id", name="uq_dashboard_generation_runs_owner_client_request"),
        Index("idx_dashboard_generation_runs_owner_created_at", "owner_id", desc("created_at")),
        Index("idx_dashboard_generation_runs_status_heartbeat", "status", "heartbeat_at"),
        Index("idx_dashboard_generation_runs_dashboard_id", "dashboard_id"),
        Index("idx_dashboard_generation_runs_owner_status", "owner_id", "status"),
    )


class DashboardGenerationItemORM(Base):
    __tablename__ = "dashboard_generation_items"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("dashboard_generation_runs.id", ondelete="CASCADE"), nullable=False
    )
    client_key: Mapped[str] = mapped_column(GUID(), nullable=False)
    dashboard_widget_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("dashboard_widgets.id", ondelete="SET NULL"), unique=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    plan_json: Mapped[dict] = mapped_column(JsonType, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="planned", server_default=text("'planned'"))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    last_error_code: Mapped[str | None] = mapped_column(Text)
    last_error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), onupdate=_utcnow
    )

    run: Mapped[DashboardGenerationRunORM] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'planned', 'queued', 'running', 'completed', "
            "'failed', 'cancelled', 'regenerating')",
            name="dashboard_generation_items_status_valid",
        ),
        UniqueConstraint("run_id", "client_key", name="uq_dashboard_generation_items_run_client_key"),
        Index("idx_dashboard_generation_items_run_order", "run_id", "order_index"),
    )


class SavedQueryORM(Base):
    __tablename__ = "saved_queries"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    connection_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("database_connections.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    sql: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JsonType, default=dict, nullable=True)
    semantic_lineage: Mapped[list | None] = mapped_column(JsonType, default=list, nullable=True)
    schedule: Mapped[dict | None] = mapped_column(JsonType, default=dict, nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_run_status: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    run_count: Mapped[int | None] = mapped_column(BigInteger, default=0, nullable=True)

    __table_args__ = (
        Index("idx_saved_queries_owner_id_created_at", "owner_id", desc("created_at")),
        Index("idx_saved_queries_connection_id", "connection_id"),
        Index("idx_saved_queries_next_run_at", "next_run_at"),
    )


class QueryExecutionORM(Base):
    __tablename__ = "query_executions"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    connection_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("database_connections.id", ondelete="SET NULL"))
    query_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("saved_queries.id", ondelete="SET NULL"))
    sql: Mapped[str] = mapped_column(Text, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    row_count: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)
    execution_time_ms: Mapped[float | None] = mapped_column(Float, default=0.0, nullable=True)
    error: Mapped[str | None] = mapped_column(Text)
    triggered_by: Mapped[str | None] = mapped_column(Text, default="manual", nullable=True)
    ran_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=True)

    __table_args__ = (
        Index("idx_query_executions_owner_id_ran_at", "owner_id", desc("ran_at")),
        Index("idx_query_executions_connection_id", "connection_id"),
        Index("idx_query_executions_query_id", "query_id"),
    )


class TemplateGenerationORM(Base):
    __tablename__ = "template_generations"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    connection_id: Mapped[str] = mapped_column(GUID(), ForeignKey("database_connections.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="not_started")
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now(), nullable=True)

    templates: Mapped[list["GeneratedTemplateORM"]] = relationship(
        back_populates="generation",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_template_generations_owner_connection", "owner_id", "connection_id", unique=True),
        Index("idx_template_generations_status", "status"),
    )


class GeneratedTemplateORM(Base):
    __tablename__ = "generated_templates"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=_uuid)
    generation_id: Mapped[str] = mapped_column(GUID(), ForeignKey("template_generations.id", ondelete="CASCADE"), nullable=False)
    owner_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    connection_id: Mapped[str] = mapped_column(GUID(), ForeignKey("database_connections.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sql: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    category_color: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str] | None] = mapped_column(StringArray, default=list, nullable=True)
    icon: Mapped[str] = mapped_column(Text, nullable=False)
    icon_bg: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=True)

    generation: Mapped[TemplateGenerationORM] = relationship(back_populates="templates")

    __table_args__ = (
        Index("idx_generated_templates_owner_connection", "owner_id", "connection_id"),
        Index("idx_generated_templates_generation_id", "generation_id"),
    )


class ChatSessionORM(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    last_connection_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("database_connections.id", ondelete="SET NULL"))
    connection_ids: Mapped[list[str] | None] = mapped_column(UuidArray, default=list, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=True)

    messages: Mapped[list["ChatMessageORM"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        foreign_keys="ChatMessageORM.session_id",
    )

    __table_args__ = (
        Index("idx_chat_sessions_owner_id_created_at", "owner_id", desc("created_at")),
        Index("idx_chat_sessions_last_connection_id", "last_connection_id"),
    )


class ChatMessageORM(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(GUID(), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    owner_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sql: Mapped[str | None] = mapped_column(Text)
    results: Mapped[dict | None] = mapped_column(JsonType)
    error: Mapped[str | None] = mapped_column(Text)
    connection_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("database_connections.id", ondelete="SET NULL"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=True)
    chart_recommendation: Mapped[dict | None] = mapped_column(JsonType)
    columns: Mapped[list[str] | None] = mapped_column(StringArray)
    is_pinned: Mapped[bool | None] = mapped_column(Boolean, default=False, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=True)
    parent_id: Mapped[str | None] = mapped_column(
        GUID(),
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        comment="References the user message that triggered this assistant response.",
    )
    prev_query_id: Mapped[str | None] = mapped_column(
        GUID(),
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        comment="References the previous USER message in this session to maintain the trunk of the conversation.",
    )
    agent_trace: Mapped[list | dict | None] = mapped_column(JsonType, nullable=True)
    agent_tier: Mapped[str | None] = mapped_column(Text, nullable=True)
    semantic_lineage: Mapped[list | None] = mapped_column(JsonType, default=list, nullable=True)
    response_kind: Mapped[str | None] = mapped_column(Text, nullable=True)
    clarification_context: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    presentation_kind: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_metadata: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    agent_run_id: Mapped[str | None] = mapped_column(
        GUID(),
        ForeignKey("chat_agent_runs.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )

    session: Mapped[ChatSessionORM] = relationship(
        back_populates="messages",
        foreign_keys=[session_id],
    )

    __table_args__ = (
        CheckConstraint(
            "response_kind IS NULL OR response_kind IN "
            "('answer', 'direct_answer', 'clarification', 'schema_answer', 'data_analysis', "
            "'result_follow_up', 'refusal')",
            name="chat_messages_response_kind_valid",
        ),
        CheckConstraint(
            "presentation_kind IS NULL OR presentation_kind IN ('none', 'table', 'kpi', 'chart')",
            name="chat_messages_presentation_kind_valid",
        ),
        Index("idx_chat_messages_session_id_created_at", "session_id", "created_at"),
        Index("idx_chat_messages_owner_id_created_at", "owner_id", desc("created_at")),
        Index("idx_chat_messages_connection_id", "connection_id"),
        Index("idx_chat_messages_parent_id", "parent_id"),
        Index("idx_chat_messages_prev_query_id", "prev_query_id"),
    )


class ChatAgentRunORM(Base):
    __tablename__ = "chat_agent_runs"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    session_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    connection_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("database_connections.id", ondelete="CASCADE"), nullable=False
    )
    user_message_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    client_request_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    celery_task_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued", server_default=text("'queued'"))
    current_stage: Mapped[str] = mapped_column(Text, nullable=False, default="preparing", server_default=text("'preparing'"))
    current_stage_label: Mapped[str] = mapped_column(
        Text, nullable=False, default="Preparing your request", server_default=text("'Preparing your request'")
    )
    failure_code: Mapped[str | None] = mapped_column(Text)
    failure_message: Mapped[str | None] = mapped_column(Text)
    llm_provider: Mapped[str | None] = mapped_column(Text)
    llm_model: Mapped[str | None] = mapped_column(Text)
    llm_credential_source: Mapped[str | None] = mapped_column(Text)
    llm_credential_revision: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'cancel_requested', 'completed', 'failed', 'cancelled')",
            name="chat_agent_runs_status_valid",
        ),
        UniqueConstraint("owner_id", "client_request_id", name="uq_chat_agent_runs_owner_client_request"),
        Index("idx_chat_agent_runs_owner_created_at", "owner_id", desc("created_at")),
        Index("idx_chat_agent_runs_session_status", "session_id", "status"),
        Index("idx_chat_agent_runs_status_heartbeat", "status", "heartbeat_at"),
        Index(
            "uq_chat_agent_runs_active_session",
            "session_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running', 'cancel_requested')"),
            sqlite_where=text("status IN ('queued', 'running', 'cancel_requested')"),
        ),
    )


class SemanticDefinitionORM(Base):
    __tablename__ = "semantic_definitions"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    connection_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("database_connections.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), onupdate=_utcnow
    )

    versions: Mapped[list["SemanticDefinitionVersionORM"]] = relationship(
        back_populates="definition",
        cascade="all, delete-orphan",
        order_by="SemanticDefinitionVersionORM.version",
    )

    __table_args__ = (
        CheckConstraint(
            "kind IN ('table', 'column', 'entity', 'dimension', 'metric', "
            "'relationship', 'filter', 'date_policy', 'synonym')",
            name="semantic_definitions_kind_valid",
        ),
        UniqueConstraint(
            "owner_id", "connection_id", "kind", "key",
            name="uq_semantic_definitions_owner_connection_kind_key",
        ),
        Index("idx_semantic_definitions_owner_connection_kind", "owner_id", "connection_id", "kind"),
    )


class SemanticDefinitionVersionORM(Base):
    __tablename__ = "semantic_definition_versions"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=_uuid)
    definition_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("semantic_definitions.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft", server_default=text("'draft'"))
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default=text("''"))
    payload: Mapped[dict] = mapped_column(JsonType, nullable=False)
    schema_hash: Mapped[str | None] = mapped_column(Text)
    validation_status: Mapped[str] = mapped_column(
        Text, nullable=False, default="unvalidated", server_default=text("'unvalidated'")
    )
    validation_report: Mapped[dict | None] = mapped_column(JsonType, default=dict)
    change_note: Mapped[str | None] = mapped_column(Text)
    draft_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    created_by: Mapped[str] = mapped_column(GUID(), nullable=False)
    verified_by: Mapped[str | None] = mapped_column(GUID())
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), onupdate=_utcnow
    )
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    definition: Mapped[SemanticDefinitionORM] = relationship(back_populates="versions")

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'verified', 'deprecated')",
            name="semantic_definition_versions_status_valid",
        ),
        CheckConstraint(
            "validation_status IN ('unvalidated', 'valid', 'invalid', 'stale')",
            name="semantic_definition_versions_validation_status_valid",
        ),
        CheckConstraint("version >= 1", name="semantic_definition_versions_version_positive"),
        CheckConstraint("draft_revision >= 1", name="semantic_definition_versions_revision_positive"),
        UniqueConstraint("definition_id", "version", name="uq_semantic_definition_versions_definition_version"),
        Index("idx_semantic_definition_versions_definition_status", "definition_id", "status"),
        Index(
            "uq_semantic_definition_versions_active_draft",
            "definition_id",
            unique=True,
            postgresql_where=text("status = 'draft'"),
            sqlite_where=text("status = 'draft'"),
        ),
        Index(
            "uq_semantic_definition_versions_active_verified",
            "definition_id",
            unique=True,
            postgresql_where=text("status = 'verified'"),
            sqlite_where=text("status = 'verified'"),
        ),
    )


class SemanticDefinitionUsageORM(Base):
    __tablename__ = "semantic_definition_usages"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    connection_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("database_connections.id", ondelete="CASCADE"), nullable=False
    )
    definition_version_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("semantic_definition_versions.id", ondelete="RESTRICT"), nullable=False
    )
    consumer_type: Mapped[str] = mapped_column(Text, nullable=False)
    consumer_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    usage_role: Mapped[str] = mapped_column(Text, nullable=False, default="applied", server_default=text("'applied'"))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "consumer_type IN ('chat_message', 'dashboard_generation', 'dashboard_widget', 'saved_query')",
            name="semantic_definition_usages_consumer_type_valid",
        ),
        CheckConstraint(
            "usage_role IN ('applied', 'policy_enforced')",
            name="semantic_definition_usages_role_valid",
        ),
        UniqueConstraint(
            "definition_version_id", "consumer_type", "consumer_id", "usage_role",
            name="uq_semantic_definition_usages_consumer",
        ),
        Index("idx_semantic_definition_usages_version", "definition_version_id"),
        Index("idx_semantic_definition_usages_consumer", "consumer_type", "consumer_id"),
        Index("idx_semantic_definition_usages_owner_connection", "owner_id", "connection_id"),
    )


class SemanticSuggestionRunORM(Base):
    __tablename__ = "semantic_suggestion_runs"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    connection_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("database_connections.id", ondelete="CASCADE"), nullable=False
    )
    client_request_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    schema_hash: Mapped[str] = mapped_column(Text, nullable=False)
    requested_kinds: Mapped[list] = mapped_column(JsonType, nullable=False)
    business_context: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued", server_default=text("'queued'"))
    candidates_json: Mapped[list | None] = mapped_column(JsonType, default=list)
    celery_task_id: Mapped[str | None] = mapped_column(Text)
    failure_code: Mapped[str | None] = mapped_column(Text)
    failure_message: Mapped[str | None] = mapped_column(Text)
    llm_provider: Mapped[str | None] = mapped_column(Text)
    llm_model: Mapped[str | None] = mapped_column(Text)
    llm_credential_source: Mapped[str | None] = mapped_column(Text)
    llm_credential_revision: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="semantic_suggestion_runs_status_valid",
        ),
        UniqueConstraint("owner_id", "client_request_id", name="uq_semantic_suggestion_runs_owner_request"),
        Index("idx_semantic_suggestion_runs_owner_created", "owner_id", desc("created_at")),
        Index(
            "uq_semantic_suggestion_runs_active_connection",
            "owner_id", "connection_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
            sqlite_where=text("status IN ('queued', 'running')"),
        ),
    )


class QuestionSuggestionSetORM(Base):
    __tablename__ = "question_suggestion_sets"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    connection_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("database_connections.id", ondelete="CASCADE"), nullable=False
    )
    schema_hash: Mapped[str] = mapped_column(Text, nullable=False)
    semantic_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    context_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    semantic_version_ids: Mapped[list] = mapped_column(
        JsonType, nullable=False, default=list, server_default=text("'[]'")
    )
    generation_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="queued", server_default=text("'queued'")
    )
    suggestions_json: Mapped[dict] = mapped_column(
        JsonType, nullable=False, default=dict, server_default=text("'{}'")
    )
    dismissed_ids: Mapped[list] = mapped_column(
        JsonType, nullable=False, default=list, server_default=text("'[]'")
    )
    client_request_id: Mapped[str | None] = mapped_column(GUID())
    celery_task_id: Mapped[str | None] = mapped_column(Text)
    failure_code: Mapped[str | None] = mapped_column(Text)
    failure_message: Mapped[str | None] = mapped_column(Text)
    llm_provider: Mapped[str | None] = mapped_column(Text)
    llm_model: Mapped[str | None] = mapped_column(Text)
    llm_credential_source: Mapped[str | None] = mapped_column(Text)
    llm_credential_revision: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
        server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'ready', 'failed')",
            name="question_suggestion_sets_status_valid",
        ),
        CheckConstraint(
            "generation_revision >= 1",
            name="question_suggestion_sets_revision_positive",
        ),
        UniqueConstraint(
            "owner_id", "connection_id",
            name="uq_question_suggestion_sets_owner_connection",
        ),
        Index(
            "idx_question_suggestion_sets_status_updated",
            "status", desc("updated_at"),
        ),
    )


class UserLlmCredentialORM(Base):
    __tablename__ = "user_llm_credentials"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    key_hint: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="valid", server_default=text("'valid'"))
    credential_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validation_failure_code: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("provider IN ('gemini', 'groq', 'openai')", name="user_llm_credentials_provider_valid"),
        CheckConstraint("status IN ('valid', 'invalid')", name="user_llm_credentials_status_valid"),
        CheckConstraint("credential_revision >= 1", name="user_llm_credentials_revision_positive"),
        UniqueConstraint("owner_id", "provider", name="uq_user_llm_credentials_owner_provider"),
        Index("idx_user_llm_credentials_owner", "owner_id"),
    )


class RevokedAuthSessionORM(Base):
    __tablename__ = "revoked_auth_sessions"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=_uuid)
    # The migration owns the auth.users FK; ORM metadata omits cross-schema
    # ownership FKs consistently so SQLite unit-test metadata remains portable.
    owner_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    session_id_hash: Mapped[str] = mapped_column(Text, nullable=False)
    access_token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="logout", server_default=text("'logout'"))
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("source IN ('logout')", name="revoked_auth_sessions_source_valid"),
        UniqueConstraint("session_id_hash", name="uq_revoked_auth_sessions_session_hash"),
        Index("idx_revoked_auth_sessions_owner_revoked", "owner_id", desc("revoked_at")),
        Index("idx_revoked_auth_sessions_expires", "access_token_expires_at"),
    )


class LlmUsageEventORM(Base):
    __tablename__ = "llm_usage_events"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    credential_source: Mapped[str] = mapped_column(Text, nullable=False)
    credential_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("user_llm_credentials.id", ondelete="SET NULL"))
    credential_revision: Mapped[int | None] = mapped_column(Integer)
    feature: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_type: Mapped[str | None] = mapped_column(Text)
    workflow_id: Mapped[str | None] = mapped_column(Text)
    interaction_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="started", server_default=text("'started'"))
    failure_code: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("provider IN ('gemini', 'groq', 'openai')", name="llm_usage_events_provider_valid"),
        CheckConstraint("credential_source IN ('user', 'deployment')", name="llm_usage_events_source_valid"),
        CheckConstraint("interaction_type IN ('explicit', 'automatic')", name="llm_usage_events_interaction_valid"),
        CheckConstraint("status IN ('started', 'completed', 'failed')", name="llm_usage_events_status_valid"),
        Index("idx_llm_usage_events_owner_created", "owner_id", desc("created_at")),
        Index("idx_llm_usage_events_source_created", "credential_source", desc("created_at")),
    )


class UserSettingsORM(Base):
    __tablename__ = "user_settings"

    owner_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(Text)
    job_title: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str | None] = mapped_column(Text, default="UTC", nullable=True)
    theme: Mapped[str | None] = mapped_column(Text, default="light", nullable=True)
    accent_color: Mapped[str | None] = mapped_column(Text, default="cyan", nullable=True)
    density: Mapped[str | None] = mapped_column(Text, default="comfortable", nullable=True)
    show_run_counts: Mapped[bool | None] = mapped_column(Boolean, default=True, nullable=True)
    animate_charts: Mapped[bool | None] = mapped_column(Boolean, default=True, nullable=True)
    syntax_highlighting: Mapped[bool | None] = mapped_column(Boolean, default=True, nullable=True)
    ai_model: Mapped[str | None] = mapped_column(Text, default="claude-sonnet-4-6", nullable=True)
    preferred_llm_provider: Mapped[str | None] = mapped_column(Text)
    preferred_llm_model: Mapped[str | None] = mapped_column(Text)
    llm_preference_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    allow_background_ai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    stream_responses: Mapped[bool | None] = mapped_column(Boolean, default=True, nullable=True)
    default_row_limit: Mapped[int | None] = mapped_column(Integer, default=500, nullable=True)
    auto_save_queries: Mapped[bool | None] = mapped_column(Boolean, default=False, nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, default="", nullable=True)
    email_scheduled: Mapped[bool | None] = mapped_column(Boolean, default=True, nullable=True)
    email_failed: Mapped[bool | None] = mapped_column(Boolean, default=True, nullable=True)
    email_alerts: Mapped[bool | None] = mapped_column(Boolean, default=False, nullable=True)
    delivery_format: Mapped[str | None] = mapped_column(Text, default="CSV + Chart PNG", nullable=True)
    slack_enabled: Mapped[bool | None] = mapped_column(Boolean, default=False, nullable=True)
    slack_webhook: Mapped[str | None] = mapped_column(Text)
    slack_channel: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now(), nullable=True)


class UserSubscriptionORM(Base):
    __tablename__ = "user_subscriptions"

    owner_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    plan_type: Mapped[str | None] = mapped_column(Text, default="free", nullable=True)
    queries_used: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)
    queries_limit: Mapped[int | None] = mapped_column(Integer, default=100, nullable=True)
    ai_used: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)
    ai_limit: Mapped[int | None] = mapped_column(Integer, default=30, nullable=True)
    deployment_llm_calls_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    deployment_llm_calls_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=10, server_default=text("10"))
    next_reset_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now(), nullable=True)


__all__ = [
    "DatabaseConnectionORM",
    "SchemaSnapshotORM",
    "ConnectionAttemptORM",
    "DashboardORM",
    "DashboardWidgetORM",
    "DashboardGenerationRunORM",
    "DashboardGenerationItemORM",
    "SavedQueryORM",
    "QueryExecutionORM",
    "TemplateGenerationORM",
    "GeneratedTemplateORM",
    "ChatSessionORM",
    "ChatMessageORM",
    "ChatAgentRunORM",
    "SemanticDefinitionORM",
    "SemanticDefinitionVersionORM",
    "SemanticDefinitionUsageORM",
    "SemanticSuggestionRunORM",
    "QuestionSuggestionSetORM",
    "UserLlmCredentialORM",
    "LlmUsageEventORM",
    "UserSettingsORM",
    "UserSubscriptionORM",
]
