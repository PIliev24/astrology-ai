"""
Authentication router for user signup, login, logout, and user management
"""

from fastapi import APIRouter, HTTPException, Depends, status
from models.astrology import SignupRequest, LoginRequest, AuthResponse, UserResponse
from middleware.auth import get_current_user, get_supabase_client
from supabase import Client
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/signup",
    response_model=AuthResponse,
    summary="Register a new user",
    description="Create a new user account with email and password"
)
async def signup(
    request: SignupRequest,
    supabase: Client = Depends(get_supabase_client)
):
    """
    Register a new user with Supabase Auth.
    
    Args:
        request: SignupRequest containing email and password
        supabase: Supabase client instance
        
    Returns:
        AuthResponse: Contains user data and authentication tokens
        
    Raises:
        HTTPException: If signup fails
    """
    try:
        # Sign up the user with Supabase
        response = supabase.auth.sign_up({
            "email": request.email,
            "password": request.password,
        })
        
        if not response.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create user account"
            )
        
        logger.info(f"New user registered: {response.user.id}")
        
        return AuthResponse(
            success=True,
            user=UserResponse(
                id=response.user.id,
                email=response.user.email,
                created_at=str(response.user.created_at) if hasattr(response.user, 'created_at') else None
            ),
            access_token=response.session.access_token if response.session else None,
            refresh_token=response.session.refresh_token if response.session else None,
            message="User registered successfully. Please check your email to confirm your account."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Signup failed: {str(e)}"
        )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Login user",
    description="Authenticate user with email and password"
)
async def login(
    request: LoginRequest,
    supabase: Client = Depends(get_supabase_client)
):
    """
    Authenticate user and return access tokens.
    
    Args:
        request: LoginRequest containing email and password
        supabase: Supabase client instance
        
    Returns:
        AuthResponse: Contains user data and authentication tokens
        
    Raises:
        HTTPException: If login fails
    """
    try:
        # Sign in the user with Supabase
        response = supabase.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password,
        })
        
        if not response.user or not response.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        logger.info(f"User logged in: {response.user.id}")
        
        return AuthResponse(
            success=True,
            user=UserResponse(
                id=response.user.id,
                email=response.user.email,
                created_at=str(response.user.created_at) if hasattr(response.user, 'created_at') else None
            ),
            access_token=response.session.access_token,
            refresh_token=response.session.refresh_token,
            message="Login successful"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Login failed: {str(e)}"
        )


@router.post(
    "/logout",
    response_model=AuthResponse,
    summary="Logout user",
    description="Invalidate the current user session"
)
async def logout(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """
    Log out the current user and invalidate their session.
    
    Args:
        current_user: Current authenticated user from JWT token
        supabase: Supabase client instance
        
    Returns:
        AuthResponse: Confirmation of logout
        
    Raises:
        HTTPException: If logout fails
    """
    try:
        # Sign out the user
        supabase.auth.sign_out()
        
        logger.info(f"User logged out: {current_user['id']}")
        
        return AuthResponse(
            success=True,
            message="Logged out successfully"
        )
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Logout failed: {str(e)}"
        )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Retrieve information about the currently authenticated user"
)
async def get_user_info(
    current_user: dict = Depends(get_current_user)
):
    """
    Get information about the currently authenticated user.
    
    Args:
        current_user: Current authenticated user from JWT token
    
    Returns:
        UserResponse: Current user data
    """
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        created_at=str(current_user.get("created_at")) if current_user.get("created_at") else None
    )


@router.post(
    "/refresh",
    response_model=AuthResponse,
    summary="Refresh access token",
    description="Get a new access token using a refresh token"
)
async def refresh_token(
    refresh_token: str,
    supabase: Client = Depends(get_supabase_client)
):
    """
    Refresh the access token using a valid refresh token.
    
    Args:
        refresh_token: Valid refresh token
        supabase: Supabase client instance
        
    Returns:
        AuthResponse: Contains new access token and user data
        
    Raises:
        HTTPException: If token refresh fails
    """
    try:
        # Refresh the session
        response = supabase.auth.refresh_session(refresh_token)
        
        if not response.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        logger.info(f"Token refreshed for user: {response.user.id if response.user else 'unknown'}")
        
        return AuthResponse(
            success=True,
            user=UserResponse(
                id=response.user.id,
                email=response.user.email,
                created_at=str(response.user.created_at) if hasattr(response.user, 'created_at') else None
            ) if response.user else None,
            access_token=response.session.access_token,
            refresh_token=response.session.refresh_token,
            message="Token refreshed successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token refresh failed: {str(e)}"
        )
