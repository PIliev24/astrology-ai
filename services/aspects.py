"""
Astrological Aspects Services
"""

from typing import List, Dict, Any
from kerykeion import AstrologicalSubject, NatalAspects, SynastryAspects

def get_synastry_aspects(
    subject1: AstrologicalSubject,
    subject2: AstrologicalSubject
) -> List[Dict[str, Any]]:
    """
    Calculate synastry aspects between two subjects.
    
    Args:
        subject1: First AstrologicalSubject
        subject2: Second AstrologicalSubject
    
    Returns:
        List of synastry aspect dictionaries
    """
    aspects = SynastryAspects(subject1, subject2)
    return aspects.relevant_aspects


def get_natal_aspects(subject: AstrologicalSubject) -> List[Dict[str, Any]]:
    """
    Get all natal aspects (not just relevant ones).
    
    Args:
        subject: AstrologicalSubject instance
    
    Returns:
        List of all aspect dictionaries
    """
    aspects = NatalAspects(subject)
    return aspects.all_aspects
