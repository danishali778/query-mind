from dataclasses import dataclass
from datetime import datetime, timezone
import json

from jose import jwk, jwt
from jose.exceptions import JOSEError, JWKError, JWTClaimsError, JWTError

from app.core.config import settings


MAX_SESSION_ID_LENGTH = 255


class JwtConfigurationError(ValueError):
    """Raised when trusted server-side JWT verification material is invalid."""


@dataclass(frozen=True)
class SupabaseJwtClaims:
    owner_id: str
    session_id: str
    expires_at: datetime
    email: str | None


def get_jwt_verification_config() -> tuple[object, str]:
    secret = settings.supabase_jwt_secret
    if not secret or not secret.strip():
        raise JwtConfigurationError("SUPABASE_JWT_SECRET is not configured")

    trimmed = secret.strip()
    if trimmed.startswith(("{", "[")):
        try:
            parsed = json.loads(trimmed)
        except json.JSONDecodeError as exc:
            raise JwtConfigurationError("SUPABASE_JWT_SECRET contains malformed JWK JSON") from exc
        if not isinstance(parsed, dict):
            raise JwtConfigurationError("SUPABASE_JWT_SECRET JWK must be a JSON object")
        if parsed.get("kty") != "EC" or parsed.get("crv") != "P-256":
            raise JwtConfigurationError("Only an EC P-256 Supabase JWK is supported")
        if parsed.get("d"):
            raise JwtConfigurationError("SUPABASE_JWT_SECRET must not contain private EC key material")
        if not isinstance(parsed.get("x"), str) or not isinstance(parsed.get("y"), str):
            raise JwtConfigurationError("Supabase EC JWK must contain public x and y coordinates")
        return parsed, "ES256"

    if "-----BEGIN" in trimmed.upper():
        raise JwtConfigurationError("PEM key material is not accepted as an HMAC secret")
    return trimmed, "HS256"


def get_jwt_key() -> object:
    key, _algorithm = get_jwt_verification_config()
    return key


def validate_jwt_configuration() -> None:
    if settings.mock_auth_enabled:
        return
    key, algorithm = get_jwt_verification_config()
    try:
        jwk.construct(key, algorithm)
    except JOSEError as exc:
        raise JwtConfigurationError("Supabase JWT verification key is invalid") from exc


def get_jwt_issuer() -> str:
    return f"{settings.require('supabase_url').rstrip('/')}/auth/v1"


def claims_from_payload(payload: dict) -> SupabaseJwtClaims:
    owner_id = payload.get("sub")
    session_id = payload.get("session_id")
    expires_at_value = payload.get("exp")
    email = payload.get("email")

    if not isinstance(owner_id, str) or not owner_id.strip():
        raise JWTClaimsError("Missing or invalid subject claim")
    if (
        not isinstance(session_id, str)
        or not session_id.strip()
        or len(session_id) > MAX_SESSION_ID_LENGTH
        or any(ord(character) < 32 or ord(character) == 127 for character in session_id)
    ):
        raise JWTClaimsError("Missing or invalid session claim")
    if isinstance(expires_at_value, bool) or not isinstance(expires_at_value, (int, float)):
        raise JWTClaimsError("Missing or invalid expiration claim")

    try:
        expires_at = datetime.fromtimestamp(expires_at_value, tz=timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise JWTClaimsError("Missing or invalid expiration claim") from exc
    if expires_at <= datetime.now(timezone.utc):
        raise JWTClaimsError("Token has expired")
    return SupabaseJwtClaims(
        owner_id=owner_id.strip(),
        session_id=session_id.strip(),
        expires_at=expires_at,
        email=email if isinstance(email, str) else None,
    )


def decode_supabase_jwt(token: str) -> dict:
    key, algorithm = get_jwt_verification_config()
    payload = jwt.decode(
        token,
        key,
        algorithms=[algorithm],
        audience="authenticated",
        issuer=get_jwt_issuer(),
        options={"require_exp": True, "require_sub": True, "require_aud": True, "require_iss": True},
    )
    claims_from_payload(payload)
    return payload


__all__ = [
    "JOSEError",
    "JWKError",
    "JWTError",
    "JwtConfigurationError",
    "SupabaseJwtClaims",
    "claims_from_payload",
    "decode_supabase_jwt",
    "get_jwt_key",
    "get_jwt_issuer",
    "get_jwt_verification_config",
    "validate_jwt_configuration",
]
