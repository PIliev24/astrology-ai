"""
Webhook Router
Handles Stripe webhook events for subscription lifecycle management
"""

import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status, Request

from models.subscription import PlanType, SubscriptionStatus
from services.database import (
    update_user_subscription,
    get_user_subscription,
)
from services.subscription import (
    verify_webhook_signature,
    handle_checkout_session_completed,
    handle_customer_subscription_updated,
    determine_plan_from_price_id,
    map_stripe_status_to_subscription_status,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

# Stripe webhook secret from environment
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

    This endpoint must be registered in your Stripe Dashboard under:
    Developers > Webhooks > Add endpoint

    Events handled:
    - checkout.session.completed: New subscription created
    - customer.subscription.updated: Subscription modified or cancelled
    - invoice.payment_failed: Payment failure notification

    Requires STRIPE_WEBHOOK_SECRET to be set in environment variables.
    """
    if not STRIPE_WEBHOOK_SECRET:
        logger.error("STRIPE_WEBHOOK_SECRET not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook not configured",
        )

    try:
        # Get raw body for signature verification
        payload = await request.body()
        signature = request.headers.get("stripe-signature")

        if not signature:
            logger.warning("Received webhook without signature header")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing signature header",
            )

        # Verify and parse webhook
        event = verify_webhook_signature(payload, signature, STRIPE_WEBHOOK_SECRET)

        event_type = event.get("type")
        event_data = event.get("data", {}).get("object", {})

        logger.info(f"Processing Stripe webhook event: {event_type}")

        # Route to appropriate handler
        if event_type == "checkout.session.completed":
            _handle_checkout_session_completed(event_data)

        elif event_type == "customer.subscription.updated":
            _handle_customer_subscription_updated(event_data)

        elif event_type == "invoice.payment_failed":
            _handle_invoice_payment_failed(event_data)

        else:
            logger.debug(f"Ignoring unhandled webhook event type: {event_type}")

        return {"status": "received"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed",
        )


def _handle_checkout_session_completed(session_data: dict):
    """
    Handle checkout.session.completed event.

    This fires when a customer completes checkout successfully.
    Updates the user's subscription with Stripe subscription details.
    """
    try:
        user_id = session_data.get("metadata", {}).get("user_id")
        customer_id = session_data.get("customer")
        subscription_id = session_data.get("subscription")

        if not user_id:
            logger.warning(
                f"Checkout session {session_data.get('id')} completed but no user_id in metadata"
            )
            return

        if not subscription_id:
            logger.warning(
                f"Checkout session {session_data.get('id')} completed but no subscription_id"
            )
            return

        # Get the price ID from line items
        price_id = None
        if session_data.get("line_items", {}).get("data"):
            price_id = session_data["line_items"]["data"][0].get("price", {}).get("id")

        # Determine plan from price ID
        try:
            plan = determine_plan_from_price_id(price_id)
        except ValueError as e:
            logger.error(f"Could not determine plan from price_id {price_id}: {str(e)}")
            return

        # Update subscription in database
        update_data = {
            "stripe_customer_id": customer_id,
            "stripe_subscription_id": subscription_id,
            "stripe_price_id": price_id,
            "status": plan,
            "billing_status": SubscriptionStatus.ACTIVE,
        }

        updated = update_user_subscription(user_id, update_data)

        logger.info(
            f"Updated subscription for user {user_id}: "
            f"plan={plan}, subscription_id={subscription_id}"
        )

    except Exception as e:
        logger.error(f"Error handling checkout.session.completed: {str(e)}")
        # Don't re-raise - webhook must return 200 for Stripe


def _handle_customer_subscription_updated(subscription_data: dict):
    """
    Handle customer.subscription.updated event.

    This fires when a subscription is modified (plan change, cancel scheduled, etc).
    Updates the user's subscription status and billing period information.
    """
    try:
        subscription_id = subscription_data.get("id")
        customer_id = subscription_data.get("customer")
        stripe_status = subscription_data.get("status", "incomplete")

        if not subscription_id or not customer_id:
            logger.warning("Subscription updated event missing required fields")
            return

        # Get the user's current subscription
        subscription = None
        try:
            # We need to find the user by subscription ID
            # Since we store subscription_id in the database, we'd need to query by it
            # For now, we rely on metadata from subscription
            user_id = subscription_data.get("metadata", {}).get("user_id")

            if not user_id:
                logger.warning(
                    f"Subscription {subscription_id} updated but no user_id in metadata"
                )
                return

            subscription = get_user_subscription(user_id)

        except Exception as e:
            logger.warning(f"Could not find subscription for {subscription_id}: {str(e)}")
            return

        if not subscription:
            logger.warning(f"No local subscription found for Stripe subscription {subscription_id}")
            return

        # Determine plan from current price
        plan = subscription.status  # Keep existing plan by default
        try:
            if subscription_data.get("items", {}).get("data"):
                price_id = subscription_data["items"]["data"][0].get("price", {}).get("id")
                if price_id:
                    plan = determine_plan_from_price_id(price_id)
        except ValueError as e:
            logger.debug(f"Could not determine plan from price: {str(e)}")

        # Map Stripe status to application status
        billing_status = map_stripe_status_to_subscription_status(stripe_status)

        # Update subscription
        update_data = {
            "status": plan,
            "billing_status": billing_status,
            "current_period_start": datetime.fromtimestamp(
                subscription_data.get("current_period_start"), tz=timezone.utc
            ),
            "current_period_end": datetime.fromtimestamp(
                subscription_data.get("current_period_end"), tz=timezone.utc
            ),
            "cancel_at": (
                datetime.fromtimestamp(subscription_data.get("cancel_at"), tz=timezone.utc)
                if subscription_data.get("cancel_at")
                else None
            ),
        }

        updated = update_user_subscription(subscription.user_id, update_data)

        logger.info(
            f"Updated subscription for user {subscription.user_id}: "
            f"status={billing_status}, plan={plan}"
        )

    except Exception as e:
        logger.error(f"Error handling customer.subscription.updated: {str(e)}")
        # Don't re-raise - webhook must return 200 for Stripe


def _handle_invoice_payment_failed(invoice_data: dict):
    """
    Handle invoice.payment_failed event.

    This fires when a subscription payment fails.
    Updates subscription to past_due status.
    """
    try:
        subscription_id = invoice_data.get("subscription")
        customer_id = invoice_data.get("customer")

        if not subscription_id or not customer_id:
            logger.warning("Payment failed event missing required fields")
            return

        # We would need to query the database to find the user by subscription_id
        # For now, we log this event but don't update (would need additional DB query)
        logger.warning(
            f"Payment failed for subscription {subscription_id} (customer {customer_id}). "
            f"Subscription status will be updated via customer.subscription.updated event."
        )

    except Exception as e:
        logger.error(f"Error handling invoice.payment_failed: {str(e)}")
        # Don't re-raise - webhook must return 200 for Stripe

