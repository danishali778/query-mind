"""Make the per-user dashboard generation limit configurable.

Revision ID: 20260713_0012
Revises: 20260712_0011
Create Date: 2026-07-13
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260713_0012"
down_revision: str | None = "20260712_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(
        "uq_dashboard_generation_runs_active_owner",
        table_name="dashboard_generation_runs",
    )
    op.create_index(
        "idx_dashboard_generation_runs_owner_status",
        "dashboard_generation_runs",
        ["owner_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_dashboard_generation_runs_owner_status",
        table_name="dashboard_generation_runs",
    )
    op.create_index(
        "uq_dashboard_generation_runs_active_owner",
        "dashboard_generation_runs",
        ["owner_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('planning', 'queued', 'running')"),
        sqlite_where=sa.text("status IN ('planning', 'queued', 'running')"),
    )
