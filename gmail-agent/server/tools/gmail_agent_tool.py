
"""
Gmail Agent Tool
Consolidates Gmail functionality (send, draft, fetch) using Composio.
"""

import os
import json
import time
from langchain_core.tools import tool
from composio import Composio

def get_composio_client() -> Composio:
    api_key = os.environ.get("COMPOSIO_API_KEY")
    return Composio(api_key=api_key)

def get_gmail_tools(user_id: str = "default") -> list:
    """Get Gmail tools bound to a specific user ID."""
    
    composio_client = get_composio_client()

    @tool("GMAIL_SEND_EMAIL")
    def gmail_send_email(
        recipient_email: str, subject: str, body: str, attachment: str = ""
    ) -> str:
        """
        Send an email using Gmail. Returns error if attachment is missing.
        """
        try:
            print(f"DEBUG: sending email to {recipient_email}")
            if not recipient_email or "@" not in str(recipient_email):
                return "ERROR: 'recipient_email' is missing or invalid. You MUST provide a valid email address."
            if attachment and "Place holder" in str(attachment):
                return "ERROR: You are using a placeholder path. You MUST call 'generate_pdf_report_wrapped' first."
            
            # Wait for file to exist if it was just generated
            if attachment:
                if not os.path.isabs(attachment):
                    attachment = os.path.abspath(attachment)
                print(f"DEBUG: Checking for attachment: {attachment}")
                retries = 20
                while retries > 0:
                    if os.path.exists(attachment):
                        print(f"DEBUG: Attachment found!")
                        break
                    print(f"DEBUG: Attachment not found yet, waiting... ({retries})")
                    time.sleep(0.5)
                    retries -= 1
                if not os.path.exists(attachment):
                    raise FileNotFoundError(
                        f"Attachment file not found at {attachment}. Did you generate it properly?"
                    )
            
            args = {
                "recipient_email": recipient_email,
                "subject": subject,
                "body": body,
                "is_html": True,
            }
            if attachment:
                args["attachment"] = attachment
            
            return composio_client.tools.execute(
                slug="GMAIL_SEND_EMAIL",
                arguments=args,
                user_id=user_id,
                dangerously_skip_version_check=True,
            )
        except Exception as e:
            print(f"ERROR: {str(e)}")
            return f"ERROR: {str(e)}"

    @tool("GMAIL_CREATE_EMAIL_DRAFT")
    def gmail_create_draft(
        recipient_email: str, subject: str, body: str, attachment: str = ""
    ) -> str:
        """Create an email draft in Gmail without sending it."""
        try:
            args = {
                "recipient_email": recipient_email,
                "subject": subject,
                "body": body,
                "is_html": True,
            }
            if attachment:
                args["attachment"] = attachment

            return composio_client.tools.execute(
                slug="GMAIL_CREATE_EMAIL_DRAFT",
                arguments=args,
                user_id=user_id,
                dangerously_skip_version_check=True,
            )
        except Exception as e:
            return f"Error creating draft: {str(e)}"

    @tool("GMAIL_FETCH_EMAILS")
    def gmail_fetch_emails(limit: int = 5, query: str = "") -> str:
        """Fetch recent emails from Gmail. If not found, do not loop, return error."""
        try:
            args = {"limit": limit}
            if query:
                args["query"] = query
            result = composio_client.tools.execute(
                slug="GMAIL_FETCH_EMAILS",
                arguments=args,
                user_id=user_id,
                dangerously_skip_version_check=True,
            )
            # Check if result contains messages
            try:
                data = json.loads(result) if isinstance(result, str) else result
                messages = data.get("data", {}).get("messages", [])
                if not messages:
                    if query:
                        # Try fetch without query if failed
                        args.pop("query", None)
                        result2 = composio_client.tools.execute(
                            slug="GMAIL_FETCH_EMAILS",
                            arguments=args,
                            user_id=user_id,
                            dangerously_skip_version_check=True,
                        )
                        return result2
                    return "ERROR: No emails found in your inbox."
            except Exception:
                pass
            return result
        except Exception as e:
            return f"Error fetching emails: {str(e)}"

    return [gmail_send_email, gmail_create_draft, gmail_fetch_emails]
