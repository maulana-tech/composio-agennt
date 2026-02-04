import os
from composio import Composio
from composio.client.enums import Action
from dotenv import load_dotenv

load_dotenv()

client = Composio(api_key=os.environ.get("COMPOSIO_API_KEY"))
tools = client.tools.get(user_id="default", tools=[Action.GMAIL_CREATE_EMAIL_DRAFT.slug])

for tool in tools:
    func = tool.get('function', {})
    print(f"Tool: {func.get('name')}")
    print(f"Parameters: {func.get('parameters', {}).get('properties', {}).keys()}")
    # print(f"Full schema: {func.get('parameters', {})}")
