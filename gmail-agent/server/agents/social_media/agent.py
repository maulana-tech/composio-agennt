"""
Social Media Plugin Agent - Handles posting to Twitter and Facebook.
"""

from ..core.base import BaseAgent, AgentContext, AgentResponse
from .logic import post_to_twitter, post_to_facebook


class SocialMediaPluginAgent(BaseAgent):
    """
    Agent responsible for social media management and posting.
    """

    name = "social_media"
    description = "Posts content and manages Twitter/X and Facebook accounts"
    keywords = [
        "post",
        "share",
        "twitter",
        "facebook",
        "sosmed",
        "social media",
        "unggah",
    ]

    async def get_status(
        self, session_id: str = "default", base_url: str = "http://localhost:8000"
    ) -> str:
        """Social media posting is stateless - always returns none."""
        return "none"

    async def handle(self, message: str, context: AgentContext) -> AgentResponse:
        """Process a social media request."""
        # For simplicity, we default to Twitter if not specified.
        # In a real scenario, we'd use an LLM or keyword detection here to decide.
        if "facebook" in message.lower():
            result = await post_to_facebook(context.user_id, message)
        else:
            result = await post_to_twitter(context.user_id, message)

        return AgentResponse(message=result, status="completed", agent_name=self.name)

    def get_tools(self) -> list:
        from .tools import get_social_media_tools

        return get_social_media_tools()
