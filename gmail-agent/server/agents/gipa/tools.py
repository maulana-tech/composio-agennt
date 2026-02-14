from langchain_core.tools import tool
from .logic import GIPARequestAgent, _gipa_sessions

# Singleton instance for tools
_agent_instance = None

def _get_agent() -> GIPARequestAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = GIPARequestAgent()
    return _agent_instance

@tool
async def gipa_start_request(session_id: str = "default") -> str:
    """Start a new GIPA request session."""
    return await _get_agent().start_request(session_id)

@tool
async def gipa_process_answer(user_answer: str, session_id: str = "default") -> str:
    """Process user answer for GIPA request."""
    return await _get_agent().process_answer(session_id, user_answer)

@tool
async def gipa_generate_document(session_id: str = "default") -> str:
    """Generate final GIPA document and email draft."""
    return await _get_agent().generate_document(session_id)

@tool
async def gipa_check_status(session_id: str = "default") -> str:
    """Check GIPA session status."""
    session = _gipa_sessions.get(session_id)
    if not session:
        return "No active session."
    return f"Status: {session.get('status', 'unknown')}"

def get_gipa_tools() -> list:
    """Returns a list of LangChain tools for GIPA."""
    return [
        gipa_start_request,
        gipa_process_answer,
        gipa_generate_document,
        gipa_check_status,
    ]
