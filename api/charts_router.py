"""
Charts Router
Handles SVG chart generation (birth, synastry, transit, composite)
"""

from fastapi import APIRouter, HTTPException, Depends
from models.astrology import (
    ChartGenerationRequest,
    SynastryChartRequest,
    TransitChartRequest,
)
from services.birth_chart import create_astrological_subject
from services.charts import (
    generate_birth_chart_svg,
    generate_synastry_chart_svg,
    generate_transit_chart_svg,
    generate_composite_chart_svg,
)
from middleware.auth import get_current_user

router = APIRouter(prefix="/astrology/chart", tags=["Chart Generation"])


@router.post(
    "/birth",
    summary="Generate birth chart SVG",
    description="Generate a visual birth/natal chart in SVG format"
)
async def generate_birth_chart(
    request: ChartGenerationRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Generate birth chart SVG file.
    Requires authentication.
    """
    try:
        subject = create_astrological_subject(
            name=request.subject.name,
            year=request.subject.year,
            month=request.subject.month,
            day=request.subject.day,
            hour=request.subject.hour,
            minute=request.subject.minute,
            city=request.subject.city,
            nation=request.subject.nation,
            lng=request.subject.lng,
            lat=request.subject.lat,
            tz_str=request.subject.tz_str,
            zodiac_type=request.subject.zodiac_type,
            sidereal_mode=request.subject.sidereal_mode,
            houses_system=request.subject.houses_system,
            perspective_type=request.subject.perspective_type,
            online=request.subject.online,
            geonames_username=request.subject.geonames_username,
        )
        
        svg_path = generate_birth_chart_svg(
            subject=subject,
            output_directory=request.output_directory,
            theme=request.theme,
            active_points=request.active_points,
            chart_language=request.chart_language,
        )
        
        return {
            "success": True,
            "message": "Birth chart generated successfully",
            "svg_path": svg_path,
            "subject": request.subject.name
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/synastry",
    summary="Generate synastry chart SVG",
    description="Generate a synastry (compatibility) chart between two people"
)
async def generate_synastry_chart(
    request: SynastryChartRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Generate synastry chart SVG file.
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
        
        svg_path = generate_synastry_chart_svg(
            subject1=subject1,
            subject2=subject2,
            output_directory=request.output_directory,
            theme=request.theme,
            chart_language=request.chart_language,
        )
        
        return {
            "success": True,
            "message": "Synastry chart generated successfully",
            "svg_path": svg_path,
            "subject1": request.subject1.name,
            "subject2": request.subject2.name
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/transit",
    summary="Generate transit chart SVG",
    description="Generate a transit chart showing current planetary positions over natal chart"
)
async def generate_transit_chart(
    request: TransitChartRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Generate transit chart SVG file.
    """
    try:
        natal_subject = create_astrological_subject(
            name=request.natal_subject.name,
            year=request.natal_subject.year,
            month=request.natal_subject.month,
            day=request.natal_subject.day,
            hour=request.natal_subject.hour,
            minute=request.natal_subject.minute,
            city=request.natal_subject.city,
            nation=request.natal_subject.nation,
            lng=request.natal_subject.lng,
            lat=request.natal_subject.lat,
            tz_str=request.natal_subject.tz_str,
            zodiac_type=request.natal_subject.zodiac_type,
            sidereal_mode=request.natal_subject.sidereal_mode,
            houses_system=request.natal_subject.houses_system,
            perspective_type=request.natal_subject.perspective_type,
            online=request.natal_subject.online,
            geonames_username=request.natal_subject.geonames_username,
        )
        
        transit_subject = create_astrological_subject(
            name=request.transit_subject.name,
            year=request.transit_subject.year,
            month=request.transit_subject.month,
            day=request.transit_subject.day,
            hour=request.transit_subject.hour,
            minute=request.transit_subject.minute,
            city=request.transit_subject.city,
            nation=request.transit_subject.nation,
            lng=request.transit_subject.lng,
            lat=request.transit_subject.lat,
            tz_str=request.transit_subject.tz_str,
            zodiac_type=request.transit_subject.zodiac_type,
            sidereal_mode=request.transit_subject.sidereal_mode,
            houses_system=request.transit_subject.houses_system,
            perspective_type=request.transit_subject.perspective_type,
            online=request.transit_subject.online,
            geonames_username=request.transit_subject.geonames_username,
        )
        
        svg_path = generate_transit_chart_svg(
            subject=natal_subject,
            transit=transit_subject,
            output_directory=request.output_directory,
            theme=request.theme,
            chart_language=request.chart_language,
        )
        
        return {
            "success": True,
            "message": "Transit chart generated successfully",
            "svg_path": svg_path,
            "natal_subject": request.natal_subject.name,
            "transit_subject": request.transit_subject.name
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/composite",
    summary="Generate composite chart SVG",
    description="Generate a composite chart (midpoint method) for two people"
)
async def generate_composite_chart(
    request: SynastryChartRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Generate composite chart SVG file.
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
        
        svg_path = generate_composite_chart_svg(
            subject1=subject1,
            subject2=subject2,
            output_directory=request.output_directory,
            theme=request.theme,
            chart_language=request.chart_language,
        )
        
        return {
            "success": True,
            "message": "Composite chart generated successfully",
            "svg_path": svg_path,
            "subject1": request.subject1.name,
            "subject2": request.subject2.name
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
