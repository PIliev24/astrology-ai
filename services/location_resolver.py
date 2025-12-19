"""
Location Resolution Service
Resolves city and country to coordinates and timezone
"""

import os
import logging
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
import httpx

logger = logging.getLogger(__name__)

# Cache for location data (simple in-memory cache)
_location_cache: Dict[str, Dict[str, Any]] = {}


async def resolve_location(city: str, country: str) -> Dict[str, Any]:
    """
    Resolve city and country to latitude, longitude, and timezone.
    
    Uses geopy and timezonefinder libraries, or falls back to a geocoding API.
    
    Args:
        city: City name
        country: Country code (e.g., "US", "GB") or country name
    
    Returns:
        Dictionary with location data:
        {
            "latitude": float,
            "longitude": float,
            "timezone": str (IANA format, e.g., "America/New_York"),
            "city": str,
            "country": str
        }
    
    Raises:
        HTTPException: If location cannot be resolved
    """
    # Create cache key
    cache_key = f"{city.lower()},{country.lower()}"
    
    # Check cache first
    if cache_key in _location_cache:
        logger.info(f"Using cached location for {city}, {country}")
        return _location_cache[cache_key]
    
    try:
        # Try using geopy first (if available)
        try:
            from geopy.geocoders import Nominatim
            from timezonefinder import TimezoneFinder
            
            geolocator = Nominatim(user_agent="astrology-api")
            location_str = f"{city}, {country}"
            
            location = geolocator.geocode(location_str, timeout=10)
            
            if not location:
                raise ValueError(f"Location not found: {location_str}")
            
            latitude = location.latitude
            longitude = location.longitude
            
            # Get timezone
            tf = TimezoneFinder()
            timezone_str = tf.timezone_at(lat=latitude, lng=longitude)
            
            if not timezone_str:
                # Fallback to UTC if timezone not found
                logger.warning(f"Timezone not found for {city}, {country}, using UTC")
                timezone_str = "UTC"
            
            result = {
                "latitude": latitude,
                "longitude": longitude,
                "timezone": timezone_str,
                "city": city,
                "country": country
            }
            
            # Cache the result
            _location_cache[cache_key] = result
            
            return result
            
        except ImportError:
            # If geopy/timezonefinder not available, use RapidAPI or another service
            logger.info("geopy/timezonefinder not available, using alternative method")
            
            # Try using a free geocoding API as fallback
            # Using OpenStreetMap Nominatim API (free, no key required)
            async with httpx.AsyncClient() as client:
                url = "https://nominatim.openstreetmap.org/search"
                params = {
                    "q": f"{city}, {country}",
                    "format": "json",
                    "limit": 1
                }
                headers = {
                    "User-Agent": "Astrology-API/1.0"
                }
                
                response = await client.get(url, params=params, headers=headers, timeout=10.0)
                
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Location service unavailable"
                    )
                
                data = response.json()
                
                if not data or len(data) == 0:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Location not found: {city}, {country}"
                    )
                
                location_data = data[0]
                latitude = float(location_data["lat"])
                longitude = float(location_data["lon"])
                
                # Get timezone using timezonefinder or estimate from coordinates
                try:
                    from timezonefinder import TimezoneFinder
                    tf = TimezoneFinder()
                    timezone_str = tf.timezone_at(lat=latitude, lng=longitude)
                    if not timezone_str:
                        timezone_str = "UTC"
                except ImportError:
                    # Fallback: estimate timezone from longitude (rough approximation)
                    # 1 hour = 15 degrees longitude
                    hours_offset = round(longitude / 15)
                    timezone_str = f"Etc/GMT{-hours_offset:+d}" if hours_offset != 0 else "UTC"
                    logger.warning(f"Using estimated timezone {timezone_str} for {city}, {country}")
                
                result = {
                    "latitude": latitude,
                    "longitude": longitude,
                    "timezone": timezone_str,
                    "city": city,
                    "country": country
                }
                
                # Cache the result
                _location_cache[cache_key] = result
                
                return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving location for {city}, {country}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resolve location: {str(e)}"
        )

