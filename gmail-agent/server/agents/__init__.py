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

from .core.base import BaseAgent, AgentContext, AgentResponse
from .core.registry import AgentRegistry
from .core.router import AgentRouter


def create_default_registry() -> AgentRegistry:
    """Create registry with all available agents pre-registered."""
    from .gipa import GIPAPluginAgent
    from .dossier import DossierPluginAgent
    from .email_analyst import EmailAnalystPluginAgent
    from .pdf import PDFPluginAgent
    from .research import ResearchPluginAgent
    from .social_media import SocialMediaPluginAgent
    from .gmail import GmailPluginAgent
    from .linkedin import LinkedInPluginAgent
    from .quote import QuotePluginAgent
    from .strategy import StrategyPluginAgent

    registry = AgentRegistry()
    registry.register(GIPAPluginAgent())
    registry.register(DossierPluginAgent())
    registry.register(EmailAnalystPluginAgent())
    registry.register(PDFPluginAgent())
    registry.register(ResearchPluginAgent())
    registry.register(SocialMediaPluginAgent())
    registry.register(GmailPluginAgent())
    registry.register(LinkedInPluginAgent())
    registry.register(QuotePluginAgent())
    registry.register(StrategyPluginAgent())
    return registry


__all__ = [
    "BaseAgent",
    "AgentContext",
    "AgentResponse",
    "AgentRegistry",
    "AgentRouter",
    "create_default_registry",
]
