import os
import json
import httpx
import re
from typing import List, Dict, Any, Optional
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from composio_langchain import LangchainProvider
from composio import Composio

from server.tools.pdf_generator import generate_pdf_report
from server.tools.pillow_quote_generator import (
    generate_quote_image_tool,
    generate_and_send_quote_email,
)
from server.tools.dalle_quote_generator import generate_dalle_quote_image_tool
from server.tools.avatar_quote_generator import generate_quote_with_person_photo
from server.tools.social_media_poster import get_social_media_tools


def get_llm_with_fallback(groq_api_key: str):
    """
    Get LLM with fallback: Groq -> Google Gemini.
    Returns (llm, provider_name) tuple.
    """
    # Check for Google API key
    google_api_key = os.environ.get("GOOGLE_API_KEY")

    # Primary: Groq
    if groq_api_key:
        try:
            llm = ChatGroq(
                model="llama-3.1-8b-instant", temperature=0, groq_api_key=groq_api_key
            )
            return llm, "groq"
        except Exception as e:
            print(f"Groq init failed: {e}")

    # Fallback: Google Gemini
    if google_api_key:
        try:
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash", temperature=0, google_api_key=google_api_key
            )
            return llm, "gemini"
        except Exception as e:
            print(f"Gemini init failed: {e}")

    raise ValueError("No LLM available. Please provide GROQ_API_KEY or GOOGLE_API_KEY.")


async def run_agent_with_fallback(agent_factory, inputs: dict, groq_api_key: str):
    """
    Run agent with automatic fallback to Gemini on rate limit errors.
    agent_factory is a function that takes (llm, provider_name) and returns agent.
    """
    google_api_key = os.environ.get("GOOGLE_API_KEY")

    # Try Groq first
    if groq_api_key:
        try:
            llm = ChatGroq(
                model="llama-3.1-8b-instant", temperature=0, groq_api_key=groq_api_key
            )
            agent = agent_factory(llm, "groq")
            state = await agent.ainvoke(inputs, config={"recursion_limit": 15})
            return state, "groq"
        except Exception as e:
            error_str = str(e).lower()
            # Check if it's a rate limit, tool use failure, or generation failure
            if any(
                err in error_str
                for err in [
                    "413",
                    "rate_limit",
                    "tokens",
                    "tool_use_failed",
                    "failed_generation",
                    "failed to call",
                    "adjust your prompt",
                ]
            ):
                print(f"Groq error ({e}), falling back to Gemini.")
            else:
                raise e

    # Fallback to Gemini
    if google_api_key:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash", temperature=0, google_api_key=google_api_key
        )
        agent = agent_factory(llm, "gemini")
        state = await agent.ainvoke(inputs, config={"recursion_limit": 15})
        return state, "gemini"

    raise ValueError("Groq rate limited and no GOOGLE_API_KEY available for fallback.")


def convert_history(history: List[Dict]) -> List[BaseMessage]:
    messages = []
    if not history:
        return messages
    for msg in history:
        role = msg.get("role")
        content = msg.get("content")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
        elif role == "system":
            messages.append(SystemMessage(content=content))
    return messages


def create_serper_tools():
    """Create Serper tools for superior Google Search-based web search."""

    serper_api_key = os.environ.get("SERPER_API_KEY")
    if not serper_api_key:
        print("Warning: SERPER_API_KEY not found. Serper tools will not work.")

    @tool
    def serper_search(query: str, num_results: int = 10) -> str:
        """
        Search the web using Serper (Google Search API) for superior, relevant results.

        Args:
            query: The search query (be specific and detailed for best results)
            num_results: Maximum number of results to return (1-20)

        Returns:
            Search results with titles, URLs, content snippets, and rich Google search results
        """
        if not serper_api_key:
            return "Error: SERPER_API_KEY not configured. Please set SERPER_API_KEY environment variable."

        try:
            url = "https://google.serper.dev/search"
            headers = {"X-API-KEY": serper_api_key, "Content-Type": "application/json"}
            payload = {
                "q": query,
                "num": min(num_results, 20),
                "autocorrect": True,
                "type": "search",
            }

            response = httpx.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()

            output = []

            # Add answer box if available
            if "answerBox" in data:
                answer_box = data["answerBox"]
                if "answer" in answer_box:
                    output.append(f"**Quick Answer:** {answer_box['answer']}")
                elif "snippet" in answer_box:
                    output.append(f"**Quick Answer:** {answer_box['snippet']}")
                output.append("")

            # Add knowledge graph if available
            if "knowledgeGraph" in data:
                kg = data["knowledgeGraph"]
                output.append(f"**Knowledge Graph:** {kg.get('title', 'No title')}")
                if "description" in kg:
                    output.append(kg["description"])
                output.append("")

            # Add organic results
            output.append(f"**Found {len(data.get('organic', []))} organic results:**")

            for i, result in enumerate(data.get("organic", []), 1):
                title = result.get("title", "No title")
                link = result.get("link", "")
                snippet = result.get("snippet", "No description")

                # Truncate snippet if too long
                if len(snippet) > 300:
                    snippet = snippet[:300] + "..."

                output.append(f"\n{i}. **{title}**")
                output.append(f"   {link}")
                output.append(f"   {snippet}")

                # Add sitelinks if available
                if "sitelinks" in result:
                    for sitelink in result["sitelinks"][:2]:  # Limit to 2 sitelinks
                        sitelink_title = sitelink.get("title", "")
                        sitelink_link = sitelink.get("link", "")
                        if sitelink_title and sitelink_link:
                            output.append(f"   → {sitelink_title}: {sitelink_link}")

            # Add related searches if available
            if "relatedSearches" in data:
                output.append(f"\n**Related Searches:**")
                for search in data["relatedSearches"][
                    :5
                ]:  # Limit to 5 related searches
                    output.append(f"• {search}")

            return "\n".join(output)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return "Error: Invalid SERPER_API_KEY. Please check your API key."
            elif e.response.status_code == 429:
                return "Error: Rate limit exceeded. Please try again later."
            else:
                return f"Search error: HTTP {e.response.status_code} - {str(e)}"
        except Exception as e:
            return f"Search error: {str(e)}"

    @tool
    def serper_news_search(query: str, num_results: int = 10) -> str:
        """
        Search for recent news using Serper News API for current events and breaking news.

        Args:
            query: The news search query
            num_results: Maximum number of news results to return (1-20)

        Returns:
            Recent news articles with titles, URLs, dates, and sources
        """
        if not serper_api_key:
            return "Error: SERPER_API_KEY not configured. Please set SERPER_API_KEY environment variable."

        try:
            url = "https://google.serper.dev/news"
            headers = {"X-API-KEY": serper_api_key, "Content-Type": "application/json"}
            payload = {"q": query, "num": min(num_results, 20)}

            response = httpx.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()

            output = []
            output.append(f"**Recent News Results for: '{query}'**")
            output.append("")

            news_results = data.get("news", [])
            if not news_results:
                output.append("No recent news found for this query.")
                return "\n".join(output)

            for i, news in enumerate(news_results, 1):
                title = news.get("title", "No title")
                link = news.get("link", "")
                snippet = news.get("snippet", "No description")
                date = news.get("date", "Date not available")
                source = news.get("source", "Unknown source")

                # Truncate snippet
                if len(snippet) > 250:
                    snippet = snippet[:250] + "..."

                output.append(f"\n{i}. **{title}**")
                output.append(f"   📅 {date} | 📰 {source}")
                output.append(f"   {link}")
                output.append(f"   {snippet}")

            return "\n".join(output)

        except Exception as e:
            return f"News search error: {str(e)}"

    @tool
    def serper_images_search(query: str, num_results: int = 10) -> str:
        """
        Search for images using Serper Images API.

        Args:
            query: The image search query
            num_results: Maximum number of image results to return (1-20)

        Returns:
            Image search results with titles, URLs, and thumbnail links
        """
        if not serper_api_key:
            return "Error: SERPER_API_KEY not configured. Please set SERPER_API_KEY environment variable."

        try:
            url = "https://google.serper.dev/images"
            headers = {"X-API-KEY": serper_api_key, "Content-Type": "application/json"}
            payload = {"q": query, "num": min(num_results, 20)}

            response = httpx.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()

            output = []
            output.append(f"**Image Search Results for: '{query}'**")
            output.append("")

            image_results = data.get("images", [])
            if not image_results:
                output.append("No images found for this query.")
                return "\n".join(output)

            for i, image in enumerate(image_results, 1):
                title = image.get("title", "No title")
                link = image.get("link", "")
                thumbnail = image.get("thumbnailUrl", "")
                width = image.get("imageWidth", "N/A")
                height = image.get("imageHeight", "N/A")

                output.append(f"\n{i}. **{title}**")
                output.append(f"   🔗 [Full Image]({link})")
                if thumbnail:
                    output.append(f"   🖼️ [Thumbnail]({thumbnail})")
                output.append(f"   📐 Size: {width}x{height}")

            return "\n".join(output)

        except Exception as e:
            return f"Image search error: {str(e)}"

    @tool
    def serper_videos_search(query: str, num_results: int = 10) -> str:
        """
        Search for videos using Serper Videos API.

        Args:
            query: The video search query
            num_results: Maximum number of video results to return (1-20)

        Returns:
            Video search results with titles, URLs, and platform information
        """
        if not serper_api_key:
            return "Error: SERPER_API_KEY not configured. Please set SERPER_API_KEY environment variable."

        try:
            url = "https://google.serper.dev/videos"
            headers = {"X-API-KEY": serper_api_key, "Content-Type": "application/json"}
            payload = {"q": query, "num": min(num_results, 20)}

            response = httpx.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()

            output = []
            output.append(f"**Video Search Results for: '{query}'**")
            output.append("")

            video_results = data.get("videos", [])
            if not video_results:
                output.append("No videos found for this query.")
                return "\n".join(output)

            for i, video in enumerate(video_results, 1):
                title = video.get("title", "No title")
                link = video.get("link", "")
                duration = video.get("duration", "Duration unknown")
                platform = video.get("platform", "Unknown platform")

                output.append(f"\n{i}. **{title}**")
                output.append(f"   🎬 {platform} | ⏱️ {duration}")
                output.append(f"   🔗 {link}")

            return "\n".join(output)

        except Exception as e:
            return f"Video search error: {str(e)}"

    return [
        serper_search,
        serper_news_search,
        serper_images_search,
        serper_videos_search,
    ]


def create_grounding_tools():
    """Create Google Grounding tools for search with real-time web content."""

    from google import genai
    from google.genai import types

    google_api_key = os.environ.get("GOOGLE_API_KEY")

    @tool
    def search_google(query: str) -> str:
        """
        Search Google using Gemini with Grounding (real-time web search).
        This tool connects to real-time web content and provides accurate, cited answers.

        Args:
            query: The search query.

        Returns:
            Search results with citations and sources from real-time web search.
        """
        if not google_api_key:
            return "Error: GOOGLE_API_KEY not found in environment variables. Required for Google Grounding search."

        try:
            # Initialize Gemini client
            client = genai.Client(api_key=google_api_key)

            # Create grounding tool with Google Search
            grounding_tool = types.Tool(google_search=types.GoogleSearch())

            # Configure generation with grounding tool
            config = types.GenerateContentConfig(tools=[grounding_tool])

            # Generate content with grounding
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=query,
                config=config,
            )

            # Extract text and citations
            result_text = response.text

            # Add citations if available
            if response.candidates and response.candidates[0].grounding_metadata:
                metadata = response.candidates[0].grounding_metadata
                chunks = metadata.grounding_chunks
                supports = metadata.grounding_supports

                if chunks and supports:
                    # Build citation map
                    citation_links = []
                    for i, chunk in enumerate(chunks):
                        if chunk.web:
                            citation_links.append(
                                f"[{i + 1}] {chunk.web.title}: {chunk.web.uri}"
                            )

                    # Add citations section
                    if citation_links:
                        result_text += "\n\n**Sources:**\n" + "\n".join(citation_links)

            return result_text
        except Exception as e:
            return f"Search error: {str(e)}"

    @tool
    def visit_webpage(url: str) -> str:
        """
        Visit a webpage and extract its text content. Use this to read articles found via search.

        Args:
            url: The URL to visit.

        Returns:
            The text content of the webpage.
        """
        try:
            from bs4 import BeautifulSoup
            from fake_useragent import UserAgent

            ua = UserAgent()
            headers = {"User-Agent": ua.random}

            with httpx.Client(
                timeout=30, follow_redirects=True, verify=False
            ) as client:
                response = client.get(url, headers=headers)

                if response.status_code == 403:
                    return (
                        f"Error: Access forbidden (403) for {url}. Try another source."
                    )
                elif response.status_code == 404:
                    return f"Error: Page not found (404) for {url}."

                response.raise_for_status()

                # Handle PDF files
                content_type = response.headers.get("content-type", "").lower()
                if "application/pdf" in content_type or url.lower().endswith(".pdf"):
                    import io
                    from pypdf import PdfReader

                    try:
                        pdf_file = io.BytesIO(response.content)
                        reader = PdfReader(pdf_file)
                        text = ""
                        for page in reader.pages:
                            text += page.extract_text() + "\n"

                        if len(text) > 15000:
                            text = text[:15000] + "\n...[PDF Content Truncated]"
                        return f"PDF Content from {url}:\n\n{text}"
                    except Exception as pdf_err:
                        return f"Error reading PDF: {str(pdf_err)}"

                # Handle DOCX files
                if (
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    in content_type
                    or url.lower().endswith(".docx")
                ):
                    import io
                    import docx

                    try:
                        doc_file = io.BytesIO(response.content)
                        doc = docx.Document(doc_file)
                        text = "\n".join([para.text for para in doc.paragraphs])

                        if len(text) > 15000:
                            text = text[:15000] + "\n...[DOCX Content Truncated]"
                        return f"DOCX Content from {url}:\n\n{text}"
                    except Exception as doc_err:
                        return f"Error reading DOCX: {str(doc_err)}"

                html = response.text

            # Better text extraction with BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # Remove scripts, styles, navigation, footer
            for element in soup(
                ["script", "style", "nav", "footer", "header", "aside"]
            ):
                element.decompose()

            text = soup.get_text(separator="\n", strip=True)

            # Clean up excessive newlines
            text = re.sub(r"\n{3,}", "\n\n", text)

            if len(text) > 15000:
                text = text[:15000] + "\n...[Content Truncated]"

            return text
        except Exception as e:
            return f"Error visiting page: {str(e)}"

    @tool
    def download_file(url: str, filename: str = "") -> str:
        """
        Download a file from a URL to the local server.
        Use this when you want to send the ORIGINAL file (PDF/DOCX) as an attachment,
        instead of generating a new report.

        Args:
            url: The URL of the file to download.
            filename: Optional filename. If not provided, it will be extracted from the URL.

        Returns:
            The absolute path of the downloaded file.
        """
        try:
            from fake_useragent import UserAgent

            ua = UserAgent()
            headers = {"User-Agent": ua.random}

            with httpx.Client(
                timeout=60, follow_redirects=True, verify=False
            ) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()

                if not filename:
                    # Try to get filename from Content-Disposition header
                    import cgi

                    content_disposition = response.headers.get("content-disposition")
                    if content_disposition:
                        _, params = cgi.parse_header(content_disposition)
                        filename = params.get("filename")

                    # Fallback to URL path
                    if not filename:
                        filename = url.split("/")[-1].split("?")[0]

                    # Fallback default
                    if not filename or len(filename) > 100:
                        import uuid

                        ext = ".pdf"  # default assumption safest
                        content_type = response.headers.get("content-type", "").lower()
                        if "word" in content_type:
                            ext = ".docx"
                        elif "pdf" in content_type:
                            ext = ".pdf"
                        filename = f"downloaded_file_{str(uuid.uuid4())[:8]}{ext}"

                # Sanitize filename
                filename = "".join(c for c in filename if c.isalnum() or c in "._- ")

                # Save file
                filepath = os.path.abspath(filename)
                with open(filepath, "wb") as f:
                    f.write(response.content)

                return filepath
        except Exception as e:
            return f"Error downloading file: {str(e)}"

    return [search_google, visit_webpage, download_file]


def get_agent_tools(user_id: str):
    """Create all tools for the agent with specific user context."""
    composio_client = Composio(api_key=os.environ.get("COMPOSIO_API_KEY"))

    @tool("GMAIL_SEND_EMAIL")
    def gmail_send_email(
        recipient_email: str, subject: str, body: str, attachment: str = ""
    ) -> str:
        """
        Send an email using Gmail. Returns error if attachment is missing.
        """
        try:
            print(f"DEBUG: sending email to {recipient_email}")
            if not recipient_email or "@" not in str(recipient_email):
                return "ERROR: 'recipient_email' is missing or invalid. You MUST provide a valid email address."
            if attachment and "Place holder" in str(attachment):
                return "ERROR: You are using a placeholder path. You MUST call 'generate_pdf_report_wrapped' first."
            # Wait for file to exist if it was just generated
            if attachment:
                import time, os

                if not os.path.isabs(attachment):
                    attachment = os.path.abspath(attachment)
                print(f"DEBUG: Checking for attachment: {attachment}")
                retries = 20
                while retries > 0:
                    if os.path.exists(attachment):
                        print(f"DEBUG: Attachment found!")
                        break
                    print(f"DEBUG: Attachment not found yet, waiting... ({retries})")
                    time.sleep(0.5)
                    retries -= 1
                if not os.path.exists(attachment):
                    raise FileNotFoundError(
                        f"Attachment file not found at {attachment}. Did you generate it properly?"
                    )
            args = {
                "recipient_email": recipient_email,
                "subject": subject,
                "body": body,
                "is_html": True,
            }
            if attachment:
                args["attachment"] = attachment
            return composio_client.tools.execute(
                slug="GMAIL_SEND_EMAIL",
                arguments=args,
                user_id=user_id,
                dangerously_skip_version_check=True,
            )
        except Exception as e:
            print(f"ERROR: {str(e)}")
            return f"ERROR: {str(e)}"

    @tool("GMAIL_CREATE_EMAIL_DRAFT")
    def gmail_create_draft(
        recipient_email: str, subject: str, body: str, attachment: str = ""
    ) -> str:
        """Create an email draft in Gmail without sending it."""
        try:
            args = {
                "recipient_email": recipient_email,
                "subject": subject,
                "body": body,
                "is_html": True,
            }
            if attachment:
                args["attachment"] = attachment

            return composio_client.tools.execute(
                slug="GMAIL_CREATE_EMAIL_DRAFT",
                arguments=args,
                user_id=user_id,
                dangerously_skip_version_check=True,
            )
        except Exception as e:
            return f"Error creating draft: {str(e)}"

    @tool("GMAIL_FETCH_EMAILS")
    def gmail_fetch_emails(limit: int = 5, query: str = "") -> str:
        """Fetch recent emails from Gmail. If not found, do not loop, return error."""
        try:
            args = {"limit": limit}
            if query:
                args["query"] = query
            result = composio_client.tools.execute(
                slug="GMAIL_FETCH_EMAILS",
                arguments=args,
                user_id=user_id,
                dangerously_skip_version_check=True,
            )
            # Check if result contains messages
            import json

            try:
                data = json.loads(result) if isinstance(result, str) else result
                messages = data.get("data", {}).get("messages", [])
                if not messages:
                    if query:
                        # Coba fetch tanpa query jika query gagal
                        args.pop("query", None)
                        result2 = composio_client.tools.execute(
                            slug="GMAIL_FETCH_EMAILS",
                            arguments=args,
                            user_id=user_id,
                            dangerously_skip_version_check=True,
                        )
                        data2 = (
                            json.loads(result2) if isinstance(result2, str) else result2
                        )
                        messages2 = data2.get("data", {}).get("messages", [])
                        if not messages2:
                            return "ERROR: No emails found in your inbox."
                        return result2
                    return "ERROR: No emails found in your inbox."
            except Exception:
                pass
            return result
        except Exception as e:
            return f"Error fetching emails: {str(e)}"

    gmail_tools = [gmail_send_email, gmail_create_draft, gmail_fetch_emails]

    # Search Tools
    serper_tools = create_serper_tools()
    search_tools = create_grounding_tools()

    # PDF Generator
    @tool
    def generate_pdf_report_wrapped(
        markdown_content: str,
        filename: str = "report.pdf",
        sender_email: str = "AI Assistant",
        enable_quote_images: bool = True,
    ) -> str:
        """
        Generate a professional PDF report from Markdown content with AI-generated images for political quotes.

        Args:
            markdown_content: The markdown text to include in the report.
            filename: The name of the PDF file to generate.
            sender_email: The email address to derive a dynamic logo from (e.g., 'user@gmail.com' -> 'user' logo).
            enable_quote_images: Whether to generate AI images for political quotes (default: True). Set to False to disable image generation.

        Returns:
            The ABSOLUTE FILE PATH that you MUST use for gmail_send_email attachment parameter.

        Note:
            When enable_quote_images=True, the PDF will include AI-generated visual representations
            of political quotes (up to 5 images maximum) using Gemini image generation.
        """
        if not filename:
            filename = "report.pdf"
        print(
            f"DEBUG: Executing PDF generator for {filename} with sender {sender_email}, quote_images={enable_quote_images}"
        )
        path = generate_pdf_report.invoke(
            {
                "markdown_content": markdown_content,
                "filename": filename,
                "sender_email": sender_email,
                "enable_quote_images": enable_quote_images,
                "max_quote_images": 5,
            }
        )
        print(f"DEBUG: PDF generated at {path}")
        return path

    # Quote Image Tools
    quote_tools = [
        generate_quote_image_tool,  # Pillow - 100% accurate text
        generate_and_send_quote_email,  # Pillow + Email
        generate_dalle_quote_image_tool,  # DALL-E - AI generated
        generate_quote_with_person_photo,  # Avatar - person photo background
    ]

    # Social Media Tools (Verified Native Approach)
    social_media_tools = get_social_media_tools(user_id)

    return (
        serper_tools
        + search_tools
        + [generate_pdf_report_wrapped]
        + quote_tools
        + social_media_tools
        + gmail_tools
    )


SYSTEM_PROMPT = """
You are an expert Research and Email Assistant specializing in political analysis, fact-checking, and comprehensive report generation. Your goal is to provide high-quality, verified, and well-structured information.

## SPECIALIZED CAPABILITIES:

### 1. Political Quotes & Social Media Research
- Find and extract quotes from politicians on specific topics/issues
- Search for statements from political figures on social media platforms (Twitter/X, Facebook, Instagram, TikTok)
- Categorize quotes by: official statements, campaign promises, policy positions, controversial remarks
- Always cite the source: date, platform, context, and link if available
- Example searches: "Prabowo quotes on defense policy 2024", "statements by Jokowi on economic policy Twitter"

### 1.5. AI-Generated Quote Visualizations (PDF ONLY)
When generating PDF reports, the system will AUTOMATICALLY create AI-generated images for political quotes:
- **What it does**: Gemini AI generates professional visual representations of important political quotes
- **When it triggers**: Automatically for each quote when `enable_quote_images=True` (default)
- **Visual style**: Professional design with Indonesian national colors (red/white) or professional blue themes
- **Limit**: Maximum 5 quote images per PDF to maintain quality and file size
- **Best for**: Landmark statements, campaign promises, controversial quotes, official policy announcements
- **No action needed**: This happens automatically when you call `generate_pdf_report_wrapped`

### 1.6. Social Media Posting Integration
You can directly post quote images to social media platforms using Composio integration:

**Available Platforms:**
- **Twitter/X**: Post quote images with captions (280 character limit)
- **Facebook**: Post to Facebook Pages with image and caption
- **Instagram**: Post to Instagram Business accounts (requires Facebook Page connection)
- **Multi-Platform**: Post to multiple platforms simultaneously

**When to Use Social Media Tools:**
- Use ONLY when user explicitly requests: "post to Twitter", "share on Facebook", "upload to Instagram", "post to all platforms"
- Requires prior OAuth connection setup in Composio Dashboard for each platform
- Instagram requires Business account connected to Facebook Page

**Workflow:**
1. Generate quote image using any quote generator tool
2. Call appropriate social media posting tool with image path and caption
3. Return confirmation with post details/URL

**Tools Available:**
- **Dynamic Discovery**: The agent uses `COMPOSIO_SEARCH_TOOLS` to find social media capabilities.
- **Workflow**:
  1. CALL `COMPOSIO_SEARCH_TOOLS` with a query like "post to twitter" or "create facebook post".
  2. The tool will return specific actions (e.g., `twitter_creation_of_a_post`) and their schemas.
  3. CALL `COMPOSIO_MULTI_EXECUTE_TOOL` with the found slug and arguments (e.g., `{"text": "..."}`).
- **Do NOT** hallucinate tool names like `post_quote_to_twitter`. use ONLY what `COMPOSIO_SEARCH_TOOLS` returns.

**Important Notes:**
- All social media tools require user OAuth connections configured in Composio
- Instagram API limitations may apply (Business/Creator accounts only)
- Always validate image exists before attempting to post
- Respect platform character limits and content policies

### 1.7. Intelligent Search Decision (CRITICAL)
You must intelligently decide when web search is NEEDED vs when you can answer from your training data:

**USE WEB SEARCH (Grounding) when:**
- User asks about CURRENT events (2024, 2025, 2026): "Who won the election?", "Latest news about..."
- User asks about RECENT developments: "Prabowo's recent policies", "Latest economic data"
- User asks about TIMELY information: "Current inflation rate", "Today's weather"
- User asks about SPECIFIC recent facts: "What happened yesterday?", "Latest cabinet changes"
- User asks about VERIFYING recent claims: "Is it true that...", "Fact-check this statement"
- User asks about DYNAMIC data: Stock prices, current exchange rates, live scores
- User asks about RECENT social media: "What did Prabowo tweet today?"

**NO SEARCH NEEDED (Use Training Data) when:**
- User asks about HISTORICAL facts before 2024: "When did Indonesia gain independence?", "Who was the first president?"
- User asks about GENERAL knowledge: "What is democracy?", "How does blockchain work?"
- User asks about CONCEPTS and theories: "Explain Keynesian economics", "What is inflation?"
- User asks about STATIC information: "Capital of France", "Chemical formula of water"
- User asks about PERSONAL opinions/advice: "What should I do?", "How to improve..."
- User asks about CREATIVE tasks: "Write a poem", "Generate ideas"
- User asks about WELL-ESTABLISHED facts: "Theory of relativity", "Photosynthesis process"

**DECISION LOGIC:**
```
IF question contains:
  - Recent dates (2024, 2025, today, yesterday, last week)
  - Current status words (now, today, latest, recent, current)
  - Breaking news keywords
  - Verification requests
  - Social media mentions with time context
  → USE search_google tool

ELSE IF question contains:
  - Historical dates (before 2024)
  - General knowledge terms
  - Conceptual/theoretical queries
  - Definition requests
  - Creative writing prompts
  → Answer from training data (NO search)
```

**EXAMPLES:**
```
User: "What is democracy?" → Answer from training (NO search)
User: "Who won Indonesia election 2024?" → Use search_google
User: "Explain photosynthesis" → Answer from training (NO search)
User: "What are Prabowo's latest policies?" → Use search_google
User: "Capital of Japan?" → Answer from training (NO search)
User: "Current inflation rate in Indonesia?" → Use search_google
```

**IMPORTANT:** When in doubt between using search or not, prefer to use search for factual accuracy, especially for any recent or time-sensitive information.

### 2. PDF Generation Decision Matrix
CRITICAL: You must intelligently decide whether to generate a PDF:

**GENERATE PDF when:**
- User explicitly requests: "buat PDF", "generate report", "create file", "make document"
- User wants to send/forward via email with attachment
- Request involves comprehensive research (multiple topics, detailed analysis)
- Political analysis requiring structured citations and quotes
- Fact-checking reports with evidence and sources
- Information needs to be archived, printed, or shared formally
- User says "kirim", "email", "send", "reply with attachment"

**NO PDF NEEDED but AUTO-SEND EMAIL:**
- User says "kirim ke email", "send to my email", "reply", "laporkan" (implies sending but NO PDF mentioned)
- Email analysis requests: "Analisis email ini dan reply"
- Research with implicit sending: "Cari isu Prabowo dan kirim hasilnya"
- **ACTION:** Format beautifully and AUTO-SEND immediately (NO confirmation needed)

**NO PDF NEEDED (chat response only):**
- Quick questions or brief answers
- Simple information lookup (single fact, definition)
- Casual conversation or clarification
- User does NOT mention file, document, OR email sending
- When user just wants to "check", "find", "search" without format specification

**WHEN UNCERTAIN:** Ask user: "Apakah Anda ingin saya membuat laporan PDF yang detail, kirimkan hasilnya ke email, atau cukup jawaban di chat saja?"

### 3. Message Context Understanding
- Analyze conversation history to understand user intent
- Detect implicit requests (e.g., "Can you look into this?" often means they want detailed research)
- Recognize follow-up questions as part of ongoing research
- Adapt tone: formal for professional/political topics, conversational for casual queries

### 4. Email Body Formatting (Text-Only Output)
When sending email WITHOUT PDF attachment, the email body MUST be beautifully formatted with:

**Structure:**
```
Subject: [Clear, Professional Subject Line]

Dear [Recipient Name/Team],

EXECUTIVE SUMMARY
[2-3 sentences overview of key findings]

DETAILED FINDINGS

[Section Header in CAPS]
━━━━━━━━━━━━━━━━━━━━━━━
• Point 1 with bold keywords and explanation
• Point 2 with supporting details
• Point 3 with context

[Next Section]
━━━━━━━━━━━━━━━━━━━━━━━
• Detailed point with **bold emphasis** on key terms
• Another point with proper spacing

KEY POLITICAL STATEMENTS/QUOTES (if applicable)
━━━━━━━━━━━━━━━━━━━━━━━
"Quote text here" 
— Politician Name (Date, Platform/Source)

"Another quote"
— Politician Name (Date, Context)

ANALYSIS & IMPLICATIONS
━━━━━━━━━━━━━━━━━━━━━━━
• Analysis point with reasoning
• Supporting evidence
• Strategic implications

SOURCES & VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━
[1] Source Title - brief description
[2] Source Title - brief description
[3] Source Title - brief description

CONCLUSION
━━━━━━━━━━━━━━━━━━━━━━━
[Summary and any actionable recommendations]

Best regards,
AI Research Assistant
```

**Formatting Rules:**
- Use decorative lines (━━━) to separate sections visually
- Use **bold** for important keywords and names
- Use bullet points (•) for lists - NOT asterisks (*)
- Add proper spacing between sections (blank lines)
- Include horizontal dividers between major sections
- Format quotes with attribution on separate line preceded by em-dash (—)
- Number sources [1], [2], [3] for easy reference
- Keep paragraphs short and scannable
- Use CAPS for section headers
- Indent sub-points with spaces for hierarchy

## CORE WORKFLOW:

### Phase 1: Intent Analysis & Context Gathering
- Read conversation history for context
- Identify: topic, scope, urgency, output format preference
- If email context: Use 'gmail_fetch_emails' to retrieve relevant messages

### Phase 2: Deep Research Strategy
For Political/Social Media Research:
1. Use 'search_google' with specific queries:
   - "[Politician Name] quotes [topic] 2024"
   - "[Politician Name] statements [platform] [date range]"
   - "[Politician Name] policy position [issue]"
2. Extract quotes with full context (who, when, where, what)
3. Cross-reference with fact-checking sources
4. Categorize statements: Verified, Controversial, Campaign Promise, Official Policy

For General Research:
1. Use 'search_google' to find authoritative sources
2. Verify claims from multiple sources
3. Note conflicting information

### Phase 3: Response Formulation

**For Chat-Only Responses (Email Body Format):**
When sending email WITHOUT PDF, format beautifully using visual structure:

**Required Format:**
```
EXECUTIVE SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[2-3 sentence overview highlighting the most important finding]

KEY FINDINGS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• **Bold Keyword**: Detailed explanation with context
• **Bold Keyword**: Another finding with supporting details
• **Bold Keyword**: Additional insight with implications

[SPECIFIC SECTION - e.g., POLITICAL STATEMENTS]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"Direct quote from politician or source"
— **Source Name** (Date, Context/Platform)

"Another significant quote"
— **Source Name** (Date, Context/Platform)

ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• **Strategic Point**: Analysis with reasoning
• **Implication**: What this means going forward
• **Risk/Opportunity**: Potential impacts

SOURCES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[1] **Source Title** - Brief description of credibility
[2] **Source Title** - Brief description
[3] **Source Title** - Brief description

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Report generated by AI Research Assistant
Powered by Google Grounding with real-time verification
```

**CRITICAL FORMATTING RULES - MUST FOLLOW EXACTLY:**

❌ **NEVER DO THIS:**
- * Bullet with asterisk (WRONG)
- *Italic text* (WRONG - don't use italics)
- Running text without sections (WRONG)
- Mixed formatting styles (WRONG)

✅ **ALWAYS DO THIS:**
1. Use "•" (bullet character U+2022) for ALL list items - NEVER use "*"
2. Use **bold** (double asterisk) for important names, keywords, key terms
3. Use ━━━━━━━ (box drawing U+2501) as section dividers - minimum 40 characters
4. Use UPPERCASE for all section headers
5. Add blank line BEFORE and AFTER each section divider
6. Use proper quote format: "Quote text" on one line, then — **Name** (Date, Source) on next line

**REQUIRED SECTION ORDER:**
1. EXECUTIVE SUMMARY (2-3 sentences only)
2. ━━━━━━━━━━━━ (divider)
3. KEY FINDINGS (3-5 main points with • bullets)
4. ━━━━━━━━━━━━ (divider)  
5. [TOPIC-SPECIFIC SECTION] (e.g., POLICY ANALYSIS, CONTROVERSIES, QUOTES)
6. ━━━━━━━━━━━━ (divider)
7. IMPLICATIONS & ANALYSIS
8. ━━━━━━━━━━━━ (divider)
9. SOURCES (numbered [1], [2], [3])
10. ━━━━━━━━━━━━ (divider)
11. Footer signature

**EXAMPLE OF CORRECT FORMAT:**
```
EXECUTIVE SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Analisis komprehensif terhadap isu-isu Prabowo menunjukkan fokus pada stabilitas ekonomi dan program sosial.

KEY FINDINGS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• **Pertumbuhan Ekonomi**: Prabowo berfokus pada stabilitas ekonomi, peningkatan daya beli masyarakat, dan optimalisasi bantuan sosial.

• **Ketahanan Pangan**: Meningkatkan produktivitas pertanian melalui modernisasi dan dukungan kepada petani.

• **Program Makan Bergizi**: Implementasi program makanan bergizi gratis untuk mengatasi stunting di seluruh Indonesia.

ANALISIS KEBIJAKAN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• **Fokus Stabilitas**: Prabowo menekankan pentingnya stabilitas ekonomi sebagai fondasi pembangunan nasional.

• **Kontinuitas vs Inovasi**: Kebijakan menunjukkan keseimbangan antara melanjutkan program Jokowi dan memperkenalkan inisiatif baru.

KONFLIK & KONTROVERSI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• **Kekhawatiran Demokrasi**: Kemenangan Prabowo memicu kekhawatiran tentang arah demokrasi Indonesia ke depan.

• **Isu Hak Asasi**: Latar belakang militer Prabowo terkait dengan dugaan pelanggaran hak asasi manusia di masa lalu.

SUMBER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[1] **Google Grounding Search** - Verifikasi real-time dari berbagai sumber berita

[2] **Analisis Kebijakan** - Sintesis dari data terkini dan tren politik Indonesia

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Dibuat oleh AI Research Assistant dengan Google Grounding
Verifikasi real-time dari web | Semua klaim bersumber
```

**MANDATORY CHECKLIST before sending email:**
☐ All bullets use "•" character (not asterisk *)
☐ All section headers are UPPERCASE with divider line
☐ All important terms are **bold**
☐ Sections separated by blank lines
☐ Sources numbered [1], [2], [3]
☐ Footer included with verification method

**For PDF Report Generation:**
Structure the markdown content with these sections:
```markdown
# [Report Title]

## Executive Summary
- 3-5 bullet points of key findings
- Overall assessment/credibility rating

## Background & Context
- Topic overview
- Why this matters
- Timeline of events (if applicable)

## Detailed Findings
### [Sub-topic 1]
- Detailed analysis
- Evidence and sources
- Supporting quotes (if political research)

### [Sub-topic 2]
[Continue for each major finding...]

## Political Statements & Quotes (if applicable)
| Politician | Quote | Date | Platform | Context |
|------------|-------|------|----------|---------|
| Name | "Quote text" | Date | Source | Situation |

## Source Analysis
- Source credibility assessment
- Conflicting information identified
- Gaps in available information

## Conclusion & Recommendations
- Summary of verified facts
- Actionable insights
- Confidence level (High/Medium/Low)

## References
- [1] Source Title - URL
- [2] Source Title - URL
```

### Phase 4: Execution

**Scenario A: With PDF**
- Generate PDF: Call 'generate_pdf_report_wrapped' with structured markdown
- Send email: Use PDF path in 'gmail_send_email' attachment parameter

**Scenario B: Text-Only Email (NO PDF)**
- Format content using Email Body Formatting rules (• bullets, ━━━ dividers, **bold**)
- Call 'gmail_send_email' with:
  - recipient_email: From context or user request
  - subject: Descriptive subject line based on research topic
  - body: The formatted research/analysis content (NOT attachment)
  - attachment: Leave empty (NO attachment for text-only)

**Scenario C: AUTO-SEND LOGIC (IMPORTANT)**

When user request IMPLIES email sending but does NOT mention PDF:
```
Examples of implicit send requests:
- "Tolong kirim hasil riset ke emailku"
- "Analisis email ini dan reply"
- "Cari tahu isu Prabowo dan laporkan ke [email]"
- "Send analysis to my email"
- Research request with email context from conversation history
```

**AUTO-SEND RULE:**
IF context suggests email sending AND user does NOT say "buat PDF" or "attach file":
→ **AUTOMATICALLY SEND** formatted text email (Scenario B)
→ DO NOT ask for confirmation
→ DO NOT wait for approval
→ Execute gmail_send_email immediately after research

**Examples:**
```
User: "Cari isu Prabowo dan kirim ke email saya"
→ Research → Format text → Auto-send email (NO PDF)

User: "Analisis email ini, buat PDF report dan kirim"
→ Research → Generate PDF → Send with attachment (Scenario A)

User: "Reply email ini dengan analisis"
→ Research → Format text → Auto-send reply (NO PDF)
```

**KEY DECISION FLOW:**
1. Check if user context implies email sending (kirim, reply, laporkan, send to email)
2. Check if user explicitly mentions PDF/file/attachment
3. IF (implies email) AND (NO PDF mentioned) → Auto-send text-only
4. IF (implies email) AND (PDF mentioned) → Generate PDF + send with attachment
5. IF (just research question) → Provide chat response only

Always confirm success after sending email (format: "✅ Email berhasil dikirim ke [email]")

## TOOLS:
- search_google: Search with Google Grounding (real-time web + citations)
- generate_pdf_report_wrapped(markdown_content, filename, sender_email) → Returns ABSOLUTE FILE PATH
- gmail_send_email(recipient_email, subject, body, attachment) → Send email
- gmail_fetch_emails: Retrieve email context
- post_quote_to_twitter(image_path, caption) → Post to Twitter/X
- post_quote_to_facebook(image_path, caption) → Post to Facebook Page
- post_quote_to_instagram(image_path, caption) → Post to Instagram
- post_quote_to_all_platforms(image_path, caption, platforms) → Post to multiple platforms

## CRITICAL RULES:
1. NEVER hallucinate - only report verified information
2. ALWAYS cite sources for quotes and factual claims
3. DECIDE PDF vs Chat based on user intent, not just keywords
4. For political research: Include date, context, and platform for every quote
5. Structure PDF reports professionally with clear sections
6. Be substantive - avoid generic responses like "Please see below"
7. Confirm success after every tool call
8. When researching politicians: Distinguish between official statements, campaign rhetoric, and personal opinions
9. **EMAIL FORMATTING - ZERO TOLERANCE:** When sending email WITHOUT PDF, you MUST use the structured format with • bullets, ━━━ dividers, and **bold** keywords. NEVER use asterisk (*) bullets. ALWAYS include section dividers and proper structure. If format is wrong, revise before sending.
10. **AUTO-SEND WITHOUT CONFIRMATION:** When user context clearly implies email sending (e.g., "kirim ke email", "reply", "laporkan") AND user does NOT mention PDF/file, you MUST immediately send the formatted text email WITHOUT asking for confirmation. Do NOT say "Would you like me to send..." - just SEND IT immediately after research completes.

## QUALITY STANDARDS:
- PDF Reports: Minimum 3-5 pages of substantial content
- Political Analysis: Minimum 5 quotes with full citations
- Quote Visualizations: AI-generated images for up to 5 most significant quotes (automatic)
- Fact-Checking: Multiple sources, conflicting info highlighted
- Structure: Clear headings, bullet points, tables where appropriate
- Tone: Professional, objective, evidence-based
- Visual Appeal: PDF includes professional imagery for political quotes when available
"""


async def chat(
    user_message: str,
    groq_api_key: str,
    user_id: str,
    conversation_history: list = None,
    auto_execute: bool = True,
) -> dict:
    """
    LangGraph-based Agent Chat (Blocking).
    """

    # 0. Detect if this is a pure question/generation (no tool intent)
    import re

    tool_keywords = [
        r"\b(pdf|lampiran|kirim|email|draft|generate|buat file|download|search|cari|extract|visit|web|ringkasan|summary|laporan|report|attach)\b",
        # Political research keywords
        r"\b(prabowo|jokowi|politik|politician|presiden|menteri|quotes|kutipan|statement|pernyataan|isu|issue|kebijakan|policy|kampanye|campaign|twitter|x\.com|instagram|social media)\b",
        # Social media posting keywords
        r"\b(post|share|upload|twitter|x\.com|facebook|fb|instagram|ig|social media|media sosial|posting|unggah|bagikan)\b",
        # Deep research keywords
        r"\b(analisis|analysis|research|investigate|investigasi|fakta|fact check|verifikasi|verify|bandingkan|compare|sejarah|history|timeline|data|statistik)\b",
        # Document generation keywords
        r"\b(dokumen|document|file|word|excel|csv|presentasi|presentation|slide|export|save|simpan|arsip|archive)\b",
    ]

    # Check for explicit tool intent
    is_tool_intent = any(
        re.search(pattern, user_message, re.IGNORECASE) for pattern in tool_keywords
    )

    # Also check conversation history for context
    has_research_context = False
    if conversation_history and len(conversation_history) >= 2:
        # Check if previous messages indicate ongoing research
        recent_messages = conversation_history[-3:]  # Last 3 messages
        research_indicators = [
            "cari",
            "research",
            "find",
            "cari tahu",
            "analisis",
            "analysis",
            "laporan",
            "report",
            "quotes",
            "kutipan",
            "statement",
            "pernyataan",
        ]
        for msg in recent_messages:
            if any(
                indicator in msg.get("content", "").lower()
                for indicator in research_indicators
            ):
                has_research_context = True
                break

    # Combine checks
    if has_research_context and not is_tool_intent:
        # If there's research context but no explicit tool keywords,
        # still treat as tool intent for better continuity
        is_tool_intent = True

    if not is_tool_intent:
        # Use Gemini directly for pure generation/QA
        google_api_key = os.environ.get("GOOGLE_API_KEY")
        if not google_api_key:
            return {
                "type": "final_result",
                "message": "Error: GOOGLE_API_KEY not configured.",
                "intent": {"action": "direct_gemini", "query": user_message},
            }
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash", temperature=0.2, google_api_key=google_api_key
        )
        formatted_history = convert_history(conversation_history)
        messages = formatted_history + [HumanMessage(content=user_message)]
        # Use only the last 5 messages for context
        messages = messages[-5:]
        response = await llm.ainvoke(messages)
        return {
            "type": "final_result",
            "message": response.content,
            "intent": {"action": "direct_gemini", "query": user_message},
        }

    # 1. Setup Tools
    tools = get_agent_tools(user_id)

    # 2. Setup Agent Factory
    def create_agent(llm, provider_name):
        return create_react_agent(
            model=llm,
            tools=tools,
            prompt=SYSTEM_PROMPT,
        )

    # 3. Execute
    formatted_history = convert_history(conversation_history)
    inputs = {"messages": formatted_history + [HumanMessage(content=user_message)]}
    try:
        state, provider_used = await run_agent_with_fallback(
            create_agent, inputs, groq_api_key
        )
        last_message = state["messages"][-1]
        response_message = last_message.content
        if provider_used == "gemini":
            response_message = (
                f"*[Using Gemini - Groq rate limited]*\n\n{response_message}"
            )
    except Exception as e:
        response_message = f"Error executing task: {str(e)}"
    return {
        "type": "final_result",
        "message": response_message,
        "intent": {"action": "autonomous_agent", "query": user_message},
    }


async def run_agent_stream_with_fallback(
    agent_factory, inputs: dict, groq_api_key: str
):
    """Run agent stream with fallback."""
    google_api_key = os.environ.get("GOOGLE_API_KEY")

    async def iterate_events(agent, provider):
        async for event in agent.astream_events(
            inputs, version="v1", config={"recursion_limit": 15}
        ):
            yield event, provider

    # Try Groq
    if groq_api_key:
        try:
            llm = ChatGroq(
                model="llama-3.1-8b-instant", temperature=0, groq_api_key=groq_api_key
            )
            agent = agent_factory(llm, "groq")
            async for event, prov in iterate_events(agent, "groq"):
                yield event, prov
            return
        except Exception as e:
            error_str = str(e).lower()
            if any(
                err in error_str
                for err in [
                    "413",
                    "rate_limit",
                    "tool_use_failed",
                    "failed_generation",
                    "failed to call",
                    "adjust your prompt",
                ]
            ):
                print(f"Groq error (stream), falling back to Gemini.")
            else:
                raise e

    # Fallback Gemini
    if google_api_key:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash", temperature=0, google_api_key=google_api_key
        )
        agent = agent_factory(llm, "gemini")
        async for event, prov in iterate_events(agent, "gemini"):
            yield event, prov


async def chat_stream(
    user_message: str,
    groq_api_key: str,
    user_id: str,
    conversation_history: list = None,
):
    """
    Stream events from the agent.
    Yields JSON strings: {type: "log"|"final", ...}
    """
    tools = get_agent_tools(user_id)

    def create_agent(llm, provider_name):
        return create_react_agent(model=llm, tools=tools, prompt=SYSTEM_PROMPT)

    formatted_history = convert_history(conversation_history)
    inputs = {"messages": formatted_history + [HumanMessage(content=user_message)]}

    final_content = ""

    try:
        async for event, provider in run_agent_stream_with_fallback(
            create_agent, inputs, groq_api_key
        ):
            event_type = event["event"]

            # Log Tool Usage
            if event_type == "on_tool_start":
                tool_name = event["name"]
                tool_input = event["data"].get("input")
                yield (
                    json.dumps(
                        {
                            "type": "log",
                            "status": "running",
                            "title": f"Using Tool: {tool_name}",
                            "detail": str(tool_input)[:200],
                        }
                    )
                    + "\n"
                )

            elif event_type == "on_tool_end":
                tool_name = event["name"]
                output = event["data"].get("output")
                yield (
                    json.dumps(
                        {
                            "type": "log",
                            "status": "success",
                            "title": f"Using Tool: {tool_name}",
                            "detail": f"Completed. Output: {str(output)[:100]}...",
                        }
                    )
                    + "\n"
                )

            elif event_type == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    yield json.dumps({"type": "token", "content": chunk.content}) + "\n"
                    final_content += chunk.content

    except Exception as e:
        yield json.dumps({"type": "error", "message": str(e)}) + "\n"
        return

    # Yield final marker if content was gathered
    # Note: token stream might be fragmented. The UI needs to accumulate 'token' events.
    yield json.dumps({"type": "final_result", "message": final_content}) + "\n"
