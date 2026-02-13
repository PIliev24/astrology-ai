"""
Birth Chart Router
Handles birth chart creation, retrieval, and deletion endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, Query, status
from uuid import UUID
from typing import List, Literal

from models.astrology import BirthChartCreateRequest, BirthChartResponse, BirthChartListItem
from models.database import UserBirthChartCreate
from services.date_parser import parse_birth_datetime
from services.location_resolver import resolve_location
from services.birth_chart import generate_birth_chart_both_themes
from services.database import (
    save_birth_chart,
    get_user_birth_charts,
    get_birth_chart_by_id,
    delete_birth_chart,
)
from middleware.auth import get_current_user

router = APIRouter(prefix="/astrology/birth-chart", tags=["Birth Chart"])


@router.post(
    "",
    response_model=BirthChartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new birth chart",
    description="Generate a birth chart from date string and location, then save it to the database"
)
async def create_birth_chart(
    request: BirthChartCreateRequest,
    user: dict = Depends(get_current_user),
):
    """
    Create a new birth chart.
    
    Accepts:
    - name: Person's name
    - birth_datetime: Date string in format "dd-mmm-yyyy hh:mm" (e.g., "15-Jun-1990 14:30")
    - city: City name
    - country: Country code or name
    
    The backend will:
    1. Parse the date string
    2. Resolve city/country to coordinates and timezone
    3. Generate chart using RapidAPI
    4. Save to database
    """
    try:
        # Parse date string
        parsed_date = parse_birth_datetime(request.birth_datetime)
        
        # Resolve location
        location = await resolve_location(request.city, request.country)
        
        # Generate birth chart using RapidAPI (both dark + classic themes)
        chart_data = await generate_birth_chart_both_themes(
            name=request.name,
            year=parsed_date["year"],
            month=parsed_date["month"],
            day=parsed_date["day"],
            hour=parsed_date["hour"],
            minute=parsed_date["minute"],
            city=location["city"],
            nation=location["country"],
            longitude=location["longitude"],
            latitude=location["latitude"],
            timezone=location["timezone"],
        )
        
        # Prepare birth data for storage
        birth_data = {
            "name": request.name,
            "year": parsed_date["year"],
            "month": parsed_date["month"],
            "day": parsed_date["day"],
            "hour": parsed_date["hour"],
            "minute": parsed_date["minute"],
            "city": location["city"],
            "country": location["country"],
            "longitude": location["longitude"],
            "latitude": location["latitude"],
            "timezone": location["timezone"],
        }
        
        # Save to database
        chart_create = UserBirthChartCreate(
            name=request.name,
            birth_data=birth_data,
            chart_data=chart_data,
        )
        
        saved_chart = save_birth_chart(user["id"], chart_create)
        
        return BirthChartResponse(
            id=saved_chart.id,
            name=saved_chart.name,
            birth_data=saved_chart.birth_data,
            chart_data=saved_chart.chart_data,
            created_at=saved_chart.created_at,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create birth chart: {str(e)}"
        )


@router.get(
    "",
    response_model=List[BirthChartListItem],
    summary="List user's birth charts",
    description="Get all birth charts saved by the authenticated user (returns only id, name, and birth_data)"
)
async def list_birth_charts(
    user: dict = Depends(get_current_user),
):
    """
    Get all birth charts for the authenticated user.
    Returns only id, name, and birth_data (excludes chart_data/SVG for performance).
    """
    try:
        charts = get_user_birth_charts(user["id"])
        
        return [
            BirthChartListItem(
                id=chart.id,
                name=chart.name,
                birth_data=chart.birth_data,
            )
            for chart in charts
        ]
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch birth charts: {str(e)}"
        )


@router.get(
    "/{chart_id}",
    response_model=BirthChartResponse,
    summary="Get a specific birth chart",
    description="Get a birth chart by ID for the authenticated user"
)
async def get_birth_chart(
    chart_id: UUID,
    user: dict = Depends(get_current_user),
    theme: Literal["dark", "classic"] = Query(default="dark"),
):
    """
    Get a specific birth chart by ID.
    Use ``?theme=classic`` to receive the light-themed SVG instead of dark.
    """
    try:
        chart = get_birth_chart_by_id(user["id"], str(chart_id))

        chart_data = {**chart.chart_data}

        if theme == "classic" and chart_data.get("chart_classic"):
            chart_data["chart"] = chart_data["chart_classic"]

        chart_data.pop("chart_classic", None)

        return BirthChartResponse(
            id=chart.id,
            name=chart.name,
            birth_data=chart.birth_data,
            chart_data=chart_data,
            created_at=chart.created_at,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch birth chart: {str(e)}"
        )


@router.delete(
    "/{chart_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a birth chart",
    description="Delete a birth chart by ID for the authenticated user"
)
async def delete_birth_chart_endpoint(
    chart_id: UUID,
    user: dict = Depends(get_current_user),
):
    """
    Delete a birth chart by ID.
    """
    try:
        delete_birth_chart(user["id"], str(chart_id))
        return None
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete birth chart: {str(e)}"
        )