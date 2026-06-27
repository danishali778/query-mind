"""Core application configuration and startup utilities."""

from app.core.config import Settings, get_settings, settings
from app.core.errors import register_exception_handlers
from app.core.middleware import configure_cors
from app.core.secrets import (
    get_encryption_key,
    require_app_database_url,
    require_groq_api_key,
    require_lemon_squeezy_webhook_secret,
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
    "require_app_database_url",
    "require_groq_api_key",
    "require_lemon_squeezy_webhook_secret",
    "validate_core_credentials",
    "encrypt",
    "decrypt",
]