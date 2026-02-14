"""
Quote Agent Tools - LangChain tool exports.
"""
from langchain_core.tools import tool
from .logic import generate_simple_quote, generate_dalle_quote

def get_quote_tools() -> list:
    """Get all quote generation tools."""
    
    @tool("generate_quote_image")
    async def generate_quote_image_tool(quote_text: str, author: str, context: str = "") -> str:
        """Generate a professional quote image using standard typography."""
        return await generate_simple_quote(quote_text, author, context)

    @tool("generate_artistic_quote")
    async def generate_artistic_quote_tool(quote_text: str, author: str, style: str = "digital art") -> str:
        """Generate an artistic AI quote image using DALL-E 3."""
        path = await generate_dalle_quote(quote_text, author, style)
        return f"Artistic quote generated at: {path}" if path else "Failed to generate."

    return [generate_quote_image_tool, generate_artistic_quote_tool]
