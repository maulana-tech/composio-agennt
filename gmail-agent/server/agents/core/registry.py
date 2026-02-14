"""
AgentRegistry - Dynamic agent registration and lookup.

Clients register only the agents they need. The registry provides
lookup by name, keyword matching, and tool aggregation.
"""

from typing import Dict, List, Optional
from .base import BaseAgent

import logging

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Registry for pluggable agents.

    Usage:
        registry = AgentRegistry()
        registry.register(GIPAAgent())
        registry.register(DossierAgent())

        # Find agent by keyword match
        agent = registry.match("Buatkan GIPA request")

        # Get all tools for ReAct agent
        tools = registry.get_all_tools()
    """

    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """Register an agent. Overwrites if name already exists."""
        if not agent.name:
            raise ValueError(f"Agent {agent.__class__.__name__} has no name set")
        self._agents[agent.name] = agent
        logger.info(f"Registered agent: {agent.name} ({agent.description})")

    def unregister(self, name: str) -> None:
        """Unregister an agent by name."""
        self._agents.pop(name, None)

    def get(self, name: str) -> Optional[BaseAgent]:
        """Get agent by name."""
        return self._agents.get(name)

    def match(self, message: str) -> Optional[BaseAgent]:
        """Find the first agent whose keywords match the message."""
        for agent in self._agents.values():
            if agent.matches_keywords(message):
                return agent
        return None

    async def find_active(
        self, session_id: str = "default", base_url: str = "http://localhost:8000"
    ) -> Optional[BaseAgent]:
        """Find agent with an active session."""
        for agent in self._agents.values():
            try:
                status = await agent.get_status(session_id, base_url)
                if agent.is_active_session(status):
                    return agent
            except Exception:
                continue
        return None

    def get_all_tools(self) -> list:
        """Aggregate tools from all registered agents for the ReAct agent."""
        tools = []
        for agent in self._agents.values():
            agent_tools = agent.get_tools()
            if agent_tools:
                tools.extend(agent_tools)
        return tools

    def get_all_agents(self) -> List[BaseAgent]:
        """Get all registered agents."""
        return list(self._agents.values())

    def list_agents(self) -> List[Dict]:
        """List all registered agents with their info."""
        return [
            {
                "name": agent.name,
                "description": agent.description,
                "keywords": agent.keywords,
                "active_statuses": agent.active_statuses,
                "num_tools": len(agent.get_tools()),
            }
            for agent in self._agents.values()
        ]

    @property
    def agents(self) -> Dict[str, BaseAgent]:
        return dict(self._agents)

    def __len__(self) -> int:
        return len(self._agents)

    def __contains__(self, name: str) -> bool:
        return name in self._agents
