"""
Usage limits and purchase configuration.

Defines message limits for free tier and purchase-related constants.
"""

from datetime import datetime, timedelta, timezone

# Free tier limits
FREE_MESSAGE_LIMIT = 1
FREE_WINDOW_HOURS = 48

# Credit amounts per product
CREDIT_AMOUNTS = {"pack_10": 10}

# Pass durations per product
PASS_DURATIONS = {"day_1": timedelta(days=1), "week_1": timedelta(weeks=1)}

# Lifetime expiry sentinel
LIFETIME_EXPIRY = datetime(2099, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

# WebSocket limits
MAX_MESSAGE_LENGTH = 10000  # Characters
MAX_CONTEXT_TOKENS = 8000
