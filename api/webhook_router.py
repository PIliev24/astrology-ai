"""
Webhook Router
Handles Stripe webhook events for subscription lifecycle management
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, status, Request

from models.subscription import SubscriptionUpdate
from services.database import (
    update_user_subscription,
    get_user_subscription,
    get_or_create_user_subscription,
    get_user_subscription_by_stripe_id,
    get_user_usage,
    reset_user_usage,
)
from services.subscription import (
    verify_webhook_signature,
    determine_plan_from_price_id,
    get_subscription_from_stripe,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
load_dotenv()

# Stripe webhook secret from environment
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")


def _unix_to_datetime(timestamp: Optional[int]) -> Optional[datetime]:
    """
    Convert Unix timestamp to datetime object.
    
    Args:
        timestamp: Unix timestamp (seconds since epoch) or None
    
    Returns:
        datetime object in UTC timezone, or None if timestamp is None
    """
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def _reset_user_message_count(user_id: str):
    """
    Helper function to reset user's message count.
    Ensures usage record exists before resetting.
    
    Args:
        user_id: User ID (UUID string)
    """
    try:
        # Ensure usage record exists (creates if needed)
        get_user_usage(user_id)
        # Reset the message count
        reset_user_usage(user_id)
        logger.info("Reset message count for user %s after subscription update", user_id)
    except Exception as exc:
        # Log error but don't fail webhook processing
        logger.error("Failed to reset message count for user %s: %s", user_id, str(exc))


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
        event_data_obj = event.get("data", {})
        event_data = event_data_obj.get("object", {})
        previous_attributes = event_data_obj.get("previous_attributes", {})

        logger.info("Processing Stripe webhook event: %s", event_type)

        # Route to appropriate handler
        if event_type == "checkout.session.completed":
            await _handle_checkout_session_completed(event_data)

        elif event_type == "customer.subscription.created":
            await _handle_customer_subscription_created(event_data)

        elif event_type == "customer.subscription.updated":
            await _handle_customer_subscription_updated(event_data, previous_attributes)

        elif event_type in ("invoice.paid", "invoice.payment_succeeded"):
            await _handle_invoice_paid(event_data)

        elif event_type == "invoice.payment_failed":
            await _handle_invoice_payment_failed(event_data)

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


async def _handle_checkout_session_completed(session_data: dict):
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
                "Checkout session %s completed but no user_id in metadata",
                session_data.get('id')
            )
            return

        if not subscription_id:
            logger.warning(
                "Checkout session %s completed but no subscription_id",
                session_data.get('id')
            )
            return

        price_id = None
        try:
            # Fetch subscription from Stripe to get price_id and current_period_end
            stripe_subscription = get_subscription_from_stripe(subscription_id)
            price_id = stripe_subscription.get("price_id")
        except Exception as exc:
            logger.error("Could not fetch subscription from Stripe: %s", str(exc))

        if not price_id:
            logger.error("Could not determine price_id for subscription %s", subscription_id)
            return

        # Determine plan from price ID
        try:
            plan = determine_plan_from_price_id(price_id)
        except ValueError as exc:
            logger.error("Could not determine plan from price_id %s: %s", price_id, str(exc))
            return

        # Ensure subscription exists in database (create if it doesn't)
        try:
            get_user_subscription(user_id)
        except HTTPException:
            # Subscription doesn't exist, create it
            logger.info("Creating subscription for user %s from checkout session", user_id)
            get_or_create_user_subscription(user_id, customer_id)

        # Update subscription in database using SubscriptionUpdate model
        update_data = SubscriptionUpdate(
            stripe_subscription_id=subscription_id,
            stripe_price_id=price_id,
            status=plan,
            is_active=True,
            current_period_end=None
        )

        update_user_subscription(user_id, update_data)

        # Reset message count when subscription is activated
        _reset_user_message_count(user_id)

        logger.info(
            "Updated subscription for user %s: plan=%s, subscription_id=%s",
            user_id, plan, subscription_id
        )

    except Exception as exc:
        logger.error("Error handling checkout.session.completed: %s", str(exc))
        # Don't re-raise - webhook must return 200 for Stripe


async def _handle_customer_subscription_created(subscription_data: dict):
    """
    Handle customer.subscription.created event.
    
    This fires when a new subscription is created in Stripe.
    Updates the user's subscription with the new subscription details.
    """
    try:
        subscription_id = subscription_data.get("id")
        customer_id = subscription_data.get("customer")
        
        if not subscription_id or not customer_id:
            logger.warning("Subscription created event missing required fields")
            return
        
        # Get user_id from metadata or find by subscription_id
        user_id = subscription_data.get("metadata", {}).get("user_id")
        
        if not user_id:
            # Try to find user by subscription_id in database
            subscription = get_user_subscription_by_stripe_id(subscription_id)
            if subscription:
                user_id = str(subscription.user_id)
            else:
                logger.warning(
                    "Subscription %s created but no user_id found",
                    subscription_id
                )
                return
        
        # Get price_id from subscription items
        price_id = None
        if subscription_data.get("items", {}).get("data"):
            price_id = subscription_data["items"]["data"][0].get("price", {}).get("id")
        
        if not price_id:
            # Fetch full subscription from Stripe to get price_id
            try:
                stripe_subscription = get_subscription_from_stripe(subscription_id)
                price_id = stripe_subscription.get("price_id")
            except Exception as exc:
                logger.error("Could not fetch subscription from Stripe: %s", str(exc))
                return
        
        # Determine plan from price ID
        if not price_id:
            logger.error("Could not determine price_id for subscription %s", subscription_id)
            return
        
        try:
            plan = determine_plan_from_price_id(price_id)
        except ValueError as exc:
            logger.error("Could not determine plan from price_id %s: %s", price_id, str(exc))
            return
        
        # Ensure subscription exists in database
        try:
            get_user_subscription(user_id)
        except HTTPException:
            get_or_create_user_subscription(user_id, customer_id)
        
        # New subscription: is_active = True, current_period_end = None
        update_data = SubscriptionUpdate(
            stripe_subscription_id=subscription_id,
            stripe_price_id=price_id,
            status=plan,
            is_active=True,
            current_period_end=None,
        )
        
        update_user_subscription(user_id, update_data)
        _reset_user_message_count(user_id)
        
    except Exception as exc:
        logger.error("Error handling customer.subscription.created: %s", str(exc), exc_info=True)


async def _handle_customer_subscription_updated(subscription_data: dict, previous_attributes: dict):
    """
    Handle customer.subscription.updated event.

    This fires when a subscription is modified (plan change, cancel scheduled, etc).
    Updates the user's subscription status and billing period information.
    """
    try:
        subscription_id = subscription_data.get("id")
        customer_id = subscription_data.get("customer")

        if not subscription_id or not customer_id:
            logger.warning("Subscription updated event missing required fields")
            return

        # Find user by subscription_id
        subscription = get_user_subscription_by_stripe_id(subscription_id)
        
        if not subscription:
            # Try to get user_id from metadata as fallback
            user_id = subscription_data.get("metadata", {}).get("user_id")
            if user_id:
                try:
                    subscription = get_user_subscription(user_id)
                except HTTPException:
                    logger.warning(
                        "Subscription %s updated but no local subscription found",
                        subscription_id
                    )
                    return
            else:
                logger.warning(
                    "Subscription %s updated but no local subscription found and no user_id in metadata",
                    subscription_id
                )
                return
        
        user_id = str(subscription.user_id)

        # Determine plan from current price
        old_plan = subscription.status  # Keep existing plan by default
        plan = old_plan
        price_id = None
        try:
            if subscription_data.get("items", {}).get("data"):
                price_id = subscription_data["items"]["data"][0].get("price", {}).get("id")
                if price_id:
                    plan = determine_plan_from_price_id(price_id)
        except ValueError as exc:
            logger.debug("Could not determine plan from price: %s", str(exc))
        
        # If we couldn't get price_id from event, fetch from Stripe
        if not price_id:
            try:
                stripe_subscription = get_subscription_from_stripe(subscription_id)
                price_id = stripe_subscription.get("price_id")
                if price_id:
                    plan = determine_plan_from_price_id(price_id)
            except Exception as exc:
                logger.debug("Could not fetch price_id from Stripe: %s", str(exc))

        # Check cancellation status
        cancel_at = subscription_data.get("cancel_at")
        cancel_at_period_end = subscription_data.get("cancel_at_period_end", False)
        previous_cancel_at = previous_attributes.get("cancel_at")
        
        # Determine is_active and current_period_end based on cancellation status
        is_active = True
        current_period_end = None
        
        if cancel_at is not None and cancel_at_period_end:
            # Subscription is cancelled but still active until cancel_at
            is_active = True
            current_period_end = _unix_to_datetime(cancel_at)
            logger.info(
                "Subscription %s cancelled, will end at %s",
                subscription_id, current_period_end
            )
        elif previous_cancel_at is not None and cancel_at is None:
            # Subscription was cancelled but cancel_at was removed (reactivation)
            is_active = True
            current_period_end = None
            logger.info("Subscription %s reactivated", subscription_id)
        else:
            # Normal update (no cancellation change)
            is_active = True
            current_period_end = None
        
        # Reset message count if plan changed or subscription became active
        plan_changed = plan != old_plan
        became_active = is_active and not subscription.is_active
        
        if plan_changed or became_active:
            _reset_user_message_count(user_id)

        update_data = SubscriptionUpdate(
            stripe_price_id=price_id if price_id else None,
            status=plan,
            is_active=is_active,
            current_period_end=current_period_end,
        )

        update_user_subscription(user_id, update_data)

    except Exception as exc:
        logger.error("Error handling customer.subscription.updated: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed",
        ) from exc


async def _handle_invoice_paid(invoice_data: dict):
    """
    Handle invoice.paid and invoice.payment_succeeded events.
    
    This fires when a subscription payment succeeds.
    Updates subscription to active status and ensures plan is correct.
    """
    try:
        subscription_id = invoice_data.get("subscription")
        
        if not subscription_id:
            logger.debug("Invoice paid event has no subscription_id (one-time payment)")
            return
        
        # Find user by subscription_id
        subscription = get_user_subscription_by_stripe_id(subscription_id)
        if not subscription:
            logger.warning(
                "Invoice paid for subscription %s but no local subscription found",
                subscription_id
            )
            return
        
        user_id = str(subscription.user_id)
        
        # Fetch subscription from Stripe to get latest data
        try:
            stripe_subscription = get_subscription_from_stripe(subscription_id)
            price_id = stripe_subscription.get("price_id")
            
            # Determine plan from price ID
            plan = subscription.status  # Keep existing plan by default
            if price_id:
                try:
                    plan = determine_plan_from_price_id(price_id)
                except ValueError:
                    logger.debug("Could not determine plan from price_id %s", price_id)
            
            
            update_data = SubscriptionUpdate(
                stripe_price_id=price_id if price_id else None,
                status=plan,
                is_active=True,  # Payment succeeded = active
                current_period_end=None,  # Update to new period end
            )
            
            update_user_subscription(user_id, update_data)
            _reset_user_message_count(user_id)

            
        except Exception as exc:
            logger.error("Error fetching subscription details: %s", str(exc))
            update_data = SubscriptionUpdate(
                is_active=True,  # Payment succeeded = active
                current_period_end=None,
            )
            update_user_subscription(user_id, update_data)
            _reset_user_message_count(user_id)
        
    except Exception as exc:
        logger.error("Error handling invoice.paid: %s", str(exc), exc_info=True)


async def _handle_invoice_payment_failed(invoice_data: dict):
    """
    Handle invoice.payment_failed event.

    This fires when a subscription payment fails.
    Updates subscription to inactive status while preserving current_period_end.
    """
    try:
        subscription_id = invoice_data.get("subscription")

        if not subscription_id:
            logger.warning("Payment failed event missing subscription_id")
            return

        subscription = get_user_subscription_by_stripe_id(subscription_id)
        if not subscription:
            return

        user_id = str(subscription.user_id)
        
        # Preserve existing current_period_end (or fetch from Stripe if not available)
        current_period_end = subscription.current_period_end
        
        # If we don't have current_period_end, try to fetch from Stripe
        if current_period_end is None:
            try:
                stripe_subscription = get_subscription_from_stripe(subscription_id)
                period_end_timestamp = stripe_subscription.get("current_period_end")
                if period_end_timestamp:
                    current_period_end = _unix_to_datetime(period_end_timestamp)
            except Exception as exc:
                logger.debug("Could not fetch current_period_end from Stripe: %s", str(exc))
        
        update_data = SubscriptionUpdate(
            is_active=False,
            current_period_end=current_period_end,  # Preserve existing value
        )
        update_user_subscription(user_id, update_data)

    except Exception as exc:
        logger.error("Error handling invoice.payment_failed: %s", str(exc), exc_info=True)

