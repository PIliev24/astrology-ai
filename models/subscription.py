"""
Subscription models for Stripe integration.
All subscription data is sourced from Stripe with local database caching.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PlanType(str, Enum):
    """Subscription plan types."""

    FREE = "free"
    BASIC = "basic"
    PRO = "pro"


class SubscriptionStatus(str, Enum):
    """Subscription billing status from Stripe."""

    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"


class SubscriptionBase(BaseModel):
    """Base subscription model with common fields."""

    stripe_customer_id: str
    stripe_subscription_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    status: PlanType = PlanType.FREE
    is_active: bool = True
    current_period_end: Optional[datetime] = None


class SubscriptionCreate(SubscriptionBase):
    """Model for creating a new subscription."""

    user_id: UUID


class SubscriptionUpdate(BaseModel):
    """Model for updating subscription from Stripe webhook."""

    stripe_subscription_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    status: Optional[PlanType] = None
    is_active: Optional[bool] = None
    current_period_end: Optional[datetime] = None


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
    stripe_subscription_id: Optional[str] = None
    current_period_end: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UsageBase(BaseModel):
    """Base usage tracking model."""

    message_count: int = Field(ge=0, description="Number of messages sent in current 24h window")
    last_reset_at: datetime = Field(description="When the 24h window started")


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

    message_count: int = Field(description="Messages used in current 24h window")
    message_limit: Optional[int] = Field(description="Total allowed messages (based on plan, None for unlimited)")
    messages_remaining: Optional[int] = Field(description="Messages remaining in 24h window (None for unlimited)")
    last_reset_at: datetime = Field(description="When the current window started")
    reset_at: datetime = Field(description="When the window will reset")
    plan: PlanType = Field(description="Current subscription plan")

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


class CancelSubscriptionRequest(BaseModel):
    """Request to cancel subscription."""

    immediate: bool = Field(
        default=False,
        description="If true, cancel immediately. If false, cancel at end of billing period",
    )


class WebhookEventData(BaseModel):
    """Generic webhook event data structure."""

    type: str = Field(description="Event type (e.g., 'checkout.session.completed')")
    data: dict = Field(description="Event data from Stripe")


class StripePriceMetadata(BaseModel):
    """Metadata stored in Stripe price object."""

    plan_name: str = Field(description="Plan name (free, basic, pro)")
    message_limit: Optional[int] = Field(
        default=None, description="Daily message limit (None for unlimited)"
    )

