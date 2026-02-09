"""
Astrology Specialist Agent
Single comprehensive agent for birth chart interpretation, analysis, and compatibility questions
"""

import json
import logging
from typing import Optional
from pydantic import BaseModel, Field
from agents import Agent, ModelSettings, RunContextWrapper, function_tool

from services.database import get_birth_chart_by_id, get_user_birth_charts, get_birth_data_by_chart_ids
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


ASTROLOGY_SPECIALIST_INSTRUCTIONS = """You are a warm, conversational expert astrologer for natal chart interpretation and compatibility.

## Style
Be concise, direct, and friendly -- like chatting with a knowledgeable friend. Reference specific positions (e.g., "Sun in Leo, 5th house"). For compatibility, balance strengths and challenges.

## Tools
- Charts: `get_user_birth_chart(chart_ids=["id"])` for one, `get_user_birth_chart(chart_ids=["id1", "id2"])` for multiple. No IDs = most recent. Use `list_user_charts()` to help users find charts.
- Compatibility: Use ONLY `calculate_compatibility(chart_ids=["id1", "id2"])` for saved charts OR `calculate_compatibility(subject1_birth_data=..., subject2_birth_data=...)` for unsaved data. Do NOT call get_user_birth_chart before compatibility -- the tool fetches data directly.

## Rules
Stay on astrology. Use provided chart data only -- don't guess. Guide users to create charts if needed."""


# Initialize the agent
astrology_specialist = Agent(
    name="Astrology Specialist",
    instructions=ASTROLOGY_SPECIALIST_INSTRUCTIONS,
    model="gpt-4.1-mini",
    model_settings=ModelSettings(
        parallel_tool_calls=True,
    ),
    tools=[
        get_user_birth_chart,
        list_user_charts,
        calculate_compatibility,
    ],
)

