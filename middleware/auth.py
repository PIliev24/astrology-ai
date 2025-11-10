"""
Authentication middleware for protecting API endpoints with Supabase JWT verification
"""

import os
from dotenv import load_dotenv
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client
from typing import Optional
import logging

load_dotenv()

logger = logging.getLogger(__name__)

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    logger.warning("Supabase credentials not found in environment variables")
    supabase_client: Optional[Client] = None
else:
    supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    logger.info("Supabase client initialized successfully")

# Security scheme for Bearer token
security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Dependency to verify JWT token and extract user information.
    
    Args:
        credentials: HTTP Authorization credentials containing the Bearer token
        
    Returns:
        dict: User information from the verified token
        
    Raises:
        HTTPException: If token is invalid or user verification fails
    """
    if not supabase_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service not configured"
        )
    
    token = credentials.credentials
    
    try:
        # Verify the token and get user information
        user_response = supabase_client.auth.get_user(token)
        
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
            "created_at": user.created_at if hasattr(user, 'created_at') else None,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))) -> Optional[dict]:
    """
    Optional dependency to verify JWT token when provided.
    Returns None if no token is provided, otherwise verifies the token.
    
    Args:
        credentials: Optional HTTP Authorization credentials
        
    Returns:
        Optional[dict]: User information if token is valid, None if no token provided
        
    Raises:
        HTTPException: If token is provided but invalid
    """
    if not credentials:
        return None
    
    return await get_current_user(credentials)


def get_supabase_client() -> Client:
    """
    Dependency to get the Supabase client instance.
    
    Returns:
        Client: Initialized Supabase client
        
    Raises:
        HTTPException: If Supabase client is not configured
    """
    if not supabase_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase client not configured"
        )
    return supabase_client
