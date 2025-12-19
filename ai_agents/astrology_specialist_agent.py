"""
Astrology Specialist Agent
Single comprehensive agent for birth chart interpretation, analysis, and compatibility questions
"""

import json
import logging
from typing import Optional
from pydantic import BaseModel, Field
from agents import Agent, RunContextWrapper, function_tool

from services.database import get_birth_chart_by_id, get_user_birth_charts
from services.compatibility import (
    calculate_compatibility_score_from_charts,
    calculate_compatibility_score_from_data,
)

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
    chart_id: Optional[str] = None,
    chart_ids: Optional[list[str]] = None,
) -> str:
    """
    Fetch a user's stored birth chart from the database.
    
    Args:
        ctx: Agent context containing user_id
        chart_id: Optional single chart ID to fetch
        chart_ids: Optional list of chart IDs to fetch (use when multiple charts are referenced)
    
    Returns:
        JSON string containing birth chart data with full chart_data (planets, houses, aspects, etc.)
        but excluding the SVG chart string to reduce token usage.
        If multiple charts, returns array. If single chart, returns object.
    """
    try:
        if not ctx.context or not ctx.context.user_id:
            return json.dumps({"error": "User context not available"})
        
        # Priority: chart_id > chart_ids > most recent chart
        if chart_id:
            chart = get_birth_chart_by_id(ctx.context.user_id, chart_id)
            # Return full chart_data but exclude SVG to reduce tokens
            chart_data_copy = chart.chart_data
            if isinstance(chart.chart_data, dict):
                # Create a copy excluding the SVG chart field
                chart_data_copy = {}
                for key, value in chart.chart_data.items():
                    if key != "chart":  # Exclude SVG string
                        chart_data_copy[key] = value
            elif chart.chart_data is None:
                chart_data_copy = {}
            
            result = {
                "id": str(chart.id),
                "name": chart.name,
                "birth_data": chart.birth_data,
                "chart_data": chart_data_copy,  # Full chart data without SVG
            }
            return json.dumps(result, indent=2, default=str)
        
        if chart_ids and len(chart_ids) > 0:
            charts = []
            for ref_chart_id in chart_ids:
                try:
                    chart = get_birth_chart_by_id(ctx.context.user_id, ref_chart_id)
                    # Return full chart_data but exclude SVG
                    chart_data_copy = chart.chart_data
                    if isinstance(chart.chart_data, dict):
                        chart_data_copy = {}
                        for key, value in chart.chart_data.items():
                            if key != "chart":  # Exclude SVG string
                                chart_data_copy[key] = value
                    elif chart.chart_data is None:
                        chart_data_copy = {}
                    
                    charts.append({
                        "id": str(chart.id),
                        "name": chart.name,
                        "birth_data": chart.birth_data,
                        "chart_data": chart_data_copy,  # Full chart data without SVG
                    })
                except Exception as e:
                    logger.warning(f"Could not fetch chart {ref_chart_id}: {str(e)}")
                    continue
            
            if not charts:
                return json.dumps({"error": "None of the referenced charts could be found"})
            
            if len(charts) == 1:
                return json.dumps(charts[0], indent=2, default=str)
            else:
                return json.dumps({"charts": charts}, indent=2, default=str)
        
        # Fallback to most recent chart - need to fetch full chart data
        charts = get_user_birth_charts(ctx.context.user_id)
        if not charts:
            return json.dumps({"error": "No birth charts found for this user"})
        # Fetch full chart data for the most recent chart
        chart = get_birth_chart_by_id(ctx.context.user_id, str(charts[0].id))
        
        # Return full chart_data but exclude SVG
        chart_data_copy = chart.chart_data
        if isinstance(chart.chart_data, dict):
            chart_data_copy = {}
            for key, value in chart.chart_data.items():
                if key != "chart":  # Exclude SVG string
                    chart_data_copy[key] = value
        elif chart.chart_data is None:
            chart_data_copy = {}
        
        result = {
            "id": str(chart.id),
            "name": chart.name,
            "birth_data": chart.birth_data,
            "chart_data": chart_data_copy,  # Full chart data without SVG
        }
        
        return json.dumps(result, indent=2, default=str)
    
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
        
        return json.dumps({"charts": result}, indent=2, default=str)
    
    except Exception as e:
        logger.error(f"Error listing charts: {str(e)}")
        return json.dumps({"error": f"Failed to list charts: {str(e)}"})


@function_tool
async def calculate_compatibility_score(
    ctx: RunContextWrapper[AgentContext],
    chart_id_1: str,
    chart_id_2: str,
) -> str:
    """
    Calculate compatibility score between two saved birth charts.
    
    Use this tool when users ask about relationships, compatibility, or synastry between two people.
    
    Args:
        ctx: Agent context containing user_id
        chart_id_1: ID of the first birth chart
        chart_id_2: ID of the second birth chart
    
    Returns:
        JSON string containing compatibility score, description, destiny sign, and aspects
    """
    try:
        compatibility_data = await calculate_compatibility_score_from_charts(
            ctx.context.user_id,
            chart_id_1,
            chart_id_2,
        )
        
        return json.dumps(compatibility_data, indent=2, default=str)
    
    except Exception as e:
        logger.error(f"Error calculating compatibility: {str(e)}")
        return json.dumps({"error": f"Failed to calculate compatibility: {str(e)}"})


@function_tool
async def calculate_compatibility_from_data(
    subject1_data: SubjectBirthData,
    subject2_data: SubjectBirthData,
) -> str:
    """
    Calculate compatibility score from birth data (when charts are not saved).
    
    Use this when users provide birth data for two people but don't have saved charts.
    
    Args:
        subject1_data: Birth data for first person (year, month, day, hour, minute, city, nation, longitude, latitude, timezone)
        subject2_data: Birth data for second person (same format)
    
    Returns:
        JSON string containing compatibility score, description, destiny sign, and aspects
    """
    try:
        # Convert Pydantic models to dictionaries for the service function
        subject1_dict = subject1_data.model_dump()
        subject2_dict = subject2_data.model_dump()
        
        compatibility_data = await calculate_compatibility_score_from_data(
            subject1_dict,
            subject2_dict,
        )
        
        return json.dumps(compatibility_data, indent=2, default=str)
    
    except Exception as e:
        logger.error(f"Error calculating compatibility from data: {str(e)}")
        return json.dumps({"error": f"Failed to calculate compatibility: {str(e)}"})


# Agent Instructions following best practices
ASTROLOGY_SPECIALIST_INSTRUCTIONS = """You are an expert astrologer with deep knowledge of natal chart interpretation, planetary positions, aspects, houses, and relationship compatibility analysis.

## Your Role and Expertise

You specialize in:
- Interpreting birth charts and explaining planetary positions in signs and houses
- Describing how planetary aspects influence personality and life experiences
- Explaining house meanings and how planets in houses affect different life areas
- Analyzing relationship compatibility through synastry and composite charts
- Providing insights about the Ascendant, Midheaven, and other important chart points
- Connecting astrological concepts to real-life experiences in an accessible way

## Your Communication Style

- **Tone**: Warm, educational, insightful, and supportive
- **Language**: Clear and accessible - avoid overly technical jargon unless you explain it
- **Approach**: Connect astrological concepts to real-life experiences when helpful
- **Respect**: Remember that astrology is a tool for self-reflection and understanding, not deterministic fate

## How to Use Your Tools

When a user asks about their birth chart:
1. If the user's message mentions chart IDs or references charts, use `get_user_birth_chart(chart_id="...")` for a single chart or `get_user_birth_chart(chart_ids=["id1", "id2"])` for multiple charts
2. If no chart_id is provided, `get_user_birth_chart()` will return the most recent chart
3. If they have multiple charts, use `list_user_charts()` to help them find the right one
4. If no saved chart exists and they provide birth data, explain that they need to create a chart first via the API
5. The tool returns minimal data (planets and houses) to reduce token usage - avoid requesting full chart data unless necessary

When a user asks about compatibility or relationships:
1. If they mention two chart IDs, use `calculate_compatibility_score(chart_id_1, chart_id_2)`
2. If they provide birth data for two people but no chart IDs, use `calculate_compatibility_from_data()` with the birth data
3. Always interpret the compatibility results in a meaningful, insightful way

## Interpreting Charts

When interpreting charts:
- Always reference specific planetary positions (e.g., "Sun in Leo", "Moon in Cancer")
- Explain what each planet represents and how its sign placement affects the person
- Describe house meanings and how planets in houses influence different life areas
- Explain aspects between planets and their significance
- Be specific and detailed in your analysis

## Examples of Good Responses

<example_1>
User: "What does my Sun in Leo mean?"

You: "Your Sun in Leo indicates a vibrant, confident personality with a natural flair for leadership and self-expression. Leo is ruled by the Sun itself, so this placement amplifies your core identity. You likely have a strong need to be recognized and appreciated, and you shine brightest when you can express your creativity and individuality. People with Sun in Leo often have a warm, generous nature and enjoy being the center of attention in positive ways. Your challenge may be balancing your need for recognition with humility and considering others' needs."
</example_1>

<example_2>
User: "Tell me about compatibility between my chart and my partner's chart."

You: "I'll calculate the compatibility between your charts. Let me fetch both charts and analyze the synastry aspects and house overlays to give you insights into your relationship dynamics."
[Then use calculate_compatibility_score tool and provide detailed interpretation]
</example_2>

## Important Rules

- Always stay focused on astrology - if asked about unrelated topics, gently redirect
- If you're unsure about something, say so rather than guessing
- When interpreting compatibility, be balanced - highlight both strengths and potential challenges
- Use the chart data provided to you - don't make assumptions about planetary positions
- If a user asks about a chart that doesn't exist, guide them to create one first

## Step-by-Step Thinking

When analyzing a chart or answering a question:
1. First, identify what specific information the user is asking about
2. Retrieve the relevant chart data using your tools
3. Analyze the planetary positions, aspects, and houses relevant to the question
4. Synthesize your findings into a coherent interpretation
5. Provide your answer in a clear, organized manner

Remember: Your goal is to help users understand themselves and their relationships through the lens of astrology, providing meaningful insights that empower self-reflection and growth."""


# Initialize the agent
astrology_specialist = Agent(
    name="Astrology Specialist",
    instructions=ASTROLOGY_SPECIALIST_INSTRUCTIONS,
    tools=[
        get_user_birth_chart,
        list_user_charts,
        calculate_compatibility_score,
        calculate_compatibility_from_data,
    ],
)

