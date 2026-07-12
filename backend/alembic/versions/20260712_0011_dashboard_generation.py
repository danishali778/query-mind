"""Add AI dashboard generation persistence.

Revision ID: 20260712_0011
Revises: 20260712_0010
Create Date: 2026-07-12
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.db.orm_models.types import GUID


revision: str = "20260712_0011"
down_revision: str | None = "20260712_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "dashboards",
        sa.Column("creation_mode", sa.Text(), server_default="manual", nullable=False),
    )
    op.add_column(
        "dashboards",
        sa.Column("lifecycle_status", sa.Text(), server_default="ready", nullable=False),
    )
    op.create_check_constraint(
        "dashboards_creation_mode_valid",
        "dashboards",
        "creation_mode IN ('manual', 'ai')",
    )
    op.create_check_constraint(
        "dashboards_lifecycle_status_valid",
        "dashboards",
        "lifecycle_status IN ('draft', 'ready')",
    )

    op.add_column(
        "dashboard_widgets",
        sa.Column("source_type", sa.Text(), server_default="manual", nullable=False),
    )
    op.add_column("dashboard_widgets", sa.Column("source_prompt", sa.Text(), nullable=True))
    op.add_column("dashboard_widgets", sa.Column("generation_item_id", GUID(), nullable=True))
    op.add_column(
        "dashboard_widgets",
        sa.Column("generation_status", sa.Text(), server_default="ready", nullable=False),
    )
    op.add_column("dashboard_widgets", sa.Column("generation_error", sa.Text(), nullable=True))
    op.add_column(
        "dashboard_widgets",
        sa.Column(
            "assumptions",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "dashboard_widgets_source_type_valid",
        "dashboard_widgets",
        "source_type IN ('manual', 'chat', 'ai')",
    )
    op.create_check_constraint(
        "dashboard_widgets_generation_status_valid",
        "dashboard_widgets",
        "generation_status IN ('ready', 'queued', 'running', 'failed', 'cancelled', 'regenerating')",
    )
    op.create_index(
        "idx_dashboard_widgets_generation_item_id",
        "dashboard_widgets",
        ["generation_item_id"],
        unique=True,
        postgresql_where=sa.text("generation_item_id IS NOT NULL"),
        sqlite_where=sa.text("generation_item_id IS NOT NULL"),
    )

    op.create_table(
        "dashboard_generation_runs",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("owner_id", GUID(), nullable=False),
        sa.Column("connection_id", GUID(), nullable=False),
        sa.Column("dashboard_id", GUID(), nullable=True),
        sa.Column("client_request_id", GUID(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("requested_widget_count", sa.Integer(), server_default="6", nullable=False),
        sa.Column("default_time_range", sa.Text(), nullable=True),
        sa.Column("extra_instructions", sa.Text(), nullable=True),
        sa.Column("plan_json", postgresql.JSONB(), nullable=True),
        sa.Column("plan_revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.Text(), server_default="planning", nullable=False),
        sa.Column("current_stage", sa.Text(), server_default="reading_objective", nullable=False),
        sa.Column(
            "current_stage_label",
            sa.Text(),
            server_default="Reading the dashboard objective",
            nullable=False,
        ),
        sa.Column("celery_task_id", sa.Text(), nullable=True),
        sa.Column("failure_code", sa.Text(), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.CheckConstraint(
            "status IN ("
            "'planning', 'awaiting_approval', 'queued', 'running', "
            "'partial', 'completed', 'failed', 'cancelled')",
            name="dashboard_generation_runs_status_valid",
        ),
        sa.CheckConstraint(
            "requested_widget_count >= 1 AND requested_widget_count <= 8",
            name="dashboard_generation_runs_widget_count_valid",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["database_connections.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dashboard_id"],
            ["dashboards.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_id",
            "client_request_id",
            name="uq_dashboard_generation_runs_owner_client_request",
        ),
    )
    op.create_index(
        "idx_dashboard_generation_runs_owner_created_at",
        "dashboard_generation_runs",
        ["owner_id", sa.literal_column("created_at DESC")],
    )
    op.create_index(
        "idx_dashboard_generation_runs_status_heartbeat",
        "dashboard_generation_runs",
        ["status", "heartbeat_at"],
    )
    op.create_index(
        "idx_dashboard_generation_runs_dashboard_id",
        "dashboard_generation_runs",
        ["dashboard_id"],
    )
    op.create_index(
        "uq_dashboard_generation_runs_active_owner",
        "dashboard_generation_runs",
        ["owner_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('planning', 'queued', 'running')"),
        sqlite_where=sa.text("status IN ('planning', 'queued', 'running')"),
    )

    op.create_table(
        "dashboard_generation_items",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("run_id", GUID(), nullable=False),
        sa.Column("client_key", GUID(), nullable=False),
        sa.Column("dashboard_widget_id", GUID(), nullable=True),
        sa.Column("order_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("plan_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), server_default="planned", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error_code", sa.Text(), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.CheckConstraint(
            "status IN ("
            "'planned', 'queued', 'running', 'completed', "
            "'failed', 'cancelled', 'regenerating')",
            name="dashboard_generation_items_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["dashboard_generation_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dashboard_widget_id"],
            ["dashboard_widgets.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "client_key", name="uq_dashboard_generation_items_run_client_key"),
        sa.UniqueConstraint(
            "dashboard_widget_id",
            name="uq_dashboard_generation_items_widget_id",
        ),
    )
    op.create_index(
        "idx_dashboard_generation_items_run_order",
        "dashboard_generation_items",
        ["run_id", "order_index"],
    )

    op.create_foreign_key(
        "fk_dashboard_widgets_generation_item_id",
        "dashboard_widgets",
        "dashboard_generation_items",
        ["generation_item_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_dashboard_widgets_generation_item_id",
        "dashboard_widgets",
        type_="foreignkey",
    )
    op.drop_index("idx_dashboard_generation_items_run_order", table_name="dashboard_generation_items")
    op.drop_table("dashboard_generation_items")
    op.drop_index(
        "uq_dashboard_generation_runs_active_owner",
        table_name="dashboard_generation_runs",
    )
    op.drop_index(
        "idx_dashboard_generation_runs_dashboard_id",
        table_name="dashboard_generation_runs",
    )
    op.drop_index(
        "idx_dashboard_generation_runs_status_heartbeat",
        table_name="dashboard_generation_runs",
    )
    op.drop_index(
        "idx_dashboard_generation_runs_owner_created_at",
        table_name="dashboard_generation_runs",
    )
    op.drop_table("dashboard_generation_runs")

    op.drop_index("idx_dashboard_widgets_generation_item_id", table_name="dashboard_widgets")
    op.drop_constraint("dashboard_widgets_generation_status_valid", "dashboard_widgets", type_="check")
    op.drop_constraint("dashboard_widgets_source_type_valid", "dashboard_widgets", type_="check")
    op.drop_column("dashboard_widgets", "assumptions")
    op.drop_column("dashboard_widgets", "generation_error")
    op.drop_column("dashboard_widgets", "generation_status")
    op.drop_column("dashboard_widgets", "generation_item_id")
    op.drop_column("dashboard_widgets", "source_prompt")
    op.drop_column("dashboard_widgets", "source_type")

    op.drop_constraint("dashboards_lifecycle_status_valid", "dashboards", type_="check")
    op.drop_constraint("dashboards_creation_mode_valid", "dashboards", type_="check")
    op.drop_column("dashboards", "lifecycle_status")
    op.drop_column("dashboards", "creation_mode")
