"""Add durable chat agent runs.

Revision ID: 20260712_0010
Revises: 20260710_0009
Create Date: 2026-07-12
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

from app.db.orm_models.types import GUID


revision: str = "20260712_0010"
down_revision: str | None = "20260710_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_agent_runs",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("owner_id", GUID(), nullable=False),
        sa.Column("session_id", GUID(), nullable=False),
        sa.Column("connection_id", GUID(), nullable=False),
        sa.Column("user_message_id", GUID(), nullable=False),
        sa.Column("client_request_id", GUID(), nullable=False),
        sa.Column("celery_task_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="queued", nullable=False),
        sa.Column("current_stage", sa.Text(), server_default="preparing", nullable=False),
        sa.Column("current_stage_label", sa.Text(), server_default="Preparing your request", nullable=False),
        sa.Column("failure_code", sa.Text(), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'cancel_requested', 'completed', 'failed', 'cancelled')",
            name="chat_agent_runs_status_valid",
        ),
        sa.ForeignKeyConstraint(["connection_id"], ["database_connections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "client_request_id", name="uq_chat_agent_runs_owner_client_request"),
    )
    op.create_index("idx_chat_agent_runs_owner_created_at", "chat_agent_runs", ["owner_id", sa.literal_column("created_at DESC")])
    op.create_index("idx_chat_agent_runs_session_status", "chat_agent_runs", ["session_id", "status"])
    op.create_index("idx_chat_agent_runs_status_heartbeat", "chat_agent_runs", ["status", "heartbeat_at"])
    op.create_index(
        "uq_chat_agent_runs_active_session",
        "chat_agent_runs",
        ["session_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running', 'cancel_requested')"),
        sqlite_where=sa.text("status IN ('queued', 'running', 'cancel_requested')"),
    )
    op.add_column("chat_messages", sa.Column("agent_run_id", GUID(), nullable=True))
    op.create_foreign_key(
        "fk_chat_messages_agent_run_id",
        "chat_messages",
        "chat_agent_runs",
        ["agent_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint("uq_chat_messages_agent_run_id", "chat_messages", ["agent_run_id"])


def downgrade() -> None:
    op.drop_constraint("uq_chat_messages_agent_run_id", "chat_messages", type_="unique")
    op.drop_constraint("fk_chat_messages_agent_run_id", "chat_messages", type_="foreignkey")
    op.drop_column("chat_messages", "agent_run_id")
    op.drop_index("uq_chat_agent_runs_active_session", table_name="chat_agent_runs")
    op.drop_index("idx_chat_agent_runs_status_heartbeat", table_name="chat_agent_runs")
    op.drop_index("idx_chat_agent_runs_session_status", table_name="chat_agent_runs")
    op.drop_index("idx_chat_agent_runs_owner_created_at", table_name="chat_agent_runs")
    op.drop_table("chat_agent_runs")
