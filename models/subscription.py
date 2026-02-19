"""
Subscription models for Stripe integration.
Usage-based purchase model: message credits, time-limited passes, and lifetime access.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PlanType(str, Enum):
    """Effective plan types based on user's current state."""

    FREE = "free"
    CREDITS = "credits"
    UNLIMITED = "unlimited"
    LIFETIME = "lifetime"


class ProductType(str, Enum):
    """Purchasable product types."""

    PACK_10 = "pack_10"
    DAY_1 = "day_1"
    WEEK_1 = "week_1"
    LIFETIME = "lifetime"


class SubscriptionBase(BaseModel):
    """Base subscription model with common fields."""

    stripe_customer_id: str
    stripe_subscription_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    status: PlanType = PlanType.FREE
    is_active: bool = True
    current_period_end: Optional[datetime] = None
    message_credits: int = 0
    unlimited_until: Optional[datetime] = None


class SubscriptionCreate(SubscriptionBase):
    """Model for creating a new subscription."""

    user_id: UUID


class SubscriptionUpdate(BaseModel):
    """Model for updating subscription from webhook or purchase."""

    stripe_subscription_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    status: Optional[PlanType] = None
    is_active: Optional[bool] = None
    current_period_end: Optional[datetime] = None
    message_credits: Optional[int] = None
    unlimited_until: Optional[datetime] = None


class Subscription(SubscriptionBase):
    """Full subscription model from database."""

    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SubscriptionResponse(BaseModel):
    """Subscription response for API endpoints."""

    id: UUID
    plan: PlanType
    is_active: bool
    stripe_customer_id: str
    message_credits: int = 0
    unlimited_until: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UsageBase(BaseModel):
    """Base usage tracking model."""

    message_count: int = Field(ge=0, description="Number of messages sent in current window")
    last_reset_at: datetime = Field(description="When the usage window started")


class UsageCreate(UsageBase):
    """Model for creating usage record."""

    user_id: UUID


class Usage(UsageBase):
    """Full usage model from database."""

    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UsageResponse(BaseModel):
    """Usage response for API endpoints."""

    effective_plan: PlanType = Field(description="Current effective plan type")
    message_credits: int = Field(description="Remaining message credits")
    unlimited_until: Optional[datetime] = Field(description="When unlimited access expires (None if not active)")
    free_messages_used: int = Field(description="Free messages used in current window")
    free_messages_remaining: Optional[int] = Field(description="Free messages remaining (None if paid)")
    window_reset_at: Optional[datetime] = Field(description="When the free usage window resets")

    class Config:
        from_attributes = True


class CheckoutSessionRequest(BaseModel):
    """Request to create Stripe Checkout session."""

    price_id: str = Field(description="Stripe price ID (price_1ABC123XYZ)")
    success_url: Optional[str] = Field(
        default=None,
        description="URL to redirect to on successful checkout (frontend will add session_id param)",
    )
    cancel_url: Optional[str] = Field(
        default=None,
        description="URL to redirect to if user cancels (frontend will add session_id param)",
    )


class CheckoutSessionResponse(BaseModel):
    """Response with Stripe Checkout session details."""

    session_id: str = Field(description="Stripe checkout session ID")
    stripe_client_secret: Optional[str] = Field(
        default=None, description="Client secret for embedded checkout"
    )
    url: str = Field(description="URL to redirect user to Stripe Checkout")


class WebhookEventData(BaseModel):
    """Generic webhook event data structure."""

    type: str = Field(description="Event type (e.g., 'checkout.session.completed')")
    data: dict = Field(description="Event data from Stripe")
