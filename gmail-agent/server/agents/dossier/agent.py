"""
Dossier Plugin Agent - Meeting preparation and research.
"""

from ..core.base import BaseAgent, AgentContext, AgentResponse
from .logic import DossierAgent, _dossier_sessions

class DossierPluginAgent(BaseAgent):
    """
    Handles Dossier (Meeting Prep) generation.
    """

    name = "dossier"
    description = "Meeting preparation and comprehensive biographical dossiers"
    keywords = ["dossier", "meeting prep", "research person", "profiling"]
    active_statuses = ["collecting", "researching", "analyzing", "generating"]

    async def get_status(self, session_id: str = "default", base_url: str = "http://localhost:8000") -> str:
        session = _dossier_sessions.get(session_id)
        return session.get("status", "none") if session else "none"

    async def handle(self, message: str, context: AgentContext) -> AgentResponse:
        # For now, simplistic routing to generation
        # In a real scenario, this would have an interview flow like GIPA
        agent = DossierAgent()
        doc = await agent.generate_dossier(context.session_id, message)
        return AgentResponse(
            message=f"Dossier generated:\n\n{doc}",
            status="completed",
            agent_name=self.name
        )

    def get_tools(self) -> list:
        from .tools import get_dossier_tools
        return get_dossier_tools()
