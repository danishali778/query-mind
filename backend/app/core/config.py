from functools import lru_cache
import ipaddress
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    allowed_origins_raw: str = Field(
        default="http://localhost:5173,http://localhost:3000",
        validation_alias="ALLOWED_ORIGINS",
    )

    database_url: str | None = None
    app_database_url: str | None = None

    redis_url: str | None = None
    celery_broker_url: str | None = None
    celery_default_queue: str = "default"
    celery_scheduled_queue: str = "scheduled"
    celery_templates_queue: str = "templates"
    celery_dispatch_lock_seconds: int = 900
    celery_worker_concurrency: int = 4

    db_connect_timeout_seconds: int = 5
    db_connect_rate_limit_attempts: int = 10
    db_connect_rate_limit_window_seconds: int = 60
    db_connect_allowed_hosts_raw: str = Field(default="", validation_alias="DB_CONNECT_ALLOWED_HOSTS")
    db_connect_allowed_cidrs_raw: str = Field(default="", validation_alias="DB_CONNECT_ALLOWED_CIDRS")
    db_connect_allow_private_in_dev: bool = True

    encryption_key: str | None = None

    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    supabase_jwt_secret: str | None = None
    auth_cookie_secure: bool | None = None
    auth_cookie_domain: str | None = None
    auth_cookie_samesite: str = "lax"
    auth_rate_limit_attempts: int = 5
    auth_rate_limit_window_seconds: int = 900
    trusted_proxy_cidrs_raw: str = Field(default="", validation_alias="TRUSTED_PROXY_CIDRS")

    llm_provider: str = "groq"
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    google_api_key: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"

    agent_mode: str = "pipeline"
    agent_model: str | None = None
    agent_max_tool_calls: int = 20
    agent_wall_clock_seconds: int = 120
    agent_preview_rows: int = 20
    agent_max_tables_per_call: int = 5
    agent_tool_output_chars: int = 12000
    agent_max_tables_listed: int = 100
    agent_max_columns_per_table: int = 80
    agent_max_cell_chars: int = 500
    agent_compaction_token_threshold: int = 6000
    agent_max_live_queries: int = 10
    agent_max_notes: int = 20
    agent_query_timeout_seconds: int = 10
    agent_profile_max_columns: int = 15
    agent_profile_row_estimate_cap: int = 5_000_000
    catalog_excluded_schemas_raw: str = Field(
        default="",
        validation_alias="CATALOG_EXCLUDED_SCHEMAS",
    )

    lemon_squeezy_webhook_secret: str | None = None
    lemon_squeezy_api_key: str | None = None

    backend_dev_mode: bool = False
    dev_user_id: str = "00000000-0000-0000-0000-000000000000"
    dev_user_email: str = "dev@query-mind.com"

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins_raw.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    @property
    def mock_auth_enabled(self) -> bool:
        return self.backend_dev_mode and not self.supabase_jwt_secret

    @property
    def resolved_redis_url(self) -> str | None:
        return self.redis_url or self.celery_broker_url

    @property
    def resolved_celery_broker_url(self) -> str | None:
        return self.celery_broker_url or self.redis_url

    @property
    def db_connect_allowed_hosts(self) -> list[str]:
        return [host.strip() for host in self.db_connect_allowed_hosts_raw.split(",") if host.strip()]

    @property
    def db_connect_allowed_cidrs(self) -> list[str]:
        return [cidr.strip() for cidr in self.db_connect_allowed_cidrs_raw.split(",") if cidr.strip()]

    @property
    def trusted_proxy_cidrs(self) -> list[str]:
        return [cidr.strip() for cidr in self.trusted_proxy_cidrs_raw.split(",") if cidr.strip()]

    @property
    def resolved_auth_cookie_secure(self) -> bool:
        if self.auth_cookie_secure is None:
            return self.is_production
        return self.auth_cookie_secure

    def validate_security_configuration(self) -> None:
        samesite = self.auth_cookie_samesite.strip().lower()
        if samesite not in {"lax", "strict", "none"}:
            raise RuntimeError("AUTH_COOKIE_SAMESITE must be one of: lax, strict, none.")

        if self.auth_rate_limit_attempts < 1 or self.auth_rate_limit_window_seconds < 1:
            raise RuntimeError("Authentication rate-limit settings must be positive.")

        for cidr in self.trusted_proxy_cidrs:
            try:
                ipaddress.ip_network(cidr, strict=False)
            except ValueError as exc:
                raise RuntimeError(f"Invalid TRUSTED_PROXY_CIDRS entry: {cidr}") from exc

        if not self.is_production:
            return

        if self.backend_dev_mode:
            raise RuntimeError("BACKEND_DEV_MODE cannot be enabled in production.")
        if not self.supabase_jwt_secret:
            raise RuntimeError("SUPABASE_JWT_SECRET is required in production.")
        if not self.resolved_auth_cookie_secure:
            raise RuntimeError("AUTH_COOKIE_SECURE cannot be disabled in production.")
        if samesite == "none":
            raise RuntimeError("AUTH_COOKIE_SAMESITE=none is not supported in production.")

        origins = self.allowed_origins
        if not origins:
            raise RuntimeError("ALLOWED_ORIGINS must contain at least one HTTPS origin in production.")
        for origin in origins:
            parsed = urlparse(origin)
            host = parsed.hostname
            if origin == "*" or parsed.scheme != "https" or not host:
                raise RuntimeError("ALLOWED_ORIGINS must contain only explicit HTTPS origins in production.")
            if host.lower() == "localhost":
                raise RuntimeError("ALLOWED_ORIGINS cannot include loopback origins in production.")
            try:
                if ipaddress.ip_address(host).is_loopback:
                    raise RuntimeError("ALLOWED_ORIGINS cannot include loopback origins in production.")
            except ValueError:
                pass

    @property
    def resolved_google_api_key(self) -> str | None:
        return self.google_api_key or self.gemini_api_key

    @property
    def resolved_llm_provider(self) -> str:
        provider = (self.llm_provider or "groq").strip().lower()
        if provider == "gemini":
            return "gemini"
        if self.groq_api_key:
            return "groq"
        if self.resolved_google_api_key:
            return "gemini"
        return "groq"

    @property
    def resolved_llm_model(self) -> str:
        if self.agent_model:
            return self.agent_model
        if self.resolved_llm_provider == "gemini":
            return self.gemini_model
        return self.groq_model

    @property
    def resolved_agent_model(self) -> str:
        return self.resolved_llm_model

    @property
    def catalog_excluded_schemas_extra(self) -> list[str]:
        return [name.strip() for name in self.catalog_excluded_schemas_raw.split(",") if name.strip()]

    def require(self, field_name: str) -> str:
        value = getattr(self, field_name)
        if not value:
            raise RuntimeError(f"Required configuration value is missing: {field_name}")
        return value

    def redacted_summary(self) -> dict[str, object]:
        """Return non-secret startup config for diagnostics."""
        return {
            "app_env": self.app_env,
            "app_host": self.app_host,
            "app_port": self.app_port,
            "allowed_origins": self.allowed_origins,
            "backend_dev_mode": self.backend_dev_mode,
            "has_database_url": bool(self.database_url),
            "has_app_database_url": bool(self.app_database_url),
            "has_redis_url": bool(self.redis_url),
            "has_celery_broker_url": bool(self.celery_broker_url),
            "celery_default_queue": self.celery_default_queue,
            "celery_scheduled_queue": self.celery_scheduled_queue,
            "celery_templates_queue": self.celery_templates_queue,
            "db_connect_timeout_seconds": self.db_connect_timeout_seconds,
            "db_connect_rate_limit_attempts": self.db_connect_rate_limit_attempts,
            "db_connect_rate_limit_window_seconds": self.db_connect_rate_limit_window_seconds,
            "db_connect_allowed_hosts_count": len(self.db_connect_allowed_hosts),
            "db_connect_allowed_cidrs_count": len(self.db_connect_allowed_cidrs),
            "db_connect_allow_private_in_dev": self.db_connect_allow_private_in_dev,
            "has_encryption_key": bool(self.encryption_key),
            "has_supabase_url": bool(self.supabase_url),
            "has_supabase_anon_key": bool(self.supabase_anon_key),
            "has_supabase_service_role_key": bool(self.supabase_service_role_key),
            "has_supabase_jwt_secret": bool(self.supabase_jwt_secret),
            "auth_cookie_secure": self.resolved_auth_cookie_secure,
            "auth_cookie_domain": bool(self.auth_cookie_domain),
            "auth_cookie_samesite": self.auth_cookie_samesite,
            "auth_rate_limit_attempts": self.auth_rate_limit_attempts,
            "auth_rate_limit_window_seconds": self.auth_rate_limit_window_seconds,
            "trusted_proxy_cidrs_count": len(self.trusted_proxy_cidrs),
            "llm_provider": self.resolved_llm_provider,
            "has_groq_api_key": bool(self.groq_api_key),
            "has_google_api_key": bool(self.resolved_google_api_key),
            "groq_model": self.groq_model,
            "gemini_model": self.gemini_model,
            "resolved_llm_model": self.resolved_llm_model,
            "agent_mode": self.agent_mode,
            "agent_model": self.resolved_agent_model,
            "agent_max_tool_calls": self.agent_max_tool_calls,
            "agent_wall_clock_seconds": self.agent_wall_clock_seconds,
            "agent_tool_output_chars": self.agent_tool_output_chars,
            "agent_max_tables_listed": self.agent_max_tables_listed,
            "agent_max_columns_per_table": self.agent_max_columns_per_table,
            "agent_max_cell_chars": self.agent_max_cell_chars,
            "agent_compaction_token_threshold": self.agent_compaction_token_threshold,
            "agent_max_live_queries": self.agent_max_live_queries,
            "agent_max_notes": self.agent_max_notes,
            "agent_query_timeout_seconds": self.agent_query_timeout_seconds,
            "has_lemon_squeezy_webhook_secret": bool(self.lemon_squeezy_webhook_secret),
            "has_lemon_squeezy_api_key": bool(self.lemon_squeezy_api_key),
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# Compatibility constants for the existing code while the refactor is gradual.
APP_HOST = settings.app_host
APP_PORT = settings.app_port
ALLOWED_ORIGINS = settings.allowed_origins
