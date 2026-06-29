import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.config import settings
from app.core.errors import ServiceUnavailableError
from app.core.supabase_auth import ACCESS_TOKEN_COOKIE_NAME
from app.db.orm_models import UserSettingsORM
from app.db.session import session_scope
from app.integrations.supabase_auth.jwt import JWTError, decode_supabase_jwt, get_jwt_key


logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


class User(BaseModel):
    id: str
    email: Optional[str] = None


async def assert_user_exists(user_id: str) -> None:
    try:
        with session_scope() as session:
            exists = session.get(UserSettingsORM, user_id) is not None
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
        except ValueError as exc:
            raise ServiceUnavailableError("Authentication service is not configured correctly.") from exc

        user_id: str | None = payload.get("sub")
        email: str | None = payload.get("email")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        if verify_existence:
            await assert_user_exists(user_id)

        return User(id=user_id, email=email)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Unexpected auth middleware error: %s", exc, exc_info=True)
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
    "security",
    "User",
    "get_jwt_key",
    "assert_user_exists",
    "authenticate_credentials",
    "get_current_user",
    "get_user_no_check",
]
