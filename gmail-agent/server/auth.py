import os
from composio import Composio
from typing import Optional


def fetch_auth_config(composio_client: Composio):
    auth_configs = composio_client.auth_configs.list()
    for auth_config in auth_configs.items:
        if auth_config.toolkit == "GMAIL":
            return auth_config
    return None


def create_auth_config(composio_client: Composio):
    client_id = os.getenv("GMAIL_CLIENT_ID")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise ValueError(
            "GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET required for custom auth"
        )

    return composio_client.auth_configs.create(
        toolkit="GMAIL",
        options={
            "name": "default_gmail_auth_config",
            "type": "use_custom_auth",
            "auth_scheme": "OAUTH2",
            "credentials": {
                "client_id": client_id,
                "client_secret": client_secret,
            },
        },
    )


def create_connection(
    composio_client: Composio, user_id: str, auth_config_id: Optional[str] = None
):
    if not auth_config_id:
        auth_config = fetch_auth_config(composio_client=composio_client)
        if not auth_config:
            try:
                auth_config = create_auth_config(composio_client=composio_client)
            except ValueError:
                auth_config = None
        if auth_config:
            auth_config_id = auth_config.id

    connection_params = {"user_id": user_id}
    if auth_config_id:
        connection_params["auth_config_id"] = auth_config_id

    return composio_client.connected_accounts.initiate(**connection_params)


def check_connected_account_exists(
    composio_client: Composio, user_id: str, toolkit: str = "GMAIL"
) -> bool:
    connected_accounts = composio_client.connected_accounts.list(
        user_ids=[user_id],
        toolkit_slugs=[toolkit],
    )
    for account in connected_accounts.items:
        if account.status == "ACTIVE":
            return True
    return False


def check_twitter_connected(composio_client: Composio, user_id: str) -> bool:
    """Check if Twitter account is connected for user."""
    return check_connected_account_exists(composio_client, user_id, "TWITTER")


def check_facebook_connected(composio_client: Composio, user_id: str) -> bool:
    """Check if Facebook account is connected for user."""
    return check_connected_account_exists(composio_client, user_id, "FACEBOOK")


def check_instagram_connected(composio_client: Composio, user_id: str) -> bool:
    """Check if Instagram account is connected for user."""
    return check_connected_account_exists(composio_client, user_id, "INSTAGRAM")


def check_linkedin_connected(composio_client: Composio, user_id: str) -> bool:
    """Check if LinkedIn account is connected for user."""
    return check_connected_account_exists(composio_client, user_id, "LINKEDIN")


def get_connected_accounts(composio_client: Composio, user_id: str) -> dict:
    """Get all connected social media accounts for a user."""
    toolkits = ["TWITTER", "FACEBOOK", "INSTAGRAM", "GMAIL", "LINKEDIN"]
    connected = {}

    for toolkit in toolkits:
        connected_accounts = composio_client.connected_accounts.list(
            user_ids=[user_id],
            toolkit_slugs=[toolkit],
        )
        accounts = []
        for account in connected_accounts.items:
            if account.status == "ACTIVE":
                accounts.append(
                    {
                        "id": account.id,
                        "toolkit": toolkit,
                        "status": account.status,
                        "created_at": str(account.created_at)
                        if hasattr(account, "created_at")
                        else None,
                    }
                )
        connected[toolkit] = accounts

    return connected


def create_social_connection(composio_client: Composio, user_id: str, toolkit: str):
    """Initiate OAuth connection for social media account."""
    try:
        # Get available auth configs for the toolkit
        auth_configs = composio_client.auth_configs.list(toolkit_slugs=[toolkit])

        auth_config_id = None
        for auth_config in auth_configs.items:
            if auth_config.toolkit == toolkit:
                auth_config_id = auth_config.id
                break

        if not auth_config_id:
            # Create auth config if not exists
            auth_config = composio_client.auth_configs.create(
                toolkit=toolkit,
                options={
                    "name": f"{toolkit.lower()}_auth",
                    "type": "use_default_auth",
                },
            )
            auth_config_id = auth_config.id

        # Initiate connection
        connection = composio_client.connected_accounts.initiate(
            user_id=user_id,
            auth_config_id=auth_config_id,
        )

        return connection

    except Exception as e:
        raise Exception(f"Failed to initiate {toolkit} connection: {str(e)}")


def get_connection_status(composio_client: Composio, connection_id: str):
    return composio_client.connected_accounts.get(connection_id=connection_id)


# ========== Tool Router Style Authentication ==========


def check_toolkits_status(
    composio_client: Composio, user_id: str, toolkits: list[str]
) -> dict:
    """
    Check connection status for specific toolkits using Tool Router session.

    Args:
        composio_client: Composio client instance
        user_id: User ID
        toolkits: List of toolkit slugs (e.g., ["twitter", "facebook"])

    Returns:
        Dictionary with toolkit status information
    """
    try:
        # Create session with specified toolkits
        session = composio_client.create(user_id=user_id, toolkits=toolkits)

        # Get toolkit status
        toolkit_status = session.toolkits()

        result = {}
        for toolkit in toolkit_status.items:
            is_connected = (
                toolkit.connection
                and hasattr(toolkit.connection, "is_active")
                and toolkit.connection.is_active
            )

            result[toolkit.slug] = {
                "name": toolkit.name,
                "connected": is_connected,
                "connection_id": (
                    toolkit.connection.connected_account.id
                    if is_connected and toolkit.connection.connected_account
                    else None
                ),
            }

        return result

    except Exception as e:
        raise Exception(f"Failed to check toolkit status: {str(e)}")


def authorize_toolkit(composio_client: Composio, user_id: str, toolkit: str) -> dict:
    """
    Authorize a toolkit using Tool Router session.authorize() method.

    Args:
        composio_client: Composio client instance
        user_id: User ID
        toolkit: Toolkit slug (e.g., "twitter", "facebook")

    Returns:
        Dictionary with redirect URL and connection info
    """
    try:
        # Create session
        session = composio_client.create(user_id=user_id)

        # Authorize toolkit
        connection_request = session.authorize(toolkit)

        return {
            "success": True,
            "toolkit": toolkit,
            "redirect_url": connection_request.redirect_url,
            "message": f"Please visit the redirect URL to authorize {toolkit}",
        }

    except Exception as e:
        raise Exception(f"Failed to authorize {toolkit}: {str(e)}")
