from server.tools.gipa_agent_tool import get_gipa_tools
from server.tools.dossier_agent_tool import get_dossier_tools
from server.tools.gmail_agent_tool import get_gmail_tools
from server.tools.linkedin_agent_tool import get_linkedin_tools
from server.tools.pdf_agent_tool import get_pdf_tools
from server.tools.quote_agent_tool import get_quote_tools
from server.tools.social_media_agent_tool import get_social_media_tools
from server.tools.strategy_diagram_agent import get_strategy_diagram_tools

def get_all_tools():
    """Returns a combined list of all available LangChain tools."""
    return (
        get_gipa_tools() +
        get_dossier_tools() +
        get_gmail_tools() +
        get_linkedin_tools() +
        get_pdf_tools() +
        get_quote_tools() +
        get_social_media_tools() +
        get_strategy_diagram_tools()
    )

__all__ = [
    "get_gipa_tools",
    "get_dossier_tools",
    "get_gmail_tools",
    "get_linkedin_tools",
    "get_pdf_tools",
    "get_quote_tools",
    "get_social_media_tools",
    "get_strategy_diagram_tools",
    "get_all_tools",
]
