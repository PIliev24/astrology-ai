"""
Stripe subscription service for handling payment integration.
Manages customers, subscriptions, checkout sessions, and webhook events.
"""

import logging
from typing import Optional

import stripe
from fastapi import HTTPException, status

from models.subscription import PlanType, Subscription, SubscriptionStatus

logger = logging.getLogger(__name__)

# Initialize Stripe with API key from environment
stripe.api_key = __import__("os").getenv("STRIPE_SECRET_KEY")

# Stripe Price IDs mapping (to be filled from environment variables)
# Format: {plan_type: stripe_price_id}
STRIPE_PRICE_IDS = {
    PlanType.FREE: None,  # Free tier has no price ID (no billing)
    PlanType.BASIC: __import__("os").getenv("STRIPE_PRICE_ID_BASIC"),
    PlanType.PRO: __import__("os").getenv("STRIPE_PRICE_ID_PRO"),
}


def get_stripe_price_id(plan_type: PlanType) -> Optional[str]:
    """
    Get the Stripe price ID for a subscription plan.
    
    Args:
        plan_type: The subscription plan type
    
    Returns:
        Stripe price ID or None for free tier
    
    Raises:
        ValueError: If price ID not configured for the plan
    """
    price_id = STRIPE_PRICE_IDS.get(plan_type)
    
    if plan_type != PlanType.FREE and not price_id:
        raise ValueError(
            f"Stripe price ID not configured for {plan_type} plan. "
            f"Set STRIPE_PRICE_ID_{plan_type.upper()} environment variable."
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
    
    Raises:
        HTTPException: If Stripe API fails
    """
    try:
        # Search for existing customer by email
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
    plan_type: PlanType,
    success_url: str,
    cancel_url: str,
    user_id: Optional[str] = None,
) -> str:
    """
    Create a Stripe Checkout session for subscription.
    
    Args:
        customer_id: Stripe customer ID
        plan_type: Subscription plan to checkout
        success_url: URL to redirect after successful payment
        cancel_url: URL to redirect after cancellation
        user_id: Application user ID for metadata
    
    Returns:
        Stripe Checkout session URL
    
    Raises:
        HTTPException: If checkout creation fails
    """
    try:
        if plan_type == PlanType.FREE:
            raise ValueError("Cannot create checkout session for free tier")
        
        price_id = get_stripe_price_id(plan_type)
        
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"user_id": user_id} if user_id else {},
            subscription_data={
                "metadata": {"user_id": user_id} if user_id else {},
            },
        )
        
        logger.info(
            "Created Checkout session %s for customer %s on plan %s",
            session.id, customer_id, plan_type
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


def get_subscription_from_stripe(subscription_id: str) -> dict:
    """
    Fetch subscription details from Stripe.
    
    Args:
        subscription_id: Stripe subscription ID
    
    Returns:
        Dictionary with subscription data
    
    Raises:
        HTTPException: If subscription not found or API fails
    """
    try:
        # Expand items to get price information
        subscription = stripe.Subscription.retrieve(
            subscription_id,
            expand=["items.data.price"]
        )
        
        # Get price_id from items
        price_id = None
        if subscription.items and hasattr(subscription.items, 'data') and subscription.items.data:
            price_id = subscription.items.data[0].price.id if subscription.items.data[0].price else None
        
        return {
            "id": subscription.id,
            "customer_id": subscription.customer,
            "status": subscription.status,
            "price_id": price_id,
            "current_period_start": subscription.current_period_start,
            "current_period_end": subscription.current_period_end,
            "cancel_at": subscription.cancel_at,
            "canceled_at": subscription.canceled_at,
            "metadata": subscription.metadata or {},
        }
    except stripe.error.InvalidRequestError as exc:
        logger.error("Stripe subscription %s not found", subscription_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        ) from exc
    except stripe.error.StripeError as exc:
        logger.error("Stripe error fetching subscription: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch subscription: {str(exc)}",
        ) from exc


def cancel_subscription(subscription_id: str, at_period_end: bool = True):
    """
    Cancel a Stripe subscription.
    
    Args:
        subscription_id: Stripe subscription ID
        at_period_end: If True, cancel at period end; if False, cancel immediately
    
    Returns:
        None
    
    Raises:
        HTTPException: If cancellation fails
    """
    try:
        if at_period_end:
            stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True,
            )
            logger.info("Scheduled cancellation at period end for subscription %s", subscription_id)
        else:
            stripe.Subscription.delete(subscription_id)
            logger.info("Immediately canceled subscription %s", subscription_id)
    
    except stripe.error.InvalidRequestError as exc:
        logger.error("Stripe subscription %s not found", subscription_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        ) from exc
    except stripe.error.StripeError as exc:
        logger.error("Stripe error canceling subscription %s: %s", subscription_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel subscription: {str(exc)}",
        ) from exc


async def reactivate_subscription(subscription_id: str):
    """
    Reactivate a cancelled Stripe subscription by removing the cancellation.
    
    Sets cancel_at_period_end to False in Stripe, which removes the scheduled cancellation.
    The router will handle updating is_active in the database.
    
    Args:
        subscription_id: Stripe subscription ID
    
    Raises:
        HTTPException: If reactivation fails
    """
    try:
        # Remove cancellation by setting cancel_at_period_end to False
        stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=False,
            cancel_at=None,
        )
        
        logger.info("Reactivated subscription %s in Stripe", subscription_id)
    
    except stripe.error.InvalidRequestError as exc:
        logger.error("Stripe subscription %s not found for reactivation", subscription_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        ) from exc
    except stripe.error.StripeError as exc:
        logger.error("Stripe error reactivating subscription: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reactivate subscription: {str(exc)}",
        ) from exc


def determine_plan_from_price_id(price_id: str) -> PlanType:
    """
    Determine subscription plan type from Stripe price ID.
    
    Args:
        price_id: Stripe price ID
    
    Returns:
        Subscription plan type
    
    Raises:
        ValueError: If price ID not recognized
    """
    for plan_type, stripe_price_id in STRIPE_PRICE_IDS.items():
        if stripe_price_id == price_id:
            return plan_type
    
    raise ValueError(f"Unknown Stripe price ID: {price_id}")


def map_stripe_status_to_subscription_status(
    stripe_status: str,
) -> SubscriptionStatus:
    """
    Map Stripe subscription status to application status enum.
    
    Args:
        stripe_status: Stripe subscription status string
    
    Returns:
        SubscriptionStatus enum value
    """
    status_mapping = {
        "active": SubscriptionStatus.ACTIVE,
        "past_due": SubscriptionStatus.PAST_DUE,
        "unpaid": SubscriptionStatus.PAST_DUE,
        "canceled": SubscriptionStatus.CANCELED,
        "incomplete": SubscriptionStatus.INCOMPLETE,
        "incomplete_expired": SubscriptionStatus.INCOMPLETE_EXPIRED,
        "trialing": SubscriptionStatus.ACTIVE,
    }
    
    return status_mapping.get(stripe_status, SubscriptionStatus.INCOMPLETE)


def verify_webhook_signature(payload: bytes, signature: str, webhook_secret: str) -> dict:
    """
    Verify and parse a Stripe webhook signature.
    
    Args:
        payload: Raw webhook payload body
        signature: Stripe-Signature header value
        webhook_secret: Webhook endpoint secret from Stripe
    
    Returns:
        Parsed event data
    
    Raises:
        HTTPException: If signature verification fails
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


def handle_checkout_session_completed(session_data: dict) -> dict:
    """
    Handle checkout.session.completed webhook event.
    
    Args:
        session_data: Stripe checkout session data
    
    Returns:
        Data needed to update subscription in database
    """
    return {
        "stripe_customer_id": session_data.get("customer"),
        "stripe_subscription_id": session_data.get("subscription"),
        "stripe_price_id": session_data.get("line_items", {}).get("data", [{}])[0].get("price", {}).get("id"),
        "user_id": session_data.get("metadata", {}).get("user_id"),
    }


def handle_customer_subscription_updated(subscription_data: dict) -> dict:
    """
    Handle customer.subscription.updated webhook event.
    
    Args:
        subscription_data: Stripe subscription data
    
    Returns:
        Data needed to update subscription in database
    """
    price_id = None
    if subscription_data.get("items", {}).get("data"):
        price_id = subscription_data["items"]["data"][0].get("price", {}).get("id")
    
    return {
        "stripe_subscription_id": subscription_data.get("id"),
        "stripe_customer_id": subscription_data.get("customer"),
        "status": map_stripe_status_to_subscription_status(subscription_data.get("status", "incomplete")),
        "stripe_price_id": price_id,
        "current_period_start": subscription_data.get("current_period_start"),
        "current_period_end": subscription_data.get("current_period_end"),
        "cancel_at": subscription_data.get("cancel_at"),
    }


def initialize_free_tier_subscription(user_id: str) -> Subscription:
    """
    Initialize a free tier subscription for a new user on first signup.
    
    This function is called when a new user registers to set up their
    default free tier subscription without requiring Stripe interaction.
    
    Args:
        user_id: UUID of the new user
    
    Returns:
        Subscription: The created free tier subscription
    
    Raises:
        HTTPException: If subscription creation fails
    """
    from services.database import get_or_create_user_subscription
    
    try:
        # Get or create subscription - if it doesn't exist, a free tier one will be created
        subscription = get_or_create_user_subscription(user_id)
        
        logger.info("Initialized free tier subscription for user %s", user_id)
        return subscription
    
    except Exception as e:
        logger.error("Failed to initialize subscription for user %s: %s", user_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize subscription",
        ) from e

