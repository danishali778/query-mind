from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import httpx
from fastapi import status

from app.core.errors import ServiceUnavailableError
from app.core import auth_metrics
from app.core.supabase_auth import (
    supabase_auth_headers,
    supabase_logout_url,
    supabase_password_login_url,
    supabase_refresh_url,
    supabase_signup_url,
)
from app.db.repositories import settings_repository
from app.db.repositories import auth_session_repository
from app.integrations.supabase_auth.jwt import (
    JOSEError,
    JwtConfigurationError,
    claims_from_payload,
    decode_supabase_jwt,
)
from app.services import billing_service


logger = logging.getLogger(__name__)


@dataclass
class AuthSessionResult:
    authenticated: bool
    user_id: str | None
    email: str | None
    access_token: str | None = None
    refresh_token: str | None = None
    expires_in: int | None = None
    message: str | None = None


@dataclass(frozen=True)
class LogoutResult:
    local_revocation_confirmed: bool
    remote_revocation_confirmed: bool


class AuthServiceError(Exception):
    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _extract_error_message(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ("msg", "message", "error_description", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return "Authentication request failed."


def _request_supabase(url: str, payload: dict[str, Any], *, invalid_status_code: int) -> dict[str, Any]:
    try:
        response = httpx.post(
            url,
            json=payload,
            headers=supabase_auth_headers(),
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        raise ServiceUnavailableError("Authentication service is temporarily unavailable.") from exc

    data: dict[str, Any]
    try:
        parsed = response.json()
        data = parsed if isinstance(parsed, dict) else {}
    except ValueError:
        data = {}

    if response.is_success:
        return data

    if response.status_code in {400, 401, 422}:
        raise AuthServiceError(_extract_error_message(data), status_code=invalid_status_code)

    raise ServiceUnavailableError("Authentication service is temporarily unavailable.")


def _user_details_from_payload(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    user = payload.get("user")
    if isinstance(user, dict):
        user_id = user.get("id") or user.get("sub")
        email = user.get("email")
        return str(user_id) if user_id else None, str(email) if email else None

    access_token = payload.get("access_token")
    if isinstance(access_token, str) and access_token:
        try:
            decoded = decode_supabase_jwt(access_token)
        except (JwtConfigurationError, JOSEError):
            return None, None
        user_id = decoded.get("sub")
        email = decoded.get("email")
        return str(user_id) if user_id else None, str(email) if email else None

    return None, None


def ensure_onboarded(user_id: str) -> None:
    success = billing_service.onboard_user(user_id)
    if not success:
        raise ServiceUnavailableError("Failed to initialize user session.")


def require_active_account(user_id: str) -> None:
    if not settings_repository.is_user_active(user_id):
        raise AuthServiceError("User account has been deactivated or deleted.", status_code=status.HTTP_401_UNAUTHORIZED)


def signup(email: str, password: str) -> AuthSessionResult:
    payload = _request_supabase(
        supabase_signup_url(),
        {"email": email, "password": password},
        invalid_status_code=status.HTTP_400_BAD_REQUEST,
    )
    user_id, resolved_email = _user_details_from_payload(payload)
    if user_id:
        ensure_onboarded(user_id)
        require_active_account(user_id)

    access_token = payload.get("access_token") if isinstance(payload.get("access_token"), str) else None
    refresh_token = payload.get("refresh_token") if isinstance(payload.get("refresh_token"), str) else None
    expires_in = payload.get("expires_in") if isinstance(payload.get("expires_in"), int) else None
    authenticated = bool(access_token and refresh_token)
    message = None if authenticated else "Check your email to complete sign up."
    return AuthSessionResult(
        authenticated=authenticated,
        user_id=user_id,
        email=resolved_email,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        message=message,
    )


def login(email: str, password: str) -> AuthSessionResult:
    payload = _request_supabase(
        supabase_password_login_url(),
        {"email": email, "password": password},
        invalid_status_code=status.HTTP_401_UNAUTHORIZED,
    )
    user_id, resolved_email = _user_details_from_payload(payload)
    if not user_id:
        raise ServiceUnavailableError("Authentication service returned an incomplete session.")
    require_active_account(user_id)

    access_token = payload.get("access_token") if isinstance(payload.get("access_token"), str) else None
    refresh_token = payload.get("refresh_token") if isinstance(payload.get("refresh_token"), str) else None
    expires_in = payload.get("expires_in") if isinstance(payload.get("expires_in"), int) else None
    if not access_token or not refresh_token:
        raise ServiceUnavailableError("Authentication service returned an incomplete session.")

    return AuthSessionResult(
        authenticated=True,
        user_id=user_id,
        email=resolved_email,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


def refresh_session(refresh_token: str) -> AuthSessionResult:
    payload = _request_supabase(
        supabase_refresh_url(),
        {"refresh_token": refresh_token},
        invalid_status_code=status.HTTP_401_UNAUTHORIZED,
    )
    access_token = payload.get("access_token") if isinstance(payload.get("access_token"), str) else None
    next_refresh_token = payload.get("refresh_token") if isinstance(payload.get("refresh_token"), str) else None
    expires_in = payload.get("expires_in") if isinstance(payload.get("expires_in"), int) else None
    if not access_token or not next_refresh_token:
        raise ServiceUnavailableError("Authentication service returned an incomplete session.")

    try:
        claims = claims_from_payload(decode_supabase_jwt(access_token))
    except JwtConfigurationError as exc:
        raise ServiceUnavailableError("Authentication service is not configured correctly.") from exc
    except JOSEError as exc:
        raise ServiceUnavailableError("Authentication service returned an incomplete session.") from exc

    if is_session_revoked(claims.owner_id, claims.session_id):
        raise AuthServiceError(
            "Could not validate credentials",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user_id, resolved_email = _user_details_from_payload(payload)
    if not user_id or user_id != claims.owner_id:
        raise ServiceUnavailableError("Authentication service returned an incomplete session.")
    require_active_account(user_id)

    return AuthSessionResult(
        authenticated=True,
        user_id=user_id,
        email=resolved_email,
        access_token=access_token,
        refresh_token=next_refresh_token,
        expires_in=expires_in,
    )


def is_session_revoked(owner_id: str, session_id: str) -> bool:
    try:
        return auth_session_repository.is_session_revoked(owner_id, session_id)
    except Exception as exc:
        auth_metrics.increment("revocation_lookup_failures")
        logger.error(
            "event=auth_revocation_lookup_failed owner_id=%s error_type=%s",
            owner_id,
            type(exc).__name__,
            exc_info=True,
        )
        raise ServiceUnavailableError(
            "Authentication service is temporarily unavailable.",
            code="auth_revocation_unavailable",
        ) from exc


def _remote_logout(access_token: str, *, owner_id: str, session_hash: str) -> bool:
    hash_prefix = session_hash[:12]
    try:
        response = httpx.post(
            supabase_logout_url(),
            headers=supabase_auth_headers(access_token),
            timeout=15.0,
        )
    except httpx.HTTPError:
        auth_metrics.increment("remote_logout_failures")
        logger.warning(
            "event=auth_logout_remote_revocation_failed code=network_error owner_id=%s session_hash_prefix=%s",
            owner_id,
            hash_prefix,
        )
        return False
    if not response.is_success:
        auth_metrics.increment("remote_logout_failures")
        logger.warning(
            "event=auth_logout_remote_revocation_failed code=http_error status=%s owner_id=%s session_hash_prefix=%s",
            response.status_code,
            owner_id,
            hash_prefix,
        )
        return False
    return True


def logout(access_token: str | None) -> LogoutResult:
    if not access_token:
        return LogoutResult(local_revocation_confirmed=True, remote_revocation_confirmed=True)

    try:
        payload = decode_supabase_jwt(access_token)
        claims = claims_from_payload(payload)
    except JOSEError:
        auth_metrics.increment("jwt_logout_rejections")
        return LogoutResult(local_revocation_confirmed=True, remote_revocation_confirmed=True)
    except JwtConfigurationError:
        auth_metrics.increment("jwt_configuration_failures")
        return LogoutResult(local_revocation_confirmed=False, remote_revocation_confirmed=False)

    try:
        session_hash = auth_session_repository.revoke_session(
            claims.owner_id,
            claims.session_id,
            claims.expires_at,
        )
        local_confirmed = True
    except Exception as exc:
        auth_metrics.increment("local_revocation_write_failures")
        logger.error(
            "event=auth_logout_local_revocation_failed owner_id=%s error_type=%s",
            claims.owner_id,
            type(exc).__name__,
            exc_info=True,
        )
        session_hash = auth_session_repository.hash_session_id(claims.session_id)
        local_confirmed = False

    remote_confirmed = _remote_logout(
        access_token,
        owner_id=claims.owner_id,
        session_hash=session_hash,
    )
    return LogoutResult(
        local_revocation_confirmed=local_confirmed,
        remote_revocation_confirmed=remote_confirmed,
    )


def build_active_session(user_id: str, email: str | None) -> AuthSessionResult:
    return AuthSessionResult(
        authenticated=True,
        user_id=user_id,
        email=email,
    )


__all__ = [
    "AuthServiceError",
    "AuthSessionResult",
    "LogoutResult",
    "build_active_session",
    "ensure_onboarded",
    "require_active_account",
    "login",
    "logout",
    "is_session_revoked",
    "refresh_session",
    "signup",
]
