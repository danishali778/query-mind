import functools
import logging
from typing import Optional

import anyio
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.config import settings
from app.core import auth_metrics
from app.core.errors import ServiceUnavailableError
from app.core.supabase_auth import ACCESS_TOKEN_COOKIE_NAME
from app.db.orm_models import UserSettingsORM
from app.db.session import read_session_scope
from app.integrations.supabase_auth import user_cache
from app.integrations.supabase_auth.jwt import (
    JOSEError,
    JWTError,
    JwtConfigurationError,
    claims_from_payload,
    decode_supabase_jwt,
    get_jwt_key,
)
from app.services import auth as auth_service


logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


class User(BaseModel):
    id: str
    email: Optional[str] = None


def _load_user_active_sync(user_id: str) -> bool:
    with read_session_scope() as session:
        row = session.get(UserSettingsORM, user_id)
        return bool(row and row.is_active)


async def assert_user_exists(user_id: str) -> None:
    if await user_cache.is_user_cached_active(user_id):
        return

    try:
        exists = await anyio.to_thread.run_sync(functools.partial(_load_user_active_sync, user_id))
    except Exception as exc:
        logger.error("Authentication database error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth system infrastructure error. Please try again later.",
        ) from exc

    if not exists:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account has been deactivated or deleted.",
        )

    await user_cache.mark_user_active(user_id)


def _mock_user() -> User:
    return User(id=settings.dev_user_id, email=settings.dev_user_email)


def _authorization_token(credentials: Optional[HTTPAuthorizationCredentials]) -> str | None:
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    return None


def _request_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials],
) -> str | None:
    cookie_token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    if cookie_token:
        return cookie_token
    return _authorization_token(credentials)


async def authenticate_credentials(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials],
    verify_existence: bool = True,
) -> User:
    token = _request_token(request, credentials)

    if settings.mock_auth_enabled:
        if token is None or token == "dev-token":
            return _mock_user()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
        )

    try:
        try:
            payload = decode_supabase_jwt(token)
        except JwtConfigurationError as exc:
            raise ServiceUnavailableError("Authentication service is not configured correctly.") from exc

        claims = claims_from_payload(payload)
        revoked = await anyio.to_thread.run_sync(
            functools.partial(
                auth_service.is_session_revoked,
                claims.owner_id,
                claims.session_id,
            )
        )
        if revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )

        if verify_existence:
            await assert_user_exists(claims.owner_id)

        return User(id=claims.owner_id, email=claims.email)
    except JOSEError as exc:
        auth_metrics.increment("jwt_request_rejections")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from exc
    except ServiceUnavailableError:
        raise
    except HTTPException:
        raise
    except Exception as exc:
        auth_metrics.increment("unexpected_auth_failures")
        logger.error(
            "Unexpected auth middleware error type=%s",
            type(exc).__name__,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal authentication service error.",
        ) from exc


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> User:
    return await authenticate_credentials(request, credentials, verify_existence=True)


async def get_user_no_check(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> User:
    return await authenticate_credentials(request, credentials, verify_existence=False)


__all__ = [
    "JWTError",
    "security",
    "User",
    "get_jwt_key",
    "assert_user_exists",
    "authenticate_credentials",
    "get_current_user",
    "get_user_no_check",
]
