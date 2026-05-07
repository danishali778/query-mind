from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.container import (
    get_analytics_service,
    get_chat_service,
    get_connection_service,
    get_dashboard_service,
    get_query_history_service,
    get_query_library_service,
    get_settings_service,
)
from app.core.errors import AppError, ServiceUnavailableError
from app.integrations.supabase_auth import User, get_current_user, get_user_no_check
from app.services.billing_service import increment_usage


CurrentUserDep = Annotated[User, Depends(get_current_user)]
UncheckedUserDep = Annotated[User, Depends(get_user_no_check)]


class RateLimitChecker:
    def __init__(self, limit_type: str):
        self.limit_type = limit_type

    def __call__(self, current_user: CurrentUserDep):
        try:
            success = increment_usage(current_user.id, self.limit_type)
        except AppError:
            raise
        except Exception as exc:
            raise ServiceUnavailableError("Usage enforcement is temporarily unavailable.") from exc
        if not success:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"{self.limit_type.upper()}_LIMIT_EXCEEDED",
            )
        return current_user

__all__ = [
    "User",
    "get_current_user",
    "get_user_no_check",
    "CurrentUserDep",
    "UncheckedUserDep",
    "RateLimitChecker",
    "get_chat_service",
    "get_connection_service",
    "get_dashboard_service",
    "get_query_library_service",
    "get_query_history_service",
    "get_settings_service",
    "get_analytics_service",
]
