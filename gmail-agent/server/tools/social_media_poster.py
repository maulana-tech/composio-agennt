"""
Social Media Tools using Composio
Provides native tools for Twitter, Facebook, and Instagram posting.
"""

import os
import json
from typing import List, Any, Optional
from langchain_core.tools import tool
from composio import Composio


def get_composio_client() -> Composio:
    """Get initialized Composio client."""
    api_key = os.environ.get("COMPOSIO_API_KEY")
    if not api_key:
        raise ValueError("COMPOSIO_API_KEY environment variable is required")
    return Composio(api_key=api_key)


@tool
def upload_media_to_twitter(image_path: str) -> str:
    """Upload media to Twitter and get media_id for posting."""
    user_id = "pg-test-a199d8f3-e74a-42e0-956b-b1fbb2808b58"
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
            media_id = data.get("id")
            return f"✅ Media uploaded successfully! Media ID: {media_id}"
        else:
            error = result.get("data", {}).get(
                "message", result.get("error", "Unknown error")
            )
            return f"❌ Upload failed: {error}"

    except Exception as e:
        return f"❌ Twitter upload error: {str(e)}"


@tool
def post_to_twitter(text: str, image_path: Optional[str] = None) -> str:
    """Post to Twitter with optional image. Use this when user wants to post to Twitter/X.

    Args:
        text: The tweet content (max 280 characters)
        image_path: Optional path to image file to attach

    Returns:
        Success message with tweet URL
    """
    user_id = "pg-test-a199d8f3-e74a-42e0-956b-b1fbb2808b58"
    try:
        client = get_composio_client()
    except Exception as e:
        return f"❌ Error: Invalid COMPOSIO_API_KEY. {str(e)}"

    try:
        if image_path and os.path.exists(image_path):
            # Upload media first
            upload_result = client.tools.execute(
                slug="TWITTER_UPLOAD_MEDIA",
                arguments={"media": image_path},
                user_id=user_id,
                dangerously_skip_version_check=True,
            )

            if upload_result.get("successful"):
                media_data = upload_result.get("data", {}).get("data", {})
                media_id = media_data.get("id")

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
                        tweet_url = f"https://twitter.com/i/status/{tweet_id}"
                        return f"✅ Successfully posted to Twitter with image!\n\n🔗 **Link:** {tweet_url}"
                    else:
                        error = result.get("data", {}).get(
                            "message", result.get("error", "Unknown error")
                        )
                        return f"❌ Twitter error: {error}"

            # Fallback to text-only
            result = client.tools.execute(
                slug="TWITTER_CREATION_OF_A_POST",
                arguments={"text": text},
                user_id=user_id,
                dangerously_skip_version_check=True,
            )
            tweet_id = result.get("data", {}).get("data", {}).get("id", "")
            tweet_url = f"https://twitter.com/i/status/{tweet_id}"
            return (
                f"⚠️ Image upload failed, posted text only!\n\n🔗 **Link:** {tweet_url}"
            )
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
                tweet_url = f"https://twitter.com/i/status/{tweet_id}"
                return f"✅ Successfully posted to Twitter!\n\n🔗 **Link:** {tweet_url}"
            else:
                error = result.get("data", {}).get(
                    "message", result.get("error", "Unknown error")
                )
                return f"❌ Twitter error: {error}"

    except Exception as e:
        return f"❌ Twitter posting failed: {str(e)}"


@tool
def get_facebook_page_id() -> str:
    """Get the default Facebook Page ID for posting. Returns the first managed page."""
    user_id = "pg-test-a199d8f3-e74a-42e0-956b-b1fbb2808b58"
    try:
        client = get_composio_client()

        result = client.tools.execute(
            slug="FACEBOOK_LIST_MANAGED_PAGES",
            arguments={"user_id": "me", "limit": 1, "fields": "id,name"},
            user_id=user_id,
            dangerously_skip_version_check=True,
        )

        if result.get("successful"):
            data = result.get("data", {}).get("data", [])
            if isinstance(data, list) and data:
                page = data[0]
                return json.dumps(
                    {"page_id": page.get("id"), "page_name": page.get("name")}
                )

            response_data = result.get("data", {}).get("response", {}).get("data", {})
            pages = response_data.get("data", [])
            if pages:
                page = pages[0]
                return json.dumps(
                    {"page_id": page.get("id"), "page_name": page.get("name")}
                )

        return "❌ Error: Could not find Facebook page"

    except Exception as e:
        return f"❌ Error fetching Facebook page: {str(e)}"


@tool
def post_to_facebook(message: str, image_path: Optional[str] = None) -> str:
    """Post to Facebook Page with optional image. Use this when user wants to post to Facebook.

    Args:
        message: The post content/caption
        image_path: Optional path to image file to attach

    Returns:
        Success message with post URL
    """
    user_id = "pg-test-a199d8f3-e74a-42e0-956b-b1fbb2808b58"
    try:
        client = get_composio_client()
    except Exception as e:
        return f"❌ Error: Invalid COMPOSIO_API_KEY. {str(e)}"

    # Get page ID first
    page_result = client.tools.execute(
        slug="FACEBOOK_LIST_MANAGED_PAGES",
        arguments={"user_id": "me", "limit": 1, "fields": "id,name"},
        user_id=user_id,
        dangerously_skip_version_check=True,
    )

    page_id = None
    page_name = None
    if page_result.get("successful"):
        data = page_result.get("data", {}).get("data", [])
        if isinstance(data, list) and data:
            page_id = data[0].get("id")
            page_name = data[0].get("name")
        else:
            response_data = (
                page_result.get("data", {}).get("response", {}).get("data", {})
            )
            pages = response_data.get("data", [])
            if pages:
                page_id = pages[0].get("id")
                page_name = pages[0].get("name")

    if not page_id:
        return "❌ Error: Could not find Facebook page ID"

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
                fb_url = f"https://www.facebook.com/{post_id}"
                return f"✅ Successfully posted photo to Facebook!\n\n🔗 **Link:** {fb_url}"
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
                fb_url = f"https://www.facebook.com/{post_id}"
                return f"✅ Successfully posted to Facebook!\n\n🔗 **Link:** {fb_url}"
            else:
                error = result.get("data", {}).get(
                    "message", result.get("error", "Unknown error")
                )
                return f"❌ Facebook error: {error}"

    except Exception as e:
        return f"❌ Facebook posting failed: {str(e)}"


@tool
def post_to_all_platforms(
    text: str, platforms: str = "twitter,facebook", image_path: Optional[str] = None
) -> str:
    """Post to multiple social media platforms simultaneously.

    Args:
        text: The post content
        platforms: Comma-separated list - "twitter", "facebook", or "twitter,facebook"
        image_path: Optional image path to attach to posts
    """
    results = []
    platform_list = [p.strip().lower() for p in platforms.split(",")]

    if "twitter" in platform_list:
        result = post_to_twitter.invoke({"text": text, "image_path": image_path})
        results.append(f"Twitter: {result}")

    if "facebook" in platform_list:
        result = post_to_facebook.invoke({"message": text, "image_path": image_path})
        results.append(f"Facebook: {result}")

    return "\n\n".join(results)


def get_social_media_tools(user_id: str = None) -> List[Any]:
    """
    Get LangChain tools for social media posting.

    Args:
        user_id: Optional user_id (not used, uses default session)

    Returns:
        List of LangChain tools for Twitter, Facebook, and Instagram.
    """
    return [
        post_to_twitter,
        post_to_facebook,
        post_to_all_platforms,
        get_facebook_page_id,
        upload_media_to_twitter,
    ]


# Export
__all__ = [
    "get_composio_client",
    "upload_media_to_twitter",
    "post_to_twitter",
    "post_to_facebook",
    "post_to_all_platforms",
    "get_facebook_page_id",
    "get_social_media_tools",
]
