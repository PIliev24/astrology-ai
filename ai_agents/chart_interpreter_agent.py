"""
Chart Interpreter Agent
Specialized agent for interpreting birth chart data and explaining planetary positions, houses, and their meanings.
"""

import json
from typing import Optional
import logging

from agents import Agent, RunContextWrapper, function_tool
from supabase import Client

from services.birth_chart import create_astrological_subject, get_birth_chart_data
from services.database import get_birth_chart_by_id, get_user_birth_charts
from models.astrology import BirthDataRequest

logger = logging.getLogger(__name__)


# Context type for agent - contains user_id and supabase client
class AgentContext:
    """Context passed to agent tools containing user and database information"""
    def __init__(self, user_id: str, supabase: Client):
        self.user_id = user_id
        self.supabase = supabase


@function_tool
async def get_user_birth_chart(
    ctx: RunContextWrapper[AgentContext],
    chart_name: Optional[str] = None,
    chart_id: Optional[str] = None,
) -> str:
    """
    Fetch a user's stored birth chart from the database.
    
    Args:
        ctx: Agent context containing user_id and supabase client
        chart_name: Optional name of the chart to fetch (if multiple charts exist)
        chart_id: Optional specific chart ID to fetch
    
    Returns:
        JSON string containing birth chart data including planetary positions and houses
    """
    try:
        if chart_id:
            chart = get_birth_chart_by_id(ctx.context.supabase, ctx.context.user_id, chart_id)
        else:
            charts = get_user_birth_charts(ctx.context.supabase, ctx.context.user_id)
            if not charts:
                return json.dumps({"error": "No birth charts found for this user"})
            
            if chart_name:
                chart = next((c for c in charts if c.name.lower() == chart_name.lower()), None)
                if not chart:
                    return json.dumps({"error": f"Chart '{chart_name}' not found"})
            else:
                # Return the most recent chart
                chart = charts[0]
        
        # Return chart data in a readable format
        result = {
            "name": chart.name,
            "birth_data": chart.birth_data,
            "chart_data": chart.chart_data,
        }
        
        return json.dumps(result, indent=2, default=str)
    
    except Exception as e:
        logger.error(f"Error fetching birth chart: {str(e)}")
        return json.dumps({"error": f"Failed to fetch birth chart: {str(e)}"})


@function_tool
async def calculate_birth_chart(
    ctx: RunContextWrapper[AgentContext],
    name: str,
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    city: Optional[str] = None,
    nation: Optional[str] = None,
    lng: Optional[float] = None,
    lat: Optional[float] = None,
    tz_str: Optional[str] = None,
    online: bool = False,
) -> str:
    """
    Calculate a birth chart on-the-fly from birth data.
    Use this when the user provides birth information but doesn't have a saved chart.
    
    Args:
        ctx: Agent context
        name: Person's name
        year: Birth year
        month: Birth month (1-12)
        day: Birth day
        hour: Birth hour (0-23)
        minute: Birth minute (0-59)
        city: City name (if using city/nation)
        nation: Nation code (e.g., "US", "GB")
        lng: Longitude (if using coordinates)
        lat: Latitude (if using coordinates)
        tz_str: Timezone string (e.g., "Europe/London")
        online: Whether to fetch geolocation online
    
    Returns:
        JSON string containing calculated birth chart data
    """
    try:
        subject = create_astrological_subject(
            name=name,
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            city=city,
            nation=nation,
            lng=lng,
            lat=lat,
            tz_str=tz_str,
            online=online,
        )
        
        chart_data = get_birth_chart_data(subject)
        return json.dumps(chart_data, indent=2, default=str)
    
    except Exception as e:
        logger.error(f"Error calculating birth chart: {str(e)}")
        return json.dumps({"error": f"Failed to calculate birth chart: {str(e)}"})


@function_tool
async def list_user_charts(
    ctx: RunContextWrapper[AgentContext],
) -> str:
    """
    List all birth charts saved by the user.
    
    Args:
        ctx: Agent context containing user_id and supabase client
    
    Returns:
        JSON string containing list of chart names and IDs
    """
    try:
        charts = get_user_birth_charts(ctx.context.supabase, ctx.context.user_id)
        
        result = [
            {
                "id": str(chart.id),
                "name": chart.name,
                "created_at": chart.created_at.isoformat() if chart.created_at else None,
            }
            for chart in charts
        ]
        
        return json.dumps({"charts": result}, indent=2, default=str)
    
    except Exception as e:
        logger.error(f"Error listing charts: {str(e)}")
        return json.dumps({"error": f"Failed to list charts: {str(e)}"})


# Agent Instructions
CHART_INTERPRETER_INSTRUCTIONS = """You are an expert astrologer specializing in birth chart interpretation.

Your expertise includes:
- Explaining planetary positions and their astrological significance
- Interpreting house placements and what they mean for the individual
- Describing how planets in different signs influence personality
- Explaining the meaning of planetary aspects (though you may refer to the Aspect Explainer for detailed aspect analysis)
- Providing insights about the Ascendant, Midheaven, and other chart points

When interpreting charts:
- Always reference specific planetary positions (e.g., "Sun in Leo", "Moon in Cancer")
- Explain what each planet represents and how its sign placement affects the person
- Describe house meanings and how planets in houses influence different life areas
- Be warm, insightful, and educational
- Use clear, accessible language - avoid overly technical jargon unless explaining it
- Connect astrological concepts to real-life experiences when helpful

If a user asks about their chart:
1. First, try to fetch their saved chart using get_user_birth_chart()
2. If no saved chart exists, use calculate_birth_chart() with the birth data they provide
3. Use list_user_charts() to help users find their charts if they have multiple

Always be respectful and remember that astrology is a tool for self-reflection and understanding, not deterministic fate."""


# Initialize the agent
chart_interpreter = Agent[AgentContext](
    name="Chart Interpreter",
    instructions=CHART_INTERPRETER_INSTRUCTIONS,
    tools=[get_user_birth_chart, calculate_birth_chart, list_user_charts],
    model="gpt-4o",
)

