"""
Astrology Specialist Agent
Single comprehensive agent for birth chart interpretation, analysis, and compatibility questions
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from agents import Agent, ModelSettings, RunContextWrapper, function_tool

from services.database import get_birth_chart_by_id, get_user_birth_charts, get_birth_data_by_chart_ids
from services.birth_chart import generate_birth_chart
from services.compatibility import calculate_compatibility_score_from_data
from utils.chart_data_extractor import extract_minimal_chart_data, extract_minimal_charts_data
from utils.token_monitor import default_monitor

logger = logging.getLogger(__name__)


# Context model for agent tools - MINIMAL to reduce token usage
class AgentContext(BaseModel):
    """Context passed to agent tools containing only essential user information"""
    user_id: str = Field(..., description="User ID for database queries")


# Pydantic models for compatibility calculation
class SubjectBirthData(BaseModel):
    """Birth data for compatibility calculation"""
    name: str = Field(..., description="Person's name")
    year: int = Field(..., ge=1800, le=2300, description="Birth year")
    month: int = Field(..., ge=1, le=12, description="Birth month")
    day: int = Field(..., ge=1, le=31, description="Birth day")
    hour: int = Field(..., ge=0, le=23, description="Birth hour")
    minute: int = Field(..., ge=0, le=59, description="Birth minute")
    city: str = Field(..., description="City name")
    nation: Optional[str] = Field(None, description="Country code (e.g., US, GB)")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude")
    timezone: str = Field(..., description="Timezone (IANA format, e.g., America/New_York)")



@function_tool
async def get_user_birth_chart(
    ctx: RunContextWrapper[AgentContext],
    chart_ids: Optional[list[str]] = None,
) -> str:
    """
    Fetch a user's stored birth chart(s) from the database.
    
    Args:
        ctx: Agent context containing user_id
        chart_ids: Optional list of chart IDs to fetch. Use [id] for single chart, [id1, id2] for multiple.
                  If not provided, returns the most recent chart.
    
    Returns:
        JSON string containing minimal chart data (planetary positions only) to reduce token usage.
        If multiple charts, returns {"charts": [...]}. If single chart, returns object.
    """
    try:
        if not ctx.context or not ctx.context.user_id:
            return json.dumps({"error": "User context not available"})
        
        # If chart_ids provided, fetch those charts
        if chart_ids and len(chart_ids) > 0:
            charts = []
            for ref_chart_id in chart_ids:
                try:
                    chart = get_birth_chart_by_id(ctx.context.user_id, ref_chart_id)
                    charts.append(chart)
                except Exception as e:
                    logger.warning(f"Could not fetch chart {ref_chart_id}: {str(e)}")
                    continue
            
            if not charts:
                return json.dumps({"error": "None of the referenced charts could be found"})
            
            # Extract minimal chart data (planetary positions only)
            result = extract_minimal_charts_data(charts)
            result_json = json.dumps(result, default=str)
            
            # Check token usage and warn if approaching limit
            within_limit, token_count, message = default_monitor.check_limit(result_json)
            if not within_limit:
                logger.warning(f"Token limit exceeded in get_user_birth_chart: {message}")
                # Truncate if needed
                result_json = default_monitor.truncate_content(result_json, default_monitor.limit - 10000)
            elif message:
                logger.info(f"Token usage warning: {message}")
            
            return result_json
        
        # Fallback to most recent chart
        charts = get_user_birth_charts(ctx.context.user_id)
        if not charts:
            return json.dumps({"error": "No birth charts found for this user"})
        
        # Fetch full chart data for the most recent chart
        chart = get_birth_chart_by_id(ctx.context.user_id, str(charts[0].id))
        
        # Extract minimal chart data (planetary positions only)
        result = extract_minimal_chart_data(chart)
        result_json = json.dumps(result, default=str)
        
        # Check token usage and warn if approaching limit
        within_limit, token_count, message = default_monitor.check_limit(result_json)
        if not within_limit:
            logger.warning(f"Token limit exceeded in get_user_birth_chart: {message}")
            # Truncate if needed
            result_json = default_monitor.truncate_content(result_json, default_monitor.limit - 10000)
        elif message:
            logger.info(f"Token usage warning: {message}")
        
        return result_json
    
    except Exception as e:
        logger.error(f"Error fetching birth chart: {str(e)}")
        return json.dumps({"error": f"Failed to fetch birth chart: {str(e)}"})


@function_tool
async def list_user_charts(
    ctx: RunContextWrapper[AgentContext],
) -> str:
    """
    List all birth charts saved by the user.
    
    Args:
        ctx: Agent context containing user_id
    
    Returns:
        JSON string containing list of chart names and IDs
    """
    try:
        charts = get_user_birth_charts(ctx.context.user_id)
        
        result = [
            {
                "id": str(chart.id),
                "name": chart.name,
                "created_at": chart.created_at.isoformat() if chart.created_at else None,
            }
            for chart in charts
        ]
        
        return json.dumps({"charts": result}, default=str)
    
    except Exception as e:
        logger.error(f"Error listing charts: {str(e)}")
        return json.dumps({"error": f"Failed to list charts: {str(e)}"})


@function_tool
async def calculate_compatibility(
    ctx: RunContextWrapper[AgentContext],
    chart_ids: Optional[list[str]] = None,
    subject1_birth_data: Optional[SubjectBirthData] = None,
    subject2_birth_data: Optional[SubjectBirthData] = None,
) -> str:
    """
    Calculate compatibility score between two people.
    
    Use this tool when users ask about relationships, compatibility, or synastry.
    Provide either chart_ids (for saved charts) OR birth_data (for unsaved data), not both.
    
    Args:
        ctx: Agent context containing user_id
        chart_ids: Optional list of 2 chart IDs for saved charts [id1, id2]
        subject1_birth_data: Optional birth data for first person (if charts not saved)
        subject2_birth_data: Optional birth data for second person (if charts not saved)
    
    Returns:
        JSON string containing compatibility score, description, destiny sign, and aspects
    """
    try:
        if not ctx.context or not ctx.context.user_id:
            return json.dumps({"error": "User context not available"})
        
        # Determine data source: chart_ids or birth_data
        if chart_ids and len(chart_ids) >= 2:
            # Fetch birth_data from saved charts (no chart_data to reduce tokens)
            birth_data_list = get_birth_data_by_chart_ids(ctx.context.user_id, chart_ids[:2])
            
            if len(birth_data_list) < 2:
                return json.dumps({"error": "Could not find both charts. Please provide valid chart IDs."})
            
            subject1_data = birth_data_list[0]["birth_data"]
            subject2_data = birth_data_list[1]["birth_data"]
            
        elif subject1_birth_data and subject2_birth_data:
            # Use provided birth data
            subject1_data = subject1_birth_data.model_dump()
            subject2_data = subject2_birth_data.model_dump()
        else:
            return json.dumps({
                "error": "Please provide either 2 chart_ids OR both subject1_birth_data and subject2_birth_data"
            })
        
        # Calculate compatibility
        compatibility_data = await calculate_compatibility_score_from_data(
            subject1_data,
            subject2_data,
        )
        
        return json.dumps(compatibility_data, default=str)
    
    except Exception as e:
        logger.error(f"Error calculating compatibility: {str(e)}")
        return json.dumps({"error": f"Failed to calculate compatibility: {str(e)}"})


# Planets relevant for transits (no Asc/MC/Desc/IC — those are location-dependent)
TRANSIT_PLANETS = [
    "sun", "moon", "mercury", "venus", "mars",
    "jupiter", "saturn", "uranus", "neptune", "pluto",
]


@function_tool
async def get_current_transits(
    ctx: RunContextWrapper[AgentContext],
    chart_id: Optional[str] = None,
) -> str:
    """
    Get current planetary transit positions (real-time).

    Use this tool when users ask about current transits, what planets are doing now,
    or how current planetary positions affect their natal chart.

    Args:
        ctx: Agent context containing user_id
        chart_id: Optional chart ID — if provided, also returns the user's natal planets for comparison

    Returns:
        JSON with transit_planets (current positions) and optionally natal_planets for transit-to-natal analysis
    """
    try:
        now = datetime.now(timezone.utc)

        # Generate a chart for the current moment using Greenwich as reference
        # Planetary zodiacal positions (sign + degree) are the same worldwide
        transit_data = await generate_birth_chart(
            name="Current Transits",
            year=now.year,
            month=now.month,
            day=now.day,
            hour=now.hour,
            minute=now.minute,
            city="Greenwich",
            nation="GB",
            longitude=-0.0005,
            latitude=51.4769,
            timezone="Europe/London",
        )

        # Extract transit planet positions
        chart_data = transit_data
        if "chart_data" in chart_data and isinstance(chart_data["chart_data"], dict):
            chart_data = chart_data["chart_data"]

        subject = chart_data.get("subject", {})
        transit_planets = {}

        for planet_key in TRANSIT_PLANETS:
            planet_data = subject.get(planet_key)
            if planet_data and isinstance(planet_data, dict):
                planet_info = {
                    "name": planet_data.get("name"),
                    "sign": planet_data.get("sign"),
                    "position": planet_data.get("abs_pos"),
                }
                # Include retrograde status if available
                if "retrograde" in planet_data:
                    planet_info["retrograde"] = planet_data["retrograde"]
                transit_planets[planet_key] = planet_info

        result = {
            "timestamp": now.isoformat(),
            "transit_planets": transit_planets,
        }

        # If chart_id provided, also fetch natal chart for comparison
        if chart_id and ctx.context and ctx.context.user_id:
            try:
                natal_chart = get_birth_chart_by_id(ctx.context.user_id, chart_id)
                natal_data = extract_minimal_chart_data(natal_chart)
                result["natal_chart_name"] = natal_data.get("name")
                result["natal_planets"] = natal_data.get("planets", {})
            except Exception as e:
                logger.warning(f"Could not fetch natal chart {chart_id} for transit comparison: {e}")
                result["natal_chart_error"] = f"Could not fetch natal chart: {str(e)}"

        result_json = json.dumps(result, default=str)

        within_limit, token_count, message = default_monitor.check_limit(result_json)
        if not within_limit:
            logger.warning(f"Token limit exceeded in get_current_transits: {message}")
            result_json = default_monitor.truncate_content(result_json, default_monitor.limit - 10000)

        return result_json

    except Exception as e:
        logger.error(f"Error fetching current transits: {str(e)}")
        return json.dumps({"error": f"Failed to fetch current transits: {str(e)}"})


ASTROLOGY_SPECIALIST_INSTRUCTIONS = """You are a warm, conversational expert astrologer for natal chart interpretation, compatibility, and transit analysis.

## Style
Be concise, direct, and friendly -- like chatting with a knowledgeable friend. Reference specific positions (e.g., "Sun in Leo, 5th house"). For compatibility, balance strengths and challenges.

## Language
- ALWAYS reply in the exact same language the user writes in.
- CRITICAL: Bulgarian and Russian are DIFFERENT languages. If the user writes in Bulgarian, respond in Bulgarian — NEVER in Russian. Pay close attention to the script and vocabulary differences.
- If you are unsure of the language, default to matching the user's message character by character.

## Bulgarian Astrology Terminology
When responding in Bulgarian, you MUST use these correct astrology terms:
- Houses → Домове (NEVER use "къщи")
- Ascendant → Асцендент
- Descendant → Десцендент
- Midheaven (MC) → Среда на небето (MC)
- IC → Дъно на небето (IC)
- Sun sign / Moon sign → Слънчев знак / Лунен знак
- Rising sign → Възходящ знак
- Transit → Транзит
- Natal chart → Натална карта
- Synastry → Синастрия
- Aspects: Конюнкция, Опозиция, Тригон, Квадратура, Секстил
- Retrograde → Ретрограден
- Cusp → Връх (на дом)
- Signs: Овен, Телец, Близнаци, Рак, Лъв, Дева, Везни, Скорпион, Стрелец, Козирог, Водолей, Риби
- Planets: Слънце, Луна, Меркурий, Венера, Марс, Юпитер, Сатурн, Уран, Нептун, Плутон

## Tools
- Charts: `get_user_birth_chart(chart_ids=["id"])` for one, `get_user_birth_chart(chart_ids=["id1", "id2"])` for multiple. No IDs = most recent. Use `list_user_charts()` to help users find charts.
- Compatibility: Use ONLY `calculate_compatibility(chart_ids=["id1", "id2"])` for saved charts OR `calculate_compatibility(subject1_birth_data=..., subject2_birth_data=...)` for unsaved data. Do NOT call get_user_birth_chart before compatibility -- the tool fetches data directly.
- Transits: Use `get_current_transits()` to get real-time planetary positions. Use `get_current_transits(chart_id="id")` to also include the user's natal chart for personalized transit readings. When the user asks about current transits relative to their chart, ALWAYS pass their chart_id so you can compare transit positions to natal positions.

## Transit Interpretation Guide
When interpreting transits:
- Compare transit planet positions to natal planet positions and identify aspects (conjunctions within ~8°, oppositions ~180°, trines ~120°, squares ~90°, sextiles ~60° — all with standard orbs).
- Note which natal house each transit planet is passing through.
- Highlight major outer planet transits: Saturn return (~29 years), Jupiter return (~12 years), Uranus opposition (~42 years).
- If a planet is retrograde, emphasize its introspective/revisionary energy for that domain.
- Prioritize slow-moving planet transits (Pluto, Neptune, Uranus, Saturn, Jupiter) as they have longer-lasting effects.

## Rules
Stay on astrology. Use provided chart data only -- don't guess. Guide users to create charts if needed."""


# Initialize the agent
astrology_specialist = Agent(
    name="Astrology Specialist",
    instructions=ASTROLOGY_SPECIALIST_INSTRUCTIONS,
    model='gpt-5-mini',
    tools=[
        get_user_birth_chart,
        list_user_charts,
        calculate_compatibility,
        get_current_transits,
    ],
)

