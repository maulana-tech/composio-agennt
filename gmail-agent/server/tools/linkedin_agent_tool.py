
"""
LinkedIn Agent Tool
Consolidates LinkedIn functionality (post, delete, get info) using Composio.
"""

import os
from langchain_core.tools import tool
from composio import Composio

def get_linkedin_tools(user_id: str = "default") -> list:
    """Get LinkedIn tools bound to a specific user ID."""
    
    api_key = os.environ.get("COMPOSIO_API_KEY")
    composio_client = Composio(api_key=api_key)

    @tool("LINKEDIN_GET_MY_INFO")
    def linkedin_get_my_info() -> str:
        """Fetch the authenticated LinkedIn user's profile info including author_id (URN) needed for posting."""
        try:
            return composio_client.tools.execute(
                slug="LINKEDIN_GET_MY_INFO",
                arguments={},
                user_id=user_id,
                dangerously_skip_version_check=True,
            )
        except Exception as e:
            return f"Error fetching LinkedIn info: {str(e)}"

    @tool("LINKEDIN_CREATE_POST")
    def linkedin_create_post(
        author: str, commentary: str, visibility: str = "PUBLIC"
    ) -> str:
        """Create a post on LinkedIn. Author must be a URN (get it from linkedin_get_my_info first). Visibility: PUBLIC, CONNECTIONS, LOGGED_IN."""
        try:
            args = {
                "author": author,
                "commentary": commentary,
                "visibility": visibility,
                "lifecycleState": "PUBLISHED",
            }
            return composio_client.tools.execute(
                slug="LINKEDIN_CREATE_LINKED_IN_POST",
                arguments=args,
                user_id=user_id,
                dangerously_skip_version_check=True,
            )
        except Exception as e:
            return f"Error creating LinkedIn post: {str(e)}"

    @tool("LINKEDIN_DELETE_POST")
    def linkedin_delete_post(share_id: str) -> str:
        """Delete a LinkedIn post by its share ID."""
        try:
            return composio_client.tools.execute(
                slug="LINKEDIN_DELETE_LINKED_IN_POST",
                arguments={"share_id": share_id},
                user_id=user_id,
                dangerously_skip_version_check=True,
            )
        except Exception as e:
            return f"Error deleting LinkedIn post: {str(e)}"

    return [linkedin_get_my_info, linkedin_create_post, linkedin_delete_post]
