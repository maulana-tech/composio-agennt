"""
Research Plugin Agent - Handles web search and information gathering.
"""

from ..core.base import BaseAgent, AgentContext, AgentResponse
from .logic import serper_search


class ResearchPluginAgent(BaseAgent):
    """
    Agent responsible for broad web research and information gathering.
    """

    name = "research"
    description = (
        "Conducts web research and gathers information from across the internet"
    )
    keywords = ["search", "cari", "research", "find info", "web search", "google"]

    async def get_status(
        self, session_id: str = "default", base_url: str = "http://localhost:8000"
    ) -> str:
        """Research is stateless - always returns none."""
        return "none"

    async def handle(self, message: str, context: AgentContext) -> AgentResponse:
        """Process a research request."""
        # Typically the router handles the initial intent, but if it lands here
        # we perform a broad search.
        results = await serper_search(message)

        return AgentResponse(message=results, status="completed", agent_name=self.name)

    def get_tools(self) -> list:
        from .tools import get_research_tools

        return get_research_tools()
