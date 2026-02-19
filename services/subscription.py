"""
Stripe payment service for one-time purchases.
Handles customers, checkout sessions, and webhook verification.
"""

import logging
import os
from typing import Optional

import stripe
from fastapi import HTTPException, status

from models.subscription import ProductType

logger = logging.getLogger(__name__)

# Initialize Stripe with API key from environment
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Stripe Price IDs mapping for one-time purchase products
STRIPE_PRICE_IDS = {
    ProductType.PACK_10: os.getenv("STRIPE_PRICE_ID_PACK_10"),
    ProductType.DAY_1: os.getenv("STRIPE_PRICE_ID_DAY_1"),
    ProductType.WEEK_1: os.getenv("STRIPE_PRICE_ID_WEEK_1"),
    ProductType.LIFETIME: os.getenv("STRIPE_PRICE_ID_LIFETIME"),
}


def get_stripe_price_id(product_type: ProductType) -> Optional[str]:
    """
    Get the Stripe price ID for a product.

    Args:
        product_type: The product type

    Returns:
        Stripe price ID

    Raises:
        ValueError: If price ID not configured for the product
    """
    price_id = STRIPE_PRICE_IDS.get(product_type)

    if not price_id:
        raise ValueError(
            f"Stripe price ID not configured for {product_type.value}. "
            f"Set the corresponding STRIPE_PRICE_ID_* environment variable."
        )

    return price_id


def get_or_create_customer(user_id: str, email: str, name: Optional[str] = None) -> str:
    """
    Get existing Stripe customer or create a new one.

    Args:
        user_id: Application user ID
        email: User's email address
        name: User's full name (optional)

    Returns:
        Stripe customer ID
    """
    try:
        customers = stripe.Customer.list(email=email, limit=1)

        if customers.data:
            logger.info("Found existing Stripe customer %s for user %s", customers.data[0].id, user_id)
            return customers.data[0].id

        customer = stripe.Customer.create(
            name=name or "",
            email=email,
        )

        logger.info("Created Stripe customer %s for user %s", customer.id, user_id)
        return customer.id

    except stripe.error.StripeError as exc:
        logger.error("Stripe error creating/fetching customer: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create Stripe customer: {str(exc)}",
        ) from exc


def create_checkout_session(
    customer_id: str,
    product_type: ProductType,
    success_url: str,
    cancel_url: str,
    user_id: Optional[str] = None,
) -> str:
    """
    Create a Stripe Checkout session for a one-time purchase.

    Args:
        customer_id: Stripe customer ID
        product_type: Product to purchase
        success_url: URL to redirect after successful payment
        cancel_url: URL to redirect after cancellation
        user_id: Application user ID for metadata

    Returns:
        Stripe Checkout session URL
    """
    try:
        price_id = get_stripe_price_id(product_type)

        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "user_id": user_id,
                "product_type": product_type.value,
            } if user_id else {},
            allow_promotion_codes=True,
        )

        logger.info(
            "Created Checkout session %s for customer %s, product %s",
            session.id, customer_id, product_type.value
        )

        return session.url

    except stripe.error.StripeError as exc:
        logger.error("Stripe error creating checkout session: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create checkout session: {str(exc)}",
        ) from exc
    except ValueError as exc:
        logger.error("Invalid checkout request: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


def determine_product_from_price_id(price_id: str) -> ProductType:
    """
    Determine product type from Stripe price ID.

    Args:
        price_id: Stripe price ID

    Returns:
        Product type

    Raises:
        ValueError: If price ID not recognized
    """
    for product_type, stripe_price_id in STRIPE_PRICE_IDS.items():
        if stripe_price_id == price_id:
            return product_type

    raise ValueError(f"Unknown Stripe price ID: {price_id}")


def verify_webhook_signature(payload: bytes, signature: str, webhook_secret: str) -> dict:
    """
    Verify and parse a Stripe webhook signature.

    Args:
        payload: Raw webhook payload body
        signature: Stripe-Signature header value
        webhook_secret: Webhook endpoint secret from Stripe

    Returns:
        Parsed event data
    """
    try:
        event = stripe.Webhook.construct_event(payload, signature, webhook_secret)
        return event
    except ValueError as exc:
        logger.error("Invalid webhook payload")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload",
        ) from exc
    except stripe.error.SignatureVerificationError as exc:
        logger.error("Invalid webhook signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        ) from exc


def initialize_free_tier_subscription(user_id: str):
    """
    Initialize a free tier subscription for a new user on first signup.
    """
    from services.database import get_or_create_user_subscription

    try:
        subscription = get_or_create_user_subscription(user_id)
        logger.info("Initialized free tier subscription for user %s", user_id)
        return subscription
    except Exception as e:
        logger.error("Failed to initialize subscription for user %s: %s", user_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize subscription",
        ) from e
