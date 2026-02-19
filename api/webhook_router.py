"""
Webhook Router
Handles Stripe webhook events for one-time purchase fulfillment.
"""

import logging
import os

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, status, Request

from constants.limits import CREDIT_AMOUNTS, PASS_DURATIONS, LIFETIME_EXPIRY
from models.subscription import ProductType
from services.database import (
    get_or_create_user_subscription,
    add_message_credits,
    set_unlimited_until,
    extend_unlimited_until,
)
from services.subscription import (
    verify_webhook_signature,
    determine_product_from_price_id,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["Webhooks"])
load_dotenv()

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")


@router.post(
    "/stripe",
    status_code=status.HTTP_200_OK,
    summary="Stripe webhook endpoint",
    description="Webhook endpoint for Stripe events (must be configured in Stripe Dashboard)",
)
async def stripe_webhook(request: Request):
    """
    Handle incoming Stripe webhook events.

    Only handles checkout.session.completed for one-time purchases.
    """
    if not STRIPE_WEBHOOK_SECRET:
        logger.error("STRIPE_WEBHOOK_SECRET not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook not configured",
        )

    try:
        payload = await request.body()
        signature = request.headers.get("stripe-signature")

        if not signature:
            logger.warning("Received webhook without signature header")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing signature header",
            )

        event = verify_webhook_signature(payload, signature, STRIPE_WEBHOOK_SECRET)

        event_type = event.get("type")
        event_data = event.get("data", {}).get("object", {})

        logger.info("Processing Stripe webhook event: %s", event_type)

        if event_type == "checkout.session.completed":
            await _handle_checkout_completed(event_data)
        else:
            logger.debug("Ignoring unhandled webhook event type: %s", event_type)

        return {"status": "received"}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Unexpected error processing webhook: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed",
        ) from exc


async def _handle_checkout_completed(session_data: dict):
    """
    Handle checkout.session.completed for one-time purchases.

    Reads product_type from session metadata and applies the purchase:
    - pack_10: add 10 message credits (stacks with existing)
    - day_1: set/extend unlimited_until by 24 hours
    - week_1: set/extend unlimited_until by 7 days
    - lifetime: set unlimited_until to 2099-12-31
    """
    try:
        metadata = session_data.get("metadata", {})
        user_id = metadata.get("user_id")
        product_type_str = metadata.get("product_type")

        if not user_id:
            logger.warning(
                "Checkout session %s completed but no user_id in metadata",
                session_data.get("id"),
            )
            return

        if not product_type_str:
            logger.warning(
                "Checkout session %s completed but no product_type in metadata",
                session_data.get("id"),
            )
            return

        try:
            product_type = ProductType(product_type_str)
        except ValueError:
            logger.error("Unknown product_type in metadata: %s", product_type_str)
            return

        # Ensure subscription exists
        get_or_create_user_subscription(user_id)

        # Apply purchase
        if product_type == ProductType.PACK_10:
            credits = CREDIT_AMOUNTS["pack_10"]
            add_message_credits(user_id, credits)
            logger.info("Added %d credits for user %s", credits, user_id)

        elif product_type == ProductType.DAY_1:
            duration = PASS_DURATIONS["day_1"]
            extend_unlimited_until(user_id, duration)
            logger.info("Extended unlimited by 1 day for user %s", user_id)

        elif product_type == ProductType.WEEK_1:
            duration = PASS_DURATIONS["week_1"]
            extend_unlimited_until(user_id, duration)
            logger.info("Extended unlimited by 1 week for user %s", user_id)

        elif product_type == ProductType.LIFETIME:
            set_unlimited_until(user_id, LIFETIME_EXPIRY)
            logger.info("Set lifetime access for user %s", user_id)

    except Exception as exc:
        logger.error("Error handling checkout.session.completed: %s", str(exc))
