import os
from composio import Composio
from dotenv import load_dotenv

load_dotenv()

client = Composio(api_key=os.environ.get("COMPOSIO_API_KEY"))
user_id = "default"

result = client.tools.execute(
    slug="GMAIL_FETCH_EMAILS",
    arguments={"limit": 3},
    user_id=user_id,
    dangerously_skip_version_check=True
)
print(result)
