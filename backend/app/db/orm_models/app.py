"""SQLAlchemy ORM models for query-mind app-owned tables."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, Text, desc, func, true
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

    __table_args__ = (
        CheckConstraint("readonly = true", name="database_connections_readonly_true"),
        Index("idx_database_connections_owner_id_created_at", "owner_id", desc("created_at")),
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

    widgets: Mapped[list["DashboardWidgetORM"]] = relationship(
        back_populates="dashboard",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint("is_public = false", name="dashboards_private_only"),
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

    dashboard: Mapped[DashboardORM] = relationship(back_populates="widgets")

    __table_args__ = (
        Index("idx_dashboard_widgets_dashboard_id_order_index", "dashboard_id", "order_index"),
        Index("idx_dashboard_widgets_owner_id", "owner_id"),
        Index("idx_dashboard_widgets_connection_id", "connection_id"),
        Index("idx_dashboard_widgets_next_run_at", "next_run_at"),
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

    session: Mapped[ChatSessionORM] = relationship(
        back_populates="messages",
        foreign_keys=[session_id],
    )

    __table_args__ = (
        Index("idx_chat_messages_session_id_created_at", "session_id", "created_at"),
        Index("idx_chat_messages_owner_id_created_at", "owner_id", desc("created_at")),
        Index("idx_chat_messages_connection_id", "connection_id"),
        Index("idx_chat_messages_parent_id", "parent_id"),
        Index("idx_chat_messages_prev_query_id", "prev_query_id"),
    )


class UserSettingsORM(Base):
    __tablename__ = "user_settings"

    owner_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
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
    next_reset_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now(), nullable=True)


__all__ = [
    "DatabaseConnectionORM",
    "ConnectionAttemptORM",
    "DashboardORM",
    "DashboardWidgetORM",
    "SavedQueryORM",
    "QueryExecutionORM",
    "TemplateGenerationORM",
    "GeneratedTemplateORM",
    "ChatSessionORM",
    "ChatMessageORM",
    "UserSettingsORM",
    "UserSubscriptionORM",
]
