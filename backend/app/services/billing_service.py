"""Billing and subscription workflows."""

from app.core.errors import ServiceUnavailableError
from app.db.models.settings import UserSubscription
from app.db.repositories import settings_repository

FREE_PLAN_QUERY_LIMIT = 100
FREE_PLAN_AI_LIMIT = 30
PRO_PLAN_QUERY_LIMIT = 5000
PRO_PLAN_AI_LIMIT = 500


def get_user_subscription(user_id: str) -> UserSubscription:
    try:
        return settings_repository.get_user_subscription(user_id)
    except RuntimeError as exc:
        raise ServiceUnavailableError("Billing information is temporarily unavailable.") from exc


def increment_usage(user_id: str, limit_type: str) -> bool:
    subscription = get_user_subscription(user_id)

    if limit_type == "query":
        if subscription.queries_used >= subscription.queries_limit:
            return False
    elif limit_type == "ai":
        if subscription.ai_used >= subscription.ai_limit:
            return False
    else:
        raise ValueError(f"Unknown limit type: {limit_type}")

    try:
        return settings_repository.increment_usage(user_id, limit_type)
    except RuntimeError as exc:
        raise ServiceUnavailableError("Usage enforcement is temporarily unavailable.") from exc


def upgrade_to_pro(user_id: str) -> UserSubscription:
    try:
        return settings_repository.upgrade_to_pro(user_id)
    except RuntimeError as exc:
        raise ServiceUnavailableError("Unable to update subscription at the moment.") from exc


def onboard_user(user_id: str) -> bool:
    try:
        return settings_repository.onboard_user(user_id)
    except RuntimeError as exc:
        raise ServiceUnavailableError("Unable to initialize user records.") from exc


__all__ = [
    "FREE_PLAN_QUERY_LIMIT",
    "FREE_PLAN_AI_LIMIT",
    "PRO_PLAN_QUERY_LIMIT",
    "PRO_PLAN_AI_LIMIT",
    "UserSubscription",
    "get_user_subscription",
    "increment_usage",
    "upgrade_to_pro",
    "onboard_user",
]
