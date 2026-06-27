"""Baseline current live Supabase app schema.

Revision ID: 20260627_0001
Revises:
Create Date: 2026-06-27

This migration captures the app tables that already exist in the live Supabase
project. For that existing project, do not run this migration as `upgrade`;
stamp the database after verifying schema drift instead:

    alembic stamp 20260627_0001

For a brand-new Supabase project, `alembic upgrade head` expects Supabase Auth
and the `auth.users` table to already exist.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260627_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_type():
    return postgresql.UUID(as_uuid=False)


def _owner_fk() -> sa.ForeignKey:
    return sa.ForeignKey("auth.users.id", ondelete="CASCADE")


def _enable_owner_rls(table_name: str, policy_name: str) -> None:
    op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY "{policy_name}"
          ON public.{table_name}
          FOR ALL
          USING ((( SELECT auth.uid() AS uid) = owner_id))
          WITH CHECK ((( SELECT auth.uid() AS uid) = owner_id))
        """
    )


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "database_connections",
        sa.Column("id", _uuid_type(), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("owner_id", _uuid_type(), _owner_fk(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("db_type", sa.Text(), nullable=False),
        sa.Column("host", sa.Text()),
        sa.Column("port", sa.Integer()),
        sa.Column("database", sa.Text(), nullable=False),
        sa.Column("username", sa.Text()),
        sa.Column("password", sa.Text()),
        sa.Column("ssl_mode", sa.Text(), server_default=sa.text("'disable'::text")),
        sa.Column("readonly", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("use_ssh", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("ssh_host", sa.Text()),
        sa.Column("ssh_port", sa.Integer()),
        sa.Column("ssh_username", sa.Text()),
        sa.Column("ssh_password", sa.Text()),
        sa.Column("ssh_private_key", sa.Text()),
    )
    op.execute(
        "CREATE INDEX idx_database_connections_owner_id_created_at "
        "ON public.database_connections USING btree (owner_id, created_at DESC)"
    )
    _enable_owner_rls("database_connections", "Users can manage their own connections")

    op.create_table(
        "dashboards",
        sa.Column("id", _uuid_type(), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("owner_id", _uuid_type(), _owner_fk(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("icon", sa.Text(), server_default=sa.text("chr(128202)")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("filters", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("share_token", _uuid_type(), server_default=sa.text("gen_random_uuid()")),
        sa.CheckConstraint("is_public = false", name="dashboards_private_only"),
    )
    op.execute(
        "CREATE INDEX idx_dashboards_owner_id_created_at "
        "ON public.dashboards USING btree (owner_id, created_at DESC)"
    )
    op.create_index("idx_dashboards_share_token", "dashboards", ["share_token"], unique=True)
    _enable_owner_rls("dashboards", "Users can manage their own dashboards")

    op.create_table(
        "saved_queries",
        sa.Column("id", _uuid_type(), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("owner_id", _uuid_type(), _owner_fk(), nullable=False),
        sa.Column("connection_id", _uuid_type(), sa.ForeignKey("database_connections.id", ondelete="SET NULL")),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("sql", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("schedule", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("run_count", sa.BigInteger(), server_default=sa.text("0")),
    )
    op.create_index("idx_saved_queries_connection_id", "saved_queries", ["connection_id"])
    op.execute(
        "CREATE INDEX idx_saved_queries_owner_id_created_at "
        "ON public.saved_queries USING btree (owner_id, created_at DESC)"
    )
    _enable_owner_rls("saved_queries", "Users can manage their own queries")

    op.create_table(
        "user_settings",
        sa.Column("owner_id", _uuid_type(), _owner_fk(), primary_key=True),
        sa.Column("full_name", sa.Text()),
        sa.Column("job_title", sa.Text()),
        sa.Column("timezone", sa.Text(), server_default=sa.text("'UTC'::text")),
        sa.Column("theme", sa.Text(), server_default=sa.text("'light'::text")),
        sa.Column("accent_color", sa.Text(), server_default=sa.text("'cyan'::text")),
        sa.Column("density", sa.Text(), server_default=sa.text("'comfortable'::text")),
        sa.Column("show_run_counts", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("animate_charts", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("syntax_highlighting", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("ai_model", sa.Text(), server_default=sa.text("'claude-sonnet-4-6'::text")),
        sa.Column("stream_responses", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("default_row_limit", sa.Integer(), server_default=sa.text("500")),
        sa.Column("auto_save_queries", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("system_prompt", sa.Text(), server_default=sa.text("''::text")),
        sa.Column("email_scheduled", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("email_failed", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("email_alerts", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("delivery_format", sa.Text(), server_default=sa.text("'CSV + Chart PNG'::text")),
        sa.Column("slack_enabled", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("slack_webhook", sa.Text()),
        sa.Column("slack_channel", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.execute("ALTER TABLE public.user_settings ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY "Users can insert their own settings"
          ON public.user_settings
          FOR INSERT
          WITH CHECK ((( SELECT auth.uid() AS uid) = owner_id))
        """
    )
    op.execute(
        """
        CREATE POLICY "Users can update their own settings"
          ON public.user_settings
          FOR UPDATE
          USING ((( SELECT auth.uid() AS uid) = owner_id))
          WITH CHECK ((( SELECT auth.uid() AS uid) = owner_id))
        """
    )
    op.execute(
        """
        CREATE POLICY "Users can view their own settings"
          ON public.user_settings
          FOR SELECT
          USING ((( SELECT auth.uid() AS uid) = owner_id))
        """
    )

    op.create_table(
        "user_subscriptions",
        sa.Column("owner_id", _uuid_type(), _owner_fk(), primary_key=True),
        sa.Column("plan_type", sa.Text(), server_default=sa.text("'free'::text")),
        sa.Column("queries_used", sa.Integer(), server_default=sa.text("0")),
        sa.Column("queries_limit", sa.Integer(), server_default=sa.text("100")),
        sa.Column("ai_used", sa.Integer(), server_default=sa.text("0")),
        sa.Column("ai_limit", sa.Integer(), server_default=sa.text("30")),
        sa.Column("next_reset_date", sa.DateTime(timezone=True), server_default=sa.text("(now() + '1 mon'::interval)")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.execute("ALTER TABLE public.user_subscriptions ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY "Users can insert their own subscription"
          ON public.user_subscriptions
          FOR INSERT
          WITH CHECK ((( SELECT auth.uid() AS uid) = owner_id))
        """
    )
    op.execute(
        """
        CREATE POLICY "Users can update their own subscription"
          ON public.user_subscriptions
          FOR UPDATE
          USING ((( SELECT auth.uid() AS uid) = owner_id))
          WITH CHECK ((( SELECT auth.uid() AS uid) = owner_id))
        """
    )
    op.execute(
        """
        CREATE POLICY "Users can view their own subscription"
          ON public.user_subscriptions
          FOR SELECT
          USING ((( SELECT auth.uid() AS uid) = owner_id))
        """
    )

    op.create_table(
        "dashboard_widgets",
        sa.Column("id", _uuid_type(), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("dashboard_id", _uuid_type(), sa.ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", _uuid_type(), _owner_fk(), nullable=False),
        sa.Column("connection_id", _uuid_type(), sa.ForeignKey("database_connections.id", ondelete="SET NULL")),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("viz_type", sa.Text(), nullable=False),
        sa.Column("size", sa.Text(), server_default=sa.text("'half'::text")),
        sa.Column("sql", sa.Text()),
        sa.Column("chart_config", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("layout_params", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("cadence", sa.Text(), server_default=sa.text("'Manual only'::text")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("rows", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), comment="Stores the serialized query results (rows) for the widget."),
        sa.Column("columns", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), comment="Stores the column names for the query results."),
        sa.Column("order_index", sa.Integer(), server_default=sa.text("0")),
    )
    op.create_index("idx_dashboard_widgets_connection_id", "dashboard_widgets", ["connection_id"])
    op.create_index("idx_dashboard_widgets_dashboard_id_order_index", "dashboard_widgets", ["dashboard_id", "order_index"])
    op.create_index("idx_dashboard_widgets_owner_id", "dashboard_widgets", ["owner_id"])
    _enable_owner_rls("dashboard_widgets", "Users can manage their own widgets")

    op.create_table(
        "query_executions",
        sa.Column("id", _uuid_type(), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("owner_id", _uuid_type(), _owner_fk(), nullable=False),
        sa.Column("connection_id", _uuid_type(), sa.ForeignKey("database_connections.id", ondelete="SET NULL")),
        sa.Column("query_id", _uuid_type(), sa.ForeignKey("saved_queries.id", ondelete="SET NULL")),
        sa.Column("sql", sa.Text(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("row_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("execution_time_ms", sa.Float(), server_default=sa.text("0.0")),
        sa.Column("error", sa.Text()),
        sa.Column("triggered_by", sa.Text(), server_default=sa.text("'manual'::text")),
        sa.Column("ran_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_query_executions_connection_id", "query_executions", ["connection_id"])
    op.execute(
        "CREATE INDEX idx_query_executions_owner_id_ran_at "
        "ON public.query_executions USING btree (owner_id, ran_at DESC)"
    )
    op.create_index("idx_query_executions_query_id", "query_executions", ["query_id"])
    _enable_owner_rls("query_executions", "Users can manage their own query executions")

    op.create_table(
        "chat_sessions",
        sa.Column("id", _uuid_type(), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("owner_id", _uuid_type(), _owner_fk(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("last_connection_id", _uuid_type(), sa.ForeignKey("database_connections.id", ondelete="SET NULL")),
        sa.Column("connection_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=False)), server_default=sa.text("'{}'::uuid[]")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_chat_sessions_last_connection_id", "chat_sessions", ["last_connection_id"])
    op.execute(
        "CREATE INDEX idx_chat_sessions_owner_id_created_at "
        "ON public.chat_sessions USING btree (owner_id, created_at DESC)"
    )
    _enable_owner_rls("chat_sessions", "Users can manage their own chat sessions")

    op.create_table(
        "chat_messages",
        sa.Column("id", _uuid_type(), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("session_id", _uuid_type(), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", _uuid_type(), _owner_fk(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sql", sa.Text()),
        sa.Column("results", postgresql.JSONB()),
        sa.Column("error", sa.Text()),
        sa.Column("connection_id", _uuid_type(), sa.ForeignKey("database_connections.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("chart_recommendation", postgresql.JSONB()),
        sa.Column("columns", postgresql.ARRAY(sa.Text())),
        sa.Column("is_pinned", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("parent_id", _uuid_type(), sa.ForeignKey("chat_messages.id", ondelete="SET NULL"), comment="References the user message that triggered this assistant response."),
        sa.Column("prev_query_id", _uuid_type(), sa.ForeignKey("chat_messages.id", ondelete="SET NULL"), comment="References the previous USER message in this session to maintain the trunk of the conversation."),
    )
    op.create_index("idx_chat_messages_connection_id", "chat_messages", ["connection_id"])
    op.execute(
        "CREATE INDEX idx_chat_messages_owner_id_created_at "
        "ON public.chat_messages USING btree (owner_id, created_at DESC)"
    )
    op.create_index("idx_chat_messages_parent_id", "chat_messages", ["parent_id"])
    op.create_index("idx_chat_messages_prev_query_id", "chat_messages", ["prev_query_id"])
    op.create_index("idx_chat_messages_session_id_created_at", "chat_messages", ["session_id", "created_at"])
    _enable_owner_rls("chat_messages", "Users can manage their own chat messages")


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("query_executions")
    op.drop_table("dashboard_widgets")
    op.drop_table("user_subscriptions")
    op.drop_table("user_settings")
    op.drop_table("saved_queries")
    op.drop_table("dashboards")
    op.drop_table("database_connections")