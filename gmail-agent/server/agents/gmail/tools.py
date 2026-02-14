"""
Gmail Agent Tools - LangChain tool exports.
"""
from langchain_core.tools import tool
from .logic import send_gmail, create_gmail_draft, fetch_gmail_emails

def get_gmail_tools(user_id: str = "default") -> list:
    """Generate tools bound to a specific user_id."""
    
    @tool("gmail_send_email")
    async def gmail_send_email_tool(recipient_email: str, subject: str, body: str, attachment: str = "") -> str:
        """Send an email using Gmail."""
        return await send_gmail(user_id, recipient_email, subject, body, attachment)

    @tool("gmail_create_draft")
    async def gmail_create_draft_tool(recipient_email: str, subject: str, body: str, attachment: str = "") -> str:
        """Create an email draft in Gmail."""
        return await create_gmail_draft(user_id, recipient_email, subject, body, attachment)

    @tool("gmail_fetch_emails")
    async def gmail_fetch_emails_tool(limit: int = 5, query: str = "") -> str:
        """Fetch recent emails from Gmail."""
        return await fetch_gmail_emails(user_id, limit, query)

    return [gmail_send_email_tool, gmail_create_draft_tool, gmail_fetch_emails_tool]
