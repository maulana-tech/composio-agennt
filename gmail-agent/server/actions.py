from composio import Composio
from typing import Any, Dict, List, Optional


def execute_tool(
    composio_client: Composio, user_id: str, tool_slug: str, arguments: Dict[str, Any]
) -> Dict[str, Any]:
    return composio_client.tools.execute(
        slug=tool_slug,
        arguments=arguments,
        user_id=user_id,
        dangerously_skip_version_check=True,
    )


def send_email(
    composio_client: Composio,
    user_id: str,
    recipient_email: str,
    subject: str,
    body: str,
    attachment: Optional[str] = None,
) -> Dict[str, Any]:
    arguments = {"recipient_email": recipient_email, "subject": subject, "body": body}
    if attachment:
        arguments["attachment"] = attachment

    return execute_tool(
        composio_client=composio_client,
        user_id=user_id,
        tool_slug="GMAIL_SEND_EMAIL",
        arguments=arguments,
    )


def fetch_emails(
    composio_client: Composio, user_id: str, limit: int = 5
) -> Dict[str, Any]:
    return execute_tool(
        composio_client=composio_client,
        user_id=user_id,
        tool_slug="GMAIL_FETCH_EMAILS",
        arguments={"limit": limit},
    )


def create_draft(
    composio_client: Composio,
    user_id: str,
    recipient_email: str,
    subject: str,
    body: str,
) -> Dict[str, Any]:
    return execute_tool(
        composio_client=composio_client,
        user_id=user_id,
        tool_slug="GMAIL_CREATE_EMAIL_DRAFT",
        arguments={
            "recipient_email": recipient_email,
            "subject": subject,
            "body": body,
        },
    )


# ========== LinkedIn Actions ==========


def create_linkedin_post(
    composio_client: Composio,
    user_id: str,
    author: str,
    commentary: str,
    visibility: str = "PUBLIC",
    lifecycle_state: str = "PUBLISHED",
) -> Dict[str, Any]:
    arguments = {
        "author": author,
        "commentary": commentary,
        "visibility": visibility,
        "lifecycleState": lifecycle_state,
    }
    return execute_tool(
        composio_client, user_id, "LINKEDIN_CREATE_LINKED_IN_POST", arguments
    )


def delete_linkedin_post(
    composio_client: Composio, user_id: str, share_id: str
) -> Dict[str, Any]:
    return execute_tool(
        composio_client,
        user_id,
        "LINKEDIN_DELETE_LINKED_IN_POST",
        {"share_id": share_id},
    )


def get_linkedin_my_info(composio_client: Composio, user_id: str) -> Dict[str, Any]:
    return execute_tool(composio_client, user_id, "LINKEDIN_GET_MY_INFO", {})


def get_linkedin_company_info(
    composio_client: Composio,
    user_id: str,
    count: Optional[int] = None,
    role: Optional[str] = None,
    start: Optional[int] = None,
    state: Optional[str] = None,
) -> Dict[str, Any]:
    arguments = {}
    if count is not None:
        arguments["count"] = count
    if role:
        arguments["role"] = role
    if start is not None:
        arguments["start"] = start
    if state:
        arguments["state"] = state
    return execute_tool(
        composio_client, user_id, "LINKEDIN_GET_COMPANY_INFO", arguments
    )
