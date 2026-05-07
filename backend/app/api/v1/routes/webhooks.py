import logging
from fastapi import APIRouter, Header, HTTPException, Request

from app.api.v1.schemas.webhooks import WebhookStatusResponse
from app.core.errors import BadRequestError, ServiceUnavailableError
from app.integrations.lemon_squeezy import (
    get_event_name,
    get_user_id,
    has_webhook_secret,
    parse_webhook_payload,
    verify_webhook_signature,
)
from app.services.billing_service import upgrade_to_pro

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
logger = logging.getLogger(__name__)

@router.post("/lemonsqueezy", response_model=WebhookStatusResponse)
async def lemonsqueezy_webhook(request: Request, x_signature: str | None = Header(None)):
    """
    Secure Webhook endpoint for Lemon Squeezy.
    Triggered when a subscription is purchased.
    """
    if not has_webhook_secret():
        logger.warning("LEMON_SQUEEZY_WEBHOOK_SECRET is not set. Rejecting webhook.")
        raise HTTPException(status_code=500, detail="Webhook secret not configured on server")

    if not x_signature:
        raise HTTPException(status_code=400, detail="Missing X-Signature header")

    raw_body = await request.body()

    if not verify_webhook_signature(raw_body, x_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        data = parse_webhook_payload(raw_body)
        event_name = get_event_name(data)

        logger.info("Received validated Lemon Squeezy event: %s", event_name)

        if event_name == "subscription_created":
            user_id = get_user_id(data)
            if not user_id:
                logger.error("Received subscription but no custom user_id attached.")
                raise BadRequestError("No user_id found in webhook custom_data.")

            upgrade_to_pro(user_id)
            logger.info("Upgraded user %s to PRO via Lemon Squeezy.", user_id)

        return {"status": "success"}

    except HTTPException:
        raise
    except BadRequestError:
        raise
    except Exception as exc:
        logger.error("Webhook processing error", exc_info=True)
        raise ServiceUnavailableError("Error processing webhook payload.") from exc
