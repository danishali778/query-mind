from functools import lru_cache
import ipaddress
import uuid
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
    celery_interactive_queue: str = "interactive"
    celery_dashboards_queue: str = "dashboards"
    celery_dispatch_lock_seconds: int = 900
    celery_worker_concurrency: int = 4
    chat_streaming_enabled: bool = True
    chat_run_event_ttl_seconds: int = 3600
    chat_run_event_maxlen: int = 500
    chat_run_heartbeat_seconds: int = 15
    chat_run_max_active_per_user: int = 3
    dashboard_ai_enabled: bool = True
    dashboard_ai_max_widgets: int = 8
    dashboard_ai_default_widgets: int = 6
    dashboard_ai_max_active_per_user: int = 1
    dashboard_ai_max_prompt_chars: int = 2048
    dashboard_run_event_ttl_seconds: int = 3600
    dashboard_run_event_maxlen: int = 500
    dashboard_run_heartbeat_seconds: int = 15
    semantic_layer_enabled: bool = True
    semantic_suggestions_enabled: bool = True
    semantic_context_max_definitions: int = Field(default=20, ge=1, le=100)
    semantic_context_max_characters: int = Field(default=12000, ge=1000, le=50000)
    semantic_preview_timeout_seconds: int = Field(default=5, ge=1, le=30)
    semantic_relationship_sample_limit: int = Field(default=1000, ge=100, le=5000)
    semantic_suggestion_max_candidates: int = Field(default=25, ge=1, le=100)
    celery_semantics_queue: str = "semantics"
    question_suggestions_enabled: bool = True
    question_suggestions_ai_enabled: bool = True
    question_suggestions_max_context_characters: int = Field(
        default=12000, ge=1000, le=50000
    )
    question_suggestions_max_per_surface: int = Field(default=8, ge=1, le=20)
    question_suggestions_refresh_cooldown_seconds: int = Field(
        default=60, ge=1, le=3600
    )
    question_suggestions_stale_run_seconds: int = Field(
        default=300, ge=30, le=3600
    )
    celery_suggestions_queue: str = "suggestions"

    db_connect_timeout_seconds: int = 5
    db_connect_rate_limit_attempts: int = 10
    db_connect_rate_limit_window_seconds: int = 60
    db_connect_allowed_hosts_raw: str = Field(default="", validation_alias="DB_CONNECT_ALLOWED_HOSTS")
    db_connect_allowed_cidrs_raw: str = Field(default="", validation_alias="DB_CONNECT_ALLOWED_CIDRS")
    db_connect_allow_private_in_dev: bool = True
    connection_health_retention_days: int = Field(default=90, ge=1, le=3650)
    connection_maintenance_batch_size: int = Field(default=100, ge=1, le=1000)
    connection_scope_cache_ttl_seconds: int = Field(default=60, ge=1, le=3600)
    connection_diagnostic_max_objects: int = Field(default=5000, ge=1, le=50000)
    connection_tls_cert_max_bytes: int = Field(default=65536, ge=1024, le=1048576)

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
    auth_signup_password_min_length: int = Field(default=12, ge=8, le=128)
    auth_password_max_length: int = Field(default=1024, ge=64, le=8192)
    auth_revoked_session_retention_grace_seconds: int = Field(default=300, ge=0, le=86400)
    # TTL for caching the per-request "user exists and is active" check.
    # 0 disables the cache; a deactivated user may retain access for up to this long.
    auth_user_cache_ttl_seconds: int = Field(default=60, ge=0, le=300)
    trusted_proxy_cidrs_raw: str = Field(default="", validation_alias="TRUSTED_PROXY_CIDRS")

    # App-owned database pool limits. Read and write engines are separate;
    # these defaults preserve SQLAlchemy's former combined ceiling of 15.
    app_db_write_pool_size: int = Field(default=5, ge=1, le=20)
    app_db_write_max_overflow: int = Field(default=5, ge=0, le=20)
    app_db_read_pool_size: int = Field(default=5, ge=1, le=20)
    app_db_read_max_overflow: int = Field(default=0, ge=0, le=20)
    app_db_pool_timeout_seconds: int = Field(default=30, ge=1, le=120)

    llm_provider: str = "groq"
    llm_credential_mode: str = "hybrid"
    llm_credential_validation_timeout_seconds: int = Field(default=10, ge=1, le=60)
    llm_credential_validation_rate_limit_attempts: int = Field(default=10, ge=1, le=1000)
    llm_credential_validation_rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    llm_credential_max_bytes: int = Field(default=8192, ge=64, le=65536)
    llm_usage_retention_days: int = Field(default=90, ge=1, le=3650)
    deployment_llm_trial_call_limit: int = Field(default=10, ge=0, le=100000)
    deployment_llm_privileged_user_ids_raw: str = Field(
        default="", validation_alias="DEPLOYMENT_LLM_PRIVILEGED_USER_IDS"
    )
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    groq_allowed_models_raw: str = Field(
        default="llama-3.3-70b-versatile", validation_alias="GROQ_ALLOWED_MODELS"
    )
    google_api_key: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    gemini_allowed_models_raw: str = Field(
        default="gemini-2.0-flash", validation_alias="GEMINI_ALLOWED_MODELS"
    )
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    openai_allowed_models_raw: str = Field(
        default="gpt-5-mini,gpt-4.1-mini", validation_alias="OPENAI_ALLOWED_MODELS"
    )

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
    agent_max_analysis_queries: int = 3
    agent_result_preview_rows: int = 50
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
        if self.auth_signup_password_min_length > self.auth_password_max_length:
            raise RuntimeError(
                "AUTH_SIGNUP_PASSWORD_MIN_LENGTH cannot exceed AUTH_PASSWORD_MAX_LENGTH."
            )

        credential_mode = self.llm_credential_mode.strip().lower()
        if credential_mode not in {"deployment", "hybrid", "byok_required"}:
            raise RuntimeError("LLM_CREDENTIAL_MODE must be one of: deployment, hybrid, byok_required.")
        if self.resolved_llm_provider not in {"gemini", "groq", "openai"}:
            raise RuntimeError("LLM_PROVIDER must be one of: gemini, groq, openai.")
        for provider, models in self.llm_allowed_models.items():
            if not models:
                raise RuntimeError(f"At least one allowed model is required for {provider}.")
            if self.llm_default_model(provider) not in models:
                raise RuntimeError(f"The default {provider} model must be present in its allowed-model list.")
        for owner_id in self.deployment_llm_privileged_user_ids:
            try:
                uuid.UUID(owner_id)
            except ValueError as exc:
                raise RuntimeError("DEPLOYMENT_LLM_PRIVILEGED_USER_IDS must contain UUID values.") from exc

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

    @staticmethod
    def _csv_values(raw: str) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in raw.split(",") if value.strip()))

    @property
    def deployment_llm_privileged_user_ids(self) -> set[str]:
        return set(self._csv_values(self.deployment_llm_privileged_user_ids_raw))

    @property
    def llm_allowed_models(self) -> dict[str, list[str]]:
        return {
            "gemini": self._csv_values(self.gemini_allowed_models_raw),
            "groq": self._csv_values(self.groq_allowed_models_raw),
            "openai": self._csv_values(self.openai_allowed_models_raw),
        }

    def llm_default_model(self, provider: str) -> str:
        return {
            "gemini": self.gemini_model,
            "groq": self.groq_model,
            "openai": self.openai_model,
        }[provider]

    def deployment_llm_api_key(self, provider: str) -> str | None:
        return {
            "gemini": self.resolved_google_api_key,
            "groq": self.groq_api_key,
            "openai": self.openai_api_key,
        }.get(provider)

    @property
    def resolved_llm_provider(self) -> str:
        provider = (self.llm_provider or "groq").strip().lower()
        if provider in {"gemini", "groq", "openai"} and self.deployment_llm_api_key(provider):
            return provider
        if self.groq_api_key:
            return "groq"
        if self.resolved_google_api_key:
            return "gemini"
        if self.openai_api_key:
            return "openai"
        return provider if provider in {"gemini", "groq", "openai"} else "groq"

    @property
    def resolved_llm_model(self) -> str:
        if self.agent_model:
            return self.agent_model
        if self.resolved_llm_provider == "gemini":
            return self.gemini_model
        if self.resolved_llm_provider == "openai":
            return self.openai_model
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
            "celery_interactive_queue": self.celery_interactive_queue,
            "celery_dashboards_queue": self.celery_dashboards_queue,
            "chat_streaming_enabled": self.chat_streaming_enabled,
            "dashboard_ai_enabled": self.dashboard_ai_enabled,
            "semantic_layer_enabled": self.semantic_layer_enabled,
            "semantic_suggestions_enabled": self.semantic_suggestions_enabled,
            "celery_semantics_queue": self.celery_semantics_queue,
            "question_suggestions_enabled": self.question_suggestions_enabled,
            "question_suggestions_ai_enabled": self.question_suggestions_ai_enabled,
            "celery_suggestions_queue": self.celery_suggestions_queue,
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
            "auth_signup_password_min_length": self.auth_signup_password_min_length,
            "auth_password_max_length": self.auth_password_max_length,
            "auth_revoked_session_retention_grace_seconds": (
                self.auth_revoked_session_retention_grace_seconds
            ),
            "trusted_proxy_cidrs_count": len(self.trusted_proxy_cidrs),
            "llm_provider": self.resolved_llm_provider,
            "llm_credential_mode": self.llm_credential_mode,
            "deployment_llm_privileged_user_count": len(self.deployment_llm_privileged_user_ids),
            "has_groq_api_key": bool(self.groq_api_key),
            "has_google_api_key": bool(self.resolved_google_api_key),
            "has_openai_api_key": bool(self.openai_api_key),
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
            "agent_max_analysis_queries": self.agent_max_analysis_queries,
            "agent_result_preview_rows": self.agent_result_preview_rows,
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
