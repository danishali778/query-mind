"""Add durable schema-aware question suggestion sets.

Revision ID: 20260713_0015
Revises: 20260713_0014
Create Date: 2026-07-13
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.db.orm_models.types import GUID


revision: str = "20260713_0015"
down_revision: str | None = "20260713_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "question_suggestion_sets",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("owner_id", GUID(), nullable=False),
        sa.Column("connection_id", GUID(), nullable=False),
        sa.Column("schema_hash", sa.Text(), nullable=False),
        sa.Column("semantic_fingerprint", sa.Text(), nullable=False),
        sa.Column("context_fingerprint", sa.Text(), nullable=False),
        sa.Column(
            "semantic_version_ids",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "generation_revision", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column(
            "status", sa.Text(), server_default=sa.text("'queued'"), nullable=False
        ),
        sa.Column(
            "suggestions_json",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "dismissed_ids",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("client_request_id", GUID()),
        sa.Column("celery_task_id", sa.Text()),
        sa.Column("failure_code", sa.Text()),
        sa.Column("failure_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'ready', 'failed')",
            name="question_suggestion_sets_status_valid",
        ),
        sa.CheckConstraint(
            "generation_revision >= 1",
            name="question_suggestion_sets_revision_positive",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["database_connections.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_id",
            "connection_id",
            name="uq_question_suggestion_sets_owner_connection",
        ),
    )
    op.create_index(
        "idx_question_suggestion_sets_status_updated",
        "question_suggestion_sets",
        ["status", sa.literal_column("updated_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_question_suggestion_sets_status_updated",
        table_name="question_suggestion_sets",
    )
    op.drop_table("question_suggestion_sets")
