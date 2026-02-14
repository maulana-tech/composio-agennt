"""
LinkedIn Agent Logic - Posting and profile management via Composio.
"""
import os
from composio import Composio

def get_composio_client() -> Composio:
    api_key = os.environ.get("COMPOSIO_API_KEY")
    return Composio(api_key=api_key)

async def get_linkedin_info(user_id: str) -> str:
    """Fetch LinkedIn profile info for the user."""
    client = get_composio_client()
    result = client.tools.execute(slug="LINKEDIN_GET_MY_INFO", arguments={}, user_id=user_id, dangerously_skip_version_check=True)
    return str(result)

async def post_to_linkedin(user_id: str, author_urn: str, commentary: str, visibility: str = "PUBLIC") -> str:
    """Create a LinkedIn post."""
    client = get_composio_client()
    args = {"author": author_urn, "commentary": commentary, "visibility": visibility, "lifecycleState": "PUBLISHED"}
    result = client.tools.execute(slug="LINKEDIN_CREATE_LINKED_IN_POST", arguments=args, user_id=user_id, dangerously_skip_version_check=True)
    return str(result)

async def delete_linkedin_post(user_id: str, share_id: str) -> str:
    """Delete a LinkedIn post."""
    client = get_composio_client()
    result = client.tools.execute(slug="LINKEDIN_DELETE_LINKED_IN_POST", arguments={"share_id": share_id}, user_id=user_id, dangerously_skip_version_check=True)
    return str(result)
