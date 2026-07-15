"""Add chat clarification response metadata.

Revision ID: 20260715_0018
Revises: 20260715_0017
Create Date: 2026-07-15
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260715_0018"
down_revision: str | None = "20260715_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("response_kind", sa.Text(), nullable=True))
    op.add_column(
        "chat_messages",
        sa.Column(
            "clarification_context",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "chat_messages_response_kind_valid",
        "chat_messages",
        "response_kind IS NULL OR response_kind IN ('answer', 'clarification')",
    )


def downgrade() -> None:
    op.drop_constraint("chat_messages_response_kind_valid", "chat_messages", type_="check")
    op.drop_column("chat_messages", "clarification_context")
    op.drop_column("chat_messages", "response_kind")
