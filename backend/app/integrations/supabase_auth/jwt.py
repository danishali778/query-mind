import json
import logging

from jose import JWTError, jwt

from app.core.config import settings


logger = logging.getLogger(__name__)


def get_jwt_key() -> object:
    secret = settings.supabase_jwt_secret
    if not secret:
        raise ValueError("SUPABASE_JWT_SECRET is not configured")

    trimmed_secret = secret.strip()
    if trimmed_secret.startswith("{") and trimmed_secret.endswith("}"):
        try:
            return json.loads(trimmed_secret)
        except json.JSONDecodeError:
            logger.warning("SUPABASE_JWT_SECRET looked like JSON but could not be parsed.")

    return secret


def get_jwt_issuer() -> str:
    return f"{settings.require('supabase_url').rstrip('/')}/auth/v1"


def decode_supabase_jwt(token: str) -> dict:
    return jwt.decode(
        token,
        get_jwt_key(),
        algorithms=["HS256", "ES256"],
        audience="authenticated",
        issuer=get_jwt_issuer(),
    )


__all__ = ["JWTError", "decode_supabase_jwt", "get_jwt_key", "get_jwt_issuer"]
