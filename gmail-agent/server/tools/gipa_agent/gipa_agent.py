"""
GIPA Request Agent - Orchestrator and LangChain Tool Exports.

This is the main entry point for the GIPA agent. It:
1. Manages the stateful clarification conversation via an in-memory session store
2. Orchestrates the ClarificationEngine -> DocumentGenerator pipeline
3. Exposes @tool decorated functions for integration into the main ReAct agent

The agent maintains per-session state so multiple users can have concurrent
GIPA clarification conversations.
"""

import asyncio
import json
import os
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool

from .clarification_engine import ClarificationEngine, GIPARequestData
from .document_generator import GIPADocumentGenerator
from .synonym_expander import SynonymExpander
from .jurisdiction_config import get_jurisdiction_config, NSW_CONFIG


# ---------------------------------------------------------------------------
# Session Store (in-memory, per-process)
# ---------------------------------------------------------------------------

# Maps session_id -> { "data": dict, "context": str, "status": str }
_gipa_sessions: Dict[str, Dict[str, Any]] = {}


def _get_or_create_session(session_id: str) -> Dict[str, Any]:
    """Get existing GIPA session or create a new one."""
    if session_id not in _gipa_sessions:
        _gipa_sessions[session_id] = {
            "data": {},
            "context": "",
            "status": "collecting",  # collecting | ready | generated
            "document": None,
        }
    return _gipa_sessions[session_id]


def _clear_session(session_id: str):
    """Clear a GIPA session."""
    _gipa_sessions.pop(session_id, None)


# ---------------------------------------------------------------------------
# GIPARequestAgent Orchestrator
# ---------------------------------------------------------------------------


class GIPARequestAgent:
    """
    Orchestrates the full GIPA request workflow:
    1. Clarification phase - interview the user
    2. Validation - ensure all required data is collected
    3. Generation - produce the formal GIPA application document
    """

    def __init__(self, google_api_key: Optional[str] = None):
        api_key = google_api_key or os.environ.get("GOOGLE_API_KEY")
        self.clarification_engine = ClarificationEngine(google_api_key=api_key)
        self.synonym_expander = SynonymExpander(google_api_key=api_key)
        self.document_generator = GIPADocumentGenerator(
            synonym_expander=self.synonym_expander
        )

    async def start_request(self, session_id: str) -> str:
        """
        Start a new GIPA request session.

        Returns the first question to ask the user.
        """
        session = _get_or_create_session(session_id)
        session["data"] = {}
        session["context"] = ""
        session["status"] = "collecting"
        session["document"] = None

        intro = (
            "I'll help you prepare a formal GIPA (Government Information Public Access) "
            "application for New South Wales. I need to collect some specific information "
            "to make the request as precise and legally robust as possible.\n\n"
            "A well-drafted GIPA request acts as a search query that a government officer "
            "cannot reject for being 'unreasonable' or 'vague.'\n\n"
            "Let's start with the basics.\n\n"
            "**Which government agency are you requesting information from?** "
            "(e.g., Department of Primary Industries, NSW Police Force, Transport for NSW)"
        )

        return intro

    async def process_answer(
        self,
        session_id: str,
        user_message: str,
    ) -> str:
        """
        Process a user's answer during the clarification phase.

        Args:
            session_id: The session identifier.
            user_message: The user's response.

        Returns:
            The next question to ask, a confirmation summary, or the generated document.
        """
        session = _get_or_create_session(session_id)

        if session["status"] == "generated":
            return (
                "The GIPA application has already been generated for this session. "
                "If you need to start a new request, please use the start command."
            )

        # Extract variables from the user's message
        (
            updated_data,
            missing_questions,
            is_complete,
        ) = await self.clarification_engine.extract_variables(
            user_message=user_message,
            current_data=session["data"],
            conversation_context=session["context"],
        )

        # Update session
        session["data"] = updated_data
        session["context"] += f"\nUser: {user_message}\n"

        if is_complete:
            session["status"] = "ready"
            # Build a confirmation summary
            return self._build_confirmation_summary(updated_data)
        else:
            # Ask the next question (take the first missing one)
            next_question = missing_questions[0]
            remaining = len(missing_questions) - 1

            response = next_question
            if remaining > 0:
                response += f"\n\n*({remaining} more question{'s' if remaining > 1 else ''} after this)*"

            return response

    async def generate_document(self, session_id: str) -> str:
        """
        Generate the GIPA application document from collected data.

        After generation, returns the document along with email draft metadata
        so the main agent can create a Gmail draft for user review.

        Args:
            session_id: The session identifier.

        Returns:
            The complete GIPA application as Markdown with email draft instructions,
            or an error message.
        """
        session = _get_or_create_session(session_id)

        if session["status"] == "collecting":
            # Check if we have enough data anyway
            is_valid, errors = self.clarification_engine.validate_data(session["data"])
            if not is_valid:
                error_list = "\n".join(f"- {e}" for e in errors)
                return (
                    f"Cannot generate the document yet. Missing information:\n{error_list}\n\n"
                    f"Please continue answering the clarification questions."
                )

        try:
            # Build the validated data object
            gipa_data = self.clarification_engine.build_gipa_request_data(
                session["data"]
            )

            # Get jurisdiction config
            config = get_jurisdiction_config(gipa_data.jurisdiction)

            # Generate the document
            document = await self.document_generator.generate(
                data=gipa_data,
                config=config,
            )

            session["status"] = "generated"
            session["document"] = document

            # Build email draft metadata
            agency_email = gipa_data.agency_email or ""
            subject = (
                f"RE: {config.act_name} ({config.act_short_name}) - Information Request"
            )

            # Return document with draft instructions for the main agent
            draft_instruction = (
                f"\n\n---\n"
                f"**EMAIL DRAFT INSTRUCTIONS (for the main agent):**\n"
                f"You MUST now create a Gmail draft using `GMAIL_CREATE_EMAIL_DRAFT` with:\n"
                f"- **recipient_email**: `{agency_email}`\n"
                f"- **subject**: `{subject}`\n"
                f"- **body**: The full document above (convert Markdown to HTML)\n\n"
                f"After creating the draft, tell the user: "
                f"\"I've created a draft email in your Gmail addressed to {agency_email}. "
                f'Please review it before sending."\n'
                f"Do NOT send the email directly — only create a draft for review."
            )

            return document + draft_instruction

        except Exception as e:
            return f"Error generating GIPA application: {str(e)}"

    def _build_confirmation_summary(self, data: Dict[str, Any]) -> str:
        """Build a confirmation summary of all collected data."""
        lines = [
            "I have all the information needed. Here's a summary of your GIPA request:\n",
            f"**Agency:** {data.get('agency_name', 'N/A')}",
        ]

        if data.get("agency_email"):
            lines.append(f"**Agency GIPA Email:** {data['agency_email']}")
        else:
            lines.append(
                "**Agency GIPA Email:** *Not provided - you should find this before submitting*"
            )

        lines.extend(
            [
                f"**Applicant:** {data.get('applicant_name', 'N/A')}",
            ]
        )

        if data.get("applicant_organization"):
            lines.append(f"**Organisation:** {data['applicant_organization']}")

        lines.append(f"**Applicant Type:** {data.get('applicant_type', 'individual')}")

        if data.get("applicant_type") in ("nonprofit", "journalist", "student"):
            lines.append(
                "**Fee Reduction:** Eligible (50% reduction will be requested)"
            )

        lines.extend(
            [
                f"**Period:** {data.get('start_date', 'N/A')} to {data.get('end_date', 'N/A')}",
                f"**Public Interest:** {data.get('public_interest_justification', 'N/A')}",
            ]
        )

        # Targets
        targets = data.get("targets", [])
        if targets:
            lines.append("**Targets:**")
            for t in targets:
                if isinstance(t, dict):
                    name = t.get("name", "Unknown")
                    role = t.get("role", "")
                    direction = t.get("direction", "both")
                else:
                    name = t.name
                    role = t.role or ""
                    direction = t.direction

                role_str = f" ({role})" if role else ""
                lines.append(f"  - {name}{role_str} [{direction}]")

        # Keywords
        keywords = data.get("keywords", [])
        if keywords:
            lines.append(f"**Keywords:** {', '.join(keywords)}")

        lines.extend(
            [
                "",
                "---",
                "**Does this look correct?** If yes, I'll generate the formal GIPA application document. "
                "If you need to change anything, let me know.",
            ]
        )

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# LangChain @tool functions
# ---------------------------------------------------------------------------

# Singleton agent instance (lazy-initialized)
_agent_instance: Optional[GIPARequestAgent] = None


def _get_agent() -> GIPARequestAgent:
    """Get or create the singleton GIPARequestAgent."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = GIPARequestAgent()
    return _agent_instance


@tool
async def gipa_start_request(session_id: str = "default") -> str:
    """Start a new GIPA (Government Information Public Access) request for NSW.

    This tool begins the interview process to collect all required information
    for a formal GIPA application. Call this when a user wants to make a
    government information access request in New South Wales.

    Args:
        session_id: Session identifier to track the conversation. Use the chat session ID.

    Returns:
        Introduction text and the first clarification question.
    """
    agent = _get_agent()
    return await agent.start_request(session_id)


@tool
async def gipa_process_answer(
    user_answer: str,
    session_id: str = "default",
) -> str:
    """Process a user's answer during GIPA request clarification.

    Call this tool each time the user provides information for their GIPA request.
    The tool extracts structured data from their response and returns the next
    question, or a confirmation summary when all data is collected.

    Args:
        user_answer: The user's response to the previous clarification question.
        session_id: Session identifier to track the conversation.

    Returns:
        The next clarification question, or a confirmation summary if all data is collected.
    """
    agent = _get_agent()
    return await agent.process_answer(session_id, user_answer)


@tool
async def gipa_generate_document(session_id: str = "default") -> str:
    """Generate the formal GIPA application document and prepare email draft instructions.

    Call this tool after all clarification questions have been answered and
    the user has confirmed the summary is correct. This generates the complete,
    legally robust GIPA application document.

    The document includes:
    - Header & routing information
    - Fee reduction request (if eligible)
    - Precise Boolean search terms
    - Comprehensive scope & definitions (legal shield)
    - AI-expanded keyword definitions

    IMPORTANT: The output includes email draft instructions. After calling this tool,
    you MUST create a Gmail draft using GMAIL_CREATE_EMAIL_DRAFT with the document
    as the email body, addressed to the agency email. Do NOT send directly — only draft.

    Args:
        session_id: Session identifier for the completed clarification session.

    Returns:
        The complete GIPA application document plus email draft metadata.
    """
    agent = _get_agent()
    return await agent.generate_document(session_id)


@tool
async def gipa_check_status(session_id: str = "default") -> str:
    """Check the current status of a GIPA request session.

    Call this tool FIRST when the user mentions GIPA and there may already be
    an active session.  This tells you whether to continue collecting answers,
    generate the document, or start a new session.

    Args:
        session_id: Session identifier to check.

    Returns:
        A status string describing the session state and collected data so far.
    """
    session = _gipa_sessions.get(session_id)
    if session is None:
        return "No active GIPA session found. Call gipa_start_request to begin."

    status = session.get("status", "unknown")
    data = session.get("data", {})

    if status == "generated":
        doc_preview = (session.get("document") or "")[:200]
        return (
            f"Session status: GENERATED. The document has already been created.\n"
            f"Preview: {doc_preview}...\n"
            f"If the user needs the full document, it is stored in the session. "
            f"If they want to start a new request, call gipa_start_request."
        )

    if status == "ready":
        summary_parts = []
        if data.get("agency_name"):
            summary_parts.append(f"Agency: {data['agency_name']}")
        if data.get("applicant_name"):
            summary_parts.append(f"Applicant: {data['applicant_name']}")
        if data.get("keywords"):
            summary_parts.append(f"Keywords: {', '.join(data['keywords'])}")
        summary = "; ".join(summary_parts) if summary_parts else "Data collected"
        return (
            f"Session status: READY. All information has been collected.\n"
            f"Collected data: {summary}\n"
            f"The user has confirmed the data. Call gipa_generate_document to produce the formal application."
        )

    # status == "collecting"
    filled = [k for k, v in data.items() if v]
    return (
        f"Session status: COLLECTING. Still gathering information.\n"
        f"Fields collected so far: {', '.join(filled) if filled else 'none'}\n"
        f"Call gipa_process_answer with the user's next response to continue."
    )


@tool
async def gipa_expand_keywords(keywords: str) -> str:
    """Expand keywords into legally robust definitions for a GIPA/FOI request.

    Takes a comma-separated list of keywords and generates comprehensive
    legal definitions that include scientific names, common aliases,
    abbreviations, and related terms. This prevents agencies from
    narrowly interpreting search terms.

    This can be used standalone without starting a full GIPA request.

    Args:
        keywords: Comma-separated list of keywords to expand (e.g., "koala, dingo, water licence").

    Returns:
        Formatted definition strings for each keyword.
    """
    agent = _get_agent()
    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]

    if not keyword_list:
        return "Please provide at least one keyword to expand."

    definitions = await agent.synonym_expander.expand_keywords(keyword_list)

    result_lines = ["**Keyword Definitions for GIPA/FOI Scope:**\n"]
    for i, definition in enumerate(definitions, 1):
        result_lines.append(f"{i}. {definition}")

    return "\n".join(result_lines)


def get_gipa_tools() -> list:
    """
    Get all GIPA-related LangChain tools for integration into the main agent.

    Returns:
        List of LangChain tool objects.
    """
    return [
        gipa_check_status,
        gipa_start_request,
        gipa_process_answer,
        gipa_generate_document,
        gipa_expand_keywords,
    ]
