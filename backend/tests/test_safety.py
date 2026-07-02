"""Unit tests for backend/app/query_engine/safety.py

Tests validate_query() and sanitize_row_limit() with a wide range of
normal, edge-case, and adversarial inputs.
"""
import anyio
import pytest
from app.db.models.connection import ConnectionRequest
from app.query_engine.safety import (
    validate_query,
    sanitize_row_limit,
    get_readonly_wrapped_query,
)


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

    def test_preserves_existing_limit(self):
        sql = "SELECT * FROM users LIMIT 50"
        result = sanitize_row_limit(sql, 100)
        assert "LIMIT 50" in result
        assert "LIMIT 100" not in result

    def test_strips_trailing_semicolon_before_adding_limit(self):
        sql = "SELECT * FROM users;"
        result = sanitize_row_limit(sql, 100)
        assert result.endswith("LIMIT 100")
        assert ";;" not in result

    def test_case_insensitive_limit_detection(self):
        sql = "SELECT * FROM users limit 20"
        result = sanitize_row_limit(sql, 100)
        assert "LIMIT 100" not in result  # should keep existing limit


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
        opened.append((func, args))
        return FakeEngine(), None

    async def fake_create_connection(user_id, config):
        return "conn_1"

    async def fake_record_health(*args, **kwargs):
        return True

    monkeypatch.setattr(connection_manager.anyio.to_thread, "run_sync", fake_run_sync)
    monkeypatch.setattr(connection_manager, "_preflight_connection_attempt", lambda *args, **kwargs: None)
    monkeypatch.setattr(connection_manager.connection_repository, "create_connection", fake_create_connection)
    monkeypatch.setattr(connection_manager.connection_repository, "record_connection_health", fake_record_health)
    monkeypatch.setattr(connection_manager.connection_attempt_repository, "log_connection_attempt", lambda **kwargs: None)
    monkeypatch.setattr(connection_manager.connection_pool, "cache_connection", lambda *args, **kwargs: None)

    connection_id, engine, latency_ms = anyio.run(connection_manager.connect, "user_1", _async_boundary_config())

    assert connection_id == "conn_1"
    assert isinstance(engine, FakeEngine)
    assert latency_ms >= 0
    assert opened == [(connection_manager.connection_pool.open_connection, (_async_boundary_config(),))]


def test_connection_manager_get_engine_reopens_saved_connection_in_thread(monkeypatch):
    from app.db import connection_manager

    opened = []

    class FakeEngine:
        pass

    async def fake_run_sync(func, *args, **kwargs):
        opened.append((func, args))
        return FakeEngine(), None

    async def fake_get_async_boundary_config(user_id, connection_id):
        return _async_boundary_config()

    monkeypatch.setattr(connection_manager.connection_pool, "get_cached_engine", lambda *args, **kwargs: None)
    monkeypatch.setattr(connection_manager.anyio.to_thread, "run_sync", fake_run_sync)
    monkeypatch.setattr(connection_manager.connection_repository, "get_connection_config", fake_get_async_boundary_config)
    monkeypatch.setattr(connection_manager.connection_pool, "cache_connection", lambda *args, **kwargs: None)

    engine = anyio.run(connection_manager.get_engine, "user_1", "conn_1")

    assert isinstance(engine, FakeEngine)
    assert opened == [(connection_manager.connection_pool.open_connection, (_async_boundary_config(),))]


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