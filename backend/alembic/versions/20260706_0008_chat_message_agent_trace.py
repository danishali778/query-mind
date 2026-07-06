"""Add chat message agent trace fields.

Revision ID: 20260706_0008
Revises: 20260705_0007
Create Date: 2026-07-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260706_0008"
down_revision: str | None = "20260705_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("agent_trace", sa.JSON(), nullable=True))
    op.add_column("chat_messages", sa.Column("agent_tier", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_messages", "agent_tier")
    op.drop_column("chat_messages", "agent_trace")
