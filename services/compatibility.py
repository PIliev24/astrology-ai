"""
Compatibility Score Service
Calls RapidAPI compatibility score endpoint
"""

import os
import logging
import httpx
from typing import Dict, Any
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = "astrologer.p.rapidapi.com"
COMPATIBILITY_ENDPOINT = "https://astrologer.p.rapidapi.com/api/v5/compatibility-score"


def format_subject_from_birth_data(birth_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format birth data into RapidAPI subject format.
    
    Args:
        birth_data: Birth data dictionary (from database or user input)
    
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
        "timezone": birth_data.get("timezone")
    }


async def calculate_compatibility_score_from_data(
    subject1_data: Dict[str, Any],
    subject2_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Calculate compatibility score from birth data dictionaries.
    This is the main function for compatibility calculations.
    Works with birth_data from database or user-provided data.
    
    Args:
        subject1_data: First subject birth data
        subject2_data: Second subject birth data
    
    Returns:
        Compatibility score data from RapidAPI
    """
    if not RAPIDAPI_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RapidAPI key not configured"
        )
    
    # Format subjects for RapidAPI
    subject1 = format_subject_from_birth_data(subject1_data)
    subject2 = format_subject_from_birth_data(subject2_data)
    
    # Call RapidAPI
    return await _call_rapidapi_compatibility(subject1, subject2)


async def _call_rapidapi_compatibility(
    subject1: Dict[str, Any],
    subject2: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Internal function to call RapidAPI compatibility endpoint.
    
    Args:
        subject1: First subject data
        subject2: Second subject data
    
    Returns:
        Compatibility score response from RapidAPI
    """
    payload = {
        "first_subject": subject1,
        "second_subject": subject2
    }
    
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST,
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                COMPATIBILITY_ENDPOINT,
                json=payload,
                headers=headers
            )
            
            if response.status_code != 200:
                logger.error(f"RapidAPI error: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"RapidAPI compatibility service error: {response.status_code}"
                )
            
            data = response.json()
            
            # Validate response structure
            if "status" not in data or data.get("status") != "OK":
                logger.error(f"RapidAPI returned error status: {data}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="RapidAPI compatibility service returned error"
                )
            
            return data
    
    except httpx.TimeoutException:
        logger.error("RapidAPI compatibility request timed out")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Compatibility service request timed out"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calling RapidAPI compatibility: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate compatibility: {str(e)}"
        )

