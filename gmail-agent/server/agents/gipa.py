"""
GIPA Plugin Agent - Government Information Public Access requests.

Wraps the existing GIPA handler logic as a BaseAgent plugin.
Clients can register this agent to enable GIPA request handling.
"""

import httpx
from typing import List
from server.agents.base import BaseAgent, AgentContext, AgentResponse


class GIPAPluginAgent(BaseAgent):
    """
    Handles GIPA (Government Information Public Access) requests for NSW.

    Features:
    - Clarification interview to collect required variables
    - Formal GIPA application document generation
    - Gmail draft creation with the generated document
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
        """Check GIPA session status via API or local store."""
        # Try local store first to avoid loopback issues in tests/scripts
        try:
            from server.tools.gipa_agent_tool import _gipa_sessions
            session = _gipa_sessions.get(session_id)
            if session:
                return session.get("status", "none")
        except ImportError:
            pass

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

        # Check current status
        current_status = await self.get_status(session_id, base_url)

        # If ready and user wants to generate
        if current_status == "ready" and is_generation_request:
            return await self._generate_document(message, base_url, session_id, user_id)

        # Start new session if none exists
        if current_status == "none":
            return await self._start_session(message, base_url, session_id)

        # Continue existing session (collecting answers)
        return await self._continue_session(message, base_url, session_id, user_id, is_generation_request)

    async def _generate_document(
        self, message: str,
        base_url: str, session_id: str, user_id: str
    ) -> AgentResponse:
        """Generate GIPA document and create email draft."""
        try:
            # Try local call first
            try:
                from server.tools.gipa_agent_tool import GIPARequestAgent, _gipa_sessions
                agent = GIPARequestAgent()
                document = await agent.generate_document(session_id)
                session = _gipa_sessions.get(session_id, {})
                
                if session.get("status") == "generated":
                    result = {
                        "success": True,
                        "html_body": session.get("html_body", ""),
                        "draft_recipient": session.get("data", {}).get("agency_email", ""),
                        "draft_subject": "GIPA Act - Information Request"
                    }
                else:
                    result = {"success": False, "message": document}
            except Exception as e:
                print(f"DEBUG: Local GIPA generate error: {e}")
                # Fallback to HTTP
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"{base_url}/gipa/generate", json={"session_id": session_id}
                    )
                    result = resp.json()

            if not result.get("success"):
                return AgentResponse(
                    message=f"❌ Error: {result.get('message', 'Unknown error')}",
                    status="error",
                    intent={"action": "gipa_error", "query": message},
                )

            html_body = result.get("html_body", "")
            recipient = result.get("draft_recipient", "gipa@agency.nsw.gov.au")
            subject = result.get("draft_subject", "GIPA Act - Information Request")

            # Create email draft
            return await self._create_draft(message, base_url, user_id, recipient, subject, html_body)
        except Exception as e:
            from server.tools.gipa_agent_tool import _gipa_sessions
            session_data = _gipa_sessions.get(session_id, {}).get("data", {})
            return AgentResponse(
                message=f"❌ Error membuat GIPA: {str(e)}",
                status="error",
                intent={"action": "gipa_error", "query": message},
                data=session_data
            )

    async def _start_session(
        self, message: str,
        base_url: str, session_id: str
    ) -> AgentResponse:
        """Start a new GIPA session and process initial message."""
        try:
            # Try local call
            try:
                from server.tools.gipa_agent_tool import GIPARequestAgent
                agent = GIPARequestAgent()
                start_msg = await agent.start_request(session_id)
                answer_msg = await agent.process_answer(session_id, message)
                
                from server.tools.gipa_agent_tool import _gipa_sessions
                session_data = _gipa_sessions.get(session_id, {}).get("data", {})
                
                return AgentResponse(
                    message=answer_msg if answer_msg else start_msg,
                    status="collecting",
                    intent={"action": "gipa_start", "query": message},
                    data=session_data
                )
            except Exception as e:
                print(f"DEBUG: Local GIPA start error: {e}")
                # Fallback to HTTP
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"{base_url}/gipa/start", json={"session_id": session_id}
                    )
                    start_data = resp.json()

                    resp2 = await client.post(
                        f"{base_url}/gipa/answer",
                        json={"session_id": session_id, "answer": message},
                    )
                    answer_data = resp2.json()

                    return AgentResponse(
                        message=answer_data.get("message", start_data.get("message", "")),
                        status=answer_data.get("status", "collecting"),
                        intent={"action": "gipa_start", "query": message},
                    )
        except Exception as e:
            return AgentResponse(
                message=f"❌ Error memulai GIPA: {str(e)}",
                status="error",
                intent={"action": "gipa_error", "query": message},
            )

    async def _continue_session(
        self, message: str,
        base_url: str, session_id: str, user_id: str,
        is_generation_request: bool,
    ) -> AgentResponse:
        """Continue an existing GIPA session with user's answer."""
        try:
            # Try local call
            try:
                from server.tools.gipa_agent_tool import GIPARequestAgent, _gipa_sessions
                agent = GIPARequestAgent()
                answer_msg = await agent.process_answer(session_id, message)
                session = _gipa_sessions.get(session_id, {})
                new_status = session.get("status", "collecting")
                
                # If now ready and user wants to generate
                if new_status == "ready" and is_generation_request:
                    return await self._generate_document(message, base_url, session_id, user_id)

                return AgentResponse(
                    message=answer_msg,
                    status=new_status,
                    intent={"action": "gipa_continue", "status": new_status, "query": message},
                    data=session.get("data", {})
                )
            except Exception as e:
                print(f"DEBUG: Local GIPA answer error: {e}")
                # Fallback to HTTP
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"{base_url}/gipa/answer",
                        json={"session_id": session_id, "answer": message},
                    )
                    answer_data = resp.json()
                    new_status = answer_data.get("status", "collecting")

                    if new_status == "ready" and is_generation_request:
                        return await self._generate_document(message, base_url, session_id, user_id)

                    return AgentResponse(
                        message=answer_data.get("message", "Processing..."),
                        status=new_status,
                        intent={"action": "gipa_continue", "status": new_status, "query": message},
                    )
        except Exception as e:
            return AgentResponse(
                message=f"❌ Error memproses: {str(e)}",
                status="error",
                intent={"action": "gipa_error", "query": message},
            )

    async def _create_draft(
        self, message: str,
        base_url: str, user_id: str,
        recipient: str, subject: str, html_body: str,
    ) -> AgentResponse:
        """Create Gmail draft with generated GIPA document."""
        try:
            # Try local call
            try:
                from server.actions import create_draft
                from server.dependencies import provide_composio_client
                client = provide_composio_client()
                # Local action is synchronous based on previous edits
                result = create_draft(client, user_id, recipient, subject, html_body)
                successful = True
            except (ImportError, Exception) as e:
                print(f"DEBUG: Local GIPA draft error: {e}")
                # Fallback to local logic but maybe client failed?
                successful = False

            if successful:
                return AgentResponse(
                    message=f"✅ Dokumen GIPA berhasil dibuat dan draft email sudah tersimpan di Gmail Anda!\n\n📧 Draft ditujukan ke: {recipient}\n\nSilakan review draft di Gmail sebelum mengirim.",
                    status="completed",
                    intent={"action": "gipa_complete", "query": message},
                )
            else:
                return AgentResponse(
                    message=f"✅ Dokumen GIPA berhasil dibuat!\n\n⚠️ Draft email gagal dibuat.\n\nSilakan coba kirim ulang dengan perintah 'create Gmail draft'.",
                    status="completed",
                    intent={"action": "gipa_complete", "query": message},
                )
        except Exception as e:
            return AgentResponse(
                message=f"✅ Dokumen GIPA berhasil dibuat!\n\n(Pembuatan draft email gagal: {str(e)})",
                status="completed",
                intent={"action": "gipa_complete", "query": message},
            )

