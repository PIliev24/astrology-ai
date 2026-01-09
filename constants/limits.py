"""
Plan limits and rate restrictions.

Defines message limits and other quotas for different subscription tiers.
"""

from typing import Optional

# Import will be updated when models are refactored
# For now, use string keys to avoid circular imports
PLAN_MESSAGE_LIMITS: dict[str, Optional[int]] = {
    "FREE": 1,
    "BASIC": 3,
    "PRO": None,  # Unlimited
}

# Time window for rolling usage (24 hours in seconds)
USAGE_WINDOW_SECONDS = 24 * 60 * 60

# WebSocket limits
MAX_MESSAGE_LENGTH = 10000  # Characters
MAX_CONTEXT_TOKENS = 8000


def get_message_limit(plan_type: str) -> Optional[int]:
    """
    Get message limit for a plan type.

    Args:
        plan_type: The subscription plan type (FREE, BASIC, PRO)

    Returns:
        Message limit (int) or None for unlimited
    """
    return PLAN_MESSAGE_LIMITS.get(plan_type.upper())


def is_unlimited(plan_type: str) -> bool:
    """
    Check if a plan has unlimited messages.

    Args:
        plan_type: The subscription plan type

    Returns:
        True if the plan has no message limit
    """
    return get_message_limit(plan_type) is None
