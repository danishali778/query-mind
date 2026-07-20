"""Add result-aware chat response metadata.

Revision ID: 20260717_0019
Revises: 20260715_0018
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.db.orm_models.types import JsonType


revision: str = "20260717_0019"
down_revision: str | None = "20260715_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("chat_messages_response_kind_valid", "chat_messages", type_="check")
    op.create_check_constraint(
        "chat_messages_response_kind_valid",
        "chat_messages",
        "response_kind IS NULL OR response_kind IN "
        "('answer', 'direct_answer', 'clarification', 'schema_answer', 'data_analysis', 'refusal')",
    )
    op.add_column("chat_messages", sa.Column("presentation_kind", sa.Text(), nullable=True))
    op.add_column("chat_messages", sa.Column("answer_metadata", JsonType, nullable=True))
    op.create_check_constraint(
        "chat_messages_presentation_kind_valid",
        "chat_messages",
        "presentation_kind IS NULL OR presentation_kind IN ('none', 'table', 'kpi', 'chart')",
    )


def downgrade() -> None:
    op.execute("UPDATE chat_messages SET response_kind = 'answer' WHERE response_kind NOT IN ('answer', 'clarification')")
    op.drop_constraint("chat_messages_presentation_kind_valid", "chat_messages", type_="check")
    op.drop_column("chat_messages", "answer_metadata")
    op.drop_column("chat_messages", "presentation_kind")
    op.drop_constraint("chat_messages_response_kind_valid", "chat_messages", type_="check")
    op.create_check_constraint(
        "chat_messages_response_kind_valid",
        "chat_messages",
        "response_kind IS NULL OR response_kind IN ('answer', 'clarification')",
    )
