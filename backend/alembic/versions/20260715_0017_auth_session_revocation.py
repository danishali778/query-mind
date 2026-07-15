"""Add durable authentication session revocation.

Revision ID: 20260715_0017
Revises: 20260714_0016
Create Date: 2026-07-15
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

from app.db.orm_models.types import GUID


revision: str = "20260715_0017"
down_revision: str | None = "20260714_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "revoked_auth_sessions",
        sa.Column("id", GUID(), nullable=False),
        sa.Column(
            "owner_id",
            GUID(),
            sa.ForeignKey("auth.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_id_hash", sa.Text(), nullable=False),
        sa.Column("access_token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.Text(), server_default=sa.text("'logout'"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("source IN ('logout')", name="revoked_auth_sessions_source_valid"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id_hash", name="uq_revoked_auth_sessions_session_hash"),
    )
    op.create_index(
        "idx_revoked_auth_sessions_owner_revoked",
        "revoked_auth_sessions",
        ["owner_id", sa.literal_column("revoked_at DESC")],
    )
    op.create_index(
        "idx_revoked_auth_sessions_expires",
        "revoked_auth_sessions",
        ["access_token_expires_at"],
    )
    op.execute("ALTER TABLE public.revoked_auth_sessions ENABLE ROW LEVEL SECURITY")
    op.execute(
        '''CREATE POLICY "revoked_auth_sessions_owner_access"
           ON public.revoked_auth_sessions
           FOR ALL
           USING (((SELECT auth.uid()) = owner_id))
           WITH CHECK (((SELECT auth.uid()) = owner_id))'''
    )


def downgrade() -> None:
    op.drop_index("idx_revoked_auth_sessions_expires", table_name="revoked_auth_sessions")
    op.drop_index("idx_revoked_auth_sessions_owner_revoked", table_name="revoked_auth_sessions")
    op.drop_table("revoked_auth_sessions")
