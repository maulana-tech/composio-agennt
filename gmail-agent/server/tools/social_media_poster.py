"""
Social Media Tools using Composio
Provides native tools for Twitter, Facebook, and Instagram posting.
"""

import os
import json
from typing import List, Any, Optional
from composio import Composio


def get_composio_client() -> Composio:
    """Get initialized Composio client."""
    api_key = os.environ.get("COMPOSIO_API_KEY")
    if not api_key:
        raise ValueError("COMPOSIO_API_KEY environment variable is required")
    return Composio(api_key=api_key)


def upload_media_to_twitter(user_id: str, image_path: str) -> Optional[str]:
    """Upload media to Twitter and get media_id."""
    try:
        client = get_composio_client()

        result = client.tools.execute(
            slug="TWITTER_UPLOAD_MEDIA",
            arguments={"media": image_path},
            user_id=user_id,
            dangerously_skip_version_check=True,
        )

        if result.get("successful"):
            data = result.get("data", {}).get("data", {})
            return data.get("id")
        return None

    except Exception as e:
        print(f"Twitter upload error: {e}")
        return None


def post_to_twitter(user_id: str, text: str, image_path: Optional[str] = None) -> str:
    """Post to Twitter with optional image."""
    try:
        client = get_composio_client()
    except Exception as e:
        return f"❌ Error: Invalid COMPOSIO_API_KEY. {str(e)}"

    try:
        if image_path and os.path.exists(image_path):
            # Upload media first
            media_id = upload_media_to_twitter(user_id, image_path)

            if media_id:
                # Post with media_id
                result = client.tools.execute(
                    slug="TWITTER_CREATION_OF_A_POST",
                    arguments={"text": text, "media_media_ids": [str(media_id)]},
                    user_id=user_id,
                    dangerously_skip_version_check=True,
                )

                if result.get("successful"):
                    tweet_id = result.get("data", {}).get("data", {}).get("id", "")
                    return f"✅ Successfully posted to Twitter with image! Tweet ID: {tweet_id}"
                else:
                    error = result.get("data", {}).get(
                        "message", result.get("error", "Unknown error")
                    )
                    return f"❌ Twitter error: {error}"
            else:
                # Fallback to text-only
                result = client.tools.execute(
                    slug="TWITTER_CREATION_OF_A_POST",
                    arguments={"text": text},
                    user_id=user_id,
                    dangerously_skip_version_check=True,
                )
                return f"⚠️ Image upload failed, posted text only. Tweet ID: {result.get('data', {}).get('data', {}).get('id', '')}"
        else:
            # Text-only post
            result = client.tools.execute(
                slug="TWITTER_CREATION_OF_A_POST",
                arguments={"text": text},
                user_id=user_id,
                dangerously_skip_version_check=True,
            )

            if result.get("successful"):
                tweet_id = result.get("data", {}).get("data", {}).get("id", "")
                return f"✅ Successfully posted to Twitter! Tweet ID: {tweet_id}"
            else:
                error = result.get("data", {}).get(
                    "message", result.get("error", "Unknown error")
                )
                return f"❌ Twitter error: {error}"

    except Exception as e:
        return f"❌ Twitter posting failed: {str(e)}"


def post_to_facebook(
    user_id: str, page_id: str, message: str, image_path: Optional[str] = None
) -> str:
    """Post to Facebook Page with optional image."""
    try:
        client = get_composio_client()
    except Exception as e:
        return f"❌ Error: Invalid COMPOSIO_API_KEY. {str(e)}"

    try:
        if image_path and os.path.exists(image_path):
            # Post with image
            result = client.tools.execute(
                slug="FACEBOOK_CREATE_PHOTO_POST",
                arguments={
                    "page_id": page_id,
                    "photo": image_path,
                    "message": message,
                    "published": True,
                },
                user_id=user_id,
                dangerously_skip_version_check=True,
            )

            if result.get("successful"):
                post_id = result.get("data", {}).get("post_id", "")
                return f"✅ Successfully posted photo to Facebook! Post ID: {post_id}"
            else:
                error = result.get("data", {}).get(
                    "message", result.get("error", "Unknown error")
                )
                return f"❌ Facebook error: {error}"
        else:
            # Text-only post
            result = client.tools.execute(
                slug="FACEBOOK_CREATE_POST",
                arguments={"page_id": page_id, "message": message, "published": True},
                user_id=user_id,
                dangerously_skip_version_check=True,
            )

            if result.get("successful"):
                post_id = result.get("data", {}).get("id", "")
                return f"✅ Successfully posted to Facebook! Post ID: {post_id}"
            else:
                error = result.get("data", {}).get(
                    "message", result.get("error", "Unknown error")
                )
                return f"❌ Facebook error: {error}"

    except Exception as e:
        return f"❌ Facebook posting failed: {str(e)}"


def get_facebook_pages(user_id: str) -> List[dict]:
    """Get list of Facebook pages managed by the user."""
    try:
        client = get_composio_client()

        result = client.tools.execute(
            slug="FACEBOOK_LIST_MANAGED_PAGES",
            arguments={"user_id": "me", "limit": 10, "fields": "id,name"},
            user_id=user_id,
            dangerously_skip_version_check=True,
        )

        if result.get("successful"):
            data = result.get("data", {}).get("data", [])
            if isinstance(data, list):
                return data
            # Try alternative path
            response_data = result.get("data", {}).get("response", {}).get("data", {})
            return response_data.get("data", [])
        return []

    except Exception as e:
        print(f"Error fetching Facebook pages: {e}")
        return []


def get_social_media_tools(user_id: str) -> List[Any]:
    """
    Get native LangChain tools for social media platforms using Tool Router.

    Args:
        user_id: The entity ID (user) to bind the tools to.

    Returns:
        List of LangChain tools for Twitter, Facebook, and Instagram.
    """
    try:
        api_key = os.environ.get("COMPOSIO_API_KEY")
        if not api_key:
            raise ValueError("COMPOSIO_API_KEY environment variable is required")

        client = Composio(api_key=api_key)

        session = client.create(
            user_id=user_id, toolkits=["twitter", "facebook", "instagram"]
        )

        tools = session.tools()

        print(f"DEBUG: Successfully loaded {len(tools)} tools.")

        for i, t in enumerate(tools[:10]):
            tool_name = "unknown"
            if hasattr(t, "name"):
                tool_name = t.name
            elif hasattr(t, "function") and isinstance(t.function, dict):
                tool_name = t.function.get("name", "unknown")
            elif isinstance(t, dict) and "function" in t:
                tool_name = t["function"].get("name", "unknown")
            print(f"  Tool {i + 1}: {tool_name}")

        if len(tools) > 10:
            print(f"  ... and {len(tools) - 10} more tools")

        return tools

    except Exception as e:
        print(f"ERROR: Failed to load social media tools: {e}")
        import traceback

        traceback.print_exc()
        return []


# Export
__all__ = [
    "get_composio_client",
    "upload_media_to_twitter",
    "post_to_twitter",
    "post_to_facebook",
    "get_facebook_pages",
    "get_social_media_tools",
]
