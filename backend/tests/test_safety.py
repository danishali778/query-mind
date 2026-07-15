"""Unit tests for backend/app/query_engine/safety.py

Tests validate_query() and sanitize_row_limit() with a wide range of
normal, edge-case, and adversarial inputs.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import anyio
import pytest
from sqlalchemy import create_engine, text
from app.db.models.chat import ChatMessage
from app.db.models.connection import ConnectionRequest
from app.query_engine.executor import execute_query
from app.query_engine.safety import (
    validate_query,
    sanitize_row_limit,
    get_readonly_wrapped_query,
)
from app.services import chat_service


# ---------------------------------------------------------------------------
# validate_query — allowed queries
# ---------------------------------------------------------------------------

class TestValidQueryAllowed:
    def test_simple_select(self):
        ok, msg = validate_query("SELECT * FROM users")
        assert ok, msg

    def test_select_with_where(self):
        ok, msg = validate_query("SELECT id, name FROM orders WHERE status = 'active'")
        assert ok, msg

    def test_select_with_join(self):
        ok, msg = validate_query(
            "SELECT u.id, o.total FROM users u JOIN orders o ON u.id = o.user_id"
        )
        assert ok, msg

    def test_with_cte(self):
        ok, msg = validate_query(
            "WITH summary AS (SELECT user_id, COUNT(*) cnt FROM orders GROUP BY user_id) "
            "SELECT * FROM summary"
        )
        assert ok, msg

    def test_explain_query(self):
        ok, msg = validate_query("EXPLAIN SELECT * FROM users")
        assert ok, msg

    def test_show_tables(self):
        ok, msg = validate_query("SHOW TABLES")
        assert ok, msg

    def test_describe_table(self):
        ok, msg = validate_query("DESCRIBE users")
        assert ok, msg

    def test_select_with_subquery(self):
        ok, msg = validate_query(
            "SELECT * FROM users WHERE id IN (SELECT user_id FROM orders)"
        )
        assert ok, msg


# ---------------------------------------------------------------------------
# validate_query — blocked simple keywords
# ---------------------------------------------------------------------------

class TestValidQueryBlocked:
    @pytest.mark.parametrize("sql", [
        "DROP TABLE users",
        "DELETE FROM users WHERE id = 1",
        "UPDATE users SET name = 'x' WHERE id = 1",
        "INSERT INTO users (name) VALUES ('x')",
        "ALTER TABLE users ADD COLUMN age INT",
        "TRUNCATE TABLE users",
        "CREATE TABLE new_table (id INT)",
        "GRANT SELECT ON users TO public",
        "REVOKE SELECT ON users FROM public",
        "EXEC sp_something",
        "EXECUTE sp_something",
    ])
    def test_blocked_keywords(self, sql):
        ok, msg = validate_query(sql)
        assert not ok
        assert "not allowed" in msg.lower() or "blocked" in msg.lower()

    @pytest.mark.parametrize("sql", [
        "SELECT lo_import('/etc/passwd')",
        "SELECT lo_export(1234, '/tmp/out')",
        "SELECT dblink('host=evil', 'DROP TABLE users')",
        "SELECT dblink_exec('host=evil', 'DROP TABLE users')",
        "SELECT pg_read_file('/etc/passwd')",
        "COPY users TO '/tmp/dump.csv'",
    ])
    def test_blocked_postgres_specific(self, sql):
        ok, msg = validate_query(sql)
        assert not ok

    def test_keyword_hidden_in_comment_blocked(self):
        """Keywords hidden in comments are still caught after comment stripping."""
        ok, msg = validate_query("-- DROP TABLE users\nSELECT 1")
        # After stripping comment, only SELECT 1 remains — should be allowed
        assert ok, msg

    def test_keyword_hidden_in_string_literal_allowed(self):
        """Keywords inside string literals must NOT be blocked.

        e.g. WHERE name = 'DROP TABLE users' is a safe SELECT query.
        The _strip_literals() step should handle this correctly.
        """
        ok, msg = validate_query("SELECT * FROM users WHERE name = 'DROP TABLE users'")
        assert ok, msg

    def test_mixed_case_blocked(self):
        ok, msg = validate_query("dRoP tAbLe users")
        assert not ok

    def test_empty_query_blocked(self):
        ok, msg = validate_query("  ")
        assert not ok
        assert "empty" in msg.lower()

    def test_non_select_first_word_blocked(self):
        ok, msg = validate_query("MERGE INTO users USING src ON users.id = src.id")
        assert not ok
        assert "MERGE" in msg


# ---------------------------------------------------------------------------
# sanitize_row_limit
# ---------------------------------------------------------------------------

class TestSanitizeRowLimit:
    def test_adds_limit_when_missing(self):
        sql = "SELECT * FROM users"
        result = sanitize_row_limit(sql, 100)
        assert result.endswith("LIMIT 100")

    def test_wraps_existing_limit_with_server_cap(self):
        sql = "SELECT * FROM users LIMIT 50"
        result = sanitize_row_limit(sql, 100)
        assert "LIMIT 50" in result
        assert result.endswith("LIMIT 100")

    def test_strips_trailing_semicolon_before_adding_limit(self):
        sql = "SELECT * FROM users;"
        result = sanitize_row_limit(sql, 100)
        assert result.endswith("LIMIT 100")
        assert ";;" not in result

    def test_case_insensitive_existing_limit_still_gets_server_cap(self):
        sql = "SELECT * FROM users limit 20"
        result = sanitize_row_limit(sql, 100)
        assert "limit 20" in result
        assert result.endswith("LIMIT 100")


    def test_wraps_cte_query_with_server_cap(self):
        sql = "WITH users AS (SELECT 1 AS id) SELECT id FROM users"
        result = sanitize_row_limit(sql, 100)
        assert result.startswith("SELECT * FROM (\nWITH users AS")
        assert result.endswith("LIMIT 100")

# ---------------------------------------------------------------------------
# get_readonly_wrapped_query
# ---------------------------------------------------------------------------

class TestGetReadonlyWrappedQuery:
    def test_wraps_with_transaction_prefix(self):
        result = get_readonly_wrapped_query("SELECT * FROM users")
        assert result.startswith("SET TRANSACTION READ ONLY;")

    def test_strips_trailing_semicolon_before_wrapping(self):
        result = get_readonly_wrapped_query("SELECT * FROM users;")
        # Should not have double semicolons
        assert ";;" not in result
        assert "SELECT * FROM users" in result


# ---------------------------------------------------------------------------
# enforced read-only connection policy
# ---------------------------------------------------------------------------

class _NeverConnectEngine:
    class _Dialect:
        name = "postgresql"

    dialect = _Dialect()

    def connect(self):
        raise AssertionError("destructive SQL should be rejected before opening a connection")


def test_connection_request_schemas_do_not_accept_readonly():
    from app.api.v1.schemas.connections import ConnectionRequest as ApiConnectionRequest
    from app.api.v1.schemas.connections import UpdateConnectionSettingsRequest

    assert "readonly" not in ApiConnectionRequest.model_fields
    assert "readonly" not in UpdateConnectionSettingsRequest.model_fields


def test_database_connection_model_enforces_readonly_default_and_constraint():
    from app.db.orm_models import DatabaseConnectionORM

    table = DatabaseConnectionORM.__table__
    readonly_column = table.c.readonly
    constraint_names = {constraint.name for constraint in table.constraints}

    assert readonly_column.nullable is False
    assert readonly_column.default is not None
    assert readonly_column.server_default is not None
    assert "database_connections_readonly_true" in constraint_names
    assert "database_connections_db_type_postgresql" in constraint_names


def test_executor_blocks_destructive_sql_even_when_readonly_false():
    from app.query_engine.executor import execute_query

    result = execute_query(
        user_id="user-1",
        engine=_NeverConnectEngine(),
        sql="DROP TABLE users",
        readonly=False,
    )

    assert result.success is False
    assert result.error is not None
    assert "not allowed" in result.error.lower() or "blocked" in result.error.lower()


def test_readonly_migration_backfills_defaults_and_constraint():
    from pathlib import Path

    migration = (Path(__file__).resolve().parents[1] / "alembic/versions/20260701_0003_force_readonly_connections.py").read_text()

    assert "UPDATE database_connections SET readonly = true" in migration
    assert "nullable=False" in migration
    assert "server_default=sa.true()" in migration
    assert "database_connections_readonly_true" in migration


# ---------------------------------------------------------------------------
# database connection target guardrails
# ---------------------------------------------------------------------------

def _connection(host="8.8.8.8", port=5432, *, use_ssh=False, ssh_host=None):
    from app.db.models.connection import ConnectionRequest

    return ConnectionRequest(
        db_type="postgresql",
        host=host,
        port=port,
        database="demo",
        username="demo",
        password="secret",
        use_ssh=use_ssh,
        ssh_host=ssh_host,
        ssh_port=22,
        ssh_username="ubuntu" if use_ssh else None,
        ssh_password="secret" if use_ssh else None,
    )


def test_connection_guardrails_block_private_targets_in_production(monkeypatch):
    from app.core.config import settings
    from app.core.db_connection_guardrails import validate_connection_target
    from app.core.errors import BadRequestError

    monkeypatch.setattr(settings, "app_env", "production", raising=False)
    monkeypatch.setattr(settings, "db_connect_allowed_hosts_raw", "", raising=False)
    monkeypatch.setattr(settings, "db_connect_allowed_cidrs_raw", "", raising=False)

    for host in ["localhost", "127.0.0.1", "10.0.0.5", "192.168.1.10", "172.16.0.1", "169.254.1.1", "::1", "fc00::1"]:
        with pytest.raises(BadRequestError):
            validate_connection_target(_connection(host=host))


def test_connection_guardrails_always_block_metadata_targets(monkeypatch):
    from app.core.config import settings
    from app.core.db_connection_guardrails import validate_connection_target
    from app.core.errors import BadRequestError

    monkeypatch.setattr(settings, "app_env", "development", raising=False)
    monkeypatch.setattr(settings, "db_connect_allow_private_in_dev", True, raising=False)

    with pytest.raises(BadRequestError):
        validate_connection_target(_connection(host="169.254.169.254"))


def test_connection_guardrails_allow_public_and_allowlisted_targets(monkeypatch):
    from app.core.config import settings
    from app.core.db_connection_guardrails import validate_connection_target

    monkeypatch.setattr(settings, "app_env", "production", raising=False)
    monkeypatch.setattr(settings, "db_connect_allowed_hosts_raw", "localhost", raising=False)
    monkeypatch.setattr(settings, "db_connect_allowed_cidrs_raw", "10.0.0.0/8", raising=False)

    validate_connection_target(_connection(host="8.8.8.8"))
    validate_connection_target(_connection(host="localhost"))
    validate_connection_target(_connection(host="10.0.0.5"))


def test_connection_guardrails_allow_private_targets_in_dev(monkeypatch):
    from app.core.config import settings
    from app.core.db_connection_guardrails import validate_connection_target

    monkeypatch.setattr(settings, "app_env", "development", raising=False)
    monkeypatch.setattr(settings, "db_connect_allow_private_in_dev", True, raising=False)
    monkeypatch.setattr(settings, "db_connect_allowed_hosts_raw", "", raising=False)
    monkeypatch.setattr(settings, "db_connect_allowed_cidrs_raw", "", raising=False)

    validate_connection_target(_connection(host="127.0.0.1"))


def test_connection_guardrails_validate_ssh_host_not_remote_database_host(monkeypatch):
    from app.core.config import settings
    from app.core.db_connection_guardrails import validate_connection_target
    from app.core.errors import BadRequestError

    monkeypatch.setattr(settings, "app_env", "production", raising=False)
    monkeypatch.setattr(settings, "db_connect_allowed_hosts_raw", "", raising=False)
    monkeypatch.setattr(settings, "db_connect_allowed_cidrs_raw", "", raising=False)

    with pytest.raises(BadRequestError):
        validate_connection_target(_connection(host="10.0.0.5", use_ssh=True, ssh_host="127.0.0.1"))


def test_connection_rate_limit_uses_redis_counter(monkeypatch):
    from app.core.config import settings
    from app.core import db_connection_guardrails as guardrails
    from app.core.db_connection_guardrails import RateLimitError, enforce_connection_attempt_rate_limit

    class FakeRedis:
        def __init__(self):
            self.count = 0

        def incr(self, key):
            self.count += 1
            return self.count

        def expire(self, key, seconds):
            return True

    fake = FakeRedis()
    monkeypatch.setattr(settings, "db_connect_rate_limit_attempts", 1, raising=False)
    monkeypatch.setattr(settings, "db_connect_rate_limit_window_seconds", 60, raising=False)
    monkeypatch.setattr(guardrails, "get_redis_client", lambda: fake)

    enforce_connection_attempt_rate_limit("user-redis")
    with pytest.raises(RateLimitError):
        enforce_connection_attempt_rate_limit("user-redis")


def test_connection_rate_limit_fails_closed_in_production_without_redis(monkeypatch):
    from app.core.config import settings
    from app.core import db_connection_guardrails as guardrails
    from app.core.db_connection_guardrails import enforce_connection_attempt_rate_limit
    from app.core.errors import ServiceUnavailableError

    monkeypatch.setattr(settings, "app_env", "production", raising=False)
    monkeypatch.setattr(settings, "redis_url", None, raising=False)
    monkeypatch.setattr(settings, "celery_broker_url", None, raising=False)
    monkeypatch.setattr(guardrails, "get_redis_client", lambda: None)

    with pytest.raises(ServiceUnavailableError):
        enforce_connection_attempt_rate_limit("user-prod-no-redis")


def test_connection_rate_limit_uses_memory_fallback_in_dev(monkeypatch):
    from app.core.config import settings
    from app.core import db_connection_guardrails as guardrails
    from app.core.db_connection_guardrails import RateLimitError, enforce_connection_attempt_rate_limit

    monkeypatch.setattr(settings, "app_env", "development", raising=False)
    monkeypatch.setattr(settings, "db_connect_rate_limit_attempts", 1, raising=False)
    monkeypatch.setattr(settings, "db_connect_rate_limit_window_seconds", 60, raising=False)
    monkeypatch.setattr(guardrails, "get_redis_client", lambda: None)
    guardrails._memory_rate_limits.clear()

    enforce_connection_attempt_rate_limit("user-dev-memory")
    with pytest.raises(RateLimitError):
        enforce_connection_attempt_rate_limit("user-dev-memory")


def test_connection_pool_build_engine_sets_driver_timeout(monkeypatch):
    from app.core.config import settings
    from app.query_engine import connection_pool

    captured = {}

    def fake_create_engine(url, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(settings, "db_connect_timeout_seconds", 7, raising=False)
    monkeypatch.setattr(connection_pool, "create_engine", fake_create_engine)

    connection_pool.build_engine("postgresql://example.com/demo", "postgresql")

    assert captured["connect_args"]["connect_timeout"] == 7

def test_connection_guardrails_reject_unsupported_database_types():
    from app.core.db_connection_guardrails import UNSUPPORTED_DATABASE_MESSAGE, validate_connection_target
    from app.core.errors import BadRequestError

    for db_type in ["mysql", "sqlite", "mssql", "snowflake", ""]:
        config = _connection()
        config.db_type = db_type
        with pytest.raises(BadRequestError) as exc:
            validate_connection_target(config)
        assert exc.value.message == UNSUPPORTED_DATABASE_MESSAGE


def test_connection_pool_rejects_unsupported_saved_config_before_engine(monkeypatch):
    from app.core.db_connection_guardrails import UNSUPPORTED_DATABASE_MESSAGE
    from app.core.errors import BadRequestError
    from app.query_engine import connection_pool

    def fail_if_called(*args, **kwargs):
        raise AssertionError("unsupported database type should be rejected before engine creation")

    config = _connection()
    config.db_type = "mysql"
    monkeypatch.setattr(connection_pool, "create_engine", fail_if_called)

    with pytest.raises(BadRequestError) as exc:
        connection_pool.open_connection(config)
    assert exc.value.message == UNSUPPORTED_DATABASE_MESSAGE


def test_connection_health_model_enforces_default_and_constraint():
    from app.db.orm_models import DatabaseConnectionORM

    table = DatabaseConnectionORM.__table__
    last_status_column = table.c.last_status
    constraint_names = {constraint.name for constraint in table.constraints}

    assert last_status_column.nullable is False
    assert last_status_column.default is not None
    assert last_status_column.server_default is not None
    assert "database_connections_last_status_valid" in constraint_names


def test_connection_status_derivation_states():
    from datetime import datetime, timedelta, timezone

    from app.db.models.connection import derive_connection_status

    now = datetime.now(timezone.utc)

    assert derive_connection_status("failed", now) == ("failed", "offline")
    assert derive_connection_status("healthy", now) == ("live", "live")
    assert derive_connection_status("healthy", now - timedelta(hours=25)) == ("stale", "warning")
    assert derive_connection_status("unknown", None) == ("unknown", "warning")


# ---------------------------------------------------------------------------
# non-blocking connection attempt boundaries
# ---------------------------------------------------------------------------

def _async_boundary_config() -> ConnectionRequest:
    return ConnectionRequest(
        db_type="postgresql",
        host="8.8.8.8",
        port=5432,
        database="demo",
        username="demo",
        password="secret",
        readonly=True,
    )


def test_connection_pool_test_wraps_full_dial_in_thread(monkeypatch):
    from app.query_engine import connection_pool

    calls = []

    async def fake_run_sync(func, *args, **kwargs):
        calls.append((func, args))
        return True, "ok"

    monkeypatch.setattr(connection_pool.anyio.to_thread, "run_sync", fake_run_sync)

    success, message = anyio.run(connection_pool.test_connection, _async_boundary_config())

    assert success is True
    assert message == "ok"
    assert calls == [(connection_pool._test_connection_sync, (_async_boundary_config(),))]


def test_connection_manager_connect_opens_connection_in_thread(monkeypatch):
    from app.db import connection_manager

    opened = []

    class FakeEngine:
        def dispose(self):
            pass

    async def fake_run_sync(func, *args, **kwargs):
        # connect() now also threadpools its preflight/audit helpers; this test
        # only asserts on the engine-opening call, so run everything else inline
        # (the stubbed sync helpers below still execute).
        target = getattr(func, "func", func)
        if target is connection_manager.connection_pool.open_connection:
            opened.append((func, args))
            return FakeEngine(), None
        return func(*args)

    async def fake_create_connection(user_id, config):
        return "conn_1"

    async def fake_create_bundle(user_id, config, schema, *, latency_ms):
        return "conn_1", object()

    async def fake_record_health(*args, **kwargs):
        return True

    monkeypatch.setattr(connection_manager.anyio.to_thread, "run_sync", fake_run_sync)
    monkeypatch.setattr(connection_manager, "_preflight_connection_attempt", lambda *args, **kwargs: None)
    monkeypatch.setattr(connection_manager.schema_inspector, "discover_schema_inventory", lambda *args: ([{"name": "public", "tables": ["demo"]}], False))
    monkeypatch.setattr(connection_manager.schema_inspector, "get_schema", lambda *args, **kwargs: [connection_manager.TableInfo(name="demo", columns=[])])
    monkeypatch.setattr(connection_manager.connection_repository, "create_connection_bundle", fake_create_bundle)
    monkeypatch.setattr(connection_manager.connection_repository, "record_connection_health", fake_record_health)
    monkeypatch.setattr(connection_manager.connection_attempt_repository, "log_connection_attempt", lambda **kwargs: None)
    monkeypatch.setattr(connection_manager.connection_pool, "cache_connection", lambda *args, **kwargs: None)
    monkeypatch.setattr(connection_manager.connection_pool, "cache_schema", lambda *args, **kwargs: None)
    monkeypatch.setattr(connection_manager.connection_pool, "cache_catalog", lambda *args, **kwargs: None)

    connection_id, engine, latency_ms = anyio.run(connection_manager.connect, "user_1", _async_boundary_config())

    assert connection_id == "conn_1"
    assert isinstance(engine, FakeEngine)
    assert latency_ms >= 0
    assert opened == [(connection_manager.connection_pool.open_connection, (_async_boundary_config(),))]


def test_connection_manager_get_engine_reopens_saved_connection_in_thread(monkeypatch):
    from app.db import connection_manager

    opened = []
    cached = []

    class FakeEngine:
        pass

    async def fake_run_sync(func, *args, **kwargs):
        target = getattr(func, "func", func)
        if target is connection_manager.connection_pool.open_connection:
            opened.append((func, args))
            return FakeEngine(), None
        if target is connection_manager.connection_pool.cache_connection:
            cached.append((func, args))
        return func(*args)

    async def fake_get_async_boundary_config(user_id, connection_id):
        return _async_boundary_config()

    monkeypatch.setattr(connection_manager.connection_pool, "get_cached_engine", lambda *args, **kwargs: None)
    monkeypatch.setattr(connection_manager.anyio.to_thread, "run_sync", fake_run_sync)
    monkeypatch.setattr(connection_manager.connection_repository, "get_connection_config", fake_get_async_boundary_config)
    monkeypatch.setattr(connection_manager.connection_pool, "cache_connection", lambda *args, **kwargs: None)

    engine = anyio.run(connection_manager.get_engine, "user_1", "conn_1")

    assert isinstance(engine, FakeEngine)
    assert opened == [(connection_manager.connection_pool.open_connection, (_async_boundary_config(),))]
    assert len(cached) == 1


def test_connect_route_does_not_inspect_schema_or_bootstrap_templates(monkeypatch):
    from app.api.v1.routes import connections
    from app.db.models.connection import ActiveConnection

    async def fake_connect(user_id, config):
        return "conn_1", object(), 12.0

    async def fake_get_connection(user_id, connection_id):
        return ActiveConnection(
            id=connection_id,
            owner_id=user_id,
            name="Warehouse Main",
            db_type="postgresql",
            database="demo",
            host="8.8.8.8",
            port=5432,
            username="demo",
            status="live",
            health_state="live",
            tables_count=0,
            readonly=True,
        )

    async def fail_schema(*args, **kwargs):
        raise AssertionError("connect route should not inspect schema inline")

    monkeypatch.setattr(connections.connection_service, "connect", fake_connect)
    monkeypatch.setattr(connections.connection_service, "get_connection", fake_get_connection)
    monkeypatch.setattr(connections.connection_service, "get_cached_schema", fail_schema)

    class User:
        id = "user_1"

    response = anyio.run(connections.connect_database, _async_boundary_config(), User())

    assert response.id == "conn_1"
    assert response.message == "Successfully connected to demo"

# ---------------------------------------------------------------------------
# execute_query row caps
# ---------------------------------------------------------------------------

class TestExecuteQueryRowLimits:
    def test_enforces_row_limit_when_query_has_huge_limit(self):
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE items (id INTEGER PRIMARY KEY)"))
            for i in range(10):
                conn.execute(text("INSERT INTO items (id) VALUES (:id)"), {"id": i + 1})

        result = execute_query(
            user_id="user-1",
            engine=engine,
            sql="SELECT id FROM items ORDER BY id LIMIT 1000000",
            row_limit=3,
        )

        assert result.success is True
        assert result.row_count == 3
        assert result.truncated is True
        assert [row["id"] for row in result.rows] == [1, 2, 3]


# ---------------------------------------------------------------------------
# chat truncated metadata
# ---------------------------------------------------------------------------

class TestChatTruncatedMetadata:
    def test_chat_response_and_stored_message_include_truncated(self, monkeypatch):
        stored_messages = []

        async def fake_get_engine(user_id, connection_id):
            return object()

        async def fake_get_schema_for_ai(user_id, connection_id):
            return "Table: items\n  - id: integer NOT NULL"

        async def fake_create_session(user_id, connection_id):
            return SimpleNamespace(id="session-1")

        async def fake_noop(*args, **kwargs):
            return None

        async def fake_record_user_turn(user_id, session_id, connection_id, message):
            user_msg = ChatMessage(role="user", content=message, connection_id=connection_id)
            stored_messages.append(user_msg)
            return user_msg, None, []

        async def fake_add_message(user_id, session_id, message):
            stored_messages.append(message)

        async def fake_prepare_chat_intent(**kwargs):
            return SimpleNamespace(intent=SimpleNamespace(decision="analyze"), history=[])

        monkeypatch.setattr(chat_service.connection_service, "get_engine", fake_get_engine)
        monkeypatch.setattr(chat_service.connection_service, "get_schema_for_ai", fake_get_schema_for_ai)
        monkeypatch.setattr(chat_service, "create_session", fake_create_session)
        monkeypatch.setattr(chat_service, "rename_session", fake_noop)
        monkeypatch.setattr(chat_service, "record_user_turn", fake_record_user_turn)
        monkeypatch.setattr(chat_service, "add_message", fake_add_message)
        monkeypatch.setattr(chat_service, "prepare_chat_intent", fake_prepare_chat_intent)
        monkeypatch.setattr(
            chat_service.analysis_service,
            "run_analysis",
            AsyncMock(
                return_value={
                    "explanation": "Preview is limited.",
                    "sql": "SELECT id FROM items LIMIT 1000000",
                    "columns": ["id"],
                    "rows": [{"id": 1}],
                    "row_count": 500,
                    "execution_time_ms": 12.5,
                    "truncated": True,
                    "chart_recommendation": None,
                    "error": "",
                    "column_metadata": {"id": "numeric"},
                }
            ),
        )

        response = asyncio.run(
            chat_service.send_message(
                user_id="user-1",
                connection_id="connection-1",
                message="show items",
            )
        )

        assert response["truncated"] is True
        assert response["row_count"] == 500
        assert len(stored_messages) == 2
        assistant_message = stored_messages[1]
        assert assistant_message.truncated is True
        assert assistant_message.results["truncated"] is True
        assert assistant_message.results["row_count"] == 500
        assert assistant_message.results["execution_time_ms"] == 12.5


# ---------------------------------------------------------------------------
# chat persistence failure handling
# ---------------------------------------------------------------------------

class _BrokenSessionScope:
    def __enter__(self):
        raise RuntimeError("database unavailable")

    def __exit__(self, exc_type, exc, tb):
        return False


class _EmptyQuery:
    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def one_or_none(self):
        return None

    def all(self):
        return []


class _EmptySession:
    def query(self, *args, **kwargs):
        return _EmptyQuery()


class _EmptySessionScope:
    def __enter__(self):
        return _EmptySession()

    def __exit__(self, exc_type, exc, tb):
        return False


class TestChatPersistenceFailures:
    def test_add_message_raises_on_db_failure(self, monkeypatch):
        from app.db.models.chat import ChatMessage
        from app.db.repositories import chat_repository

        monkeypatch.setattr(chat_repository, "session_scope", lambda: _BrokenSessionScope())

        with pytest.raises(RuntimeError, match="database unavailable"):
            asyncio.run(chat_repository.add_message("user-1", "session-1", ChatMessage(role="user", content="hi")))

    def test_update_message_raises_on_db_failure(self, monkeypatch):
        from app.db.repositories import chat_repository

        monkeypatch.setattr(chat_repository, "session_scope", lambda: _BrokenSessionScope())

        with pytest.raises(RuntimeError, match="database unavailable"):
            asyncio.run(chat_repository.update_message("user-1", "session-1", "message-1", {"content": "x"}))

    def test_update_message_missing_message_returns_false(self, monkeypatch):
        from app.db.repositories import chat_repository

        monkeypatch.setattr(chat_repository, "session_scope", lambda: _EmptySessionScope())

        updated = asyncio.run(
            chat_repository.update_message(
                "00000000-0000-0000-0000-00000000ffff",
                "00000000-0000-0000-0000-00000000aaa1",
                "00000000-0000-0000-0000-00000000aaa2",
                {"content": "x"},
            )
        )

        assert updated is False

    def test_get_history_for_llm_raises_on_db_failure(self, monkeypatch):
        from app.db.repositories import chat_repository

        monkeypatch.setattr(chat_repository, "read_session_scope", lambda: _BrokenSessionScope())

        with pytest.raises(RuntimeError, match="database unavailable"):
            asyncio.run(chat_repository.get_history_for_llm("user-1", "session-1"))

    def test_get_history_for_llm_empty_history_returns_empty_list(self, monkeypatch):
        from app.db.repositories import chat_repository

        monkeypatch.setattr(chat_repository, "read_session_scope", lambda: _EmptySessionScope())

        history = asyncio.run(
            chat_repository.get_history_for_llm(
                "00000000-0000-0000-0000-00000000ffff",
                "00000000-0000-0000-0000-00000000aaa1",
            )
        )

        assert history == []

    def test_send_message_does_not_call_llm_when_user_message_persistence_fails(self, monkeypatch):
        async def fake_get_engine(user_id, connection_id):
            return object()

        async def fake_get_schema_for_ai(user_id, connection_id):
            return "schema"

        async def fake_create_session(user_id, connection_id):
            return SimpleNamespace(id="session-1")

        async def fake_noop(*args, **kwargs):
            return True

        async def fake_record_user_turn(user_id, session_id, connection_id, message):
            raise RuntimeError("write failed")

        async def fake_prepare_chat_intent(**kwargs):
            return SimpleNamespace(intent=SimpleNamespace(decision="analyze"), history=[])

        monkeypatch.setattr(chat_service.connection_service, "get_engine", fake_get_engine)
        monkeypatch.setattr(chat_service.connection_service, "get_schema_for_ai", fake_get_schema_for_ai)
        monkeypatch.setattr(chat_service, "create_session", fake_create_session)
        monkeypatch.setattr(chat_service, "rename_session", fake_noop)
        monkeypatch.setattr(chat_service, "record_user_turn", fake_record_user_turn)
        monkeypatch.setattr(chat_service, "prepare_chat_intent", fake_prepare_chat_intent)
        analysis_mock = AsyncMock(side_effect=AssertionError("LLM should not run"))
        monkeypatch.setattr(chat_service.analysis_service, "run_analysis", analysis_mock)

        with pytest.raises(chat_service.ChatPersistenceError):
            asyncio.run(chat_service.send_message("user-1", "connection-1", "show rows"))

        assert analysis_mock.await_count == 0

    def test_send_message_fails_if_assistant_message_persistence_fails_after_llm(self, monkeypatch):
        add_calls = 0

        async def fake_get_engine(user_id, connection_id):
            return object()

        async def fake_get_schema_for_ai(user_id, connection_id):
            return "schema"

        async def fake_create_session(user_id, connection_id):
            return SimpleNamespace(id="session-1")

        async def fake_noop(*args, **kwargs):
            return True

        async def fake_record_user_turn(user_id, session_id, connection_id, message):
            user_msg = ChatMessage(role="user", content=message, connection_id=connection_id)
            return user_msg, None, []

        async def fake_add_message(*args, **kwargs):
            nonlocal add_calls
            add_calls += 1
            raise RuntimeError("assistant write failed")

        async def fake_prepare_chat_intent(**kwargs):
            return SimpleNamespace(intent=SimpleNamespace(decision="analyze"), history=[])

        monkeypatch.setattr(chat_service.connection_service, "get_engine", fake_get_engine)
        monkeypatch.setattr(chat_service.connection_service, "get_schema_for_ai", fake_get_schema_for_ai)
        monkeypatch.setattr(chat_service, "create_session", fake_create_session)
        monkeypatch.setattr(chat_service, "rename_session", fake_noop)
        monkeypatch.setattr(chat_service, "record_user_turn", fake_record_user_turn)
        monkeypatch.setattr(chat_service, "add_message", fake_add_message)
        monkeypatch.setattr(chat_service, "prepare_chat_intent", fake_prepare_chat_intent)
        monkeypatch.setattr(
            chat_service.analysis_service,
            "run_analysis",
            AsyncMock(
                return_value={
                    "explanation": "done",
                    "sql": "SELECT 1",
                    "columns": ["id"],
                    "rows": [{"id": 1}],
                    "row_count": 1,
                    "execution_time_ms": 1.0,
                    "truncated": False,
                }
            ),
        )

        with pytest.raises(chat_service.ChatPersistenceError):
            asyncio.run(chat_service.send_message("user-1", "connection-1", "show rows"))

        assert add_calls == 1
# ---------------------------------------------------------------------------
# edit-SQL preflight validation
# ---------------------------------------------------------------------------

class TestEditSqlPreflight:
    def test_missing_session_does_not_execute(self, monkeypatch):
        executed = False

        async def fake_get_session(user_id, session_id):
            return None

        async def fake_execute_for_connection(*args, **kwargs):
            nonlocal executed
            executed = True

        monkeypatch.setattr(chat_service, "get_session", fake_get_session)
        monkeypatch.setattr(chat_service.query_execution_service, "execute_for_connection", fake_execute_for_connection)

        with pytest.raises(chat_service.ChatEditNotFoundError):
            asyncio.run(chat_service.edit_message_sql("user-1", "missing", "msg-1", "SELECT 1", "conn-1"))

        assert executed is False

    def test_missing_message_does_not_execute(self, monkeypatch):
        executed = False

        async def fake_get_session(user_id, session_id):
            return SimpleNamespace(id=session_id)

        async def fake_get_message(user_id, session_id, message_id):
            return None

        async def fake_execute_for_connection(*args, **kwargs):
            nonlocal executed
            executed = True

        monkeypatch.setattr(chat_service, "get_session", fake_get_session)
        monkeypatch.setattr(chat_service, "get_message", fake_get_message)
        monkeypatch.setattr(chat_service.query_execution_service, "execute_for_connection", fake_execute_for_connection)

        with pytest.raises(chat_service.ChatEditNotFoundError):
            asyncio.run(chat_service.edit_message_sql("user-1", "session-1", "missing", "SELECT 1", "conn-1"))

        assert executed is False

    def test_user_message_target_does_not_execute(self, monkeypatch):
        executed = False

        async def fake_get_session(user_id, session_id):
            return SimpleNamespace(id=session_id)

        async def fake_get_message(user_id, session_id, message_id):
            return SimpleNamespace(role="user", sql=None)

        async def fake_execute_for_connection(*args, **kwargs):
            nonlocal executed
            executed = True

        monkeypatch.setattr(chat_service, "get_session", fake_get_session)
        monkeypatch.setattr(chat_service, "get_message", fake_get_message)
        monkeypatch.setattr(chat_service.query_execution_service, "execute_for_connection", fake_execute_for_connection)

        with pytest.raises(chat_service.ChatEditValidationError):
            asyncio.run(chat_service.edit_message_sql("user-1", "session-1", "msg-1", "SELECT 1", "conn-1"))

        assert executed is False

    def test_assistant_without_sql_does_not_execute(self, monkeypatch):
        executed = False

        async def fake_get_session(user_id, session_id):
            return SimpleNamespace(id=session_id)

        async def fake_get_message(user_id, session_id, message_id):
            return SimpleNamespace(role="assistant", sql=None)

        async def fake_execute_for_connection(*args, **kwargs):
            nonlocal executed
            executed = True

        monkeypatch.setattr(chat_service, "get_session", fake_get_session)
        monkeypatch.setattr(chat_service, "get_message", fake_get_message)
        monkeypatch.setattr(chat_service.query_execution_service, "execute_for_connection", fake_execute_for_connection)

        with pytest.raises(chat_service.ChatEditValidationError):
            asyncio.run(chat_service.edit_message_sql("user-1", "session-1", "msg-1", "SELECT 1", "conn-1"))

        assert executed is False

    def test_missing_connection_does_not_execute(self, monkeypatch):
        executed = False

        async def fake_get_session(user_id, session_id):
            return SimpleNamespace(id=session_id)

        async def fake_get_message(user_id, session_id, message_id):
            return SimpleNamespace(role="assistant", sql="SELECT 1")

        async def fake_get_engine(user_id, connection_id):
            return None

        async def fake_execute_for_connection(*args, **kwargs):
            nonlocal executed
            executed = True

        monkeypatch.setattr(chat_service, "get_session", fake_get_session)
        monkeypatch.setattr(chat_service, "get_message", fake_get_message)
        monkeypatch.setattr(chat_service.connection_service, "get_engine", fake_get_engine)
        monkeypatch.setattr(chat_service.query_execution_service, "execute_for_connection", fake_execute_for_connection)

        with pytest.raises(chat_service.ChatEditNotFoundError):
            asyncio.run(chat_service.edit_message_sql("user-1", "session-1", "msg-1", "SELECT 1", "missing"))

        assert executed is False

    def test_valid_message_executes_and_updates(self, monkeypatch):
        updates = []

        async def fake_get_session(user_id, session_id):
            return SimpleNamespace(id=session_id)

        async def fake_get_message(user_id, session_id, message_id):
            return SimpleNamespace(role="assistant", sql="SELECT 1")

        async def fake_get_engine(user_id, connection_id):
            return object()

        async def fake_execute_for_connection(*args, **kwargs):
            return SimpleNamespace(
                success=True,
                rows=[],
                columns=["id"],
                row_count=0,
                execution_time_ms=4.5,
                truncated=False,
                error=None,
            )

        async def fake_get_history_for_llm(user_id, session_id):
            return []

        async def fake_update_message(user_id, session_id, message_id, update):
            updates.append(update)
            return True

        monkeypatch.setattr(chat_service, "get_session", fake_get_session)
        monkeypatch.setattr(chat_service, "get_message", fake_get_message)
        monkeypatch.setattr(chat_service.connection_service, "get_engine", fake_get_engine)
        monkeypatch.setattr(chat_service.query_execution_service, "execute_for_connection", fake_execute_for_connection)
        monkeypatch.setattr(chat_service, "get_history_for_llm", fake_get_history_for_llm)
        monkeypatch.setattr(chat_service, "update_message", fake_update_message)

        response = asyncio.run(chat_service.edit_message_sql("user-1", "session-1", "msg-1", "SELECT 2", "conn-1"))

        assert response.sql == "SELECT 2"
        assert response.columns == ["id"]
        assert updates[0]["results"]["execution_time_ms"] == 4.5
        assert updates[0]["results"]["truncated"] is False

    def test_failed_post_execution_update_raises_service_failure(self, monkeypatch):
        async def fake_get_session(user_id, session_id):
            return SimpleNamespace(id=session_id)

        async def fake_get_message(user_id, session_id, message_id):
            return SimpleNamespace(role="assistant", sql="SELECT 1")

        async def fake_get_engine(user_id, connection_id):
            return object()

        async def fake_execute_for_connection(*args, **kwargs):
            return SimpleNamespace(
                success=True,
                rows=[],
                columns=["id"],
                row_count=0,
                execution_time_ms=4.5,
                truncated=False,
                error=None,
            )

        async def fake_get_history_for_llm(user_id, session_id):
            return []

        async def fake_update_message(user_id, session_id, message_id, update):
            return False

        monkeypatch.setattr(chat_service, "get_session", fake_get_session)
        monkeypatch.setattr(chat_service, "get_message", fake_get_message)
        monkeypatch.setattr(chat_service.connection_service, "get_engine", fake_get_engine)
        monkeypatch.setattr(chat_service.query_execution_service, "execute_for_connection", fake_execute_for_connection)
        monkeypatch.setattr(chat_service, "get_history_for_llm", fake_get_history_for_llm)
        monkeypatch.setattr(chat_service, "update_message", fake_update_message)

        with pytest.raises(chat_service.ChatPersistenceError):
            asyncio.run(chat_service.edit_message_sql("user-1", "session-1", "msg-1", "SELECT 2", "conn-1"))
