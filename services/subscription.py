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
            logger.info(f"Found existing Stripe customer {customers.data[0].id} for user {user_id}")
            return customers.data[0].id
        
        # Create new customer
        customer_data = {
            "email": email,
            "metadata": {"user_id": user_id},
        }
        
        if name:
            customer_data["name"] = name
        
        customer = stripe.Customer.create(**customer_data)
        logger.info(f"Created Stripe customer {customer.id} for user {user_id}")
        
        return customer.id
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating/fetching customer: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create Stripe customer: {str(e)}",
        )


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
            f"Created Checkout session {session.id} for customer {customer_id} "
            f"on plan {plan_type}"
        )
        
        return session.url
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create checkout session: {str(e)}",
        )
    except ValueError as e:
        logger.error(f"Invalid checkout request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


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
        subscription = stripe.Subscription.retrieve(subscription_id)
        return {
            "id": subscription.id,
            "customer_id": subscription.customer,
            "status": subscription.status,
            "price_id": subscription.items.data[0].price.id if subscription.items.data else None,
            "current_period_start": subscription.current_period_start,
            "current_period_end": subscription.current_period_end,
            "cancel_at": subscription.cancel_at,
            "canceled_at": subscription.canceled_at,
        }
    except stripe.error.InvalidRequestError:
        logger.error(f"Stripe subscription {subscription_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error fetching subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch subscription: {str(e)}",
        )


def cancel_subscription(subscription_id: str, at_period_end: bool = True) -> dict:
    """
    Cancel a Stripe subscription.
    
    Args:
        subscription_id: Stripe subscription ID
        at_period_end: If True, cancel at period end; if False, cancel immediately
    
    Returns:
        Updated subscription data
    
    Raises:
        HTTPException: If cancellation fails
    """
    try:
        if at_period_end:
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True,
            )
            logger.info(f"Scheduled cancellation for subscription {subscription_id} at period end")
        else:
            subscription = stripe.Subscription.delete(subscription_id)
            logger.info(f"Immediately canceled subscription {subscription_id}")
        
        return {
            "id": subscription.id,
            "status": subscription.status,
            "cancel_at": subscription.cancel_at,
            "canceled_at": subscription.canceled_at,
        }
    
    except stripe.error.InvalidRequestError:
        logger.error(f"Stripe subscription {subscription_id} not found for cancellation")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error canceling subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel subscription: {str(e)}",
        )


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
    except ValueError:
        logger.error("Invalid webhook payload")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload",
        )
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid webhook signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )


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

