"""
Pydantic models for astrology API requests and responses
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime


class BirthDataRequest(BaseModel):
    """Request model for creating an astrological subject"""
    name: str = Field(..., description="Person's name")
    year: int = Field(..., ge=1900, le=2100, description="Birth year")
    month: int = Field(..., ge=1, le=12, description="Birth month")
    day: int = Field(..., ge=1, le=31, description="Birth day")
    hour: int = Field(..., ge=0, le=23, description="Birth hour")
    minute: int = Field(..., ge=0, le=59, description="Birth minute")
    
    # Location - either city/nation or coordinates
    city: Optional[str] = Field(None, description="City name")
    nation: Optional[str] = Field(None, description="Nation code (e.g., US, GB)")
    lng: Optional[float] = Field(None, description="Longitude")
    lat: Optional[float] = Field(None, description="Latitude")
    tz_str: Optional[str] = Field(None, description="Timezone string (e.g., Europe/London)")
    
    # Advanced options
    zodiac_type: Literal["Tropic", "Sidereal"] = Field("Tropic", description="Zodiac type")
    sidereal_mode: Optional[str] = Field(None, description="Sidereal mode (e.g., LAHIRI)")
    houses_system: str = Field("P", description="House system (P=Placidus, K=Koch, etc.)")
    perspective_type: Literal["Apparent Geocentric", "Heliocentric", "Topocentric"] = Field(
        "Apparent Geocentric", description="Astrological perspective"
    )
    online: bool = Field(False, description="Fetch geolocation data online")
    geonames_username: Optional[str] = Field(None, description="GeoNames username")

class TwoSubjectsRequest(BaseModel):
    """Request model for operations requiring two subjects"""
    subject1: BirthDataRequest
    subject2: BirthDataRequest


class ChartGenerationRequest(BaseModel):
    """Request model for chart generation"""
    subject: BirthDataRequest
    output_directory: Optional[str] = Field(None, description="Custom output directory")
    theme: Literal["classic", "dark", "dark_high_contrast", "light"] = Field(
        "classic", description="Chart theme"
    )
    chart_language: str = Field("EN", description="Chart language (EN, ES, IT, etc.)")
    active_points: Optional[List[str]] = Field(
        None, description="List of active points to include in chart"
    )


class SynastryChartRequest(BaseModel):
    """Request model for synastry chart generation"""
    subject1: BirthDataRequest
    subject2: BirthDataRequest
    output_directory: Optional[str] = Field(None, description="Custom output directory")
    theme: str = Field("classic", description="Chart theme")
    chart_language: str = Field("EN", description="Chart language")


class TransitChartRequest(BaseModel):
    """Request model for transit chart generation"""
    natal_subject: BirthDataRequest
    transit_subject: BirthDataRequest
    output_directory: Optional[str] = Field(None, description="Custom output directory")
    theme: str = Field("classic", description="Chart theme")
    chart_language: str = Field("EN", description="Chart language")


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
