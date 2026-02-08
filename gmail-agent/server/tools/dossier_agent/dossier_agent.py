"""
Dossier Agent - Orchestrator and LangChain Tool Exports.

Main entry point for the Dossier/Meeting Prep agent. It:
1. Manages per-session dossier state in an in-memory store
2. Orchestrates: DataCollector -> ResearchSynthesizer -> StrategicAnalyzer -> DossierGenerator
3. Exposes @tool decorated functions for integration into the main ReAct agent

The agent accepts a name + optional LinkedIn URL and produces a one-page
meeting prep dossier with bio, statements, associates, and conversation starters.
"""

import os
import time
from typing import Dict, Any, Optional
from langchain_core.tools import tool

from .data_collector import DataCollector
from .research_synthesizer import ResearchSynthesizer
from .strategic_analyzer import StrategicAnalyzer
from .dossier_generator import DossierGenerator
from .exceptions import (
    DossierError,
    DossierCollectionError,
    DossierSynthesisError,
    DossierAnalysisError,
    DossierGenerationError,
    DossierSessionError,
)


# ---------------------------------------------------------------------------
# Session Store (in-memory, per-process)
# ---------------------------------------------------------------------------

# Maps dossier_id -> {
#   "name": str,
#   "linkedin_url": str,
#   "meeting_context": str,
#   "status": str,  # "collecting" | "researching" | "analyzing" | "generated"
#   "collected_data": dict | None,
#   "synthesized_data": dict | None,
#   "strategic_insights": dict | None,
#   "document": str | None,
#   "created_at": float,  # time.time()
#   "last_accessed": float,  # time.time()
# }
_dossier_sessions: Dict[str, Dict[str, Any]] = {}

# Default TTL: 24 hours
SESSION_TTL_SECONDS = 24 * 60 * 60


def _get_session(dossier_id: str) -> Optional[Dict[str, Any]]:
    """Get an existing dossier session and update its last_accessed time."""
    session = _dossier_sessions.get(dossier_id)
    if session is not None:
        session["last_accessed"] = time.time()
    return session


def _create_session(
    dossier_id: str,
    name: str,
    linkedin_url: str = "",
    meeting_context: str = "",
) -> Dict[str, Any]:
    """Create a new dossier session."""
    now = time.time()
    session = {
        "name": name,
        "linkedin_url": linkedin_url,
        "meeting_context": meeting_context,
        "status": "collecting",
        "collected_data": None,
        "synthesized_data": None,
        "strategic_insights": None,
        "document": None,
        "created_at": now,
        "last_accessed": now,
    }
    _dossier_sessions[dossier_id] = session
    return session


def _clear_session(dossier_id: str):
    """Remove a dossier session."""
    _dossier_sessions.pop(dossier_id, None)


def _cleanup_expired_sessions():
    """Remove sessions that have exceeded the TTL."""
    now = time.time()
    expired = [
        sid
        for sid, session in _dossier_sessions.items()
        if now - session.get("last_accessed", session.get("created_at", 0))
        > SESSION_TTL_SECONDS
    ]
    for sid in expired:
        _dossier_sessions.pop(sid, None)
    return len(expired)


# ---------------------------------------------------------------------------
# DossierAgent Orchestrator
# ---------------------------------------------------------------------------


class DossierAgent:
    """
    Orchestrates the full dossier generation workflow:
    1. Data collection (Serper + LinkedIn scraping)
    2. Research synthesis (Gemini)
    3. Strategic analysis (Gemini)
    4. Document generation (Markdown)
    """

    def __init__(
        self,
        google_api_key: Optional[str] = None,
        serper_api_key: Optional[str] = None,
        composio_api_key: Optional[str] = None,
    ):
        self.collector = DataCollector(
            serper_api_key=serper_api_key,
            composio_api_key=composio_api_key,
        )
        self.synthesizer = ResearchSynthesizer(google_api_key=google_api_key)
        self.analyzer = StrategicAnalyzer(google_api_key=google_api_key)
        self.generator = DossierGenerator()

    async def generate_dossier(
        self,
        dossier_id: str,
        name: str,
        linkedin_url: str = "",
        meeting_context: str = "",
        is_self_lookup: bool = False,
        composio_user_id: str = "default",
    ) -> str:
        """
        Run the full dossier pipeline from data collection to document generation.

        Args:
            dossier_id: Unique session identifier.
            name: Full name of the person.
            linkedin_url: Optional LinkedIn profile URL.
            meeting_context: Optional context about why the meeting is happening.
            is_self_lookup: If True, use Composio GET_MY_INFO for LinkedIn data.
            composio_user_id: Composio user ID (required if is_self_lookup=True).

        Returns:
            The complete dossier as a Markdown string.
        """
        session = _create_session(dossier_id, name, linkedin_url, meeting_context)

        # Opportunistic cleanup of expired sessions
        _cleanup_expired_sessions()

        try:
            # Step 1: Collect data
            session["status"] = "collecting"
            collected = await self.collector.collect(
                name=name,
                linkedin_url=linkedin_url,
                is_self_lookup=is_self_lookup,
                composio_user_id=composio_user_id,
            )
            session["collected_data"] = collected.to_dict()

            # Step 2: Synthesize research
            session["status"] = "researching"
            synthesized = await self.synthesizer.synthesize(session["collected_data"])
            session["synthesized_data"] = synthesized.to_dict()

            # Step 3: Strategic analysis
            session["status"] = "analyzing"
            insights = await self.analyzer.analyze(
                session["synthesized_data"],
                meeting_context=meeting_context,
            )
            session["strategic_insights"] = insights.to_dict()

            # Step 4: Generate document
            document = await self.generator.generate(
                session["synthesized_data"],
                session["strategic_insights"],
            )
            session["document"] = document
            session["status"] = "generated"

            return document

        except DossierError as e:
            session["status"] = "error"
            error_msg = f"Dossier generation failed at {e.stage}: {str(e)}"
            session["document"] = error_msg
            return error_msg
        except Exception as e:
            session["status"] = "error"
            error_msg = f"Dossier generation failed: {str(e)}"
            session["document"] = error_msg
            return error_msg

    async def get_status(self, dossier_id: str) -> Dict[str, Any]:
        """
        Get the current status of a dossier session.
        """
        session = _get_session(dossier_id)
        if session is None:
            return {"status": "none", "message": "No active dossier session found."}

        status = session["status"]
        result = {
            "status": status,
            "name": session["name"],
            "linkedin_url": session["linkedin_url"],
        }

        if status == "generated":
            doc = session.get("document", "")
            result["message"] = "Dossier has been generated."
            result["document_preview"] = doc[:300] if doc else ""
        elif status == "error":
            result["message"] = session.get("document", "Unknown error")
        else:
            result["message"] = f"Dossier is currently: {status}"

        return result

    async def update_dossier(
        self,
        dossier_id: str,
        additional_context: str,
    ) -> str:
        """
        Update an existing dossier with additional meeting context.
        Re-runs strategic analysis and regenerates the document.

        Args:
            dossier_id: Existing dossier session ID.
            additional_context: New context to incorporate.

        Returns:
            The updated dossier document, or an error message.
        """
        session = _get_session(dossier_id)
        if session is None:
            return "No dossier found with that ID. Generate one first."

        if session["synthesized_data"] is None:
            return "Dossier data not yet collected. Please generate first."

        # Update meeting context
        existing_context = session.get("meeting_context", "")
        session["meeting_context"] = f"{existing_context}\n{additional_context}".strip()

        try:
            # Re-run strategic analysis with new context
            session["status"] = "analyzing"
            insights = await self.analyzer.analyze(
                session["synthesized_data"],
                meeting_context=session["meeting_context"],
            )
            session["strategic_insights"] = insights.to_dict()

            # Regenerate document
            document = await self.generator.generate(
                session["synthesized_data"],
                session["strategic_insights"],
            )
            session["document"] = document
            session["status"] = "generated"

            return document

        except DossierError as e:
            return f"Failed to update dossier at {e.stage}: {str(e)}"
        except Exception as e:
            return f"Failed to update dossier: {str(e)}"


# ---------------------------------------------------------------------------
# LangChain @tool functions
# ---------------------------------------------------------------------------

# Singleton agent instance (lazy-initialized)
_agent_instance: Optional[DossierAgent] = None


def _get_agent() -> DossierAgent:
    """Get or create the singleton DossierAgent."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = DossierAgent()
    return _agent_instance


@tool
async def dossier_check_status(dossier_id: str = "default") -> str:
    """Check the current status of a dossier/meeting prep session.

    Call this tool FIRST when the user mentions dossier or meeting prep
    and there may already be an active session.

    Args:
        dossier_id: Dossier session identifier. Use the chat session ID.

    Returns:
        Status string describing the dossier state.
    """
    session = _dossier_sessions.get(dossier_id)
    if session is None:
        return "No active dossier session found. Call dossier_generate to create one."

    status = session.get("status", "unknown")
    name = session.get("name", "Unknown")

    if status == "generated":
        doc_preview = (session.get("document") or "")[:200]
        return (
            f"Dossier status: GENERATED for {name}.\n"
            f"Preview: {doc_preview}...\n"
            f"You can retrieve the full document or update it with dossier_update."
        )

    if status == "error":
        return f"Dossier status: ERROR for {name}. {session.get('document', 'Unknown error')}"

    return f"Dossier status: {status.upper()} for {name}. Generation is in progress."


@tool
async def dossier_generate(
    name: str,
    linkedin_url: str = "",
    meeting_context: str = "",
    is_self_lookup: bool = False,
    dossier_id: str = "default",
) -> str:
    """Generate a comprehensive meeting prep dossier for a person.

    This tool researches a person using web search and LinkedIn,
    then produces a one-page dossier with:
    - Biographical context and career highlights
    - Recent statements and positions
    - Known associates and relationship map
    - Strategic conversation starters
    - Topics to avoid
    - Recommended meeting approach

    For LinkedIn data:
    - Set is_self_lookup=True if the user is researching THEMSELVES
      (uses Composio LinkedIn to get rich profile data).
    - Leave is_self_lookup=False (default) when researching OTHER people
      (uses web search to extract LinkedIn data from Google's index).

    Args:
        name: Full name of the person to research.
        linkedin_url: Optional LinkedIn profile URL for richer data.
        meeting_context: Optional context about the meeting purpose.
        is_self_lookup: True if researching the authenticated user themselves.
        dossier_id: Session identifier. Use the chat session ID.

    Returns:
        The complete meeting prep dossier in Markdown format.
    """
    agent = _get_agent()
    return await agent.generate_dossier(
        dossier_id=dossier_id,
        name=name,
        linkedin_url=linkedin_url,
        meeting_context=meeting_context,
        is_self_lookup=is_self_lookup,
    )


@tool
async def dossier_update(
    additional_context: str,
    dossier_id: str = "default",
) -> str:
    """Update an existing dossier with new meeting context.

    Re-runs strategic analysis with the additional context and
    regenerates the dossier document. Does NOT re-collect data.

    Args:
        additional_context: New context to incorporate (e.g., meeting topic, your goals).
        dossier_id: Session identifier for the existing dossier.

    Returns:
        The updated dossier document, or an error message.
    """
    agent = _get_agent()
    return await agent.update_dossier(
        dossier_id=dossier_id,
        additional_context=additional_context,
    )


@tool
async def dossier_get_document(dossier_id: str = "default") -> str:
    """Retrieve the full generated dossier document.

    Use this to get the complete document after it has been generated,
    for example to send it via email or convert to PDF.

    Args:
        dossier_id: Session identifier for the dossier.

    Returns:
        The full dossier Markdown document, or an error if not yet generated.
    """
    session = _dossier_sessions.get(dossier_id)
    if session is None:
        return "No dossier found. Call dossier_generate first."

    if session.get("status") != "generated":
        return f"Dossier is not ready yet. Current status: {session.get('status', 'unknown')}"

    document = session.get("document")
    if not document:
        return "Dossier document is empty. Try regenerating."

    return document


@tool
async def dossier_delete(dossier_id: str = "default") -> str:
    """Delete a dossier session and free its resources.

    Use this when a dossier is no longer needed, or to start fresh
    before generating a new dossier for the same session.

    Args:
        dossier_id: Session identifier for the dossier to delete.

    Returns:
        Confirmation message.
    """
    session = _dossier_sessions.get(dossier_id)
    if session is None:
        return f"No dossier session found with ID '{dossier_id}'."

    name = session.get("name", "Unknown")
    _clear_session(dossier_id)
    return f"Dossier session for '{name}' (ID: {dossier_id}) has been deleted."


def get_dossier_tools() -> list:
    """
    Get all Dossier-related LangChain tools for integration into the main agent.

    Returns:
        List of LangChain tool objects.
    """
    return [
        dossier_check_status,
        dossier_generate,
        dossier_update,
        dossier_get_document,
        dossier_delete,
    ]
