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

from server.tools.pdf_agent_tool import get_pdf_tools
from server.tools.gmail_agent_tool import get_gmail_tools
from server.tools.linkedin_agent_tool import get_linkedin_tools
from server.prompts.main_prompt import SYSTEM_PROMPT
from server.tools.quote_agent_tool import get_quote_tools
from server.tools.strategy_diagram_agent import get_strategy_tools

from server.tools.gipa_agent_tool import get_gipa_tools
from server.tools.dossier_agent_tool import get_dossier_tools
from server.agents import create_default_registry, AgentRouter


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


# Initialize global agent registry and router
_agent_registry = create_default_registry()
_agent_router = AgentRouter(_agent_registry)


async def handle_gipa_request(
    user_message: str, conversation_history: List[Dict] = None, user_id: str = "default"
) -> dict:
    """
    Legacy wrapper - delegates to GIPAPluginAgent via AgentRouter.
    Kept for backward compatibility with existing callers.
    """
    from server.agents.base import AgentContext

    context = AgentContext(
        user_id=user_id,
        session_id="default",
        conversation_history=conversation_history,
    )
    gipa_agent = _agent_registry.get("gipa")
    if gipa_agent:
        response = await gipa_agent.handle(user_message, context)
        return response.to_dict()
    return {
        "type": "final_result",
        "message": "❌ GIPA agent not registered.",
        "intent": {"action": "gipa_error", "query": user_message},
    }


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
    
    # Search Tools
    serper_tools = create_serper_tools()
    search_tools = create_grounding_tools()

    # PDF Generator
    pdf_tools = get_pdf_tools()

    # Quote/Image Tools
    quote_tools = get_quote_tools()

    # Email Analysis Tools
    @tool
    async def analyze_email_claims(email_content: str, user_query: str = "") -> str:
        """
        Analyze an email for factual claims and conduct web research to verify them.
        Generates a comprehensive fact-check report and optional PDF.
        
        Args:
            email_content: The full content of the email to analyze.
            user_query: Specific instructions or questions about the email content.
            
        Returns:
            A summary of the analysis and the path to any generated PDF report.
        """
        from server.email_analysis_agents import MultiAgentEmailAnalyzer
        try:
            analyzer = MultiAgentEmailAnalyzer()
            results = await analyzer.analyze_and_report(
                email_content=email_content,
                user_query=user_query,
                generate_pdf=True
            )
            
            if results.get("success"):
                report = results.get("final_report", "")
                pdf_path = results.get("pdf_path", "")
                return f"Analysis completed successfully.\n\nSummary:\n{report[:500]}...\n\nPDF Report: {pdf_path}"
            else:
                return f"Analysis failed: {results.get('error', 'Unknown error')}"
        except Exception as e:
            return f"Error during email analysis: {str(e)}"

    # Social Media Tools
    from server.tools.social_media_agent_tool import get_social_media_tools
    social_media_tools = get_social_media_tools(user_id)

    # Strategy Diagram Tools
    strategy_tools = get_strategy_tools()

    # Dossier (Meeting Prep) Tools
    dossier_tools = _agent_registry.get("dossier")
    dossier_tool_list = dossier_tools.get_tools() if dossier_tools else []

    # Gmail Tools
    gmail_tools = get_gmail_tools(user_id)
    
    # LinkedIn Tools
    linkedin_tools = get_linkedin_tools(user_id)

    return (
        serper_tools
        + search_tools
        + pdf_tools
        + quote_tools
        + social_media_tools
        + strategy_tools
        + dossier_tool_list
        + gmail_tools
        + linkedin_tools
        + [analyze_email_claims]
    )




async def chat(
    user_message: str,
    groq_api_key: str,
    user_id: str,
    conversation_history: list = None,
    auto_execute: bool = True,
    session_id: str = "default",
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
        # GIPA / FOI / Government Information Access keywords
        r"\b(gipa|foi|freedom of information|government information|public access|information request|information access|right to information|rti)\b",
        # Dossier / Meeting Prep keywords
        r"\b(dossier|meeting prep|meeting preparation|briefing|background check|profile research|profil|person research|relationship map)\b",
        # LinkedIn posting/management keywords
        r"\b(linkedin|linked in|post on linkedin|linkedin post|linkedin article|linkedin connection|linkedin company|linkedin profile)\b",
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

    # AGENT ROUTER: Check if any specialized agent (GIPA, Dossier, etc.) should handle this
    router_result = await _agent_router.route(
        message=user_message,
        user_id=user_id,
        session_id=session_id,
        conversation_history=conversation_history,
    )
    if router_result:
        return router_result.to_dict()

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
    session_id: str = "default",
):
    """
    Stream events from the agent.
    Yields JSON strings: {type: "log"|"final", ...}
    """
    # AGENT ROUTER: Check if any specialized agent should handle this
    _router_result = await _agent_router.route(
        message=user_message,
        user_id=user_id,
        session_id=session_id,
        conversation_history=conversation_history,
    )
    if _router_result:
        yield json.dumps({
            "type": "log",
            "status": "running",
            "title": f"{_router_result.agent_name.upper()} Handler",
            "detail": f"Processing via {_router_result.agent_name} agent...",
        }) + "\n"
        yield json.dumps({"type": "token", "content": _router_result.message}) + "\n"
        yield json.dumps({"type": "final_result", "message": _router_result.message}) + "\n"
        return

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
