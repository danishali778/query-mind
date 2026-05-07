"""External service integrations."""

from app.integrations.supabase_auth import (
    JWTError,
    User,
    decode_supabase_jwt,
    get_current_user,
    get_user_no_check,
)
from app.integrations.email import EmailDeliveryResult, EmailMessage, send_email
from app.integrations.groq_client import get_chat_groq, get_groq_client
from app.integrations.lemon_squeezy import (
    get_event_name,
    get_user_id,
    has_webhook_secret,
    parse_webhook_payload,
    verify_webhook_signature,
)
from app.integrations.slack import send_slack_message
from app.integrations.supabase_db import (
    SUPABASE_SERVICE_KEY,
    SUPABASE_URL,
    async_supabase,
    supabase,
)

__all__ = [
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "supabase",
    "async_supabase",
    "JWTError",
    "User",
    "decode_supabase_jwt",
    "get_current_user",
    "get_user_no_check",
    "get_groq_client",
    "get_chat_groq",
    "has_webhook_secret",
    "verify_webhook_signature",
    "parse_webhook_payload",
    "get_event_name",
    "get_user_id",
    "EmailMessage",
    "EmailDeliveryResult",
    "send_email",
    "send_slack_message",
]
