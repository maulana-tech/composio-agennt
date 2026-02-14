"""
LinkedIn Agent Tools - LangChain tool exports.
"""
from langchain_core.tools import tool
from .logic import get_linkedin_info, post_to_linkedin, delete_linkedin_post

def get_linkedin_tools(user_id: str = "default") -> list:
    """Generate tools bound to a specific user_id."""
    
    @tool("linkedin_get_info")
    async def linkedin_get_info_tool() -> str:
        """Fetch LinkedIn profile info for the user."""
        return await get_linkedin_info(user_id)

    @tool("linkedin_post")
    async def linkedin_post_tool(author_urn: str, commentary: str, visibility: str = "PUBLIC") -> str:
        """Create a LinkedIn post."""
        return await post_to_linkedin(user_id, author_urn, commentary, visibility)

    @tool("linkedin_delete_post")
    async def linkedin_delete_post_tool(share_id: str) -> str:
        """Delete a LinkedIn post by its share ID."""
        return await delete_linkedin_post(user_id, share_id)

    return [linkedin_get_info_tool, linkedin_post_tool, linkedin_delete_post_tool]
