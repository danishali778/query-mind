"""Add local account status.

Revision ID: 20260710_0009
Revises: d32ec5765c5d
Create Date: 2026-07-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260710_0009"
down_revision: str | None = "d32ec5765c5d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("user_settings", "is_active", server_default=None)


def downgrade() -> None:
    op.drop_column("user_settings", "is_active")
