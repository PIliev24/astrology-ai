"""
RapidAPI Astrologer client for birth chart and compatibility calculations.

Provides methods for generating birth charts and calculating
compatibility scores using the RapidAPI Astrologer service.
"""

import logging
from functools import lru_cache
from typing import Any, Dict, Optional

from config.settings import get_settings
from core.clients.base import BaseAPIClient
from core.exceptions import AstrologyAPIError, ExternalServiceError

logger = logging.getLogger(__name__)


class RapidAPIClient(BaseAPIClient):
    """
    Client for RapidAPI Astrologer endpoints.

    Provides methods for birth chart generation and compatibility calculations.
    Uses the base client's error handling for consistent behavior.
    """

    def __init__(self):
        """Initialize RapidAPI client with credentials from settings."""
        settings = get_settings()
        super().__init__(
            base_url=f"https://{settings.rapidapi_host}",
            timeout=30.0,
            headers={
                "x-rapidapi-key": settings.rapidapi_key,
                "x-rapidapi-host": settings.rapidapi_host,
                "Content-Type": "application/json",
            },
        )

    async def _validate_response(self, data: Dict[str, Any], operation: str) -> Dict[str, Any]:
        """
        Validate RapidAPI response structure.

        Args:
            data: Response data from API
            operation: Name of the operation (for error messages)

        Returns:
            Validated response data

        Raises:
            AstrologyAPIError: If response indicates an error
        """
        if "status" in data and data.get("status") != "OK":
            logger.error(f"RapidAPI {operation} returned error: {data}")
            raise AstrologyAPIError(
                message=f"Astrology API error during {operation}",
                details=data.get("error") or data.get("message"),
            )
        return data

    async def generate_birth_chart(
        self,
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
        Generate birth chart using RapidAPI Astrologer.

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
            timezone: Timezone string (IANA format)
            zodiac_type: Zodiac type ("Tropical" or "Sidereal")
            houses_system_identifier: House system code (default "P" for Placidus)

        Returns:
            Dictionary containing birth chart response with:
            - status: Response status
            - chart_data: Chart data (planets, aspects, houses, etc.)
            - chart: SVG string of the birth chart

        Raises:
            AstrologyAPIError: If API returns an error
            ExternalServiceError: If request fails
            TimeoutError: If request times out
        """
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

        data = await self.post("/api/v5/chart/birth-chart", json=payload)
        return await self._validate_response(data, "birth chart generation")

    async def generate_birth_chart_from_data(
        self,
        birth_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate birth chart from a birth_data dictionary.

        Convenience method that extracts fields from a birth_data dict.

        Args:
            birth_data: Dictionary containing birth information

        Returns:
            Birth chart response data
        """
        return await self.generate_birth_chart(
            name=birth_data.get("name", "Unknown"),
            year=birth_data["year"],
            month=birth_data["month"],
            day=birth_data["day"],
            hour=birth_data["hour"],
            minute=birth_data["minute"],
            city=birth_data["city"],
            nation=birth_data.get("nation") or birth_data.get("country", ""),
            longitude=birth_data["longitude"],
            latitude=birth_data["latitude"],
            timezone=birth_data["timezone"],
        )

    async def calculate_compatibility(
        self,
        subject1: Dict[str, Any],
        subject2: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Calculate compatibility score between two subjects.

        Args:
            subject1: First subject's birth data
            subject2: Second subject's birth data

        Returns:
            Compatibility score data from RapidAPI

        Raises:
            AstrologyAPIError: If API returns an error
            ExternalServiceError: If request fails
            TimeoutError: If request times out
        """
        payload = {
            "first_subject": self._format_subject(subject1),
            "second_subject": self._format_subject(subject2),
        }

        data = await self.post("/api/v5/compatibility-score", json=payload)
        return await self._validate_response(data, "compatibility calculation")

    def _format_subject(self, birth_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format birth data into RapidAPI subject format.

        Args:
            birth_data: Birth data dictionary

        Returns:
            Formatted subject dictionary for RapidAPI
        """
        return {
            "name": birth_data.get("name", "Unknown"),
            "year": birth_data.get("year"),
            "month": birth_data.get("month"),
            "day": birth_data.get("day"),
            "hour": birth_data.get("hour"),
            "minute": birth_data.get("minute"),
            "city": birth_data.get("city"),
            "nation": birth_data.get("nation") or birth_data.get("country"),
            "longitude": birth_data.get("longitude"),
            "latitude": birth_data.get("latitude"),
            "timezone": birth_data.get("timezone"),
        }


@lru_cache
def get_rapidapi_client() -> RapidAPIClient:
    """
    Get cached RapidAPI client instance.

    Returns:
        RapidAPIClient: Cached client instance
    """
    return RapidAPIClient()
