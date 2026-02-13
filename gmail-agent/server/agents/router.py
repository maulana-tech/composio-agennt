"""
AgentRouter - Unified routing logic for all agents.

Replaces the duplicated routing code in chat() and chat_stream().
Checks registered agents for keyword matches and active sessions,
routing to the appropriate handler before falling through to ReAct.
"""

from typing import Optional, List, Dict
from server.agents.base import AgentContext, AgentResponse
from server.agents.registry import AgentRegistry

import logging

logger = logging.getLogger(__name__)


class AgentRouter:
    """
    Routes messages to the appropriate specialized agent.

    Priority:
    1. Active session check — if any agent has an active session, route to it
    2. Keyword match — if message matches an agent's keywords, route to it
    3. Fall through — return None, let ReAct agent handle it

    Usage:
        router = AgentRouter(registry)
        result = await router.route("Buatkan GIPA request", user_id="default")
        if result:
            # Handled by specialized agent
        else:
            # Fall through to ReAct
    """

    def __init__(self, registry: AgentRegistry):
        self.registry = registry

    async def route(
        self,
        message: str,
        user_id: str = "default",
        session_id: str = "default",
        conversation_history: Optional[List[Dict]] = None,
        base_url: str = "http://localhost:8000",
        metadata: Optional[Dict] = None,
    ) -> Optional[AgentResponse]:
        """
        Attempt to route message to a specialized agent.

        Returns:
            AgentResponse if an agent handled the message, None otherwise.
        """
        context = AgentContext(
            user_id=user_id,
            session_id=session_id,
            conversation_history=conversation_history,
            base_url=base_url,
            metadata=metadata or {},
        )

        # 1. Check for active sessions first
        active_agent = await self.registry.find_active(session_id, base_url)
        if active_agent:
            logger.info(f"Routing to active agent: {active_agent.name}")
            response = await active_agent.handle(message, context)
            if response.message == "__PASSTHROUGH__":
                return None  # Fall through to ReAct
            response.agent_name = active_agent.name
            return response

        # 2. Check keyword match
        matched_agent = self.registry.match(message)
        if matched_agent:
            logger.info(f"Routing by keyword to: {matched_agent.name}")
            response = await matched_agent.handle(message, context)
            if response.message == "__PASSTHROUGH__":
                return None  # Fall through to ReAct
            response.agent_name = matched_agent.name
            return response

        # 3. No match — fall through to ReAct agent
        return None
