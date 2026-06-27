import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.errors import ServiceUnavailableError
from app.db.orm_models import UserSettingsORM
from app.db.session import session_scope
from app.integrations.supabase_auth.jwt import JWTError, decode_supabase_jwt, get_jwt_key


logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=True)


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


async def authenticate_credentials(
    credentials: Optional[HTTPAuthorizationCredentials],
    verify_existence: bool = True,
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
        )

    try:
        try:
            payload = decode_supabase_jwt(credentials.credentials)
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
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    verify_existence: bool = True,
) -> User:
    return await authenticate_credentials(credentials, verify_existence=verify_existence)


async def get_user_no_check(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> User:
    return await authenticate_credentials(credentials, verify_existence=False)


__all__ = [
    "security",
    "User",
    "get_jwt_key",
    "assert_user_exists",
    "authenticate_credentials",
    "get_current_user",
    "get_user_no_check",
]