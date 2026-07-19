"""Add durable agent-owned conversation memory.

Revision ID: 20260718_0021
Revises: 20260717_0020
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.db.orm_models.types import JsonType


revision: str = "20260718_0021"
down_revision: str | None = "20260717_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_sessions", sa.Column("memory_state", JsonType, nullable=True))
    op.add_column(
        "chat_sessions",
        sa.Column("memory_revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )
    op.add_column(
        "chat_sessions",
        sa.Column("memory_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "chat_sessions_memory_revision_positive",
        "chat_sessions",
        "memory_revision >= 1",
    )


def downgrade() -> None:
    op.drop_constraint(
        "chat_sessions_memory_revision_positive", "chat_sessions", type_="check"
    )
    op.drop_column("chat_sessions", "memory_updated_at")
    op.drop_column("chat_sessions", "memory_revision")
    op.drop_column("chat_sessions", "memory_state")
