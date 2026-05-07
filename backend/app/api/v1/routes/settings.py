from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUserDep, UncheckedUserDep
from app.api.v1.schemas.settings import (
    BillingInfoResponse,
    CurrentUserResponse,
    OnboardResponse,
    UserSettingsResponse,
    UserSettingsUpdate,
)
from app.core.errors import ServiceUnavailableError
from app.db.models.settings import UserSettingsUpdate as UserSettingsUpdateInput
from app.services import billing_service
from app.services import settings_service as store

router = APIRouter(prefix="/api/settings", tags=["User Settings"])

@router.get("", response_model=UserSettingsResponse)
def get_user_settings(current_user: CurrentUserDep):
    """Get the current authenticated user's settings. Defaults are injected if none exist."""
    try:
        return store.get_settings_for_user(current_user.id)
    except Exception as exc:
        raise ServiceUnavailableError("Failed to fetch user settings.") from exc

@router.put("", response_model=UserSettingsResponse)
def update_user_settings(
    updates: UserSettingsUpdate,
    current_user: CurrentUserDep
):
    """Partially update user settings."""
    try:
        domain_updates = UserSettingsUpdateInput(**updates.model_dump(exclude_unset=True))
        return store.update_settings_for_user(current_user.id, domain_updates)
    except Exception as exc:
        raise ServiceUnavailableError("Failed to update user settings.") from exc

# --- Billing & Subscriptions ---

@router.get("/billing", response_model=BillingInfoResponse)
def get_billing_info(current_user: CurrentUserDep):
    """Get the user's current subscription tier and usage limit counters."""
    try:
        return billing_service.get_user_subscription(current_user.id)
    except Exception as exc:
        raise ServiceUnavailableError("Failed to fetch billing information.") from exc

@router.post("/billing/upgrade", response_model=BillingInfoResponse)
def trigger_mock_upgrade(current_user: CurrentUserDep):
    """Mock webhook: Upgrades the user to Pro and instantly resets/increases their limits."""
    try:
        return billing_service.upgrade_to_pro(current_user.id)
    except Exception as exc:
        raise ServiceUnavailableError("Failed to update subscription.") from exc


@router.post("/onboard", response_model=OnboardResponse)
def onboard_user(current_user: UncheckedUserDep):
    """Register the user in the database (Source of Truth)."""
    try:
        success = billing_service.onboard_user(current_user.id)
    except Exception as exc:
        raise ServiceUnavailableError("Failed to initialize user session.") from exc
    if not success:
        raise ServiceUnavailableError("Failed to initialize user session.")
    return {"status": "success"}


@router.get("/me", response_model=CurrentUserResponse)
def check_auth(current_user: CurrentUserDep):
    """A lightweight endpoint for the frontend to verify that the user still exists in the DB."""
    return {"id": current_user.id, "email": current_user.email}
