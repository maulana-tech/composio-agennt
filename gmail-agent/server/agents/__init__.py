"""
Composio Agents - Pluggable Agent Architecture

Usage:
    from server.agents import AgentRegistry, AgentRouter, BaseAgent
    from server.agents import GIPAAgent, DossierAgent

    registry = AgentRegistry()
    registry.register(GIPAAgent())
    registry.register(DossierAgent())

    router = AgentRouter(registry)
    result = await router.route(message, user_id="default")
"""

from server.agents.base import BaseAgent, AgentContext, AgentResponse
from server.agents.registry import AgentRegistry
from server.agents.router import AgentRouter


def create_default_registry() -> AgentRegistry:
    """Create registry with all available agents pre-registered."""
    from server.agents.gipa import GIPAPluginAgent
    from server.agents.dossier import DossierPluginAgent

    registry = AgentRegistry()
    registry.register(GIPAPluginAgent())
    registry.register(DossierPluginAgent())
    return registry


__all__ = [
    "BaseAgent",
    "AgentContext",
    "AgentResponse",
    "AgentRegistry",
    "AgentRouter",
    "create_default_registry",
]
