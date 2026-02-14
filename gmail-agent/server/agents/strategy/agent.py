"""
Strategy Plugin Agent - Handles strategic analysis and diagram generation.
"""

from ..core.base import BaseAgent, AgentContext, AgentResponse
from .logic import analyze_strategic_prompt_logic


class StrategyPluginAgent(BaseAgent):
    """
    Agent responsible for analyzing complex strategies and visualizing them.
    """

    name = "strategy"
    description = (
        "Analyzes strategic goals and generates Mermaid diagrams to visualize plans"
    )
    keywords = [
        "strategy",
        "strategi",
        "diagram",
        "plan",
        "roadmap",
        "mermaid",
        "visualisasi",
    ]

    async def get_status(
        self, session_id: str = "default", base_url: str = "http://localhost:8000"
    ) -> str:
        """Strategy analysis is stateless - always returns none."""
        return "none"

    async def handle(self, message: str, context: AgentContext) -> AgentResponse:
        """Process a strategy request."""
        # Typically the router handles the initial intent, but if it lands here:
        results = await analyze_strategic_prompt_logic(message)

        return AgentResponse(
            message=f"Strategic analysis complete:\n\n{results}",
            status="completed",
            agent_name=self.name,
        )

    def get_tools(self) -> list:
        from .tools import get_strategy_tools

        return get_strategy_tools()
