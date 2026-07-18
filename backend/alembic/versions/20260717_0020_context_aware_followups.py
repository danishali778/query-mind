"""Allow result-aware follow-up chat responses.

Revision ID: 20260717_0020
Revises: 20260717_0019
"""

from __future__ import annotations

from alembic import op


revision: str = "20260717_0020"
down_revision: str | None = "20260717_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("chat_messages_response_kind_valid", "chat_messages", type_="check")
    op.create_check_constraint(
        "chat_messages_response_kind_valid",
        "chat_messages",
        "response_kind IS NULL OR response_kind IN "
        "('answer', 'direct_answer', 'clarification', 'schema_answer', 'data_analysis', "
        "'result_follow_up', 'refusal')",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE chat_messages SET response_kind = 'answer' "
        "WHERE response_kind = 'result_follow_up'"
    )
    op.drop_constraint("chat_messages_response_kind_valid", "chat_messages", type_="check")
    op.create_check_constraint(
        "chat_messages_response_kind_valid",
        "chat_messages",
        "response_kind IS NULL OR response_kind IN "
        "('answer', 'direct_answer', 'clarification', 'schema_answer', 'data_analysis', 'refusal')",
    )
