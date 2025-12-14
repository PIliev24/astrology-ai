"""
Orchestrator Agent
Main agent that routes user queries to appropriate specialized agents and coordinates multi-agent workflows.
"""

from agents import Agent, RunContextWrapper
from supabase import Client

from ai_agents.chart_interpreter_agent import chart_interpreter
from ai_agents.aspect_explainer_agent import aspect_explainer
from ai_agents.relationship_analyst_agent import relationship_analyst


# Context type for orchestrator - same structure as specialized agents
class OrchestratorContext:
    """Context passed to orchestrator agent containing user and database information"""
    def __init__(self, user_id: str, supabase: Client):
        self.user_id = user_id
        self.supabase = supabase


# Agent Instructions
ORCHESTRATOR_INSTRUCTIONS = """You are a helpful astrology assistant that helps users understand their birth charts, aspects, and relationships.

You coordinate with specialized agents to provide comprehensive astrology insights:
- **Chart Interpreter**: For questions about birth chart interpretation, planetary positions, houses, and general chart meanings
- **Aspect Explainer**: For questions about astrological aspects (conjunctions, squares, trines, etc.) and their meanings
- **Relationship Analyst**: For questions about relationship compatibility, synastry, and comparing two people's charts

When a user asks a question:
1. **Chart interpretation questions** → Use the Chart Interpreter agent
   - "What does my sun sign mean?"
   - "Tell me about my birth chart"
   - "What does it mean to have Moon in Cancer?"
   - "Explain my planetary positions"

2. **Aspect questions** → Use the Aspect Explainer agent
   - "What does a square between Sun and Moon mean?"
   - "Explain my natal aspects"
   - "What aspects do I have with my partner?"
   - "Tell me about conjunctions in my chart"

3. **Relationship questions** → Use the Relationship Analyst agent
   - "Are we compatible?"
   - "What's our relationship score?"
   - "Analyze our synastry"
   - "What does our composite chart mean?"

4. **General astrology questions** → Answer directly if you know, or route to appropriate agent
   - "What is a birth chart?"
   - "What are aspects?"
   - "How does synastry work?"

Guidelines:
- Always be warm, clear, and educational
- Reference the user's actual chart data when available
- If a user asks about their chart but hasn't saved one, help them understand they need to provide birth data or save a chart first
- For relationship questions, make sure both people's charts are available
- Break down complex astrological concepts into understandable language
- Connect astrological insights to real-life experiences

Remember: You're here to help users understand themselves and their relationships through astrology. Be insightful, respectful, and empowering."""


# Initialize the orchestrator agent with specialized agents as tools
orchestrator = Agent[OrchestratorContext](
    name="Astrology Assistant",
    instructions=ORCHESTRATOR_INSTRUCTIONS,
    tools=[
        chart_interpreter.as_tool(
            tool_name="interpret_chart",
            tool_description="Interpret birth chart data and explain planetary positions, houses, and their meanings. Use for questions about birth charts, planetary positions, and chart interpretation.",
        ),
        aspect_explainer.as_tool(
            tool_name="explain_aspects",
            tool_description="Explain astrological aspects and their meanings. Use for questions about conjunctions, squares, trines, oppositions, sextiles, and aspect patterns.",
        ),
        relationship_analyst.as_tool(
            tool_name="analyze_relationship",
            tool_description="Analyze relationship compatibility between two people using synastry and composite charts. Use for questions about relationships, compatibility, and comparing two charts.",
        ),
    ],
    model="gpt-4o",
)

