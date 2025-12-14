"""
Birth Chart Router
Handles birth chart creation and data retrieval endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from models.astrology import BirthDataRequest
from services.birth_chart import (
    create_astrological_subject,
    get_birth_chart_data,
)
from middleware.auth import get_current_user

router = APIRouter(prefix="/astrology/birth-chart", tags=["Birth Chart"])


@router.post(
    "",
    summary="Get complete birth chart data",
    description="Create an astrological subject and retrieve all planetary and house positions"
)
async def get_birth_chart(
    request: BirthDataRequest,
):
    """
    Get comprehensive birth chart data including all planets and houses.
    Requires authentication.
    """
    try:
        subject = create_astrological_subject(
            name=request.name,
            year=request.year,
            month=request.month,
            day=request.day,
            hour=request.hour,
            minute=request.minute,
            city=request.city,
            nation=request.nation,
            lng=request.lng,
            lat=request.lat,
            tz_str=request.tz_str,
            zodiac_type=request.zodiac_type,
            sidereal_mode=request.sidereal_mode,
            houses_system=request.houses_system,
            perspective_type=request.perspective_type,
            online=request.online,
            geonames_username=request.geonames_username,
        )
        
        chart_data = get_birth_chart_data(subject)
        return {"success": True, "data": chart_data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))