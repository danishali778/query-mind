"""Add user-owned LLM credentials and deployment fallback accounting.

Revision ID: 20260714_0016
Revises: 20260713_0015
Create Date: 2026-07-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

from app.db.orm_models.types import GUID


revision: str = "20260714_0016"
down_revision: str | None = "20260713_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RUN_TABLES = (
    "chat_agent_runs",
    "dashboard_generation_runs",
    "semantic_suggestion_runs",
    "question_suggestion_sets",
)


def _owner_fk() -> sa.ForeignKey:
    return sa.ForeignKey("auth.users.id", ondelete="CASCADE")


def _enable_owner_rls(table_name: str, policy_name: str) -> None:
    op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f'''CREATE POLICY "{policy_name}"
            ON public.{table_name}
            FOR ALL
            USING (((SELECT auth.uid()) = owner_id))
            WITH CHECK (((SELECT auth.uid()) = owner_id))'''
    )


def upgrade() -> None:
    op.create_table(
        "user_llm_credentials",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("owner_id", GUID(), _owner_fk(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=False),
        sa.Column("key_hint", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'valid'"), nullable=False),
        sa.Column("credential_revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("last_validated_at", sa.DateTime(timezone=True)),
        sa.Column("validation_failure_code", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("provider IN ('gemini', 'groq', 'openai')", name="user_llm_credentials_provider_valid"),
        sa.CheckConstraint("status IN ('valid', 'invalid')", name="user_llm_credentials_status_valid"),
        sa.CheckConstraint("credential_revision >= 1", name="user_llm_credentials_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "provider", name="uq_user_llm_credentials_owner_provider"),
    )
    op.create_index("idx_user_llm_credentials_owner", "user_llm_credentials", ["owner_id"])

    op.create_table(
        "llm_usage_events",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("owner_id", GUID(), _owner_fk(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("credential_source", sa.Text(), nullable=False),
        sa.Column("credential_id", GUID()),
        sa.Column("credential_revision", sa.Integer()),
        sa.Column("feature", sa.Text(), nullable=False),
        sa.Column("workflow_type", sa.Text()),
        sa.Column("workflow_id", sa.Text()),
        sa.Column("interaction_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'started'"), nullable=False),
        sa.Column("failure_code", sa.Text()),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("latency_ms", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("provider IN ('gemini', 'groq', 'openai')", name="llm_usage_events_provider_valid"),
        sa.CheckConstraint("credential_source IN ('user', 'deployment')", name="llm_usage_events_source_valid"),
        sa.CheckConstraint("interaction_type IN ('explicit', 'automatic')", name="llm_usage_events_interaction_valid"),
        sa.CheckConstraint("status IN ('started', 'completed', 'failed')", name="llm_usage_events_status_valid"),
        sa.ForeignKeyConstraint(["credential_id"], ["user_llm_credentials.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_llm_usage_events_owner_created", "llm_usage_events", ["owner_id", sa.literal_column("created_at DESC")])
    op.create_index("idx_llm_usage_events_source_created", "llm_usage_events", ["credential_source", sa.literal_column("created_at DESC")])
    _enable_owner_rls("user_llm_credentials", "user_llm_credentials_owner_access")
    _enable_owner_rls("llm_usage_events", "llm_usage_events_owner_access")

    op.add_column("user_settings", sa.Column("preferred_llm_provider", sa.Text()))
    op.add_column("user_settings", sa.Column("preferred_llm_model", sa.Text()))
    op.add_column("user_settings", sa.Column("llm_preference_revision", sa.Integer(), server_default=sa.text("1"), nullable=False))
    op.add_column("user_settings", sa.Column("allow_background_ai", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.execute("UPDATE user_settings SET ai_model = NULL WHERE ai_model IS NOT NULL")

    op.add_column("user_subscriptions", sa.Column("deployment_llm_calls_used", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("user_subscriptions", sa.Column("deployment_llm_calls_limit", sa.Integer(), server_default=sa.text("10"), nullable=False))

    for table_name in RUN_TABLES:
        op.add_column(table_name, sa.Column("llm_provider", sa.Text()))
        op.add_column(table_name, sa.Column("llm_model", sa.Text()))
        op.add_column(table_name, sa.Column("llm_credential_source", sa.Text()))
        op.add_column(table_name, sa.Column("llm_credential_revision", sa.Integer()))


def downgrade() -> None:
    for table_name in reversed(RUN_TABLES):
        op.drop_column(table_name, "llm_credential_revision")
        op.drop_column(table_name, "llm_credential_source")
        op.drop_column(table_name, "llm_model")
        op.drop_column(table_name, "llm_provider")

    op.drop_column("user_subscriptions", "deployment_llm_calls_limit")
    op.drop_column("user_subscriptions", "deployment_llm_calls_used")
    op.drop_column("user_settings", "allow_background_ai")
    op.drop_column("user_settings", "llm_preference_revision")
    op.drop_column("user_settings", "preferred_llm_model")
    op.drop_column("user_settings", "preferred_llm_provider")
    op.drop_index("idx_llm_usage_events_source_created", table_name="llm_usage_events")
    op.drop_index("idx_llm_usage_events_owner_created", table_name="llm_usage_events")
    op.drop_table("llm_usage_events")
    op.drop_index("idx_user_llm_credentials_owner", table_name="user_llm_credentials")
    op.drop_table("user_llm_credentials")
