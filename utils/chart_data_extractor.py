"""
Chart Data Extractor Utility
Extracts minimal essential data from birth charts to reduce token usage
"""

from typing import Dict, Any, List
from models.database import UserBirthChart

# Essential planets and points for chart interpretation
ESSENTIAL_PLANETS = [
    "sun", "moon", "mercury", "venus", "mars", 
    "jupiter", "saturn", "uranus", "neptune", "pluto",
    "ascendant", "medium_coeli", "descendant", "imum_coeli"
]


def extract_minimal_chart_data(chart: UserBirthChart) -> Dict[str, Any]:
    """
    Extract minimal essential data from a birth chart for AI agent interpretation.
    Only includes planetary positions (sign, house, position) - no aspects or distributions.
    
    Args:
        chart: UserBirthChart object from database
    
    Returns:
        Dictionary with minimal chart data: id, name, birth_data, and planets
    """
    result = {
        "id": str(chart.id),
        "name": chart.name,
        "birth_data": chart.birth_data,
        "planets": {}
    }
    
    # Extract planetary positions from chart_data
    if not chart.chart_data or not isinstance(chart.chart_data, dict):
        return result
    
    # Navigate to the actual chart data (may be nested under "chart_data" key)
    chart_data = chart.chart_data
    if "chart_data" in chart_data and isinstance(chart_data["chart_data"], dict):
        chart_data = chart_data["chart_data"]
    
    # Extract subject data (planetary positions)
    subject = chart_data.get("subject", {})
    if not isinstance(subject, dict):
        return result
    
    # Extract essential planetary positions
    for planet_key in ESSENTIAL_PLANETS:
        planet_data = subject.get(planet_key)
        if planet_data and isinstance(planet_data, dict):
            result["planets"][planet_key] = {
                "name": planet_data.get("name"),
                "sign": planet_data.get("sign"),
                "house": planet_data.get("house"),
                "position": planet_data.get("abs_pos"),  # Absolute position in degrees
                "emoji": planet_data.get("emoji"),
            }
    
    return result


def extract_minimal_charts_data(charts: List[UserBirthChart]) -> Dict[str, Any]:
    """
    Extract minimal data from multiple charts.
    
    Args:
        charts: List of UserBirthChart objects
    
    Returns:
        Dictionary with "charts" array containing minimal chart data
    """
    if len(charts) == 1:
        return extract_minimal_chart_data(charts[0])
    
    return {
        "charts": [extract_minimal_chart_data(chart) for chart in charts]
    }

