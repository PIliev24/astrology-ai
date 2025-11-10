"""
Birth Chart & Subject Creation Services
"""

import os
from typing import Optional, Literal
from kerykeion import AstrologicalSubject


def create_astrological_subject(
    name: str,
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    city: Optional[str] = None,
    nation: Optional[str] = None,
    lng: Optional[float] = None,
    lat: Optional[float] = None,
    tz_str: Optional[str] = None,
    zodiac_type: Literal["Tropic", "Sidereal"] = "Tropic",
    sidereal_mode: Optional[str] = None,
    houses_system: str = "P",  # Placidus by default
    perspective_type: Literal["Apparent Geocentric", "Heliocentric", "Topocentric"] = "Apparent Geocentric",
    online: bool = False,
    geonames_username: Optional[str] = None,
) -> AstrologicalSubject:
    """
    Create an astrological subject with birth data.
    
    Args:
        name: Person's name
        year: Birth year
        month: Birth month (1-12)
        day: Birth day
        hour: Birth hour (0-23)
        minute: Birth minute (0-59)
        city: City name (used with online=True)
        nation: Nation code (e.g., "US", "GB")
        lng: Longitude (if not using city/nation)
        lat: Latitude (if not using city/nation)
        tz_str: Timezone string (e.g., "Europe/London")
        zodiac_type: "Tropic" or "Sidereal"
        sidereal_mode: Sidereal mode if using Sidereal zodiac (e.g., "LAHIRI")
        houses_system: House system code (P=Placidus, K=Koch, etc.)
        perspective_type: Astrological perspective
        online: Whether to fetch geolocation data online
        geonames_username: Username for GeoNames API
    
    Returns:
        AstrologicalSubject instance
    """
    kwargs = {
        "name": name,
        "year": year,
        "month": month,
        "day": day,
        "hour": hour,
        "minute": minute,
        "zodiac_type": zodiac_type,
        "houses_system_identifier": houses_system,
        "perspective_type": perspective_type,
        "online": online,
    }
    
    # Add location data
    if city and nation:
        kwargs["city"] = city
        kwargs["nation"] = nation
        # If using city/nation without coordinates, we need online mode
        if lng is None or lat is None or tz_str is None:
            kwargs["online"] = True
    elif lng is not None and lat is not None and tz_str:
        kwargs["lng"] = lng
        kwargs["lat"] = lat
        kwargs["tz_str"] = tz_str
    else:
        raise ValueError("Must provide either (city, nation) or (lng, lat, tz_str)")
    
    # Add optional parameters
    if sidereal_mode:
        kwargs["sidereal_mode"] = sidereal_mode
    
    # Use provided geonames_username or fall back to environment variable
    username = geonames_username or os.getenv("GEONAMES_USERNAME")
    if username:
        kwargs["geonames_username"] = username
    
    return AstrologicalSubject(**kwargs)


def get_birth_chart_data(subject: AstrologicalSubject) -> dict:
    """
    Extract comprehensive birth chart data from an astrological subject.
    
    Args:
        subject: AstrologicalSubject instance
    
    Returns:
        Dictionary with planets, houses, and other chart data
    """
    return {
        "name": subject.name,
        "birth_data": {
            "year": subject.year,
            "month": subject.month,
            "day": subject.day,
            "hour": subject.hour,
            "minute": subject.minute,
            "city": subject.city,
            "nation": subject.nation,
            "longitude": subject.lng,
            "latitude": subject.lat,
            "timezone": subject.tz_str,
        },
        "sun": subject.sun,
        "moon": subject.moon,
        "mercury": subject.mercury,
        "venus": subject.venus,
        "mars": subject.mars,
        "jupiter": subject.jupiter,
        "saturn": subject.saturn,
        "uranus": subject.uranus,
        "neptune": subject.neptune,
        "pluto": subject.pluto,
        "mean_node": subject.mean_node,
        "true_node": subject.true_node,
        "chiron": subject.chiron,
        "first_house": subject.first_house,
        "second_house": subject.second_house,
        "third_house": subject.third_house,
        "fourth_house": subject.fourth_house,
        "fifth_house": subject.fifth_house,
        "sixth_house": subject.sixth_house,
        "seventh_house": subject.seventh_house,
        "eighth_house": subject.eighth_house,
        "ninth_house": subject.ninth_house,
        "tenth_house": subject.tenth_house,
        "eleventh_house": subject.eleventh_house,
        "twelfth_house": subject.twelfth_house,
    }
