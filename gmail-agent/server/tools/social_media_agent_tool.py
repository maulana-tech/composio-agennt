
"""
Social Media Agent Tool
Consolidates Twitter and Facebook functionality with robust media handling and dynamic user IDs.
"""

import os
import json
from typing import List, Any, Optional
from langchain_core.tools import tool, StructuredTool
from composio import Composio

def get_composio_client() -> Composio:
    """Get initialized Composio client."""
    api_key = os.environ.get("COMPOSIO_API_KEY")
    if not api_key:
        raise ValueError("COMPOSIO_API_KEY environment variable is required")
    return Composio(api_key=api_key)

def _execute_composio_action(
    client: Composio, 
    slug: str, 
    args: dict, 
    user_id: str
) -> dict:
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

# ============================================================================
# Core Logic Functions (Internal)
# ============================================================================

def _upload_media_to_twitter_logic(user_id: str, image_path: str) -> str:
    """Robust Twitter media upload trying multiple schemas."""
    client = get_composio_client()
    
    # Try different media upload approaches (ported from direct_social_media.py)
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
                # Normalize response structure
                data = result.get("data", {})
                # Some endpoints nest data in 'data' again
                if "data" in data and isinstance(data["data"], dict):
                    media_id = data["data"].get("id") or data["data"].get("media_id")
                else:
                    media_id = data.get("id") or data.get("media_id")
                
                if media_id:
                    return str(media_id)
            
            last_error = result.get("error", "Unknown error")
            
        except Exception as e:
            last_error = str(e)
            continue

    raise Exception(f"Failed to upload media to Twitter. Last error: {last_error}")

def _get_facebook_page_logic(user_id: str) -> tuple[Optional[str], Optional[str]]:
    """Get the first managed Facebook page ID and Name."""
    client = get_composio_client()
    
    result = _execute_composio_action(
        client, 
        "FACEBOOK_LIST_MANAGED_PAGES", 
        {"user_id": "me", "limit": 1, "fields": "id,name"}, 
        user_id
    )

    if result.get("successful"):
        # Handle various response structures
        data = result.get("data", {})
        
        # Structure 1: Direct list
        results_list = data.get("data", [])
        
        # Structure 2: Nested response
        if not results_list:
            results_list = data.get("response", {}).get("data", {}).get("data", [])
            
        # Structure 3: Results list wrapper (common in direct_social_media.py logic)
        if not results_list and "results" in data:
             # This path is complex, simplified fallback
             pass

        if isinstance(results_list, list) and results_list:
             page = results_list[0]
             return page.get("id"), page.get("name")
             
    return None, None

def _post_to_facebook_logic(user_id: str, message: str, image_path: Optional[str] = None) -> str:
    client = get_composio_client()
    page_id, page_name = _get_facebook_page_logic(user_id)
    
    if not page_id:
        return "❌ Error: Could not find any managed Facebook Pages."

    if image_path and os.path.exists(image_path):
        # Image Post
        # Try multiple upload slugs
        photo_slugs = [
            ("FACEBOOK_create_photo_post", {"page_id": page_id, "photo": image_path, "message": message, "published": True}),
             # Fallback to direct upload first then post if needed, but CREATE_PHOTO_POST is best standard
            ("FACEBOOK_UPLOAD_PHOTO", {"page_id": page_id, "photo": image_path}),
        ]
        
        for slug, args in photo_slugs:
            result = _execute_composio_action(client, slug, args, user_id)
            if result.get("successful"):
                post_id = result.get("data", {}).get("post_id") or result.get("data", {}).get("id")
                return f"✅ Posted photo to Facebook Page '{page_name}'! (ID: {post_id})"
                
        return "❌ Failed to upload photo to Facebook."
        
    else:
        # Text Post
        result = _execute_composio_action(
            client, 
            "FACEBOOK_CREATE_POST", 
            {"page_id": page_id, "message": message, "published": True}, 
            user_id
        )
        if result.get("successful"):
            post_id = result.get("data", {}).get("id")
            return f"✅ Posted text to Facebook Page '{page_name}'! (ID: {post_id})"
        return f"❌ Facebook text post failed: {result.get('error')}"

# ============================================================================
# Tool Generators (Factory)
# ============================================================================

def get_social_media_tools(user_id: str = "default") -> List[StructuredTool]:
    """
    Generate LangChain tools with the bound user_id.
    """
    
    # 1. Twitter Post Tool
    @tool("post_to_twitter")
    def post_to_twitter_tool(text: str, image_path: Optional[str] = None) -> str:
        """Post to Twitter/X with optional image."""
        try:
            client = get_composio_client()
            media_ids = []
            
            if image_path and os.path.exists(image_path):
                try:
                    media_id = _upload_media_to_twitter_logic(user_id, image_path)
                    media_ids.append(media_id)
                except Exception as e:
                    return f"⚠️ Image upload failed: {e}. Post aborted."

            args = {"text": text}
            if media_ids:
                args["media_media_ids"] = media_ids

            result = _execute_composio_action(client, "TWITTER_CREATION_OF_A_POST", args, user_id)
            
            if result.get("successful"):
                tweet_id = result.get("data", {}).get("data", {}).get("id")
                url = f"https://twitter.com/i/status/{tweet_id}" if tweet_id else "unknown"
                return f"✅ Tweet posted successfully! Link: {url}"
            else:
                return f"❌ Tweet failed: {result.get('error')}"
                
        except Exception as e:
            return f"❌ Error: {str(e)}"

    # 2. Facebook Post Tool
    @tool("post_to_facebook")
    def post_to_facebook_tool(message: str, image_path: Optional[str] = None) -> str:
        """Post to Facebook Page with optional image."""
        try:
            return _post_to_facebook_logic(user_id, message, image_path)
        except Exception as e:
            return f"❌ Error: {str(e)}"

    # 3. Validation Tool (Get Page)
    @tool("get_facebook_page_info")
    def get_facebook_page_tool() -> str:
        """Check which Facebook Page is connected."""
        pid, pname = _get_facebook_page_logic(user_id)
        if pid:
            return f"Connected Page: {pname} (ID: {pid})"
        return "No managed pages found."

    # 4. Multi-platform Tool
    @tool("post_to_all_platforms")
    def post_to_all_tool(text: str, platforms: str = "twitter,facebook", image_path: Optional[str] = None) -> str:
        """Post to multiple platforms (comma-separated: 'twitter,facebook')."""
        results = []
        platform_list = [p.strip().lower() for p in platforms.split(",")]

        if "twitter" in platform_list:
            results.append(f"Twitter: {post_to_twitter_tool.invoke({'text': text, 'image_path': image_path})}")
        
        if "facebook" in platform_list:
            results.append(f"Facebook: {post_to_facebook_tool.invoke({'message': text, 'image_path': image_path})}")
            
        return "\n\n".join(results)

    return [
        post_to_twitter_tool,
        post_to_facebook_tool,
        post_to_all_tool,
        get_facebook_page_tool
    ]

# ============================================================================
# API Helpers (for usage in api.py without LangChain tool wrapper overhead)
# ============================================================================

async def api_post_to_twitter(user_id: str, text: str, image_path: Optional[str] = None) -> dict:
    """Direct API helper for Twitter."""
    try:
        client = get_composio_client()
        media_ids = []
        if image_path:
             media_id = _upload_media_to_twitter_logic(user_id, image_path)
             media_ids.append(media_id)
        
        args = {"text": text}
        if media_ids:
            args["media_media_ids"] = media_ids
            
        result = _execute_composio_action(client, "TWITTER_CREATION_OF_A_POST", args, user_id)
        return result
    except Exception as e:
        return {"successful": False, "error": str(e)}

async def api_post_to_facebook(user_id: str, message: str, image_path: Optional[str] = None) -> dict:
    """Direct API helper for Facebook."""
    result_str = _post_to_facebook_logic(user_id, message, image_path)
    # Convert string response back to dict-like for API consistency if needed
    # (The original API endpoint returns a dict, so we might want to adjust logic to return dicts)
    if "❌" in result_str:
        return {"successful": False, "error": result_str}
    return {"successful": True, "message": result_str}
