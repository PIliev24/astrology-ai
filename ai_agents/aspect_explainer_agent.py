"""
Aspect Explainer Agent
Specialized agent for explaining astrological aspects (conjunctions, squares, trines, etc.) and their meanings.
"""

import json
from typing import Optional
import logging

from agents import Agent, RunContextWrapper, function_tool
from supabase import Client

from services.birth_chart import create_astrological_subject
from services.aspects import get_natal_aspects, get_synastry_aspects
from services.database import get_birth_chart_by_id, get_user_aspects

logger = logging.getLogger(__name__)


# Context type for agent
class AgentContext:
    """Context passed to agent tools containing user and database information"""
    def __init__(self, user_id: str, supabase: Client):
        self.user_id = user_id
        self.supabase = supabase


@function_tool
async def get_natal_aspects_for_chart(
    ctx: RunContextWrapper[AgentContext],
    chart_id: Optional[str] = None,
    chart_name: Optional[str] = None,
) -> str:
    """
    Get natal aspects for a user's saved birth chart.
    
    Args:
        ctx: Agent context containing user_id and supabase client
        chart_id: Optional specific chart ID
        chart_name: Optional chart name to look up
    
    Returns:
        JSON string containing all natal aspects for the chart
    """
    try:
        from services.database import get_user_birth_charts
        
        if chart_id:
            chart = get_birth_chart_by_id(ctx.context.supabase, ctx.context.user_id, chart_id)
        else:
            charts = get_user_birth_charts(ctx.context.supabase, ctx.context.user_id)
            if not charts:
                return json.dumps({"error": "No birth charts found"})
            
            if chart_name:
                chart = next((c for c in charts if c.name.lower() == chart_name.lower()), None)
                if not chart:
                    return json.dumps({"error": f"Chart '{chart_name}' not found"})
            else:
                chart = charts[0]
        
        # Recreate subject from stored data
        birth_data = chart.birth_data
        subject = create_astrological_subject(
            name=chart.name,
            year=birth_data["year"],
            month=birth_data["month"],
            day=birth_data["day"],
            hour=birth_data["hour"],
            minute=birth_data["minute"],
            city=birth_data.get("city"),
            nation=birth_data.get("nation"),
            lng=birth_data.get("longitude"),
            lat=birth_data.get("latitude"),
            tz_str=birth_data.get("timezone"),
            online=birth_data.get("online", False),
        )
        
        aspects = get_natal_aspects(subject)
        
        return json.dumps({
            "chart_name": chart.name,
            "aspects": aspects,
            "total_aspects": len(aspects),
        }, indent=2, default=str)
    
    except Exception as e:
        logger.error(f"Error fetching natal aspects: {str(e)}")
        return json.dumps({"error": f"Failed to get natal aspects: {str(e)}"})


@function_tool
async def get_synastry_aspects_for_charts(
    ctx: RunContextWrapper[AgentContext],
    chart1_id: str,
    chart2_id: str,
) -> str:
    """
    Get synastry aspects between two saved birth charts.
    
    Args:
        ctx: Agent context containing user_id and supabase client
        chart1_id: First chart ID
        chart2_id: Second chart ID
    
    Returns:
        JSON string containing synastry aspects between the two charts
    """
    try:
        chart1 = get_birth_chart_by_id(ctx.context.supabase, ctx.context.user_id, chart1_id)
        chart2 = get_birth_chart_by_id(ctx.context.supabase, ctx.context.user_id, chart2_id)
        
        # Recreate subjects from stored data
        birth_data1 = chart1.birth_data
        subject1 = create_astrological_subject(
            name=chart1.name,
            year=birth_data1["year"],
            month=birth_data1["month"],
            day=birth_data1["day"],
            hour=birth_data1["hour"],
            minute=birth_data1["minute"],
            city=birth_data1.get("city"),
            nation=birth_data1.get("nation"),
            lng=birth_data1.get("longitude"),
            lat=birth_data1.get("latitude"),
            tz_str=birth_data1.get("timezone"),
            online=birth_data1.get("online", False),
        )
        
        birth_data2 = chart2.birth_data
        subject2 = create_astrological_subject(
            name=chart2.name,
            year=birth_data2["year"],
            month=birth_data2["month"],
            day=birth_data2["day"],
            hour=birth_data2["hour"],
            minute=birth_data2["minute"],
            city=birth_data2.get("city"),
            nation=birth_data2.get("nation"),
            lng=birth_data2.get("longitude"),
            lat=birth_data2.get("latitude"),
            tz_str=birth_data2.get("timezone"),
            online=birth_data2.get("online", False),
        )
        
        aspects = get_synastry_aspects(subject1, subject2)
        
        return json.dumps({
            "subject1": chart1.name,
            "subject2": chart2.name,
            "aspects": aspects,
            "total_aspects": len(aspects),
        }, indent=2, default=str)
    
    except Exception as e:
        logger.error(f"Error fetching synastry aspects: {str(e)}")
        return json.dumps({"error": f"Failed to get synastry aspects: {str(e)}"})


@function_tool
async def explain_aspect(
    ctx: RunContextWrapper[AgentContext],
    aspect_name: str,
    planet1: str,
    planet2: str,
    orb: Optional[float] = None,
) -> str:
    """
    Get a detailed explanation of a specific astrological aspect.
    Use this to provide in-depth information about what an aspect means.
    
    Args:
        ctx: Agent context
        aspect_name: Name of the aspect (e.g., "conjunction", "square", "trine", "opposition", "sextile")
        planet1: First planet in the aspect
        planet2: Second planet in the aspect
        orb: Optional orb (degree of separation)
    
    Returns:
        JSON string with aspect explanation
    """
    # This is a helper tool that returns structured information
    # The agent will use this to provide detailed explanations
    aspect_info = {
        "aspect": aspect_name,
        "planets": [planet1, planet2],
        "orb": orb,
        "note": "Use this information to explain the aspect's meaning and significance",
    }
    
    return json.dumps(aspect_info, indent=2)


# Agent Instructions
ASPECT_EXPLAINER_INSTRUCTIONS = """You are an expert in astrological aspects - the angular relationships between planets.

Your expertise includes:
- Explaining what each aspect type means (conjunction, square, trine, opposition, sextile)
- Describing how planetary aspects influence personality and life experiences
- Interpreting aspect patterns and configurations
- Explaining the difference between harmonious (trine, sextile) and challenging (square, opposition) aspects
- Providing insights about how aspects manifest in daily life

When explaining aspects:
- Always identify the planets involved and the aspect type
- Explain what the aspect means in general terms
- Describe how the specific planets involved add nuance to the aspect
- For challenging aspects (squares, oppositions), explain both the tension and growth potential
- For harmonious aspects (trines, sextiles), explain the natural flow and talents
- Mention the orb (degree of separation) when relevant - tighter orbs are stronger
- Connect aspects to real-life experiences and behaviors

Aspect meanings:
- **Conjunction** (0°): Planets blend their energies, creating a strong combined influence
- **Square** (90°): Creates tension and challenges that require growth and integration
- **Trine** (120°): Harmonious flow, natural talents, and ease of expression
- **Opposition** (180°): Creates polarity and awareness through contrast and balance
- **Sextile** (60°): Opportunities and supportive connections between planets

When users ask about aspects:
1. Use get_natal_aspects_for_chart() to get all aspects in their birth chart
2. Use get_synastry_aspects_for_charts() to compare aspects between two people
3. Use explain_aspect() to provide detailed explanations of specific aspects

Be clear, insightful, and help users understand how aspects shape their astrological profile."""


# Initialize the agent
aspect_explainer = Agent[AgentContext](
    name="Aspect Explainer",
    instructions=ASPECT_EXPLAINER_INSTRUCTIONS,
    tools=[get_natal_aspects_for_chart, get_synastry_aspects_for_charts, explain_aspect],
    model="gpt-4o",
)

