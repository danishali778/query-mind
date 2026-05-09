import logging
from datetime import datetime, timezone

from app.db.models.settings import UserSettings, UserSettingsBase, UserSubscription
from app.integrations.supabase_db import supabase


logger = logging.getLogger(__name__)


def get_user_settings(user_id: str) -> UserSettings:
    """Fetch user settings, falling back to defaults if the row is missing."""
    try:
        response = supabase.table("user_settings").select("*").eq("owner_id", user_id).execute()
        if response.data:
            return UserSettings(**response.data[0])
    except Exception as exc:
        logger.error("Failed to fetch settings for %s", user_id, exc_info=True)
        raise RuntimeError("Settings storage is unavailable.") from exc

    fallback = UserSettingsBase().model_dump()
    fallback["owner_id"] = user_id
    return UserSettings(**fallback)


def update_user_settings(user_id: str, updates: dict) -> UserSettings:
    """Partially update user settings."""
    try:
        data = dict(updates)
        if not data:
            return get_user_settings(user_id)

        data["updated_at"] = "now()"
        response = supabase.table("user_settings").update(data).eq("owner_id", user_id).execute()
        if response.data:
            return UserSettings(**response.data[0])
        return get_user_settings(user_id)
    except Exception as exc:
        logger.error("Error updating settings for %s: %s", user_id, exc, exc_info=True)
        raise


def get_user_subscription(user_id: str) -> UserSubscription:
    """Fetch user subscription, creating a default row if not present."""
    defaults = {
        "owner_id": user_id,
        "plan_type": "free",
        "queries_used": 0,
        "queries_limit": 100,
        "ai_used": 0,
        "ai_limit": 30,
        "next_reset_date": "soon",
    }

    try:
        response = supabase.table("user_subscriptions").select("*").eq("owner_id", user_id).execute()
        if not response.data:
            insert_defaults = defaults.copy()
            del insert_defaults["next_reset_date"]
            insert_resp = supabase.table("user_subscriptions").insert(insert_defaults).execute()
            if insert_resp.data:
                return UserSubscription(**insert_resp.data[0])
            return UserSubscription(**defaults)
        return UserSubscription(**response.data[0])
    except Exception as exc:
        logger.error("Failed to fetch or create subscription for %s", user_id, exc_info=True)
        raise RuntimeError("Billing state is unavailable.") from exc


def increment_usage(user_id: str, type: str) -> bool:
    """Increment either query or AI usage. Returns False when the limit is exceeded."""
    subscription = get_user_subscription(user_id)
    try:
        if type == "query":
            if subscription.queries_used >= subscription.queries_limit:
                return False
            response = supabase.table("user_subscriptions").update(
                {"queries_used": subscription.queries_used + 1}
            ).eq("owner_id", user_id).execute()
            if not response.data:
                raise RuntimeError("Failed to update query usage.")
            return True

        if type == "ai":
            if subscription.ai_used >= subscription.ai_limit:
                return False
            response = supabase.table("user_subscriptions").update(
                {"ai_used": subscription.ai_used + 1}
            ).eq("owner_id", user_id).execute()
            if not response.data:
                raise RuntimeError("Failed to update AI usage.")
            return True
    except Exception as exc:
        logger.error("Usage update failed for %s", user_id, exc_info=True)
        raise RuntimeError("Billing state is unavailable.") from exc
    return False


def upgrade_to_pro(user_id: str) -> UserSubscription:
    """Upgrade the user to pro and reset their usage counters."""
    # Ensure a row exists for this user (e.g., new accounts that have never run a query).
    get_user_subscription(user_id)

    data = {
        "plan_type": "pro",
        "queries_limit": 5000,
        "ai_limit": 500,
        "queries_used": 0,
        "ai_used": 0,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        response = (
            supabase.table("user_subscriptions")
            .update(data)
            .eq("owner_id", user_id)
            .execute()
        )
        if response.data:
            return UserSubscription(**response.data[0])
        raise RuntimeError("No subscription record was updated.")
    except Exception as exc:
        logger.error("Failed to upgrade %s to pro", user_id, exc_info=True)
        raise RuntimeError("Billing update failed.") from exc


def onboard_user(user_id: str) -> bool:
    """Ensure default settings and subscription rows exist for a user."""
    try:
        logger.debug("Checking settings for user %s", user_id)
        existing_settings = supabase.table("user_settings").select("owner_id").eq("owner_id", user_id).execute()
        logger.debug("Settings check response: %s", existing_settings.data)
        
        if not existing_settings.data:
            logger.info("Initializing settings for new user %s", user_id)
            defaults = UserSettingsBase().model_dump()
            defaults["owner_id"] = user_id
            supabase.table("user_settings").insert(defaults).execute()
            logger.debug("Settings initialized")

        logger.debug("Checking subscription for user %s", user_id)
        existing_subscription = (
            supabase.table("user_subscriptions").select("owner_id").eq("owner_id", user_id).execute()
        )
        logger.debug("Subscription check response: %s", existing_subscription.data)
        
        if not existing_subscription.data:
            logger.info("Initializing subscription for new user %s", user_id)
            sub_defaults = {
                "owner_id": user_id,
                "plan_type": "free",
                "queries_used": 0,
                "queries_limit": 100,
                "ai_used": 0,
                "ai_limit": 30,
            }
            supabase.table("user_subscriptions").insert(sub_defaults).execute()
            logger.debug("Subscription initialized")
            
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
