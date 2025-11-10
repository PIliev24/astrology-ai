"""
Relationship Analysis Services
"""

import os
from typing import Dict, Any
from datetime import datetime, timedelta, timezone
from kerykeion import AstrologicalSubject, RelationshipScoreFactory, CompositeSubjectFactory


def get_relationship_score(
    subject1: AstrologicalSubject,
    subject2: AstrologicalSubject,
) -> Dict[str, Any]:
    """
    Calculate compatibility/relationship score between two subjects.
    
    Note: This returns a simplified compatibility analysis.
    For full analysis, use synastry aspects and composite charts.
    
    Args:
        subject1: First AstrologicalSubject
        subject2: Second AstrologicalSubject
    
    Returns:
        Dictionary with relationship compatibility information
    """
    # Simplified compatibility - compare sun signs and elements
    from services.aspects import get_synastry_aspects
    
    aspects = get_synastry_aspects(subject1, subject2)
    
    # Count positive vs challenging aspects
    positive = sum(1 for a in aspects if a.get('aspect') in ['trine', 'sextile', 'conjunction'])
    challenging = sum(1 for a in aspects if a.get('aspect') in ['square', 'opposition'])
    
    compatibility_score = (positive / (positive + challenging) * 100) if (positive + challenging) > 0 else 50
    
    return {
        "subject1": subject1.name,
        "subject2": subject2.name,
        "compatibility_percentage": round(compatibility_score, 2),
        "total_aspects": len(aspects),
        "positive_aspects": positive,
        "challenging_aspects": challenging,
        "note": "Based on synastry aspects analysis"
    }


def create_composite_subject(
    subject1: AstrologicalSubject,
    subject2: AstrologicalSubject,
) -> Dict[str, Any]:
    """
    Create a composite subject using midpoint method.
    
    Args:
        subject1: First AstrologicalSubject
        subject2: Second AstrologicalSubject
    
    Returns:
        Dictionary with composite chart data including planetary midpoints
    """
    # Calculate midpoint date/time
    from datetime import datetime, timezone
    
    dt1 = datetime(subject1.year, subject1.month, subject1.day, 
                   subject1.hour, subject1.minute, tzinfo=timezone.utc)
    dt2 = datetime(subject2.year, subject2.month, subject2.day, 
                   subject2.hour, subject2.minute, tzinfo=timezone.utc)
    
    # Calculate time difference and midpoint
    delta = (dt2 - dt1).total_seconds() / 2
    midpoint_dt = dt1 + timedelta(seconds=delta)
    
    # Calculate midpoint location
    mid_lng = (subject1.lng + subject2.lng) / 2
    mid_lat = (subject1.lat + subject2.lat) / 2
    
    # Create composite subject with midpoint data
    composite_name = f"Composite: {subject1.name} & {subject2.name}"
    
    # Get geonames username from environment
    geonames_username = os.getenv("GEONAMES_USERNAME")
    
    kwargs = {
        "name": composite_name,
        "year": midpoint_dt.year,
        "month": midpoint_dt.month,
        "day": midpoint_dt.day,
        "hour": midpoint_dt.hour,
        "minute": midpoint_dt.minute,
        "lng": mid_lng,
        "lat": mid_lat,
        "tz_str": subject1.tz_str,
        "zodiac_type": subject1.zodiac_type,
    }
    
    if geonames_username:
        kwargs["geonames_username"] = geonames_username
    
    composite = AstrologicalSubject(**kwargs)
    
    return {
        "name": composite_name,
        "midpoint_datetime": midpoint_dt.isoformat(),
        "midpoint_location": {"lng": mid_lng, "lat": mid_lat},
        "sun": composite.sun,
        "moon": composite.moon,
        "mercury": composite.mercury,
        "venus": composite.venus,
        "mars": composite.mars,
        "jupiter": composite.jupiter,
        "saturn": composite.saturn,
        "uranus": composite.uranus,
        "neptune": composite.neptune,
        "pluto": composite.pluto,
        "chiron": composite.chiron,
        "true_node": composite.true_node,
    }
