"""Constrain database connections to PostgreSQL.

Revision ID: 20260702_0005
Revises: 20260701_0004
Create Date: 2026-07-02
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260702_0005"
down_revision: str | None = "20260701_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CONSTRAINT_NAME = "database_connections_db_type_postgresql"


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE database_connections
        ADD CONSTRAINT {CONSTRAINT_NAME}
        CHECK (db_type = 'postgresql') NOT VALID
        """
    )


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT_NAME, "database_connections", type_="check")