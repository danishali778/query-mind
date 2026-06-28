"""Add durable Celery runtime state and template persistence.

Revision ID: 20260628_0002
Revises: 20260627_0001
Create Date: 2026-06-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260628_0002"
down_revision: str | None = "20260627_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_type():
    return postgresql.UUID(as_uuid=False)


def _owner_fk() -> sa.ForeignKey:
    return sa.ForeignKey("auth.users.id", ondelete="CASCADE")


def _enable_owner_rls(table_name: str, policy_name: str) -> None:
    op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY "{policy_name}"
          ON public.{table_name}
          FOR ALL
          USING ((( SELECT auth.uid() AS uid) = owner_id))
          WITH CHECK ((( SELECT auth.uid() AS uid) = owner_id))
        """
    )


def upgrade() -> None:
    op.add_column("saved_queries", sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("saved_queries", sa.Column("last_run_status", sa.Text(), nullable=True))
    op.add_column("saved_queries", sa.Column("last_error", sa.Text(), nullable=True))
    op.create_index("idx_saved_queries_next_run_at", "saved_queries", ["next_run_at"])

    op.add_column("dashboard_widgets", sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("dashboard_widgets", sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("dashboard_widgets", sa.Column("last_run_status", sa.Text(), nullable=True))
    op.add_column("dashboard_widgets", sa.Column("last_error", sa.Text(), nullable=True))
    op.create_index("idx_dashboard_widgets_next_run_at", "dashboard_widgets", ["next_run_at"])

    op.create_table(
        "template_generations",
        sa.Column("id", _uuid_type(), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("owner_id", _uuid_type(), _owner_fk(), nullable=False),
        sa.Column("connection_id", _uuid_type(), sa.ForeignKey("database_connections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'not_started'::text")),
        sa.Column("error", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(
        "idx_template_generations_owner_connection",
        "template_generations",
        ["owner_id", "connection_id"],
        unique=True,
    )
    op.create_index("idx_template_generations_status", "template_generations", ["status"])
    _enable_owner_rls("template_generations", "Users can manage their own template generations")

    op.create_table(
        "generated_templates",
        sa.Column("id", _uuid_type(), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("generation_id", _uuid_type(), sa.ForeignKey("template_generations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", _uuid_type(), _owner_fk(), nullable=False),
        sa.Column("connection_id", _uuid_type(), sa.ForeignKey("database_connections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("''::text")),
        sa.Column("sql", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("category_color", sa.Text(), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]")),
        sa.Column("icon", sa.Text(), nullable=False),
        sa.Column("icon_bg", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_generated_templates_generation_id", "generated_templates", ["generation_id"])
    op.create_index("idx_generated_templates_owner_connection", "generated_templates", ["owner_id", "connection_id"])
    _enable_owner_rls("generated_templates", "Users can manage their own generated templates")


def downgrade() -> None:
    op.drop_table("generated_templates")
    op.drop_table("template_generations")
    op.drop_index("idx_dashboard_widgets_next_run_at", table_name="dashboard_widgets")
    op.drop_column("dashboard_widgets", "last_error")
    op.drop_column("dashboard_widgets", "last_run_status")
    op.drop_column("dashboard_widgets", "last_run_at")
    op.drop_column("dashboard_widgets", "next_run_at")
    op.drop_index("idx_saved_queries_next_run_at", table_name="saved_queries")
    op.drop_column("saved_queries", "last_error")
    op.drop_column("saved_queries", "last_run_status")
    op.drop_column("saved_queries", "next_run_at")

