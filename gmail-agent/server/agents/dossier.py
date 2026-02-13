"""
Dossier Plugin Agent - Meeting Prep / Person Research.

Wraps the existing Dossier agent tools as a BaseAgent plugin.
The Dossier agent currently works through LangChain tools via ReAct,
so this plugin exposes those tools rather than bypassing ReAct.
"""

import httpx
from typing import List
from server.agents.base import BaseAgent, AgentContext, AgentResponse


class DossierPluginAgent(BaseAgent):
    """
    Handles Dossier / Meeting Prep requests.

    Features:
    - Multi-source data collection (Serper + LinkedIn)
    - Research synthesis with Gemini
    - Strategic analysis and relationship mapping
    - Comprehensive one-page dossier generation
    """

    name = "dossier"
    description = "Meeting prep dossier and person research agent"
    keywords = [
        "dossier", "meeting prep", "meeting preparation",
        "briefing", "background check", "profile research",
        "profil", "person research", "relationship map",
    ]
    active_statuses = ["collecting", "researching", "analyzing"]

    async def get_status(self, session_id: str = "default", base_url: str = "http://localhost:8000") -> str:
        """Check dossier session status via API."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{base_url}/dossier/status", json={"dossier_id": session_id}
                )
                data = resp.json()
                return data.get("status", "none")
        except Exception:
            return "none"

    async def handle(self, message: str, context: AgentContext) -> AgentResponse:
        """
        Process a dossier-related message.

        Dossier agent works via LangChain tools through the ReAct agent,
        so this handler is minimal — it just provides routing guidance.
        The actual work is done by the tools returned from get_tools().
        """
        base_url = context.base_url
        session_id = context.session_id

        current_status = await self.get_status(session_id, base_url)

        if current_status == "generated":
            return AgentResponse(
                message="Dossier sudah selesai di-generate. Anda bisa meminta saya untuk mengirimnya via email atau mengonversinya ke PDF.",
                status="generated",
                intent={"action": "dossier_ready", "query": message},
            )
        elif current_status in self.active_statuses:
            return AgentResponse(
                message=f"Dossier sedang dalam proses ({current_status}). Mohon tunggu sebentar...",
                status=current_status,
                intent={"action": "dossier_processing", "query": message},
            )

        # For new requests, return None-like response to let ReAct handle it
        # The ReAct agent has the dossier tools to actually generate
        return AgentResponse(
            message="__PASSTHROUGH__",  # Signal to router to fall through to ReAct
            status="passthrough",
            intent={"action": "dossier_new", "query": message},
        )

    def get_tools(self) -> list:
        """Return the dossier LangChain tools for the ReAct agent."""
        try:
            from server.tools.dossier_agent_tool import get_dossier_tools
            return get_dossier_tools()
        except ImportError:
            return []
