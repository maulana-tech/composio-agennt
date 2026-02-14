"""
Gmail Agent Logic - Handling emails and drafts via Composio.
"""
import os
import json
import time
from typing import Optional
from composio import Composio

def get_composio_client() -> Composio:
    api_key = os.environ.get("COMPOSIO_API_KEY")
    return Composio(api_key=api_key)

async def send_gmail(user_id: str, recipient_email: str, subject: str, body: str, attachment: str = "") -> str:
    """Core logic for sending a Gmail message."""
    client = get_composio_client()
    if attachment:
        if not os.path.exists(attachment):
            # Try waiting a bit for generation
            retries = 10
            while retries > 0:
                if os.path.exists(attachment): break
                time.sleep(0.5); retries -= 1
            if not os.path.exists(attachment):
                return f"Error: Attachment not found at {attachment}"

    args = {"recipient_email": recipient_email, "subject": subject, "body": body, "is_html": True}
    if attachment: args["attachment"] = attachment
    
    result = client.tools.execute(slug="GMAIL_SEND_EMAIL", arguments=args, user_id=user_id, dangerously_skip_version_check=True)
    return str(result)

async def create_gmail_draft(user_id: str, recipient_email: str, subject: str, body: str, attachment: str = "") -> str:
    """Core logic for creating a Gmail draft."""
    client = get_composio_client()
    args = {"recipient_email": recipient_email, "subject": subject, "body": body, "is_html": True}
    if attachment: args["attachment"] = attachment
    
    result = client.tools.execute(slug="GMAIL_CREATE_EMAIL_DRAFT", arguments=args, user_id=user_id, dangerously_skip_version_check=True)
    return str(result)

async def fetch_gmail_emails(user_id: str, limit: int = 5, query: str = "") -> str:
    """Core logic for fetching Gmail emails."""
    client = get_composio_client()
    args = {"limit": limit}
    if query: args["query"] = query
    
    result = client.tools.execute(slug="GMAIL_FETCH_EMAILS", arguments=args, user_id=user_id, dangerously_skip_version_check=True)
    return str(result)
