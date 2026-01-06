"""
Shared API dependencies for FastAPI routes.

Provides authentication dependencies and other shared utilities
for use across all API routers.
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import Client

from config.settings import get_settings
from core.clients.supabase import get_supabase_client
from core.exceptions import UnauthorizedError, AppException

logger = logging.getLogger(__name__)

# Security scheme for Bearer token
security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Dependency to verify JWT token and extract user information.

    Validates the JWT token with Supabase and returns user data
    for use in protected endpoints.

    Args:
        credentials: HTTP Authorization credentials with Bearer token

    Returns:
        dict: User information with id, email, created_at

    Raises:
        HTTPException: If token is invalid or verification fails
    """
    client = get_supabase_client()
    token = credentials.credentials

    try:
        user_response = client.auth.get_user(token)

        if not user_response or not user_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = user_response.user
        logger.info(f"User authenticated: {user.id}")

        return {
            "id": user.id,
            "email": user.email,
            "created_at": user.created_at if hasattr(user, "created_at") else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
) -> Optional[dict]:
    """
    Optional dependency for routes that work with or without authentication.

    Returns None if no token provided, otherwise validates the token.

    Args:
        credentials: Optional HTTP Authorization credentials

    Returns:
        dict or None: User information if authenticated, None otherwise

    Raises:
        HTTPException: If token is provided but invalid
    """
    if not credentials:
        return None

    return await get_current_user(credentials)


def supabase_client() -> Client:
    """
    Dependency for injecting Supabase client.

    Usage:
        @router.get("/items")
        async def get_items(db: Client = Depends(supabase_client)):
            return db.table("items").select("*").execute()

    Returns:
        Client: Supabase client instance
    """
    return get_supabase_client()


async def verify_websocket_token(token: str) -> dict:
    """
    Verify JWT token for WebSocket connections.

    WebSocket connections pass the token as a query parameter
    instead of in headers, so this function validates it directly.

    Args:
        token: JWT token string

    Returns:
        dict: User information with id, email, created_at

    Raises:
        UnauthorizedError: If token is invalid
    """
    client = get_supabase_client()

    try:
        user_response = client.auth.get_user(token)

        if not user_response or not user_response.user:
            raise UnauthorizedError(message="Invalid authentication credentials")

        user = user_response.user
        logger.info(f"WebSocket user authenticated: {user.id}")

        return {
            "id": user.id,
            "email": user.email,
            "created_at": user.created_at if hasattr(user, "created_at") else None,
        }

    except UnauthorizedError:
        raise
    except Exception as e:
        logger.error(f"WebSocket token verification failed: {e}")
        raise UnauthorizedError(message=f"Could not validate credentials: {str(e)}")
