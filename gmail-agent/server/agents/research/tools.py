"""
Research Agent Tools - LangChain tool exports.
"""

from langchain_core.tools import tool
from .logic import serper_search, google_grounding_search


@tool
async def search_web(query: str) -> str:
    """
    Search the web for information using multiple search engines.
    Returns high-quality search results with snippets and links.
    """
    return await serper_search(query)


@tool
async def search_google_grounding(query: str) -> str:
    """
    Search using Google Grounding with real-time web search.
    Returns factual information with citations from authoritative sources.
    """
    return await google_grounding_search(query)


@tool
async def visit_webpage_tool(url: str) -> str:
    """Visit a webpage and extract its text content."""
    return await visit_webpage(url)


@tool
async def download_file_tool(url: str, filename: str = "") -> str:
    """Download a file from a URL to the project's attachment folder."""
    return await download_file(url, filename)


def get_research_tools() -> list:
    return [search_web, search_google_grounding, visit_webpage_tool, download_file_tool]
