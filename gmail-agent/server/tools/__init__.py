from server.agents.gipa import get_gipa_tools
from server.agents.dossier import get_dossier_tools
from server.agents.email_analyst import get_email_analyst_tools
from server.agents.pdf import get_pdf_tools
from server.agents.research import get_research_tools
from server.agents.social_media import get_social_media_tools
from server.agents.gmail import get_gmail_tools
from server.agents.linkedin import get_linkedin_tools
from server.agents.quote import get_quote_tools
from server.agents.strategy import get_strategy_tools

def get_all_tools(user_id: str = "default"):
    """Returns a combined list of all available LangChain tools."""
    return (
        get_gipa_tools() +
        get_dossier_tools() +
        get_email_analyst_tools() +
        get_pdf_tools() +
        get_research_tools() +
        get_social_media_tools(user_id) +
        get_gmail_tools(user_id) +
        get_linkedin_tools(user_id) +
        get_quote_tools() +
        get_strategy_tools()
    )

__all__ = [
    "get_gipa_tools",
    "get_dossier_tools",
    "get_email_analyst_tools",
    "get_pdf_tools",
    "get_research_tools",
    "get_social_media_tools",
    "get_gmail_tools",
    "get_linkedin_tools",
    "get_quote_tools",
    "get_strategy_tools",
    "get_all_tools",
]
