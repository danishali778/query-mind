"""Add versioned semantic definitions and lineage.

Revision ID: 20260713_0013
Revises: 20260713_0012
Create Date: 2026-07-13
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.db.orm_models.types import GUID


revision: str = "20260713_0013"
down_revision: str | None = "20260713_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "semantic_definitions",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("owner_id", GUID(), nullable=False),
        sa.Column("connection_id", GUID(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "kind IN ('table', 'column', 'entity', 'dimension', 'metric', "
            "'relationship', 'filter', 'date_policy', 'synonym')",
            name="semantic_definitions_kind_valid",
        ),
        sa.ForeignKeyConstraint(["connection_id"], ["database_connections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_id", "connection_id", "kind", "key",
            name="uq_semantic_definitions_owner_connection_kind_key",
        ),
    )
    op.create_index(
        "idx_semantic_definitions_owner_connection_kind",
        "semantic_definitions",
        ["owner_id", "connection_id", "kind"],
    )

    op.create_table(
        "semantic_definition_versions",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("definition_id", GUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("schema_hash", sa.Text(), nullable=True),
        sa.Column("validation_status", sa.Text(), server_default="unvalidated", nullable=False),
        sa.Column("validation_report", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("change_note", sa.Text(), nullable=True),
        sa.Column("draft_revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("verified_by", GUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deprecated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'verified', 'deprecated')",
            name="semantic_definition_versions_status_valid",
        ),
        sa.CheckConstraint(
            "validation_status IN ('unvalidated', 'valid', 'invalid', 'stale')",
            name="semantic_definition_versions_validation_status_valid",
        ),
        sa.CheckConstraint("version >= 1", name="semantic_definition_versions_version_positive"),
        sa.CheckConstraint("draft_revision >= 1", name="semantic_definition_versions_revision_positive"),
        sa.ForeignKeyConstraint(
            ["definition_id"], ["semantic_definitions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "definition_id", "version",
            name="uq_semantic_definition_versions_definition_version",
        ),
    )
    op.create_index(
        "idx_semantic_definition_versions_definition_status",
        "semantic_definition_versions",
        ["definition_id", "status"],
    )
    op.create_index(
        "uq_semantic_definition_versions_active_draft",
        "semantic_definition_versions",
        ["definition_id"],
        unique=True,
        postgresql_where=sa.text("status = 'draft'"),
        sqlite_where=sa.text("status = 'draft'"),
    )
    op.create_index(
        "uq_semantic_definition_versions_active_verified",
        "semantic_definition_versions",
        ["definition_id"],
        unique=True,
        postgresql_where=sa.text("status = 'verified'"),
        sqlite_where=sa.text("status = 'verified'"),
    )

    op.create_table(
        "semantic_definition_usages",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("owner_id", GUID(), nullable=False),
        sa.Column("connection_id", GUID(), nullable=False),
        sa.Column("definition_version_id", GUID(), nullable=False),
        sa.Column("consumer_type", sa.Text(), nullable=False),
        sa.Column("consumer_id", GUID(), nullable=False),
        sa.Column("usage_role", sa.Text(), server_default="applied", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "consumer_type IN ('chat_message', 'dashboard_generation', 'dashboard_widget', 'saved_query')",
            name="semantic_definition_usages_consumer_type_valid",
        ),
        sa.CheckConstraint(
            "usage_role IN ('applied', 'policy_enforced')",
            name="semantic_definition_usages_role_valid",
        ),
        sa.ForeignKeyConstraint(["connection_id"], ["database_connections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["definition_version_id"], ["semantic_definition_versions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "definition_version_id", "consumer_type", "consumer_id", "usage_role",
            name="uq_semantic_definition_usages_consumer",
        ),
    )
    op.create_index(
        "idx_semantic_definition_usages_version",
        "semantic_definition_usages",
        ["definition_version_id"],
    )
    op.create_index(
        "idx_semantic_definition_usages_consumer",
        "semantic_definition_usages",
        ["consumer_type", "consumer_id"],
    )
    op.create_index(
        "idx_semantic_definition_usages_owner_connection",
        "semantic_definition_usages",
        ["owner_id", "connection_id"],
    )

    op.create_table(
        "semantic_suggestion_runs",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("owner_id", GUID(), nullable=False),
        sa.Column("connection_id", GUID(), nullable=False),
        sa.Column("client_request_id", GUID(), nullable=False),
        sa.Column("schema_hash", sa.Text(), nullable=False),
        sa.Column("requested_kinds", postgresql.JSONB(), nullable=False),
        sa.Column("business_context", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="queued", nullable=False),
        sa.Column("candidates_json", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("celery_task_id", sa.Text(), nullable=True),
        sa.Column("failure_code", sa.Text(), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="semantic_suggestion_runs_status_valid",
        ),
        sa.ForeignKeyConstraint(["connection_id"], ["database_connections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_id", "client_request_id",
            name="uq_semantic_suggestion_runs_owner_request",
        ),
    )
    op.create_index(
        "idx_semantic_suggestion_runs_owner_created",
        "semantic_suggestion_runs",
        ["owner_id", sa.literal_column("created_at DESC")],
    )
    op.create_index(
        "uq_semantic_suggestion_runs_active_connection",
        "semantic_suggestion_runs",
        ["owner_id", "connection_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
        sqlite_where=sa.text("status IN ('queued', 'running')"),
    )

    op.add_column(
        "chat_messages",
        sa.Column("semantic_lineage", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "dashboard_generation_runs",
        sa.Column("semantic_context_json", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "dashboard_widgets",
        sa.Column("semantic_lineage", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "saved_queries",
        sa.Column("semantic_lineage", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("saved_queries", "semantic_lineage")
    op.drop_column("dashboard_widgets", "semantic_lineage")
    op.drop_column("dashboard_generation_runs", "semantic_context_json")
    op.drop_column("chat_messages", "semantic_lineage")

    op.drop_index("uq_semantic_suggestion_runs_active_connection", table_name="semantic_suggestion_runs")
    op.drop_index("idx_semantic_suggestion_runs_owner_created", table_name="semantic_suggestion_runs")
    op.drop_table("semantic_suggestion_runs")

    op.drop_index("idx_semantic_definition_usages_owner_connection", table_name="semantic_definition_usages")
    op.drop_index("idx_semantic_definition_usages_consumer", table_name="semantic_definition_usages")
    op.drop_index("idx_semantic_definition_usages_version", table_name="semantic_definition_usages")
    op.drop_table("semantic_definition_usages")

    op.drop_index(
        "uq_semantic_definition_versions_active_verified",
        table_name="semantic_definition_versions",
    )
    op.drop_index(
        "uq_semantic_definition_versions_active_draft",
        table_name="semantic_definition_versions",
    )
    op.drop_index(
        "idx_semantic_definition_versions_definition_status",
        table_name="semantic_definition_versions",
    )
    op.drop_table("semantic_definition_versions")

    op.drop_index(
        "idx_semantic_definitions_owner_connection_kind",
        table_name="semantic_definitions",
    )
    op.drop_table("semantic_definitions")
