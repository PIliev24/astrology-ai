"""
Birth Chart Service
Uses RapidAPI Hub - Astrologer for birth chart calculations
"""

import os
import logging
from typing import Dict, Any
import httpx
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = "astrologer.p.rapidapi.com"
BIRTH_CHART_ENDPOINT = "https://astrologer.p.rapidapi.com/api/v5/chart/birth-chart"


async def generate_birth_chart(
    name: str,
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    city: str,
    nation: str,
    longitude: float,
    latitude: float,
    timezone: str,
    zodiac_type: str = "Tropical",
    houses_system_identifier: str = "P",
) -> Dict[str, Any]:
    """
    Generate birth chart data using RapidAPI Hub - Astrologer.
    
    Args:
        name: Person's name
        year: Birth year
        month: Birth month (1-12)
        day: Birth day
        hour: Birth hour (0-23)
        minute: Birth minute (0-59)
        city: City name
        nation: Nation code (e.g., "US", "GB")
        longitude: Longitude
        latitude: Latitude
        timezone: Timezone string (IANA format, e.g., "America/New_York")
        zodiac_type: Zodiac type ("Tropical" or "Sidereal")
        houses_system_identifier: House system code (default "P" for Placidus)
    
    Returns:
        Dictionary containing birth chart response from RapidAPI with:
        - status: Response status
        - chart_data: Chart data (planets, aspects, houses, etc.)
        - chart: SVG string of the birth chart
    
    Raises:
        HTTPException: If API call fails or returns error
    """
    if not RAPIDAPI_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RapidAPI key not configured"
        )
    
    payload = {
        "subject": {
            "name": name,
            "year": year,
            "month": month,
            "day": day,
            "hour": hour,
            "minute": minute,
            "city": city,
            "nation": nation,
            "longitude": longitude,
            "latitude": latitude,
            "timezone": timezone,
            "zodiac_type": zodiac_type,
            "houses_system_identifier": houses_system_identifier,
        },
        "theme": "classic",
        "language": "EN",
        "split_chart": False,
        "transparent_background": False,
        "show_house_position_comparison": True,
    }
    
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST,
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                BIRTH_CHART_ENDPOINT,
                json=payload,
                headers=headers
            )
            
            if response.status_code != 200:
                logger.error(f"RapidAPI error: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"RapidAPI birth chart service error: {response.status_code}"
                )
            
            data = response.json()
            
            # Validate response structure
            if "status" in data and data.get("status") != "OK":
                logger.error(f"RapidAPI returned error status: {data}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="RapidAPI birth chart service returned error"
                )
            
            return data
    
    except httpx.TimeoutException:
        logger.error("RapidAPI birth chart request timed out")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Birth chart service request timed out"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calling RapidAPI birth chart: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate birth chart: {str(e)}"
        )