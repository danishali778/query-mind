"""Add schema_snapshots.

Revision ID: 20260705_0007
Revises: 20260702_0006
Create Date: 2026-07-05
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260705_0007"
down_revision: str | None = "20260702_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_type():
    return postgresql.UUID(as_uuid=False)


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
        "schema_snapshots",
        sa.Column("id", _uuid_type(), nullable=False),
        sa.Column("connection_id", _uuid_type(), nullable=False),
        sa.Column("owner_id", _uuid_type(), sa.ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("schema_hash", sa.Text(), nullable=False),
        sa.Column("db_type", sa.Text(), nullable=False),
        sa.Column("catalog_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["connection_id"], ["database_connections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connection_id"),
    )
    op.create_index("idx_schema_snapshots_connection_id", "schema_snapshots", ["connection_id"], unique=True)
    op.create_index("idx_schema_snapshots_owner_id", "schema_snapshots", ["owner_id"], unique=False)
    _enable_owner_rls("schema_snapshots", "Users manage own schema snapshots")


def downgrade() -> None:
    op.drop_index("idx_schema_snapshots_owner_id", table_name="schema_snapshots")
    op.drop_index("idx_schema_snapshots_connection_id", table_name="schema_snapshots")
    op.drop_table("schema_snapshots")
