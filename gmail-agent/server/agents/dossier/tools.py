from langchain_core.tools import tool
from .logic import DossierAgent, _dossier_sessions

_agent = None

def _get_agent() -> DossierAgent:
    global _agent
    if _agent is None: _agent = DossierAgent()
    return _agent

@tool
async def dossier_check_status(dossier_id: str = "default") -> str:
    """Check status of dossier/meeting prep."""
    session = _dossier_sessions.get(dossier_id)
    if not session: return "No active dossier."
    return f"Status: {session['status']} for {session.get('name', 'unknown')}"

@tool
async def dossier_generate(name: str, linkedin_url: str = "", meeting_context: str = "", dossier_id: str = "default") -> str:
    """Generate meeting prep dossier."""
    return await _get_agent().generate_dossier(dossier_id, name, linkedin_url, meeting_context)

def get_dossier_tools() -> list:
    return [dossier_check_status, dossier_generate]
