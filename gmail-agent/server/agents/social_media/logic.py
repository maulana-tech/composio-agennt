"""
Social Media Agent Logic - Robust Twitter and Facebook posting.
"""
import os
from typing import List, Optional, Tuple
from composio import Composio

def get_composio_client() -> Composio:
    """Get initialized Composio client."""
    api_key = os.environ.get("COMPOSIO_API_KEY")
    if not api_key:
        raise ValueError("COMPOSIO_API_KEY environment variable is required")
    return Composio(api_key=api_key)

def _execute_composio_action(client: Composio, slug: str, args: dict, user_id: str) -> dict:
    """Helper to execute Composio tools safely."""
    try:
        return client.tools.execute(
            slug=slug,
            arguments=args,
            user_id=user_id,
            dangerously_skip_version_check=True,
        )
    except Exception as e:
        return {"error": str(e), "successful": False}

async def upload_media_to_twitter(user_id: str, image_path: str) -> str:
    """Robust Twitter media upload trying multiple schemas."""
    client = get_composio_client()
    media_slugs = [
        ("TWITTER_UPLOAD_MEDIA", {"media": image_path}),
        ("TWITTER_UPLOAD_MEDIA", {"media_file_path": image_path}),
        ("TWITTER_POST_MEDIA", {"media": image_path}),
        ("UPLOAD_MEDIA", {"file": image_path}),
    ]
    last_error = ""
    for slug, args in media_slugs:
        try:
            result = _execute_composio_action(client, slug, args, user_id)
            if result.get("successful"):
                data = result.get("data", {})
                if "data" in data and isinstance(data["data"], dict):
                    media_id = data["data"].get("id") or data["data"].get("media_id")
                else:
                    media_id = data.get("id") or data.get("media_id")
                if media_id: return str(media_id)
            last_error = result.get("error", "Unknown error")
        except Exception as e:
            last_error = str(e); continue
    raise Exception(f"Failed to upload media to Twitter. Last error: {last_error}")

async def post_to_twitter(user_id: str, text: str, image_path: Optional[str] = None) -> str:
    """Post to Twitter/X with optional image."""
    try:
        client = get_composio_client()
        media_ids = []
        if image_path and os.path.exists(image_path):
            media_id = await upload_media_to_twitter(user_id, image_path)
            media_ids.append(media_id)
        args = {"text": text}
        if media_ids: args["media_media_ids"] = media_ids
        result = _execute_composio_action(client, "TWITTER_CREATION_OF_A_POST", args, user_id)
        if result.get("successful"):
            tweet_id = result.get("data", {}).get("data", {}).get("id")
            url = f"https://twitter.com/i/status/{tweet_id}" if tweet_id else "unknown"
            return f"✅ Tweet posted successfully! Link: {url}"
        else:
            return f"❌ Tweet failed: {result.get('error')}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

async def get_facebook_page(user_id: str) -> Tuple[Optional[str], Optional[str]]:
    """Get the first managed Facebook page ID and Name."""
    client = get_composio_client()
    result = _execute_composio_action(client, "FACEBOOK_LIST_MANAGED_PAGES", {"user_id": "me", "limit": 1, "fields": "id,name"}, user_id)
    if result.get("successful"):
        data = result.get("data", {})
        results_list = data.get("data", [])
        if not results_list: results_list = data.get("response", {}).get("data", {}).get("data", [])
        if isinstance(results_list, list) and results_list:
             page = results_list[0]
             return page.get("id"), page.get("name")
    return None, None

async def post_to_facebook(user_id: str, message: str, image_path: Optional[str] = None) -> str:
    """Post to Facebook Page with optional image."""
    try:
        client = get_composio_client()
        page_id, page_name = await get_facebook_page(user_id)
        if not page_id: return "❌ Error: Could not find any managed Facebook Pages."
        if image_path and os.path.exists(image_path):
            photo_slugs = [("FACEBOOK_create_photo_post", {"page_id": page_id, "photo": image_path, "message": message, "published": True})]
            for slug, args in photo_slugs:
                result = _execute_composio_action(client, slug, args, user_id)
                if result.get("successful"):
                    post_id = result.get("data", {}).get("post_id") or result.get("data", {}).get("id")
                    return f"✅ Posted photo to Facebook Page '{page_name}'! (ID: {post_id})"
            return "❌ Failed to upload photo to Facebook."
        else:
            result = _execute_composio_action(client, "FACEBOOK_CREATE_POST", {"page_id": page_id, "message": message, "published": True}, user_id)
            if result.get("successful"):
                post_id = result.get("data", {}).get("id")
                return f"✅ Posted text to Facebook Page '{page_name}'! (ID: {post_id})"
            return f"❌ Facebook text post failed: {result.get('error')}"
    except Exception as e:
        return f"❌ Error: {str(e)}"
