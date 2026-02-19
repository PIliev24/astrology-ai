"""
Subscription Router
Handles purchase checkout, usage tracking, and plan listing endpoints.
"""

import logging
from datetime import timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, HttpUrl
import stripe

from middleware.auth import get_current_user
from models.subscription import PlanType, ProductType, SubscriptionResponse, UsageResponse
from services.database import (
    get_or_create_user_subscription,
    get_user_usage,
)
from services.subscription import (
    get_or_create_customer,
    create_checkout_session,
    get_stripe_price_id,
    STRIPE_PRICE_IDS,
)
from services.usage_tracker import (
    get_effective_plan,
    get_remaining_free_messages,
    get_time_until_reset,
)
from constants.limits import FREE_WINDOW_HOURS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


# Request/Response Models
class CheckoutRequest(BaseModel):
    """Request to create a Stripe checkout session for a one-time purchase."""

    product: ProductType
    success_url: HttpUrl
    cancel_url: HttpUrl


class CheckoutResponse(BaseModel):
    """Checkout session response."""

    checkout_url: str


class PlanFeature(BaseModel):
    """Plan feature details."""

    name: str


class ProductDetailsResponse(BaseModel):
    """Details about a purchasable product."""

    type: ProductType
    name: str
    description: str
    price: int  # In cents (e.g., 199 = €1.99)
    currency: str
    features: list[PlanFeature]
    stripe_price_id: str


class ProductsListResponse(BaseModel):
    """List of all available products."""

    products: list[ProductDetailsResponse]


@router.get(
    "/me",
    response_model=SubscriptionResponse,
    summary="Get current subscription",
    description="Retrieve the current user's subscription details including credits and pass status",
)
async def get_my_subscription(user: dict = Depends(get_current_user)):
    """Get current user's subscription details."""
    try:
        user_id = user["id"]
        subscription = get_or_create_user_subscription(user_id)
        effective = get_effective_plan(subscription)

        return SubscriptionResponse(
            id=subscription.id,
            plan=effective,
            is_active=subscription.is_active,
            stripe_customer_id=subscription.stripe_customer_id,
            message_credits=subscription.message_credits,
            unlimited_until=subscription.unlimited_until,
            created_at=subscription.created_at,
            updated_at=subscription.updated_at,
        )
    except Exception as e:
        logger.error("Error fetching subscription for user %s: %s", user["id"], str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch subscription",
        ) from e


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Create checkout session",
    description="Generate a Stripe Checkout session for a one-time purchase",
)
async def create_checkout(
    request: CheckoutRequest,
    user: dict = Depends(get_current_user),
):
    """Create a Stripe Checkout session for purchasing a product."""
    try:
        user_id = user["id"]
        user_email = user.get("email", "")
        user_name = user.get("name")

        customer_id = get_or_create_customer(user_id, user_email, user_name)

        checkout_url = create_checkout_session(
            customer_id=customer_id,
            product_type=request.product,
            success_url=str(request.success_url),
            cancel_url=str(request.cancel_url),
            user_id=user_id,
        )

        logger.info("Created checkout session for user %s, product %s", user_id, request.product.value)

        return CheckoutResponse(checkout_url=checkout_url)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating checkout for user %s: %s", user["id"], str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session",
        ) from e


@router.get(
    "/usage",
    response_model=UsageResponse,
    status_code=status.HTTP_200_OK,
    summary="Get usage statistics",
    description="Get current message usage: credits, pass status, and free tier info",
)
async def get_usage(user: dict = Depends(get_current_user)):
    """Get user's current usage statistics."""
    try:
        user_id = user["id"]

        subscription = get_or_create_user_subscription(user_id)
        usage = get_user_usage(user_id)
        effective = get_effective_plan(subscription)

        free_remaining = None
        window_reset_at = None

        if effective == PlanType.FREE:
            free_remaining = get_remaining_free_messages(usage)
            last_reset = usage.last_reset_at
            if last_reset:
                window_reset_at = last_reset + timedelta(hours=FREE_WINDOW_HOURS)

        return UsageResponse(
            effective_plan=effective,
            message_credits=subscription.message_credits,
            unlimited_until=subscription.unlimited_until,
            free_messages_used=usage.message_count,
            free_messages_remaining=free_remaining,
            window_reset_at=window_reset_at,
        )

    except Exception as e:
        logger.error("Error fetching usage for user %s: %s", user["id"], str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch usage statistics",
        ) from e


@router.get(
    "/plans",
    response_model=ProductsListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all available products",
    description="Get all available purchase options with pricing from Stripe",
)
async def list_plans():
    """Get all available purchase products with pricing from Stripe."""
    try:
        products = []

        product_configs = [
            {
                "type": ProductType.PACK_10,
                "name": "10 Message Pack",
                "description": "10 messages to use anytime, no expiry",
                "features": [
                    PlanFeature(name="10 messages"),
                    PlanFeature(name="No expiration"),
                    PlanFeature(name="Chat history saved"),
                    PlanFeature(name="Stacks with existing credits"),
                ],
            },
            {
                "type": ProductType.DAY_1,
                "name": "1 Day Unlimited",
                "description": "Unlimited messages for 24 hours",
                "features": [
                    PlanFeature(name="Unlimited messages"),
                    PlanFeature(name="24 hours access"),
                    PlanFeature(name="Chat history saved"),
                    PlanFeature(name="Extends existing pass"),
                ],
            },
            {
                "type": ProductType.WEEK_1,
                "name": "1 Week Unlimited",
                "description": "Unlimited messages for 7 days",
                "features": [
                    PlanFeature(name="Unlimited messages"),
                    PlanFeature(name="7 days access"),
                    PlanFeature(name="Chat history saved"),
                    PlanFeature(name="Extends existing pass"),
                ],
            },
            {
                "type": ProductType.LIFETIME,
                "name": "Lifetime Unlimited",
                "description": "Permanent unlimited access forever",
                "features": [
                    PlanFeature(name="Unlimited messages forever"),
                    PlanFeature(name="Full chat history"),
                    PlanFeature(name="All future features"),
                    PlanFeature(name="One-time payment"),
                ],
            },
        ]

        for config in product_configs:
            try:
                price_id = get_stripe_price_id(config["type"])
                if price_id:
                    price = stripe.Price.retrieve(price_id)
                    products.append(
                        ProductDetailsResponse(
                            type=config["type"],
                            name=config["name"],
                            description=config["description"],
                            price=price.unit_amount,
                            currency=price.currency,
                            features=config["features"],
                            stripe_price_id=price_id,
                        )
                    )
            except (stripe.error.StripeError, ValueError) as e:
                logger.error("Error fetching product %s from Stripe: %s", config["type"].value, str(e))

        logger.info("Retrieved %d products from Stripe", len(products))
        return ProductsListResponse(products=products)

    except Exception as e:
        logger.error("Error fetching products: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch products",
        ) from e
