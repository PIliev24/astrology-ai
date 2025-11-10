"""
Aspects Router
Handles natal and synastry aspects calculations
"""

from fastapi import APIRouter, HTTPException, Depends
from models.astrology import BirthDataRequest, TwoSubjectsRequest
from services.birth_chart import create_astrological_subject
from services.aspects import get_natal_aspects as calculate_natal_aspects, get_synastry_aspects as calculate_synastry_aspects
from middleware.auth import get_current_user

router = APIRouter(prefix="/astrology/aspects", tags=["Aspects"])


@router.post(
    "/natal",
    summary="Get all natal aspects",
    description="Calculate ALL natal aspects (not just relevant ones)"
)
async def get_natal_aspects(
    request: BirthDataRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all natal aspects for a subject.
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
        
        aspects = calculate_natal_aspects(subject)
        return {"success": True, "aspects": aspects, "total_aspects": len(aspects)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/synastry",
    summary="Get synastry aspects",
    description="Calculate aspects between two birth charts for compatibility analysis"
)
async def get_synastry_aspects_endpoint(
    request: TwoSubjectsRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Get synastry aspects between two subjects.
    Requires authentication.
    """
    try:
        subject1 = create_astrological_subject(
            name=request.subject1.name,
            year=request.subject1.year,
            month=request.subject1.month,
            day=request.subject1.day,
            hour=request.subject1.hour,
            minute=request.subject1.minute,
            city=request.subject1.city,
            nation=request.subject1.nation,
            lng=request.subject1.lng,
            lat=request.subject1.lat,
            tz_str=request.subject1.tz_str,
            zodiac_type=request.subject1.zodiac_type,
            sidereal_mode=request.subject1.sidereal_mode,
            houses_system=request.subject1.houses_system,
            perspective_type=request.subject1.perspective_type,
            online=request.subject1.online,
            geonames_username=request.subject1.geonames_username,
        )
        
        subject2 = create_astrological_subject(
            name=request.subject2.name,
            year=request.subject2.year,
            month=request.subject2.month,
            day=request.subject2.day,
            hour=request.subject2.hour,
            minute=request.subject2.minute,
            city=request.subject2.city,
            nation=request.subject2.nation,
            lng=request.subject2.lng,
            lat=request.subject2.lat,
            tz_str=request.subject2.tz_str,
            zodiac_type=request.subject2.zodiac_type,
            sidereal_mode=request.subject2.sidereal_mode,
            houses_system=request.subject2.houses_system,
            perspective_type=request.subject2.perspective_type,
            online=request.subject2.online,
            geonames_username=request.subject2.geonames_username,
        )
        
        aspects = calculate_synastry_aspects(subject1, subject2)
        return {
            "success": True,
            "subject1": request.subject1.name,
            "subject2": request.subject2.name,
            "aspects": aspects,
            "total_aspects": len(aspects)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
