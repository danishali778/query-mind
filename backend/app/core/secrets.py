"""Secret access and validation helpers."""

from app.core.config import settings


def get_encryption_key() -> str:
    """Return the configured Fernet key."""
    return settings.require("encryption_key")


def require_groq_api_key() -> str:
    return settings.require("groq_api_key")


def require_lemon_squeezy_webhook_secret() -> str:
    return settings.require("lemon_squeezy_webhook_secret")


def require_supabase_url() -> str:
    return settings.require("supabase_url")


def require_supabase_service_role_key() -> str:
    return settings.require("supabase_service_role_key")


def validate_core_credentials() -> None:
    """Fail fast when required core runtime credentials are missing."""
    required = [
        "encryption_key",
        "supabase_url",
        "supabase_service_role_key",
        "supabase_jwt_secret",
        "groq_api_key",
    ]
    missing = [name for name in required if not getattr(settings, name)]
    if missing:
        raise RuntimeError(f"Missing required configuration values: {', '.join(missing)}")


__all__ = [
    "get_encryption_key",
    "require_groq_api_key",
    "require_lemon_squeezy_webhook_secret",
    "require_supabase_url",
    "require_supabase_service_role_key",
    "validate_core_credentials",
]
