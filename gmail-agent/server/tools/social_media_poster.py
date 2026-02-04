"""
Social Media Poster - Corrected with proper media upload approach.
Based on official Composio documentation for Twitter and Facebook.
"""

import os
import json
import base64
from typing import Optional
from langchain.tools import tool
from composio import Composio


def get_composio_client():
    """Get initialized Composio client."""
    api_key = os.environ.get("COMPOSIO_API_KEY")
    if not api_key:
        raise ValueError("COMPOSIO_API_KEY environment variable is required")
    return Composio(api_key=api_key)


def upload_media_to_twitter(user_id: str, image_path: str) -> Optional[str]:
    """Upload media to Twitter and get media_id."""
    try:
        composio_client = get_composio_client()

        upload_payload = {
            "tools": [
                {
                    "tool_slug": "TWITTER_UPLOAD_MEDIA",
                    "arguments": {"media_file_path": image_path},
                }
            ],
            "sync_response_to_workbench": False,
            "session_id": user_id,
        }

        result = composio_client.tools.execute(
            slug="COMPOSIO_MULTI_EXECUTE_TOOL",
            arguments=upload_payload,
            user_id=user_id,
            dangerously_skip_version_check=True,
        )

        try:
            if isinstance(result, str):
                result_data = json.loads(result)
            else:
                result_data = result

            results = result_data.get("data", {}).get("results", [])
            if results:
                resp = results[0].get("response", {})
                data = resp.get("data", resp)
                return data.get("id") or data.get("media_id")
        except:
            pass

        return None

    except Exception as e:
        print(f"Twitter upload error: {e}")
        return None


def post_to_twitter_with_media_id(user_id: str, image_path: str, caption: str) -> str:
    """Fallback: Post to Twitter using media_id approach."""
    try:
        composio_client = get_composio_client()
    except Exception as e:
        return f"❌ Error: Invalid COMPOSIO_API_KEY. {str(e)}"

    media_id = upload_media_to_twitter(user_id, image_path)

    if media_id:
        tweet_args = {
            "text": caption,
            "media_media_ids": [str(media_id)],
        }
        print(f"Media uploaded successfully: {media_id}")
    else:
        tweet_args = {"text": caption}

    try:
        tweet_payload = {
            "tools": [
                {"tool_slug": "TWITTER_CREATION_OF_A_POST", "arguments": tweet_args}
            ],
            "sync_response_to_workbench": False,
            "session_id": user_id,
        }

        result = composio_client.tools.execute(
            slug="COMPOSIO_MULTI_EXECUTE_TOOL",
            arguments=tweet_payload,
            user_id=user_id,
            dangerously_skip_version_check=True,
        )

        if media_id:
            return f"✅ Successfully posted to Twitter with image! {result}"
        else:
            return f"⚠️ Posted to Twitter text only: {result}"

    except Exception as e:
        try:
            tweet_payload = {
                "tools": [
                    {
                        "tool_slug": "TWITTER_CREATION_OF_A_POST",
                        "arguments": {"text": caption},
                    }
                ],
                "sync_response_to_workbench": False,
                "session_id": user_id,
            }
            result = composio_client.tools.execute(
                slug="COMPOSIO_MULTI_EXECUTE_TOOL",
                arguments=tweet_payload,
                user_id=user_id,
                dangerously_skip_version_check=True,
            )
            return f"⚠️ Image upload failed, posted text only: {result}"
        except Exception as e2:
            return f"❌ Twitter posting failed: {str(e2)}"


def post_to_twitter_correct(user_id: str, image_path: str, caption: str) -> str:
    """Post to Twitter with image using direct media file path."""
    try:
        composio_client = get_composio_client()
    except Exception as e:
        return f"❌ Error: Invalid COMPOSIO_API_KEY. {str(e)}"

    if not os.path.exists(image_path):
        return f"Error: Image file not found at {image_path}"

    if len(caption) > 280:
        return f"Error: Caption too long ({len(caption)} chars). Twitter limit is 280 characters."

    # Try TWITTER_CREATE_TWEET_WITH_MEDIA first (simpler approach)
    try:
        tweet_payload = {
            "tools": [
                {
                    "tool_slug": "TWITTER_CREATE_TWEET_WITH_MEDIA",
                    "arguments": {"text": caption, "media_file_path": image_path},
                }
            ],
            "sync_response_to_workbench": False,
            "session_id": user_id,
        }

        result = composio_client.tools.execute(
            slug="COMPOSIO_MULTI_EXECUTE_TOOL",
            arguments=tweet_payload,
            user_id=user_id,
            dangerously_skip_version_check=True,
        )

        # Check if tool was successful
        if isinstance(result, dict):
            if result.get("successful") is True:
                return f"✅ Successfully posted to Twitter with image! {result}"
            # Check for "not found" error
            error_msg = result.get("error", "")
            if "not found" in error_msg.lower():
                return post_to_twitter_with_media_id(user_id, image_path, caption)
            return f"❌ Twitter error: {result.get('error', result)}"

        return f"✅ Successfully posted to Twitter with image! {result}"

    except Exception as e:
        error_str = str(e)
        if "not found" in error_str.lower():
            return post_to_twitter_with_media_id(user_id, image_path, caption)
        return f"❌ Twitter posting failed: {error_str}"


def post_to_facebook_correct(user_id: str, image_path: str, caption: str) -> str:
    """Post to Facebook with photo using simpler direct file approach."""
    try:
        composio_client = get_composio_client()
    except Exception as e:
        return f"❌ Error: Invalid COMPOSIO_API_KEY. {str(e)}"

    if not os.path.exists(image_path):
        return f"Error: Image file not found at {image_path}"

    pages_payload = {
        "tools": [
            {
                "tool_slug": "FACEBOOK_LIST_MANAGED_PAGES",
                "arguments": {"user_id": "me", "limit": 1, "fields": "id,name"},
            }
        ],
        "sync_response_to_workbench": False,
        "session_id": user_id,
    }

    try:
        pages_result = composio_client.tools.execute(
            slug="COMPOSIO_MULTI_EXECUTE_TOOL",
            arguments=pages_payload,
            user_id=user_id,
            dangerously_skip_version_check=True,
        )

        page_id = None
        try:
            if isinstance(pages_result, str):
                pages_data = json.loads(pages_result)
            else:
                pages_data = pages_result

            results = pages_data.get("data", {}).get("results", [])
            if results:
                response_data = results[0].get("response", {}).get("data", {})
                pages_list = response_data.get("data", [])
                if pages_list:
                    page_id = pages_list[0].get("id")
        except Exception as parse_e:
            return f"❌ Error parsing Facebook pages: {str(parse_e)}"

        if not page_id:
            return "❌ Error: Could not find Facebook page ID"

        # Try FACEBOOK_CREATE_POST_WITH_PHOTO first (simpler approach)
        try:
            photo_payload = {
                "tools": [
                    {
                        "tool_slug": "FACEBOOK_CREATE_POST_WITH_PHOTO",
                        "arguments": {
                            "page_id": page_id,
                            "message": caption,
                            "photo_file_path": image_path,
                        },
                    }
                ],
                "sync_response_to_workbench": False,
                "session_id": user_id,
            }

            result = composio_client.tools.execute(
                slug="COMPOSIO_MULTI_EXECUTE_TOOL",
                arguments=photo_payload,
                user_id=user_id,
                dangerously_skip_version_check=True,
            )

            # Check if tool was successful
            if isinstance(result, dict):
                if result.get("successful") is True:
                    return f"✅ Successfully posted photo to Facebook! {result}"
                error_msg = result.get("error", "")
                if "not found" in error_msg.lower():
                    return post_to_facebook_with_base64(
                        user_id, image_path, caption, page_id
                    )
                return f"❌ Facebook error: {result.get('error', result)}"

            return f"✅ Successfully posted photo to Facebook! {result}"

        except Exception as e:
            error_str = str(e)
            if "not found" in error_str.lower():
                return post_to_facebook_with_base64(
                    user_id, image_path, caption, page_id
                )
            return f"❌ Facebook posting failed: {error_str}"

    except Exception as e:
        return f"❌ Facebook posting failed: {str(e)}"


def post_to_facebook_with_base64(
    user_id: str, image_path: str, caption: str, page_id: str
) -> str:
    """Fallback: Post to Facebook using base64-encoded image."""
    try:
        composio_client = get_composio_client()

        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        photo_payload = {
            "tools": [
                {
                    "tool_slug": "FACEBOOK_CREATE_PHOTO_POST",
                    "arguments": {
                        "page_id": page_id,
                        "photo": {
                            "data": image_data,
                            "mime_type": "image/png"
                            if image_path.endswith(".png")
                            else "image/jpeg",
                        },
                        "message": caption,
                        "published": True,
                    },
                }
            ],
            "sync_response_to_workbench": False,
            "session_id": user_id,
        }

        result = composio_client.tools.execute(
            slug="COMPOSIO_MULTI_EXECUTE_TOOL",
            arguments=photo_payload,
            user_id=user_id,
            dangerously_skip_version_check=True,
        )

        return f"✅ Successfully posted photo to Facebook! {result}"

    except Exception as e:
        return f"❌ Facebook base64 posting failed: {str(e)}"


@tool
def post_quote_to_twitter(user_id: str, image_path: str, caption: str) -> str:
    """Post a quote image to Twitter/X."""
    return post_to_twitter_correct(user_id, image_path, caption)


@tool
def post_quote_to_facebook(user_id: str, image_path: str, caption: str) -> str:
    """Post a quote image to Facebook Page."""
    return post_to_facebook_correct(user_id, image_path, caption)


@tool
def post_quote_to_instagram(user_id: str, image_path: str, caption: str) -> str:
    """Post a quote image to Instagram."""
    # Instagram requires business account connected to Facebook
    return "❌ Instagram posting requires business account. Please connect Instagram Business account in Composio dashboard."


@tool
def post_quote_to_all_platforms(
    user_id: str,
    image_path: str,
    caption: str,
    platforms: Optional[str] = "twitter,facebook",
) -> str:
    """Post to multiple platforms."""
    platforms = platforms or "twitter,facebook"
    requested_platforms = [p.strip().lower() for p in platforms.split(",")]

    results = []

    if "twitter" in requested_platforms:
        result = post_to_twitter_correct(user_id, image_path, caption[:280])
        results.append(f"Twitter: {result}")

    if "facebook" in requested_platforms:
        result = post_to_facebook_correct(user_id, image_path, caption)
        results.append(f"Facebook: {result}")

    if "instagram" in requested_platforms:
        results.append("Instagram: ❌ Not yet implemented")

    return "\n\n".join(results)


def get_social_media_tools(user_id: str):
    """Get all social media posting tools."""

    @tool("post_quote_to_twitter")
    def post_quote_to_twitter_wrapped(image_path: str, caption: str) -> str:
        """Post quote image to Twitter/X."""
        return post_to_twitter_correct(user_id, image_path, caption)

    @tool("post_quote_to_facebook")
    def post_quote_to_facebook_wrapped(image_path: str, caption: str) -> str:
        """Post quote image to Facebook Page."""
        return post_to_facebook_correct(user_id, image_path, caption)

    @tool("post_quote_to_instagram")
    def post_quote_to_instagram_wrapped(image_path: str, caption: str) -> str:
        """Post quote image to Instagram."""
        return post_quote_to_instagram(user_id, image_path, caption)

    @tool("post_quote_to_all_platforms")
    def post_quote_to_all_platforms_wrapped(
        image_path: str, caption: str, platforms: str = "twitter,facebook"
    ) -> str:
        """Post to multiple platforms."""
        return post_quote_to_all_platforms(user_id, image_path, caption, platforms)

    return [
        post_quote_to_twitter_wrapped,
        post_quote_to_facebook_wrapped,
        post_quote_to_instagram_wrapped,
        post_quote_to_all_platforms_wrapped,
    ]


__all__ = [
    "post_quote_to_twitter",
    "post_quote_to_facebook",
    "post_quote_to_instagram",
    "post_quote_to_all_platforms",
    "get_social_media_tools",
    "post_to_twitter_correct",
    "post_to_facebook_correct",
]
