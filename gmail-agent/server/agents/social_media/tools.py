"""
Social Media Agent Tools - LangChain tool exports.
"""
from typing import Optional
from langchain_core.tools import tool
from .logic import post_to_twitter, post_to_facebook

def get_social_media_tools(user_id: str = "default") -> list:
    """Generate tools bound to a specific user_id."""
    
    @tool("post_to_twitter")
    async def post_to_twitter_tool(text: str, image_path: Optional[str] = None) -> str:
        """Post to Twitter/X with optional image."""
        return await post_to_twitter(user_id, text, image_path)

    @tool("post_to_facebook")
    async def post_to_facebook_tool(message: str, image_path: Optional[str] = None) -> str:
        """Post to Facebook Page with optional image."""
        return await post_to_facebook(user_id, message, image_path)

    @tool("post_to_all_social_media")
    async def post_to_all_tool(text: str, platforms: str = "twitter,facebook", image_path: Optional[str] = None) -> str:
        """Post to multiple platforms (comma-separated: 'twitter,facebook')."""
        results = []
        platform_list = [p.strip().lower() for p in platforms.split(",")]
        if "twitter" in platform_list:
            results.append(f"Twitter: {await post_to_twitter(user_id, text, image_path)}")
        if "facebook" in platform_list:
            results.append(f"Facebook: {await post_to_facebook(user_id, text, image_path)}")
        return "\n\n".join(results)

    return [post_to_twitter_tool, post_to_facebook_tool, post_to_all_tool]
