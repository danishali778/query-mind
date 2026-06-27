import logging
from datetime import datetime, timedelta, timezone
from typing import TypeVar

from app.db.models.settings import UserSettings, UserSettingsBase, UserSubscription
from app.db.orm_models import UserSettingsORM, UserSubscriptionORM
from app.db.session import session_scope


logger = logging.getLogger(__name__)
T = TypeVar("T")


def _as_iso(value: datetime | str | None) -> str:
    if value is None:
        return "soon"
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _coalesce(value: T | None, default: T) -> T:
    return default if value is None else value


def _settings_to_domain(row: UserSettingsORM) -> UserSettings:
    defaults = UserSettingsBase().model_dump()
    return UserSettings(
        owner_id=row.owner_id,
        full_name=row.full_name,
        job_title=row.job_title,
        timezone=_coalesce(row.timezone, defaults["timezone"]),
        theme=_coalesce(row.theme, defaults["theme"]),
        accent_color=_coalesce(row.accent_color, defaults["accent_color"]),
        density=_coalesce(row.density, defaults["density"]),
        show_run_counts=_coalesce(row.show_run_counts, defaults["show_run_counts"]),
        animate_charts=_coalesce(row.animate_charts, defaults["animate_charts"]),
        syntax_highlighting=_coalesce(row.syntax_highlighting, defaults["syntax_highlighting"]),
        ai_model=_coalesce(row.ai_model, defaults["ai_model"]),
        stream_responses=_coalesce(row.stream_responses, defaults["stream_responses"]),
        default_row_limit=_coalesce(row.default_row_limit, defaults["default_row_limit"]),
        auto_save_queries=_coalesce(row.auto_save_queries, defaults["auto_save_queries"]),
        system_prompt=_coalesce(row.system_prompt, defaults["system_prompt"]),
        email_scheduled=_coalesce(row.email_scheduled, defaults["email_scheduled"]),
        email_failed=_coalesce(row.email_failed, defaults["email_failed"]),
        email_alerts=_coalesce(row.email_alerts, defaults["email_alerts"]),
        delivery_format=_coalesce(row.delivery_format, defaults["delivery_format"]),
        slack_enabled=_coalesce(row.slack_enabled, defaults["slack_enabled"]),
        slack_webhook=row.slack_webhook,
        slack_channel=row.slack_channel,
    )


def _subscription_to_domain(row: UserSubscriptionORM) -> UserSubscription:
    return UserSubscription(
        owner_id=row.owner_id,
        plan_type=_coalesce(row.plan_type, "free"),
        queries_used=_coalesce(row.queries_used, 0),
        queries_limit=_coalesce(row.queries_limit, 100),
        ai_used=_coalesce(row.ai_used, 0),
        ai_limit=_coalesce(row.ai_limit, 30),
        next_reset_date=_as_iso(row.next_reset_date),
    )


def _default_settings(owner_id: str) -> UserSettings:
    fallback = UserSettingsBase().model_dump()
    fallback["owner_id"] = owner_id
    return UserSettings(**fallback)


def _new_settings_row(owner_id: str) -> UserSettingsORM:
    defaults = UserSettingsBase().model_dump()
    return UserSettingsORM(owner_id=owner_id, **defaults)


def _new_subscription_row(owner_id: str) -> UserSubscriptionORM:
    return UserSubscriptionORM(
        owner_id=owner_id,
        plan_type="free",
        queries_used=0,
        queries_limit=100,
        ai_used=0,
        ai_limit=30,
        next_reset_date=datetime.now(timezone.utc) + timedelta(days=30),
    )


def get_user_settings(user_id: str) -> UserSettings:
    """Fetch user settings, falling back to defaults if the row is missing."""
    try:
        with session_scope() as session:
            row = session.get(UserSettingsORM, user_id)
            if row:
                return _settings_to_domain(row)
    except Exception as exc:
        logger.error("Failed to fetch settings for %s", user_id, exc_info=True)
        raise RuntimeError("Settings storage is unavailable.") from exc

    return _default_settings(user_id)


def update_user_settings(user_id: str, updates: dict) -> UserSettings:
    """Partially update user settings."""
    try:
        with session_scope() as session:
            row = session.get(UserSettingsORM, user_id)
            if not row:
                row = _new_settings_row(user_id)
                session.add(row)

            if updates:
                for key, value in updates.items():
                    if hasattr(row, key):
                        setattr(row, key, value)
                row.updated_at = datetime.now(timezone.utc)

            session.flush()
            return _settings_to_domain(row)
    except Exception as exc:
        logger.error("Error updating settings for %s: %s", user_id, exc, exc_info=True)
        raise RuntimeError("Settings storage is unavailable.") from exc


def get_user_subscription(user_id: str) -> UserSubscription:
    """Fetch user subscription, creating a default row if not present."""
    try:
        with session_scope() as session:
            row = session.get(UserSubscriptionORM, user_id)
            if not row:
                row = _new_subscription_row(user_id)
                session.add(row)
                session.flush()
            return _subscription_to_domain(row)
    except Exception as exc:
        logger.error("Failed to fetch or create subscription for %s", user_id, exc_info=True)
        raise RuntimeError("Billing state is unavailable.") from exc


def increment_usage(user_id: str, type: str) -> bool:
    """Increment either query or AI usage. Returns False when the limit is exceeded."""
    try:
        with session_scope() as session:
            row = session.get(UserSubscriptionORM, user_id)
            if not row:
                row = _new_subscription_row(user_id)
                session.add(row)
                session.flush()

            queries_used = _coalesce(row.queries_used, 0)
            queries_limit = _coalesce(row.queries_limit, 100)
            ai_used = _coalesce(row.ai_used, 0)
            ai_limit = _coalesce(row.ai_limit, 30)

            if type == "query":
                if queries_used >= queries_limit:
                    return False
                row.queries_used = queries_used + 1
            elif type == "ai":
                if ai_used >= ai_limit:
                    return False
                row.ai_used = ai_used + 1
            else:
                raise ValueError(f"Unknown limit type: {type}")

            row.updated_at = datetime.now(timezone.utc)
            return True
    except ValueError:
        raise
    except Exception as exc:
        logger.error("Usage update failed for %s", user_id, exc_info=True)
        raise RuntimeError("Billing state is unavailable.") from exc


def upgrade_to_pro(user_id: str) -> UserSubscription:
    """Upgrade the user to pro and reset their usage counters."""
    try:
        with session_scope() as session:
            row = session.get(UserSubscriptionORM, user_id)
            if not row:
                row = _new_subscription_row(user_id)
                session.add(row)

            row.plan_type = "pro"
            row.queries_limit = 5000
            row.ai_limit = 500
            row.queries_used = 0
            row.ai_used = 0
            row.updated_at = datetime.now(timezone.utc)
            session.flush()
            return _subscription_to_domain(row)
    except Exception as exc:
        logger.error("Failed to upgrade %s to pro", user_id, exc_info=True)
        raise RuntimeError("Billing update failed.") from exc


def onboard_user(user_id: str) -> bool:
    """Ensure default settings and subscription rows exist for a user."""
    try:
        with session_scope() as session:
            if not session.get(UserSettingsORM, user_id):
                logger.info("Initializing settings for new user %s", user_id)
                session.add(_new_settings_row(user_id))

            if not session.get(UserSubscriptionORM, user_id):
                logger.info("Initializing subscription for new user %s", user_id)
                session.add(_new_subscription_row(user_id))

        return True
    except Exception as exc:
        logger.error("Error onboarding user %s", user_id, exc_info=True)
        raise RuntimeError("Failed to initialize user records.") from exc


__all__ = [
    "get_user_settings",
    "update_user_settings",
    "get_user_subscription",
    "increment_usage",
    "upgrade_to_pro",
    "onboard_user",
]