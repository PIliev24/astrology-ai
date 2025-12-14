"""
Relationship Analyst Agent
Specialized agent for analyzing relationship compatibility and synastry between two people.
"""

import json
from typing import Optional
import logging

from agents import Agent, RunContextWrapper, function_tool
from supabase import Client

from services.birth_chart import create_astrological_subject
from services.relationships import get_relationship_score, create_composite_subject
from services.aspects import get_synastry_aspects
from services.database import get_birth_chart_by_id, get_user_relationships

logger = logging.getLogger(__name__)


# Context type for agent
class AgentContext:
    """Context passed to agent tools containing user and database information"""
    def __init__(self, user_id: str, supabase: Client):
        self.user_id = user_id
        self.supabase = supabase


@function_tool
async def get_relationship_score_for_charts(
    ctx: RunContextWrapper[AgentContext],
    chart1_id: str,
    chart2_id: str,
) -> str:
    """
    Calculate compatibility score between two saved birth charts.
    
    Args:
        ctx: Agent context containing user_id and supabase client
        chart1_id: First chart ID
        chart2_id: Second chart ID
    
    Returns:
        JSON string containing compatibility score and analysis
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
        
        score_data = get_relationship_score(subject1, subject2)
        
        return json.dumps(score_data, indent=2, default=str)
    
    except Exception as e:
        logger.error(f"Error calculating relationship score: {str(e)}")
        return json.dumps({"error": f"Failed to calculate relationship score: {str(e)}"})


@function_tool
async def analyze_synastry(
    ctx: RunContextWrapper[AgentContext],
    chart1_id: str,
    chart2_id: str,
) -> str:
    """
    Perform a full synastry analysis between two charts.
    Returns detailed aspect information for relationship compatibility.
    
    Args:
        ctx: Agent context containing user_id and supabase client
        chart1_id: First chart ID
        chart2_id: Second chart ID
    
    Returns:
        JSON string containing detailed synastry analysis
    """
    try:
        chart1 = get_birth_chart_by_id(ctx.context.supabase, ctx.context.user_id, chart1_id)
        chart2 = get_birth_chart_by_id(ctx.context.supabase, ctx.context.user_id, chart2_id)
        
        # Recreate subjects
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
        
        # Get synastry aspects
        aspects = get_synastry_aspects(subject1, subject2)
        
        # Get relationship score
        score_data = get_relationship_score(subject1, subject2)
        
        # Analyze aspect types
        positive_aspects = [a for a in aspects if a.get("aspect") in ["trine", "sextile", "conjunction"]]
        challenging_aspects = [a for a in aspects if a.get("aspect") in ["square", "opposition"]]
        
        result = {
            "subject1": chart1.name,
            "subject2": chart2.name,
            "compatibility_score": score_data.get("compatibility_percentage"),
            "total_aspects": len(aspects),
            "positive_aspects_count": len(positive_aspects),
            "challenging_aspects_count": len(challenging_aspects),
            "aspects": aspects,
            "analysis": {
                "communication": "Analyze Mercury aspects for communication style",
                "emotions": "Analyze Moon and Venus aspects for emotional connection",
                "passion": "Analyze Mars aspects for physical attraction and drive",
                "long_term": "Analyze Saturn aspects for commitment and stability",
            },
        }
        
        return json.dumps(result, indent=2, default=str)
    
    except Exception as e:
        logger.error(f"Error analyzing synastry: {str(e)}")
        return json.dumps({"error": f"Failed to analyze synastry: {str(e)}"})


@function_tool
async def get_composite_chart(
    ctx: RunContextWrapper[AgentContext],
    chart1_id: str,
    chart2_id: str,
) -> str:
    """
    Get composite chart data (midpoint method) for two people.
    The composite chart represents the relationship itself as a third entity.
    
    Args:
        ctx: Agent context containing user_id and supabase client
        chart1_id: First chart ID
        chart2_id: Second chart ID
    
    Returns:
        JSON string containing composite chart data
    """
    try:
        chart1 = get_birth_chart_by_id(ctx.context.supabase, ctx.context.user_id, chart1_id)
        chart2 = get_birth_chart_by_id(ctx.context.supabase, ctx.context.user_id, chart2_id)
        
        # Recreate subjects
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
        
        composite_data = create_composite_subject(subject1, subject2)
        
        return json.dumps(composite_data, indent=2, default=str)
    
    except Exception as e:
        logger.error(f"Error getting composite chart: {str(e)}")
        return json.dumps({"error": f"Failed to get composite chart: {str(e)}"})


# Agent Instructions
RELATIONSHIP_ANALYST_INSTRUCTIONS = """You are a relationship astrology expert specializing in compatibility analysis.

Your expertise includes:
- Analyzing synastry (aspects between two people's charts)
- Interpreting composite charts (the relationship as a third entity)
- Explaining compatibility scores and what they mean
- Describing how planetary aspects between two people affect their relationship
- Providing insights about communication styles, emotional connection, and long-term potential

When analyzing relationships:
- Always consider both synastry aspects AND composite charts for a complete picture
- Explain what the compatibility score means - it's a starting point, not a final judgment
- Break down relationship dynamics by planetary pairs:
  * Sun-Sun: Core identity and ego expression
  * Moon-Moon: Emotional needs and responses
  * Venus-Venus: Love language and values
  * Mars-Mars: Physical attraction and conflict style
  * Mercury-Mercury: Communication and mental connection
  * Saturn aspects: Commitment, responsibility, and long-term potential
- Be balanced - explain both strengths and challenges
- Remember that challenging aspects (squares, oppositions) can create growth and depth
- Harmonious aspects (trines, sextiles) create ease but may lack spark

When users ask about relationships:
1. Use get_relationship_score_for_charts() to get a compatibility percentage
2. Use analyze_synastry() for detailed aspect analysis between two people
3. Use get_composite_chart() to understand the relationship as its own entity

Be constructive, insightful, and help users understand relationship dynamics through astrology. 
Remember that astrology shows potential and tendencies, not fixed outcomes."""


# Initialize the agent
relationship_analyst = Agent[AgentContext](
    name="Relationship Analyst",
    instructions=RELATIONSHIP_ANALYST_INSTRUCTIONS,
    tools=[get_relationship_score_for_charts, analyze_synastry, get_composite_chart],
    model="gpt-4o",
)

