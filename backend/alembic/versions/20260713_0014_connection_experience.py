"""Add production connection configuration, scope, and health history.

Revision ID: 20260713_0014
Revises: 20260713_0013
Create Date: 2026-07-13
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.db.orm_models.types import GUID


revision: str = "20260713_0014"
down_revision: str | None = "20260713_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("database_connections", sa.Column("credential_revision", sa.Integer(), server_default="1", nullable=False))
    op.add_column("database_connections", sa.Column("credentials_updated_at", sa.DateTime(timezone=True)))
    op.add_column("database_connections", sa.Column("ssl_root_certificate", sa.Text()))
    op.add_column("database_connections", sa.Column("ssl_client_certificate", sa.Text()))
    op.add_column("database_connections", sa.Column("ssl_client_private_key", sa.Text()))
    op.add_column("database_connections", sa.Column("scope_mode", sa.Text(), server_default="all", nullable=False))
    op.add_column("database_connections", sa.Column("included_schemas", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("database_connections", sa.Column("included_tables", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("database_connections", sa.Column("scope_revision", sa.Integer(), server_default="1", nullable=False))
    op.add_column("database_connections", sa.Column("scope_updated_at", sa.DateTime(timezone=True)))
    op.add_column("database_connections", sa.Column("health_check_enabled", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("database_connections", sa.Column("health_check_interval_minutes", sa.Integer(), server_default="60", nullable=False))
    op.add_column("database_connections", sa.Column("next_health_check_at", sa.DateTime(timezone=True)))
    op.add_column("database_connections", sa.Column("schema_refresh_enabled", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("database_connections", sa.Column("schema_refresh_interval_hours", sa.Integer(), server_default="24", nullable=False))
    op.add_column("database_connections", sa.Column("next_schema_refresh_at", sa.DateTime(timezone=True)))

    op.create_check_constraint("database_connections_ssl_mode_valid", "database_connections", "ssl_mode IN ('disable', 'require', 'verify-ca', 'verify-full')")
    op.create_check_constraint("database_connections_scope_mode_valid", "database_connections", "scope_mode IN ('all', 'allowlist')")
    op.create_check_constraint("database_connections_allowlist_nonempty", "database_connections", "scope_mode = 'all' OR included_schemas <> '[]' OR included_tables <> '[]'")
    op.create_check_constraint("database_connections_credential_revision_positive", "database_connections", "credential_revision >= 1")
    op.create_check_constraint("database_connections_scope_revision_positive", "database_connections", "scope_revision >= 1")
    op.create_check_constraint("database_connections_health_interval_valid", "database_connections", "health_check_interval_minutes IN (15, 60, 360, 1440)")
    op.create_check_constraint("database_connections_schema_interval_valid", "database_connections", "schema_refresh_interval_hours IN (6, 12, 24, 168)")
    op.create_index("idx_database_connections_due_health", "database_connections", ["health_check_enabled", "next_health_check_at"])
    op.create_index("idx_database_connections_due_schema", "database_connections", ["schema_refresh_enabled", "next_schema_refresh_at"])

    op.create_table(
        "connection_health_events",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("owner_id", GUID(), nullable=False),
        sa.Column("connection_id", GUID(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("diagnostic_code", sa.Text()),
        sa.Column("message", sa.Text()),
        sa.Column("latency_ms", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("source IN ('initial_connect', 'manual_test', 'scheduled_check', 'credential_rotation', 'schema_refresh')", name="connection_health_events_source_valid"),
        sa.CheckConstraint("status IN ('healthy', 'failed')", name="connection_health_events_status_valid"),
        sa.ForeignKeyConstraint(["connection_id"], ["database_connections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_connection_health_owner_connection_created",
        "connection_health_events",
        ["owner_id", "connection_id", sa.literal_column("created_at DESC")],
    )
    op.create_index(
        "idx_connection_health_connection_status_created",
        "connection_health_events",
        ["connection_id", "status", sa.literal_column("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_connection_health_connection_status_created", table_name="connection_health_events")
    op.drop_index("idx_connection_health_owner_connection_created", table_name="connection_health_events")
    op.drop_table("connection_health_events")
    op.drop_index("idx_database_connections_due_schema", table_name="database_connections")
    op.drop_index("idx_database_connections_due_health", table_name="database_connections")
    for name in (
        "database_connections_schema_interval_valid",
        "database_connections_health_interval_valid",
        "database_connections_scope_revision_positive",
        "database_connections_credential_revision_positive",
        "database_connections_scope_mode_valid",
        "database_connections_allowlist_nonempty",
        "database_connections_ssl_mode_valid",
    ):
        op.drop_constraint(name, "database_connections", type_="check")
    for column in (
        "next_schema_refresh_at", "schema_refresh_interval_hours", "schema_refresh_enabled",
        "next_health_check_at", "health_check_interval_minutes", "health_check_enabled",
        "scope_updated_at", "scope_revision", "included_tables", "included_schemas", "scope_mode",
        "ssl_client_private_key", "ssl_client_certificate", "ssl_root_certificate",
        "credentials_updated_at", "credential_revision",
    ):
        op.drop_column("database_connections", column)
