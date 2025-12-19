"""
Pydantic models for astrology API requests and responses
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class BirthChartCreateRequest(BaseModel):
    """Request model for creating a birth chart"""
    name: str = Field(..., description="Person's name")
    birth_datetime: str = Field(..., description="Birth date and time in format 'dd-mmm-yyyy hh:mm' (e.g., '15-Jun-1990 14:30')")
    city: str = Field(..., description="City name")
    country: str = Field(..., description="Country code (e.g., 'US', 'GB') or country name")


class BirthChartResponse(BaseModel):
    """Response model for birth chart data"""
    id: UUID = Field(..., description="Birth chart ID")
    name: str = Field(..., description="Person's name")
    birth_data: Dict[str, Any] = Field(..., description="Full birth data (year, month, day, hour, minute, location)")
    chart_data: Dict[str, Any] = Field(..., description="Calculated chart data from RapidAPI")
    created_at: datetime = Field(..., description="Creation timestamp")


class BirthChartListItem(BaseModel):
    """Response model for birth chart list items (without chart_data)"""
    id: UUID = Field(..., description="Birth chart ID")
    name: str = Field(..., description="Person's name")
    birth_data: Dict[str, Any] = Field(..., description="Full birth data (year, month, day, hour, minute, location)")


class CompatibilityScoreRequest(BaseModel):
    """Request model for compatibility score calculation (optional, for direct API calls)"""
    chart_id_1: UUID = Field(..., description="First chart ID")
    chart_id_2: UUID = Field(..., description="Second chart ID")


class CompatibilityScoreResponse(BaseModel):
    """Response model for compatibility score"""
    score: int = Field(..., description="Compatibility score (0-100)")
    score_description: str = Field(..., description="Description of the score")
    is_destiny_sign: bool = Field(..., description="Whether it's a destiny sign")
    aspects: List[Dict[str, Any]] = Field(..., description="List of aspects between the two charts")
    chart_data: Dict[str, Any] = Field(..., description="Additional chart data")


# Authentication Models
class SignupRequest(BaseModel):
    """Request model for user signup"""
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="User password (min 6 characters)")


class LoginRequest(BaseModel):
    """Request model for user login"""
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class UserResponse(BaseModel):
    """Response model for user data"""
    model_config = {"from_attributes": True}
    
    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email address")


class AuthResponse(BaseModel):
    """Response model for authentication operations"""
    success: bool = Field(..., description="Whether the operation was successful")
    user: Optional[UserResponse] = Field(None, description="User data")
    access_token: Optional[str] = Field(None, description="JWT access token")
    refresh_token: Optional[str] = Field(None, description="JWT refresh token")
    message: Optional[str] = Field(None, description="Optional message")
