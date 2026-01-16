import os
import typing_extensions as te
from composio import Composio
from fastapi import Depends
from dotenv import load_dotenv

load_dotenv()

_composio_client: Composio | None = None


def provide_composio_client() -> Composio:
    global _composio_client
    if _composio_client is None:
        api_key = os.getenv("COMPOSIO_API_KEY")
        if not api_key:
            raise ValueError("COMPOSIO_API_KEY environment variable is required")
        _composio_client = Composio(api_key=api_key)
    return _composio_client


ComposioClient = te.Annotated[Composio, Depends(provide_composio_client)]
