from functools import lru_cache
from pathlib import Path

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

    encryption_key: str | None = None

    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    supabase_jwt_secret: str | None = None

    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"

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
            "has_encryption_key": bool(self.encryption_key),
            "has_supabase_url": bool(self.supabase_url),
            "has_supabase_anon_key": bool(self.supabase_anon_key),
            "has_supabase_service_role_key": bool(self.supabase_service_role_key),
            "has_supabase_jwt_secret": bool(self.supabase_jwt_secret),
            "has_groq_api_key": bool(self.groq_api_key),
            "groq_model": self.groq_model,
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
