"""
Research Agent Logic - Consolidated search capabilities.
"""

import os
import httpx
from typing import List, Dict, Any, Optional


async def serper_search(query: str, num_results: int = 10) -> str:
    """Core logic for Serper web search."""
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        return "Error: SERPER_API_KEY not configured."

    try:
        url = "https://google.serper.dev/search"
        headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
        payload = {"q": query, "num": min(num_results, 20)}

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()

            output = [f"**Search Results for: '{query}'**\n"]
            for i, result in enumerate(data.get("organic", []), 1):
                output.append(f"{i}. **[{result.get('title')}]({result.get('link')})**")
                output.append(f"   {result.get('snippet')}\n")
            return "\n".join(output)
    except Exception as e:
        return f"Search error: {str(e)}"


async def google_grounding_search(query: str) -> str:
    """Core logic for Google Grounding search."""
    google_api_key = os.environ.get("GOOGLE_API_KEY")
    if not google_api_key:
        return "Error: GOOGLE_API_KEY not found."

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=google_api_key)
        grounding_tool = types.Tool(google_search=types.GoogleSearch())
        config = types.GenerateContentConfig(tools=[grounding_tool])

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"Search and provide factual information about: {query}. Include sources and citations.",
            config=config,
        )

        result_text = response.text or "No results found"

        # Extract sources from grounding metadata
        sources = []
        if response.candidates and response.candidates[0].grounding_metadata:
            metadata = response.candidates[0].grounding_metadata
            chunks = metadata.grounding_chunks
            if chunks:
                for i, chunk in enumerate(chunks):
                    if chunk.web:
                        sources.append(
                            {
                                "title": chunk.web.title or f"Source {i + 1}",
                                "link": chunk.web.uri,
                            }
                        )

        output = [f"**Grounding Search Results for: '{query}'**\n"]
        output.append(result_text)
        if sources:
            output.append("\n**Sources:**")
            for src in sources:
                output.append(f"- [{src['title']}]({src['link']})")

        return "\n".join(output)
    except Exception as e:
        return f"Grounding search error: {str(e)}"


async def visit_webpage(url: str) -> str:
    """Extract text content from a webpage."""
    try:
        from bs4 import BeautifulSoup
        from fake_useragent import UserAgent

        ua = UserAgent()
        headers = {"User-Agent": ua.random}
        async with httpx.AsyncClient(
            timeout=30, follow_redirects=True, verify=False
        ) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for element in soup(
                ["script", "style", "nav", "footer", "header", "aside"]
            ):
                element.decompose()
            text = soup.get_text(separator="\n", strip=True)
            return text[:15000]
    except Exception as e:
        return f"Error visiting page: {str(e)}"


async def download_file(url: str, filename: str = "") -> str:
    """Download a file to the attachment folder."""
    try:
        from fake_useragent import UserAgent

        ua = UserAgent()
        headers = {"User-Agent": ua.random}
        async with httpx.AsyncClient(
            timeout=60, follow_redirects=True, verify=False
        ) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            if not filename:
                filename = url.split("/")[-1] or "downloaded_file"
            root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
            dest = os.path.join(root, "attachment", filename)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f:
                f.write(response.content)
            return dest
    except Exception as e:
        return f"Error downloading file: {str(e)}"
