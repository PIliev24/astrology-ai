"""
Usage tracking service for usage-based purchase model.
Handles credit-based, time-pass-based, and free tier message access.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from constants.limits import FREE_MESSAGE_LIMIT, FREE_WINDOW_HOURS
from models.subscription import PlanType, Subscription, Usage


def get_effective_plan(subscription: Subscription) -> PlanType:
    """
    Determine the user's effective plan based on their subscription state.

    Priority: lifetime > active unlimited pass > credits > free
    """
    now = datetime.now(timezone.utc)

    if subscription.unlimited_until:
        until = subscription.unlimited_until
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)

        if until > now:
            # Far-future date means lifetime
            if until.year >= 2099:
                return PlanType.LIFETIME
            return PlanType.UNLIMITED

    if subscription.message_credits > 0:
        return PlanType.CREDITS

    return PlanType.FREE


def can_send_message(subscription: Subscription, usage: Usage) -> bool:
    """
    Check if user is allowed to send a message.

    1. unlimited_until in the future -> YES
    2. message_credits > 0 -> YES (credit deducted after message)
    3. Free tier: 1 msg per 48h rolling window
    4. Otherwise -> NO
    """
    plan = get_effective_plan(subscription)

    if plan in (PlanType.LIFETIME, PlanType.UNLIMITED):
        return True

    if plan == PlanType.CREDITS:
        return True

    # Free tier: check rolling window
    return _free_tier_can_send(usage)


def _free_tier_can_send(usage: Usage) -> bool:
    """Check if free tier user can send within their rolling window."""
    if _should_reset_usage(usage.last_reset_at):
        return True
    return usage.message_count < FREE_MESSAGE_LIMIT


def should_reset_daily_usage(usage: Usage) -> bool:
    """Check if the user's free tier usage window should be reset."""
    return _should_reset_usage(usage.last_reset_at)


def get_remaining_free_messages(usage: Usage) -> int:
    """Get remaining free messages in current window."""
    if _should_reset_usage(usage.last_reset_at):
        return FREE_MESSAGE_LIMIT
    return max(0, FREE_MESSAGE_LIMIT - usage.message_count)


def get_time_until_reset(usage: Usage) -> timedelta:
    """Get time until the free tier rolling window resets."""
    if usage.last_reset_at is None:
        return timedelta(0)

    last_reset = usage.last_reset_at
    if last_reset.tzinfo is None:
        last_reset = last_reset.replace(tzinfo=timezone.utc)

    reset_time = last_reset + timedelta(hours=FREE_WINDOW_HOURS)
    now = datetime.now(timezone.utc)
    remaining = reset_time - now

    if remaining.total_seconds() <= 0:
        return timedelta(0)
    return remaining


def is_paid_plan(plan: PlanType) -> bool:
    """Check if a plan type is a paid plan (for chat history saving)."""
    return plan in (PlanType.CREDITS, PlanType.UNLIMITED, PlanType.LIFETIME)


def _should_reset_usage(last_reset_at: Optional[datetime]) -> bool:
    """Check if the free tier window has elapsed."""
    if last_reset_at is None:
        return True

    now = datetime.now(timezone.utc)

    if last_reset_at.tzinfo is None:
        last_reset_at = last_reset_at.replace(tzinfo=timezone.utc)

    return (now - last_reset_at) >= timedelta(hours=FREE_WINDOW_HOURS)
