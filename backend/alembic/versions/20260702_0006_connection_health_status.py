"""Add durable health metadata for saved database connections.

Revision ID: 20260702_0006
Revises: 20260702_0005
Create Date: 2026-07-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260702_0006"
down_revision: str | None = "20260702_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CONSTRAINT_NAME = "database_connections_last_status_valid"


def upgrade() -> None:
    op.add_column("database_connections", sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "database_connections",
        sa.Column("last_status", sa.Text(), nullable=False, server_default=sa.text("'unknown'")),
    )
    op.add_column("database_connections", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column("database_connections", sa.Column("latency_ms", sa.Float(), nullable=True))
    op.add_column("database_connections", sa.Column("last_schema_sync_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE database_connections SET last_status = 'unknown' WHERE last_status IS NULL")
    op.create_check_constraint(
        CONSTRAINT_NAME,
        "database_connections",
        "last_status IN ('unknown', 'healthy', 'failed')",
    )


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT_NAME, "database_connections", type_="check")
    op.drop_column("database_connections", "last_schema_sync_at")
    op.drop_column("database_connections", "latency_ms")
    op.drop_column("database_connections", "last_error")
    op.drop_column("database_connections", "last_status")
    op.drop_column("database_connections", "last_tested_at")
