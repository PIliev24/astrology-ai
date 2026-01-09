"""
Supabase client singleton.

Provides a singleton Supabase client instance to avoid creating
new connections for every database operation.
"""

import logging
from typing import Optional

from supabase import create_client, Client

from config.settings import get_settings
from core.exceptions import AppException

logger = logging.getLogger(__name__)

# Global client instance
_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """
    Get or create Supabase client singleton.

    Returns:
        Client: Initialized Supabase client

    Raises:
        AppException: If Supabase client cannot be created
    """
    global _client

    if _client is None:
        try:
            settings = get_settings()
            _client = create_client(settings.supabase_url, settings.supabase_secret_key)
            logger.info("Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            raise AppException(
                message="Database service not configured",
                details={"error": str(e)}
            )

    return _client


def supabase_dependency() -> Client:
    """
    FastAPI dependency for injecting Supabase client.

    Usage:
        @router.get("/items")
        async def get_items(db: Client = Depends(supabase_dependency)):
            return db.table("items").select("*").execute()

    Returns:
        Client: Supabase client instance
    """
    return get_supabase_client()


def reset_client() -> None:
    """
    Reset the global client instance.

    Useful for testing or when credentials change.
    """
    global _client
    _client = None
    logger.info("Supabase client reset")
