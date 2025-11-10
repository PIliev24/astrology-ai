"""
Relationship Analysis Router
Handles compatibility scores and composite subjects
"""

from fastapi import APIRouter, HTTPException, Depends
from models.astrology import TwoSubjectsRequest
from services.birth_chart import create_astrological_subject, get_birth_chart_data
from services.relationships import get_relationship_score, create_composite_subject
from middleware.auth import get_current_user

router = APIRouter(prefix="/astrology/relationship", tags=["Relationship Analysis"])


@router.post(
    "/score",
    summary="Calculate relationship compatibility score",
    description="Calculate compatibility score between two people"
)
async def get_relationship_score_endpoint(
    request: TwoSubjectsRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Get relationship compatibility score.
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
        
        score = get_relationship_score(subject1, subject2)
        
        return {
            "success": True,
            "subject1": request.subject1.name,
            "subject2": request.subject2.name,
            "score": score
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/composite-subject",
    summary="Create composite subject",
    description="Create a composite subject using midpoint method"
)
async def create_composite_subject_endpoint(
    request: TwoSubjectsRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Create composite subject from two subjects.
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
        
        composite_data = create_composite_subject(subject1, subject2)
        
        return {
            "success": True,
            "subject1": request.subject1.name,
            "subject2": request.subject2.name,
            "composite_data": composite_data
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
