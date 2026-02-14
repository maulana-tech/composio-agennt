"""
Quote Plugin Agent - Handles graphic quote generation.
"""

from ..core.base import BaseAgent, AgentContext, AgentResponse
from .logic import generate_simple_quote


class QuotePluginAgent(BaseAgent):
    """
    Agent responsible for generating visual quote graphics.
    """

    name = "quote"
    description = "Generates beautiful graphic quote cards from text and author names"
    keywords = ["quote", "kutipan", "gambar kutipan", "quote image", "kartu kutipan"]

    async def get_status(
        self, session_id: str = "default", base_url: str = "http://localhost:8000"
    ) -> str:
        """Quote generation is stateless - always returns none."""
        return "none"

    async def handle(self, message: str, context: AgentContext) -> AgentResponse:
        """Process a quote generation request."""
        # Simple extraction for demo: message is quote, author is 'User'
        path = await generate_simple_quote(message, "User")

        return AgentResponse(
            message=f"✅ Quote image generated: {path}",
            status="completed",
            agent_name=self.name,
            data={"image_path": path},
        )

    def get_tools(self) -> list:
        from .tools import get_quote_tools

        return get_quote_tools()
