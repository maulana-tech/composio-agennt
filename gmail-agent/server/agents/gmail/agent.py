"""
Gmail Plugin Agent - Handles email communication.
"""

from ..core.base import BaseAgent, AgentContext, AgentResponse
from .logic import send_gmail


class GmailPluginAgent(BaseAgent):
    """
    Agent responsible for Gmail processing and sending.
    """

    name = "gmail"
    description = "Sends emails, creates drafts, and fetches messages from Gmail"
    keywords = ["email", "gmail", "kirim email", "pesan", "inbox", "surat"]

    async def get_status(
        self, session_id: str = "default", base_url: str = "http://localhost:8000"
    ) -> str:
        """Gmail operations are stateless - always returns none."""
        return "none"

    async def handle(self, message: str, context: AgentContext) -> AgentResponse:
        """Process a Gmail request."""
        # Simple fallback to sending if not specific
        result = await send_gmail(
            context.user_id, "me@example.com", "Message from AI", message
        )

        return AgentResponse(message=result, status="completed", agent_name=self.name)

    def get_tools(self) -> list:
        from .tools import get_gmail_tools

        return get_gmail_tools()
