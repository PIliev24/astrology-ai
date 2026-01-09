"""
Subscription and usage database service.

Provides operations for managing user subscriptions and
tracking message usage with rolling 24-hour windows.
"""

import logging
from datetime import datetime
from typing import Optional

from core.clients.supabase import get_supabase_client
from core.exceptions import SubscriptionNotFoundError, AppException
from models.subscription import (
    Subscription,
    SubscriptionUpdate,
    Usage,
    PlanType,
)

logger = logging.getLogger(__name__)


class SubscriptionService:
    """
    Subscription and usage database operations.

    Unlike other services, subscriptions don't use the standard
    BaseService pattern because:
    1. Subscriptions are created via Stripe webhooks, not user action
    2. The "get or create" pattern is common for subscriptions
    3. Usage tracking has special increment/reset logic
    """

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            return get_supabase_client()
        return self._client

    # Subscription Operations

    def get_or_create(
        self,
        user_id: str,
        stripe_customer_id: Optional[str] = None,
    ) -> Subscription:
        """
        Get existing subscription or create free tier.

        Args:
            user_id: User ID
            stripe_customer_id: Optional Stripe customer ID

        Returns:
            User's subscription
        """
        try:
            # Try to get existing
            response = (
                self.client.table("user_subscriptions")
                .select("*")
                .eq("user_id", user_id)
                .execute()
            )

            if response.data and len(response.data) > 0:
                return Subscription(**response.data[0])

            # Create free tier
            customer_id = stripe_customer_id or f"cus_free_{user_id}"

            data = {
                "user_id": user_id,
                "stripe_customer_id": customer_id,
                "status": "free",
                "is_active": True,
            }

            create_response = self.client.table("user_subscriptions").insert(data).execute()

            if not create_response.data:
                raise AppException(message="Failed to create subscription")

            logger.info(f"Created free tier subscription for user {user_id}")
            return Subscription(**create_response.data[0])

        except AppException:
            raise
        except Exception as e:
            logger.error(f"Error getting or creating subscription: {e}")
            raise AppException(message="Failed to get or create subscription", details=str(e))

    def get(self, user_id: str) -> Subscription:
        """
        Get user's subscription.

        Args:
            user_id: User ID

        Returns:
            User's subscription

        Raises:
            SubscriptionNotFoundError: If no subscription exists
        """
        try:
            response = (
                self.client.table("user_subscriptions")
                .select("*")
                .eq("user_id", user_id)
                .single()
                .execute()
            )

            if not response.data:
                raise SubscriptionNotFoundError()

            return Subscription(**response.data)

        except SubscriptionNotFoundError:
            raise
        except Exception as e:
            error_str = str(e)
            if "PGRST116" in error_str:
                raise SubscriptionNotFoundError()
            logger.error(f"Error fetching subscription: {e}")
            raise AppException(message="Failed to fetch subscription", details=str(e))

    def get_by_stripe_id(self, stripe_subscription_id: str) -> Optional[Subscription]:
        """
        Get subscription by Stripe subscription ID.

        Args:
            stripe_subscription_id: Stripe subscription ID

        Returns:
            Subscription if found, None otherwise
        """
        try:
            response = (
                self.client.table("user_subscriptions")
                .select("*")
                .eq("stripe_subscription_id", stripe_subscription_id)
                .single()
                .execute()
            )

            if not response.data:
                return None

            return Subscription(**response.data)

        except Exception as e:
            error_str = str(e)
            if "PGRST116" in error_str:
                return None
            logger.error(f"Error fetching subscription by Stripe ID: {e}")
            return None

    def update(self, user_id: str, update_data: SubscriptionUpdate) -> Subscription:
        """
        Update subscription (typically from Stripe webhook).

        Args:
            user_id: User ID
            update_data: Fields to update

        Returns:
            Updated subscription
        """
        try:
            update_dict = {}

            if update_data.stripe_subscription_id is not None:
                update_dict["stripe_subscription_id"] = update_data.stripe_subscription_id
            if update_data.stripe_price_id is not None:
                update_dict["stripe_price_id"] = update_data.stripe_price_id
            if update_data.status is not None:
                status_value = update_data.status.value if hasattr(update_data.status, 'value') else update_data.status
                update_dict["status"] = status_value
            if update_data.is_active is not None:
                update_dict["is_active"] = update_data.is_active
            if update_data.current_period_end is not None:
                if isinstance(update_data.current_period_end, datetime):
                    update_dict["current_period_end"] = update_data.current_period_end.isoformat()
                else:
                    update_dict["current_period_end"] = update_data.current_period_end
            elif update_data.current_period_end is None:
                update_dict["current_period_end"] = None

            if not update_dict:
                return self.get(user_id)

            update_dict["updated_at"] = "now()"

            response = (
                self.client.table("user_subscriptions")
                .update(update_dict)
                .eq("user_id", user_id)
                .execute()
            )

            if not response.data:
                raise SubscriptionNotFoundError()

            logger.info(f"Updated subscription for user {user_id}")
            return Subscription(**response.data[0])

        except SubscriptionNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error updating subscription: {e}")
            raise AppException(message="Failed to update subscription", details=str(e))

    # Usage Operations

    def get_usage(self, user_id: str) -> Usage:
        """
        Get user's message usage (creates if doesn't exist).

        Args:
            user_id: User ID

        Returns:
            Usage record
        """
        try:
            response = (
                self.client.table("user_usage")
                .select("*")
                .eq("user_id", user_id)
                .execute()
            )

            if not response.data or len(response.data) == 0:
                return self._create_usage(user_id)

            return Usage(**response.data[0])

        except AppException:
            raise
        except Exception as e:
            logger.error(f"Error fetching usage: {e}")
            raise AppException(message="Failed to fetch usage", details=str(e))

    def _create_usage(self, user_id: str) -> Usage:
        """Create a new usage record."""
        try:
            data = {
                "user_id": user_id,
                "message_count": 0,
                "last_reset_at": "now()",
            }

            response = self.client.table("user_usage").insert(data).execute()

            if not response.data:
                raise AppException(message="Failed to create usage record")

            logger.info(f"Created usage record for user {user_id}")
            return Usage(**response.data[0])

        except AppException:
            raise
        except Exception as e:
            logger.error(f"Error creating usage: {e}")
            raise AppException(message="Failed to create usage record", details=str(e))

    def increment_message_count(self, user_id: str) -> Usage:
        """
        Increment user's message count.

        Args:
            user_id: User ID

        Returns:
            Updated usage record
        """
        try:
            current_usage = self.get_usage(user_id)
            new_count = current_usage.message_count + 1

            response = (
                self.client.table("user_usage")
                .update({"message_count": new_count})
                .eq("user_id", user_id)
                .execute()
            )

            if not response.data:
                raise AppException(message="Failed to increment message count")

            logger.debug(f"Incremented message count for user {user_id}: {new_count}")
            return Usage(**response.data[0])

        except AppException:
            raise
        except Exception as e:
            logger.error(f"Error incrementing message count: {e}")
            raise AppException(message="Failed to increment message count", details=str(e))

    def reset_usage(self, user_id: str) -> Usage:
        """
        Reset user's message count and window.

        Args:
            user_id: User ID

        Returns:
            Reset usage record
        """
        try:
            response = (
                self.client.table("user_usage")
                .update({
                    "message_count": 0,
                    "last_reset_at": "now()",
                })
                .eq("user_id", user_id)
                .execute()
            )

            if not response.data:
                raise AppException(message="Failed to reset usage")

            logger.info(f"Reset usage for user {user_id}")
            return Usage(**response.data[0])

        except AppException:
            raise
        except Exception as e:
            logger.error(f"Error resetting usage: {e}")
            raise AppException(message="Failed to reset usage", details=str(e))


# Singleton service instance
subscription_service = SubscriptionService()
