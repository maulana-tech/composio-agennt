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
        raise ValueError("GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET required for custom auth")
    
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


def create_connection(composio_client: Composio, user_id: str, auth_config_id: Optional[str] = None):
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


def check_connected_account_exists(composio_client: Composio, user_id: str) -> bool:
    connected_accounts = composio_client.connected_accounts.list(
        user_ids=[user_id],
        toolkit_slugs=["GMAIL"],
    )
    for account in connected_accounts.items:
        if account.status == "ACTIVE":
            return True
    return False


def get_connection_status(composio_client: Composio, connection_id: str):
    return composio_client.connected_accounts.get(connection_id=connection_id)
