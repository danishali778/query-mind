"""Force database connections to read-only.

Revision ID: 20260701_0003
Revises: 20260628_0002
Create Date: 2026-07-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260701_0003"
down_revision: str | None = "20260628_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CONSTRAINT_NAME = "database_connections_readonly_true"


def upgrade() -> None:
    op.execute("UPDATE database_connections SET readonly = true WHERE readonly IS DISTINCT FROM true")
    op.alter_column(
        "database_connections",
        "readonly",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.true(),
    )
    op.create_check_constraint(
        _CONSTRAINT_NAME,
        "database_connections",
        "readonly = true",
    )


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT_NAME, "database_connections", type_="check")
    op.alter_column(
        "database_connections",
        "readonly",
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=sa.true(),
    )
