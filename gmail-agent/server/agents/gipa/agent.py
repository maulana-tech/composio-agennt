"""
GIPA Plugin Agent - Government Information Public Access requests.
"""

import httpx
from typing import List
from ..core.base import BaseAgent, AgentContext, AgentResponse
from .logic import GIPARequestAgent, _gipa_sessions

class GIPAPluginAgent(BaseAgent):
    """
    Handles GIPA (Government Information Public Access) requests for NSW.
    """

    name = "gipa"
    description = "Government Information Public Access (GIPA/FOI) request handler for NSW"
    keywords = [
        "gipa", "foi", "freedom of information",
        "government information", "public access",
        "information request", "information access",
        "right to information", "rti",
    ]
    active_statuses = ["collecting", "ready", "generated"]

    # Keywords indicating user wants to generate/confirm
    GENERATE_KEYWORDS = [
        "generate", "generat", "buat", "siapkan", "buatkan",
        "iya", "ya", "yes", "benar", "betul", "ok", "oke",
        "confirm", "konfirmasi", "sudah", "done", "complete", "selesai",
    ]

    async def get_status(self, session_id: str = "default", base_url: str = "http://localhost:8000") -> str:
        """Check GIPA session status via local store or API."""
        session = _gipa_sessions.get(session_id)
        if session:
            return session.get("status", "none")

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{base_url}/gipa/status", json={"session_id": session_id}
                )
                data = resp.json()
                return data.get("status", "none")
        except Exception:
            return "none"

    async def handle(self, message: str, context: AgentContext) -> AgentResponse:
        """Process a GIPA-related message."""
        base_url = context.base_url
        session_id = context.session_id
        user_id = context.user_id
        user_lower = message.lower()

        is_generation_request = any(kw in user_lower for kw in self.GENERATE_KEYWORDS)
        current_status = await self.get_status(session_id, base_url)

        if current_status == "ready" and is_generation_request:
            return await self._generate_document(message, base_url, session_id, user_id)

        if current_status == "none":
            return await self._start_session(message, base_url, session_id)

        return await self._continue_session(message, base_url, session_id, user_id, is_generation_request)

    async def _generate_document(self, message: str, base_url: str, session_id: str, user_id: str) -> AgentResponse:
        try:
            agent = GIPARequestAgent()
            document = await agent.generate_document(session_id)
            session = _gipa_sessions.get(session_id, {})
            
            if session.get("status") == "generated":
                html_body = session.get("html_body", "")
                recipient = session.get("data", {}).get("agency_email", "rti@agency.nsw.gov.au")
                subject = "GIPA Act - Information Request"
                return await self._create_draft(message, user_id, recipient, subject, html_body)
            else:
                return AgentResponse(message=f"❌ Error: {document}", status="error")
        except Exception as e:
            return AgentResponse(message=f"❌ Error membuat GIPA: {str(e)}", status="error")

    async def _start_session(self, message: str, base_url: str, session_id: str) -> AgentResponse:
        agent = GIPARequestAgent()
        await agent.start_request(session_id)
        answer_msg = await agent.process_answer(session_id, message)
        return AgentResponse(
            message=answer_msg,
            status="collecting",
            intent={"action": "gipa_start", "query": message},
            data=_gipa_sessions.get(session_id, {}).get("data", {})
        )

    async def _continue_session(self, message: str, base_url: str, session_id: str, user_id: str, is_gen: bool) -> AgentResponse:
        agent = GIPARequestAgent()
        answer_msg = await agent.process_answer(session_id, message)
        session = _gipa_sessions.get(session_id, {})
        new_status = session.get("status", "collecting")
        
        if new_status == "ready" and is_gen:
            return await self._generate_document(message, base_url, session_id, user_id)

        return AgentResponse(
            message=answer_msg,
            status=new_status,
            intent={"action": "gipa_continue", "status": new_status, "query": message},
            data=session.get("data", {})
        )

    async def _create_draft(self, message, user_id, recipient, subject, html_body) -> AgentResponse:
        from server.actions import create_draft
        from server.dependencies import provide_composio_client
        client = provide_composio_client()
        create_draft(client, user_id, recipient, subject, html_body)
        return AgentResponse(
            message=f"✅ Dokumen GIPA berhasil dibuat dan draft email sudah tersimpan di Gmail Anda!",
            status="completed",
            intent={"action": "gipa_complete", "query": message},
        )

    def get_tools(self) -> list:
        from .tools import get_gipa_tools
        return get_gipa_tools()
