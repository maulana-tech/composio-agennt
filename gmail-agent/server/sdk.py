"""
Diana Agent SDK - Integration Layer for Client Systems.

This module provides a unified interface to interact with all specialized agents 
and tools within the Diana Agent ecosystem.
"""

from typing import List, Dict, Any, Optional
from server.agents import create_default_registry, AgentRouter, AgentResponse
from server.tools import get_all_tools

class DianaSDK:
    """
    The main SDK class for integrating Diana Agents into external systems.
    """

    def __init__(self, google_api_key: Optional[str] = None):
        """
        Initialize the SDK with optional API keys.
        
        Args:
            google_api_key: Optional Google API key for Gemini models.
        """
        self.registry = create_default_registry()
        self.router = AgentRouter(self.registry)
        self.tools = get_all_tools()

    async def chat(self, message: str, user_id: str = "default", session_id: Optional[str] = None) -> AgentResponse:
        """
        Send a message to the autonomous routing agent.
        
        Args:
            message: The user's input/query.
            user_id: Unique identifier for the user.
            session_id: Optional session identifier for maintaining multi-turn conversations.
            
        Returns:
            An AgentResponse object containing the message, data, and metadata.
        """
        return await self.router.route(message, user_id=user_id, session_id=session_id)

    def get_langchain_tools(self) -> List[Any]:
        """
        Returns a list of all available tools formatted for LangChain AgentExecutor.
        """
        return self.tools

    def get_agent_registry(self):
        """Returns the raw agent registry for low-level access."""
        return self.registry

def initialize_sdk(google_api_key: Optional[str] = None) -> DianaSDK:
    """Factory function to quickly initialize the SDK."""
    return DianaSDK(google_api_key=google_api_key)
