"""
LinkedIn Plugin Agent - Handles professional networking and posts.
"""

from ..core.base import BaseAgent, AgentContext, AgentResponse
from .logic import get_linkedin_info


class LinkedInPluginAgent(BaseAgent):
    """
    Agent responsible for LinkedIn profile management and posting.
    """

    name = "linkedin"
    description = "Manages LinkedIn profiles, fetches info, and creates posts"
    keywords = [
        "linkedin",
        "linked in",
        "professional",
        "post linkedin",
        "kerja",
        "profil linkedin",
    ]

    async def get_status(
        self, session_id: str = "default", base_url: str = "http://localhost:8000"
    ) -> str:
        """LinkedIn operations are stateless - always returns none."""
        return "none"

    async def handle(self, message: str, context: AgentContext) -> AgentResponse:
        """Process a LinkedIn request."""
        # Simple fallback for now
        result = await get_linkedin_info(context.user_id)

        return AgentResponse(message=result, status="completed", agent_name=self.name)

    def get_tools(self) -> list:
        from .tools import get_linkedin_tools

        return get_linkedin_tools()
