"""Client modules for external services."""

from core.clients.supabase import get_supabase_client, supabase_dependency
from core.clients.base import BaseAPIClient

__all__ = [
    "get_supabase_client",
    "supabase_dependency",
    "BaseAPIClient",
]
