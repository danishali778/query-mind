"""Add connection attempt guardrail audit table.

Revision ID: 20260701_0004
Revises: 20260701_0003
Create Date: 2026-07-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260701_0004"
down_revision: str | None = "20260701_0003"
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
    op.create_table(
        "connection_attempts",
        sa.Column("id", _uuid_type(), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("owner_id", _uuid_type(), _owner_fk(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("db_type", sa.Text(), nullable=True),
        sa.Column("host", sa.Text(), nullable=True),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )
    op.create_index(
        "idx_connection_attempts_owner_id_created_at",
        "connection_attempts",
        ["owner_id", "created_at"],
    )
    op.create_index(
        "idx_connection_attempts_action_created_at",
        "connection_attempts",
        ["action", "created_at"],
    )
    op.create_index(
        "idx_connection_attempts_decision_created_at",
        "connection_attempts",
        ["decision", "created_at"],
    )
    _enable_owner_rls("connection_attempts", "Users can manage their own connection attempts")


def downgrade() -> None:
    op.drop_table("connection_attempts")

