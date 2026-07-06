"""Secret access and validation helpers."""

from app.core.config import settings


def get_encryption_key() -> str:
    """Return the configured Fernet key."""
    return settings.require("encryption_key")


def require_groq_api_key() -> str:
    return settings.require("groq_api_key")


def require_llm_api_key() -> str:
    if settings.resolved_llm_provider == "gemini":
        key = settings.resolved_google_api_key
        if not key:
            raise RuntimeError("Required configuration value is missing: google_api_key or gemini_api_key")
        return key
    return settings.require("groq_api_key")


def require_lemon_squeezy_webhook_secret() -> str:
    return settings.require("lemon_squeezy_webhook_secret")


def require_app_database_url() -> str:
    return settings.require("app_database_url")


def validate_core_credentials() -> None:
    """Fail fast when required core runtime credentials are missing."""
    missing: list[str] = []

    for name in ("encryption_key", "app_database_url"):
        if not getattr(settings, name, None):
            missing.append(name)

    if settings.resolved_llm_provider == "gemini":
        if not settings.resolved_google_api_key:
            missing.append("google_api_key or gemini_api_key")
    elif not settings.groq_api_key:
        missing.append("groq_api_key")

    if not settings.mock_auth_enabled:
        for name in ("supabase_url", "supabase_anon_key", "supabase_jwt_secret"):
            if not getattr(settings, name, None):
                missing.append(name)

    if missing:
        raise RuntimeError(f"Missing required configuration values: {', '.join(missing)}")


__all__ = [
    "get_encryption_key",
    "require_groq_api_key",
    "require_llm_api_key",
    "require_lemon_squeezy_webhook_secret",
    "require_app_database_url",
    "validate_core_credentials",
]
