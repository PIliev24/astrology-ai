"""
Subscription Router
Handles subscription management, checkout, and usage tracking endpoints
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, HttpUrl
import stripe

from middleware.auth import get_current_user
from models.subscription import PlanType, SubscriptionResponse, SubscriptionUpdate, UsageResponse
from services.database import (
    get_or_create_user_subscription,
    get_user_subscription,
    get_user_usage,
    increment_user_message_count,
    update_user_subscription,
)
from services.subscription import (
    get_or_create_customer,
    create_checkout_session,
    cancel_subscription,
    reactivate_subscription,
    get_stripe_price_id,
)
from services.usage_tracker import calculate_usage_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


# Request/Response Models
class CheckoutRequest(BaseModel):
    """Request to create a Stripe checkout session."""

    plan: PlanType
    success_url: HttpUrl
    cancel_url: HttpUrl


class CheckoutResponse(BaseModel):
    """Checkout session response."""

    checkout_url: str
    session_id: Optional[str] = None


class CancelSubscriptionRequest(BaseModel):
    """Request to cancel a subscription."""

    at_period_end: bool = True  # If True, cancel at period end; False = immediate


class UpgradeDowngradeRequest(BaseModel):
    """Request to upgrade or downgrade plan."""

    new_plan: PlanType


class PlanFeature(BaseModel):
    """Plan feature details."""

    name: str
    description: Optional[str] = None


class PlanDetailsResponse(BaseModel):
    """Details about a subscription plan."""

    type: PlanType
    name: str
    description: str
    price: int  # In cents (e.g., 200 = €2.00)
    currency: str  # ISO 4217 currency code
    interval: str  # "month" or "year"
    messages_per_day: Optional[int]  # None = unlimited
    features: list[PlanFeature]
    stripe_price_id: Optional[str]  # None for free tier
    stripe_product_id: Optional[str]


class PlansListResponse(BaseModel):
    """List of all available plans."""

    plans: list[PlanDetailsResponse]


@router.get(
    "/me",
    response_model=SubscriptionResponse,
    summary="Get current subscription",
    description="Retrieve the current user's subscription details",
)
async def get_my_subscription(user: dict = Depends(get_current_user)):
    """
    Get current user's subscription details.

    Returns subscription status including plan type, billing period, and Stripe IDs.
    """
    try:
        user_id = user["id"]

        # Get or create subscription (free tier by default)
        subscription = get_or_create_user_subscription(user_id)

        return SubscriptionResponse(
            id=subscription.id,
            plan=subscription.status,
            is_active=subscription.is_active,
            stripe_customer_id=subscription.stripe_customer_id,
            stripe_subscription_id=subscription.stripe_subscription_id,
            current_period_end=subscription.current_period_end,
            created_at=subscription.created_at,
            updated_at=subscription.updated_at,
        )
    except Exception as e:
        logger.error("Error fetching subscription for user %s: %s", user['id'], str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch subscription",
        ) from e


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Create checkout session",
    description="Generate a Stripe Checkout session for subscription upgrade",
)
async def create_checkout(
    request: CheckoutRequest,
    user: dict = Depends(get_current_user),
):
    """
    Create a Stripe Checkout session for subscription upgrade/downgrade.

    The user will be redirected to Stripe's hosted checkout page.
    """
    try:
        user_id = user["id"]
        user_email = user.get("email", "")
        user_name = user.get("name")

        if request.plan == PlanType.FREE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot checkout for free tier",
            )

        # Get or create Stripe customer
        customer_id = get_or_create_customer(user_id, user_email, user_name)

        # Create checkout session
        checkout_url = create_checkout_session(
            customer_id=customer_id,
            plan_type=request.plan,
            success_url=str(request.success_url),
            cancel_url=str(request.cancel_url),
            user_id=user_id,
        )

        logger.info("Created checkout session for user %s on plan %s", user_id, request.plan)

        return CheckoutResponse(checkout_url=checkout_url)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating checkout for user %s: %s", user['id'], str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session",
        ) from e


@router.post(
    "/reactivate",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Reactivate subscription",
    description="Reactivate a cancelled subscription",
)
async def reactivate_user_subscription(
    user: dict = Depends(get_current_user),
):
    """
    Reactivate a cancelled subscription.
    
    If current_period_end is in the past, payment is required to start a new subscription.
    If current_period_end is in the future, reactivates the subscription immediately.
    """
    try:
        user_id = user["id"]

        subscription = get_user_subscription(user_id)

        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No subscription found",
            )

        if not subscription.stripe_subscription_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reactivate free tier subscription",
            )

        await reactivate_subscription(subscription.stripe_subscription_id)

        update_data = SubscriptionUpdate(
            status=subscription.status, 
            is_active=True,  
            current_period_end=None
        )
        updated_subscription = update_user_subscription(user_id, update_data)

        logger.info("Reactivated subscription for user %s", user_id)

        return SubscriptionResponse(
            id=updated_subscription.id,
            plan=updated_subscription.status,
            is_active=updated_subscription.is_active,
            stripe_customer_id=updated_subscription.stripe_customer_id,
            stripe_subscription_id=updated_subscription.stripe_subscription_id,
            current_period_end=updated_subscription.current_period_end,
            created_at=updated_subscription.created_at,
            updated_at=updated_subscription.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error reactivating subscription for user %s: %s", user['id'], str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reactivate subscription",
        ) from e


@router.post(
    "/cancel",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel subscription",
    description="Cancel the user's active subscription",
)
async def cancel_user_subscription(
    request: CancelSubscriptionRequest,
    user: dict = Depends(get_current_user),
):
    """
    Cancel the user's active subscription.

    If at_period_end=True, cancellation will occur at the end of the billing period.
    If at_period_end=False, cancellation is immediate.
    """
    try:
        user_id = user["id"]
        subscription = get_user_subscription(user_id)

        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active subscription found",
            )

        if not subscription.stripe_subscription_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel free tier subscription",
            )

        # Cancel in Stripe
        cancel_subscription(
            subscription.stripe_subscription_id,
            at_period_end=request.at_period_end,
        )

        update_data = SubscriptionUpdate(
            status=subscription.status, 
            is_active=False,  
        )
        updated_subscription = update_user_subscription(user_id, update_data)

        logger.info("Canceled subscription for user %s", user_id)

        return SubscriptionResponse(
            id=updated_subscription.id,
            plan=updated_subscription.status,
            is_active=updated_subscription.is_active,
            stripe_customer_id=updated_subscription.stripe_customer_id,
            stripe_subscription_id=updated_subscription.stripe_subscription_id,
            current_period_end=updated_subscription.current_period_end,
            created_at=updated_subscription.created_at,
            updated_at=updated_subscription.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error canceling subscription for user %s: %s", user['id'], str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel subscription",
        ) from e


@router.get(
    "/usage",
    response_model=UsageResponse,
    status_code=status.HTTP_200_OK,
    summary="Get usage statistics",
    description="Get current message usage and remaining messages for today",
)
async def get_usage(user: dict = Depends(get_current_user)):
    """
    Get user's current message usage statistics.

    Returns:
    - message_count: Messages sent in current 24-hour window
    - limit: Daily message limit (None for unlimited)
    - remaining: Messages left today (None for unlimited)
    - percent_used: Percentage of limit used (0-100)
    - should_reset: Whether the 24-hour window has elapsed
    - time_until_reset: Time until rolling window resets
    """
    try:
        user_id = user["id"]

        # Get user's subscription and usage
        subscription = get_or_create_user_subscription(user_id)
        usage = get_user_usage(user_id)

        # Calculate comprehensive stats
        stats = calculate_usage_stats(usage, subscription.status)

        # Calculate reset_at (24 hours after last_reset_at)
        last_reset = usage.last_reset_at
        reset_at = last_reset + timedelta(hours=24)

        return UsageResponse(
            message_count=stats["message_count"],
            message_limit=stats["limit"],
            messages_remaining=stats["remaining"],
            last_reset_at=usage.last_reset_at,
            reset_at=reset_at,
            plan=subscription.status,
        )

    except Exception as e:
        logger.error("Error fetching usage for user %s: %s", user['id'], str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch usage statistics",
        ) from e


@router.post(
    "/usage/increment",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Increment message usage",
    description="Internal endpoint to track message usage (called by websocket handler)",
)
async def track_message_usage(user: dict = Depends(get_current_user)):
    """
    Increment message usage counter for the current user.

    This endpoint is called by the websocket handler after a message is successfully sent.
    Used internally to track daily message quota.
    """
    try:
        user_id = user["id"]

        # Increment message count
        increment_user_message_count(user_id)

        logger.debug("Incremented message usage for user %s", user_id)

    except Exception as e:
        logger.error("Error incrementing usage for user %s: %s", user['id'], str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to track usage",
        ) from e


@router.get(
    "/plans",
    response_model=PlansListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all available plans",
    description="Get all available subscription plans with their details from Stripe",
)
async def list_plans():
    """
    Get all available subscription plans.

    Returns plan details including pricing, features, and message limits.
    Plan data is fetched from Stripe to ensure it's always up-to-date.
    """
    try:
        plans = []

        # Free Plan
        plans.append(
            PlanDetailsResponse(
                type=PlanType.FREE,
                name="Free",
                description="Perfect for getting started",
                price=0,
                currency="eur",
                interval="month",
                messages_per_day=1,
                features=[
                    PlanFeature(name="1 message per day"),
                    PlanFeature(name="Natal chart creation"),
                    PlanFeature(name="No chat history"),
                ],
                stripe_price_id=None,
                stripe_product_id=None,
            )
        )

        # Basic Plan
        try:
            basic_price_id = get_stripe_price_id(PlanType.BASIC)
            if basic_price_id:
                price = stripe.Price.retrieve(basic_price_id)
                product = stripe.Product.retrieve(price.product)

                plans.append(
                    PlanDetailsResponse(
                        type=PlanType.BASIC,
                        name="Basic",
                        description="For regular astrology exploration",
                        price=price.unit_amount,
                        currency=price.currency,
                        interval=price.recurring.interval if price.recurring else "month",
                        messages_per_day=3,
                        features=[
                            PlanFeature(name="3 messages per day"),
                            PlanFeature(name="Natal chart creation"),
                            PlanFeature(name="Chat history saved"),
                            PlanFeature(name="Daily insights"),
                        ],
                        stripe_price_id=basic_price_id,
                        stripe_product_id=product.id,
                    )
                )
        except stripe.error.StripeError as e:
            logger.error("Error fetching Basic plan from Stripe: %s", str(e))
            # Continue with other plans on error

        # Pro Plan
        try:
            pro_price_id = get_stripe_price_id(PlanType.PRO)
            if pro_price_id:
                price = stripe.Price.retrieve(pro_price_id)
                product = stripe.Product.retrieve(price.product)

                plans.append(
                    PlanDetailsResponse(
                        type=PlanType.PRO,
                        name="Pro",
                        description="For unlimited cosmic insights",
                        price=price.unit_amount,
                        currency=price.currency,
                        interval=price.recurring.interval if price.recurring else "month",
                        messages_per_day=None,  # Unlimited
                        features=[
                            PlanFeature(name="Unlimited messages"),
                            PlanFeature(name="Natal chart creation"),
                            PlanFeature(name="Full chat history"),
                            PlanFeature(name="Advanced insights"),
                            PlanFeature(name="Priority support"),
                        ],
                        stripe_price_id=pro_price_id,
                        stripe_product_id=product.id,
                    )
                )
        except stripe.error.StripeError as e:
            logger.error("Error fetching Pro plan from Stripe: %s", str(e))
            # Continue with other plans on error

        logger.info("Retrieved %d plans from Stripe", len(plans))
        return PlansListResponse(plans=plans)

    except Exception as e:
        logger.error("Error fetching plans: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch subscription plans",
        ) from e

