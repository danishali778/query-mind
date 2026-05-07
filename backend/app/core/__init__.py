"""Core application configuration and startup utilities."""

from app.core.config import Settings, get_settings, settings
from app.core.errors import register_exception_handlers
from app.core.middleware import configure_cors
from app.core.secrets import (
    get_encryption_key,
    require_groq_api_key,
    require_lemon_squeezy_webhook_secret,
    require_supabase_service_role_key,
    require_supabase_url,
    validate_core_credentials,
)
from app.core.security import decrypt, encrypt

__all__ = [
    "Settings",
    "settings",
    "get_settings",
    "register_exception_handlers",
    "configure_cors",
    "get_encryption_key",
    "require_groq_api_key",
    "require_lemon_squeezy_webhook_secret",
    "require_supabase_url",
    "require_supabase_service_role_key",
    "validate_core_credentials",
    "encrypt",
    "decrypt",
]
