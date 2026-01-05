"""
Usage tracking service for subscription-based message limits.
Handles rolling 24-hour window message counting and limit enforcement.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from models.subscription import PlanType, Usage


# Plan message limits (daily rolling 24h window)
PLAN_LIMITS = {
    PlanType.FREE: 1,
    PlanType.BASIC: 3,
    PlanType.PRO: None,  # Unlimited
}


def get_plan_message_limit(plan_type: PlanType) -> Optional[int]:
    """
    Get the daily message limit for a subscription plan.
    
    Args:
        plan_type: The subscription plan type
    
    Returns:
        Message limit (None for unlimited)
    """
    return PLAN_LIMITS.get(plan_type)


def is_message_limit_exceeded(usage: Usage, plan_type: PlanType) -> bool:
    """
    Check if user has exceeded their daily message limit.
    Uses rolling 24-hour window from usage.last_reset_at.
    
    Args:
        usage: User's current usage record
        plan_type: User's subscription plan type
    
    Returns:
        True if limit is exceeded, False otherwise
    """
    limit = get_plan_message_limit(plan_type)
    
    # Pro plan has unlimited messages
    if limit is None:
        return False
    
    # Check if 24 hours have passed since last reset
    if _should_reset_usage(usage.last_reset_at):
        return False
    
    # Check if current count exceeds limit
    return usage.message_count >= limit


def can_send_message(usage: Usage, plan_type: PlanType) -> bool:
    """
    Check if user is allowed to send another message.
    
    Args:
        usage: User's current usage record
        plan_type: User's subscription plan type
    
    Returns:
        True if user can send a message, False otherwise
    """
    return not is_message_limit_exceeded(usage, plan_type)


def get_remaining_messages(usage: Usage, plan_type: PlanType) -> int:
    """
    Get the number of remaining messages for today.
    
    Args:
        usage: User's current usage record
        plan_type: User's subscription plan type
    
    Returns:
        Number of remaining messages (negative if over limit)
    """
    limit = get_plan_message_limit(plan_type)
    
    # Pro plan has unlimited messages
    if limit is None:
        return 999999  # Return large number for UI display
    
    # Check if 24 hours have passed (would reset the count)
    if _should_reset_usage(usage.last_reset_at):
        return limit
    
    return max(0, limit - usage.message_count)


def get_messages_until_reset(usage: Usage) -> timedelta:
    """
    Get the time until the rolling 24-hour window resets.
    
    Args:
        usage: User's current usage record
    
    Returns:
        Timedelta until reset (0 if already reset)
    """
    if usage.last_reset_at is None:
        return timedelta(0)
    
    # Ensure last_reset_at is timezone-aware
    last_reset = usage.last_reset_at
    if last_reset.tzinfo is None:
        last_reset = last_reset.replace(tzinfo=timezone.utc)
    
    reset_time = last_reset + timedelta(hours=24)
    now = datetime.now(timezone.utc)
    
    time_until_reset = reset_time - now
    
    # Return 0 if already past reset time
    if time_until_reset.total_seconds() <= 0:
        return timedelta(0)
   
    return time_until_reset


def should_reset_daily_usage(usage: Usage) -> bool:
    """
    Check if the user's daily usage should be reset.
    Rolling 24-hour window from last_reset_at.
    
    Args:
        usage: User's current usage record
    
    Returns:
        True if 24 hours have passed, False otherwise
    """
    return _should_reset_usage(usage.last_reset_at)


def _should_reset_usage(last_reset_at: Optional[datetime]) -> bool:
    """
    Internal helper to check if 24 hours have passed since last reset.
    
    Args:
        last_reset_at: Timestamp of last reset
    
    Returns:
        True if 24 hours have passed, False otherwise
    """
    if last_reset_at is None:
        return True
    
    now = datetime.now(timezone.utc)
    
    # Ensure last_reset_at is timezone-aware
    if last_reset_at.tzinfo is None:
        last_reset_at = last_reset_at.replace(tzinfo=timezone.utc)
    
    time_elapsed = now - last_reset_at
    return time_elapsed >= timedelta(hours=24)


def calculate_usage_stats(usage: Usage, plan_type: PlanType) -> dict:
    """
    Calculate comprehensive usage statistics for a user.
    
    Args:
        usage: User's current usage record
        plan_type: User's subscription plan type
    
    Returns:
        Dictionary with usage statistics including:
        - message_count: Current messages used today
        - limit: Daily limit (None for unlimited)
        - remaining: Messages left (None for unlimited)
        - percent_used: Percentage of limit used (0-100, None for unlimited)
        - should_reset: Whether the window has passed 24 hours
        - time_until_reset: Timedelta until window resets
    """
    limit = get_plan_message_limit(plan_type)
    should_reset = should_reset_daily_usage(usage)
    
    current_count = 0 if should_reset else usage.message_count
    
    remaining = None
    percent_used = None
    
    if limit is not None:
        remaining = max(0, limit - current_count)
        percent_used = int((current_count / limit) * 100) if limit > 0 else 0
    
    return {
        "message_count": current_count,
        "limit": limit,
        "remaining": remaining,
        "percent_used": percent_used,
        "should_reset": should_reset,
        "time_until_reset": get_messages_until_reset(usage) if not should_reset else timedelta(0),
    }

