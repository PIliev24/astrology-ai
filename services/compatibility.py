"""
Compatibility Score Service
Calls RapidAPI compatibility score endpoint
"""

import os
import json
import logging
import httpx
from typing import Dict, Any, Optional
from fastapi import HTTPException, status

from services.database import get_birth_chart_by_id

logger = logging.getLogger(__name__)

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = "astrologer.p.rapidapi.com"
COMPATIBILITY_ENDPOINT = "https://astrologer.p.rapidapi.com/api/v5/compatibility-score"


def format_subject_from_chart_data(chart_data: Dict[str, Any], birth_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format birth chart data into RapidAPI subject format.
    
    Args:
        chart_data: Chart data from database (may contain RapidAPI response)
        birth_data: Birth data from database
    
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
        "nation": birth_data.get("country") or birth_data.get("nation"),
        "longitude": birth_data.get("longitude"),
        "latitude": birth_data.get("latitude"),
        "timezone": birth_data.get("timezone")
    }


async def calculate_compatibility_score_from_charts(
    user_id: str,
    chart_id_1: str,
    chart_id_2: str
) -> Dict[str, Any]:
    """
    Calculate compatibility score between two saved birth charts.
    
    Args:
        user_id: User ID
        chart_id_1: First chart ID
        chart_id_2: Second chart ID
    
    Returns:
        Compatibility score data from RapidAPI
    """
    if not RAPIDAPI_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RapidAPI key not configured"
        )
    
    # Load both charts from database
    try:
        chart1 = get_birth_chart_by_id(user_id, chart_id_1)
        chart2 = get_birth_chart_by_id(user_id, chart_id_2)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading charts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load charts: {str(e)}"
        )
    
    # Format subjects for RapidAPI
    subject1 = format_subject_from_chart_data(chart1.chart_data, chart1.birth_data)
    subject2 = format_subject_from_chart_data(chart2.chart_data, chart2.birth_data)
    
    # Call RapidAPI
    return await _call_rapidapi_compatibility(subject1, subject2)


async def calculate_compatibility_score_from_data(
    subject1_data: Dict[str, Any],
    subject2_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Calculate compatibility score from birth data dictionaries.
    
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
    
    # Ensure data is in correct format
    subject1 = {
        "name": subject1_data.get("name", "Subject 1"),
        "year": subject1_data.get("year"),
        "month": subject1_data.get("month"),
        "day": subject1_data.get("day"),
        "hour": subject1_data.get("hour"),
        "minute": subject1_data.get("minute"),
        "city": subject1_data.get("city"),
        "nation": subject1_data.get("nation") or subject1_data.get("country"),
        "longitude": subject1_data.get("longitude"),
        "latitude": subject1_data.get("latitude"),
        "timezone": subject1_data.get("timezone")
    }
    
    subject2 = {
        "name": subject2_data.get("name", "Subject 2"),
        "year": subject2_data.get("year"),
        "month": subject2_data.get("month"),
        "day": subject2_data.get("day"),
        "hour": subject2_data.get("hour"),
        "minute": subject2_data.get("minute"),
        "city": subject2_data.get("city"),
        "nation": subject2_data.get("nation") or subject2_data.get("country"),
        "longitude": subject2_data.get("longitude"),
        "latitude": subject2_data.get("latitude"),
        "timezone": subject2_data.get("timezone")
    }
    
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

