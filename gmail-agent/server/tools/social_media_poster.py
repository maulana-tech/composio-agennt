"""
Social Media Posting Integration with Composio
Connects quote image generators to Instagram, Facebook, and Twitter for direct posting.
"""

import os
import base64
from typing import Optional
from langchain.tools import tool
from composio import Composio


def get_composio_client():
    """Get initialized Composio client."""
    return Composio(api_key=os.environ.get("COMPOSIO_API_KEY"))


@tool
def post_quote_to_twitter(
    user_id: str,
    image_path: str,
    caption: str,
) -> str:
    """
    Post a quote image to Twitter/X with caption.
    Use ONLY when user explicitly says: "post to Twitter", "share on X", etc.

    Args:
        user_id: Composio user ID for authentication
        image_path: Absolute path to the image file
        caption: Tweet text (max 280 characters)
    """
    try:
        composio_client = get_composio_client()

        # Validate image exists
        if not os.path.exists(image_path):
            return f"Error: Image file not found at {image_path}"

        # Validate caption length
        if len(caption) > 280:
            return f"Error: Caption too long ({len(caption)} chars). Twitter limit is 280 characters."

        # Prepare arguments for Twitter API
        args = {"text": caption, "media_file_path": image_path}

        # Execute Twitter post
        result = composio_client.tools.execute(
            slug="TWITTER_CREATE_TWEET_WITH_MEDIA",
            arguments=args,
            user_id=user_id,
            dangerously_skip_version_check=True,
        )

        return f"✅ Successfully posted to Twitter! {result}"

    except Exception as e:
        return f"Error posting to Twitter: {str(e)}"


@tool
def post_quote_to_facebook(
    user_id: str,
    image_path: str,
    caption: str,
) -> str:
    """
    Post a quote image to Facebook Page.
    Use ONLY when user explicitly says: "post to Facebook", "share on FB", etc.

    Args:
        user_id: Composio user ID for authentication
        image_path: Absolute path to the image file
        caption: Post caption text
    """
    try:
        composio_client = get_composio_client()

        # Validate image exists
        if not os.path.exists(image_path):
            return f"Error: Image file not found at {image_path}"

        # Prepare arguments for Facebook API
        args = {"message": caption, "photo_file_path": image_path}

        # Execute Facebook post
        result = composio_client.tools.execute(
            slug="FACEBOOK_CREATE_POST_WITH_PHOTO",
            arguments=args,
            user_id=user_id,
            dangerously_skip_version_check=True,
        )

        return f"✅ Successfully posted to Facebook! {result}"

    except Exception as e:
        return f"Error posting to Facebook: {str(e)}"


@tool
def post_quote_to_instagram(
    user_id: str,
    image_path: str,
    caption: str,
) -> str:
    """
    Post a quote image to Instagram.
    Use ONLY when user explicitly says: "post to Instagram", "share on IG", etc.
    Requires Instagram Business account connected to Facebook Page.

    Args:
        user_id: Composio user ID for authentication
        image_path: Absolute path to the image file
        caption: Post caption with hashtags
    """
    try:
        composio_client = get_composio_client()

        # Validate image exists
        if not os.path.exists(image_path):
            return f"Error: Image file not found at {image_path}"

        # Prepare arguments for Instagram API
        args = {"caption": caption, "media_file_path": image_path}

        # Execute Instagram post
        result = composio_client.tools.execute(
            slug="INSTAGRAM_CREATE_MEDIA_POST",
            arguments=args,
            user_id=user_id,
            dangerously_skip_version_check=True,
        )

        return f"✅ Successfully posted to Instagram! {result}"

    except Exception as e:
        return f"Error posting to Instagram: {str(e)}"


@tool
def post_quote_to_all_platforms(
    user_id: str,
    image_path: str,
    caption: str,
    platforms: Optional[str] = "twitter,facebook,instagram",
) -> str:
    """
    Post a quote image to multiple social media platforms at once.
    Use ONLY when user explicitly says: "post to all", "share everywhere", etc.

    Args:
        user_id: Composio user ID for authentication
        image_path: Absolute path to the image file
        caption: Post caption text
        platforms: Comma-separated list of platforms (twitter,facebook,instagram)
    """
    try:
        # Parse platforms
        requested_platforms = [p.strip().lower() for p in platforms.split(",")]
        available_platforms = ["twitter", "facebook", "instagram"]
        platforms_to_post = [p for p in requested_platforms if p in available_platforms]

        if not platforms_to_post:
            return (
                "Error: No valid platforms specified. Use: twitter, facebook, instagram"
            )

        results = []

        # Post to each requested platform
        if "twitter" in platforms_to_post:
            # Adjust caption for Twitter length limit
            twitter_caption = caption[:280] if len(caption) > 280 else caption
            result = post_quote_to_twitter(user_id, image_path, twitter_caption)
            results.append(f"Twitter: {result}")

        if "facebook" in platforms_to_post:
            result = post_quote_to_facebook(user_id, image_path, caption)
            results.append(f"Facebook: {result}")

        if "instagram" in platforms_to_post:
            result = post_quote_to_instagram(user_id, image_path, caption)
            results.append(f"Instagram: {result}")

        return "\n\n".join(results)

    except Exception as e:
        return f"Error posting to multiple platforms: {str(e)}"


# Export all tools for easy importing
__all__ = [
    "post_quote_to_twitter",
    "post_quote_to_facebook",
    "post_quote_to_instagram",
    "post_quote_to_all_platforms",
]
