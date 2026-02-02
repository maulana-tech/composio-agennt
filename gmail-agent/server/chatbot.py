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
from tavily import TavilyClient
from composio_langchain import LangchainProvider
from composio import Composio

from server.tools.pdf_generator import generate_pdf_report


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


def create_tavily_tools():
    """Create Tavily tools for search, extract, crawl, and map."""

    tavily_api_key = os.environ.get("TAVILY_API_KEY")
    tavily_client = TavilyClient(api_key=tavily_api_key)

    @tool
    def tavily_search(query: str, max_results: int = 5) -> str:
        """
        Search the web using Tavily Search API.

        Args:
            query: The search query (be specific and detailed)
            max_results: Maximum number of results to return (1-10)

        Returns:
            Search results with titles, URLs, content snippets, and an AI-generated answer
        """
        try:
            result = tavily_client.search(
                query=query,
                search_depth="advanced",
                max_results=min(max_results, 10),
                include_answer=True,
            )

            output = []
            if result.get("answer"):
                output.append(f"**Summary:** {result['answer']}\n")

            output.append(f"**Found {len(result.get('results', []))} results:**\n")

            for i, r in enumerate(result.get("results", []), 1):
                title = r.get("title", "No title")
                url = r.get("url", "")
                content = r.get("content", "No content")[:400]
                # Format as clickable markdown link
                output.append(f"\n{i}. [{title}]({url})")
                output.append(f"   {content}...")

            return "\n".join(output)
        except Exception as e:
            return f"Search error: {str(e)}"

    @tool
    def tavily_extract(urls: str) -> str:
        """
        Extract full content from one or more URLs.

        Args:
            urls: Comma-separated list of URLs to extract content from (e.g., "https://example.com,https://other.com")

        Returns:
            Extracted raw content from the URLs in markdown format
        """
        try:
            url_list = [u.strip() for u in urls.split(",") if u.strip()]
            if not url_list:
                return "Error: No valid URLs provided"

            result = tavily_client.extract(urls=url_list)

            output = []

            for r in result.get("results", []):
                output.append(f"\n## Content from: {r.get('url', 'Unknown URL')}\n")
                content = r.get("raw_content", "No content extracted")
                if len(content) > 3000:
                    content = content[:3000] + "...[truncated]"
                output.append(content)

            if result.get("failed_results"):
                output.append("\n**Failed extractions:**")
                for f in result["failed_results"]:
                    output.append(f"- {f.get('url')}: {f.get('error')}")

            return "\n".join(output)
        except Exception as e:
            return f"Extract error: {str(e)}"

    @tool
    def tavily_crawl(url: str, limit: int = 10) -> str:
        """
        Crawl a website starting from a base URL to extract content from multiple pages.

        Args:
            url: The root URL to begin the crawl (e.g., "https://docs.example.com")
            limit: Maximum number of pages to crawl (1-20)

        Returns:
            Crawled content from discovered pages
        """
        try:
            result = tavily_client.crawl(
                url=url, max_depth=2, max_breadth=10, limit=min(limit, 20)
            )

            output = [f"**Crawl Results for:** {result.get('base_url', url)}\n"]
            output.append(f"**Pages crawled:** {len(result.get('results', []))}\n")

            for i, r in enumerate(result.get("results", []), 1):
                output.append(f"\n### {i}. {r.get('url', 'Unknown URL')}")
                content = r.get("raw_content", "No content")
                if len(content) > 1000:
                    content = content[:1000] + "...[truncated]"
                output.append(content)

            return "\n".join(output)
        except Exception as e:
            return f"Crawl error: {str(e)}"

    @tool
    def tavily_map(url: str, limit: int = 30) -> str:
        """
        Discover all URLs from a website (like a sitemap).

        Args:
            url: The root URL to begin mapping (e.g., "https://example.com")
            limit: Maximum number of URLs to discover (1-50)

        Returns:
            List of discovered URLs from the website
        """
        try:
            result = tavily_client.map(
                url=url, max_depth=2, max_breadth=20, limit=min(limit, 50)
            )

            urls = result.get("results", [])
            output = [f"**Sitemap for:** {result.get('base_url', url)}\n"]
            output.append(f"**Total URLs discovered:** {len(urls)}\n")
            output.append("**URLs:**")

            for i, discovered_url in enumerate(urls, 1):
                output.append(f"{i}. {discovered_url}")

            return "\n".join(output)
        except Exception as e:
            return f"Map error: {str(e)}"

    return [tavily_search, tavily_extract, tavily_crawl, tavily_map]


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
    tavily_tools = create_tavily_tools()
    search_tools = create_grounding_tools()

    # PDF Generator
    @tool
    def generate_pdf_report_wrapped(
        markdown_content: str,
        filename: str = "report.pdf",
        sender_email: str = "AI Assistant",
    ) -> str:
        """
        Generate a professional PDF report from Markdown content.

        Args:
            markdown_content: The markdown text to include in the report.
            filename: The name of the PDF file to generate.
            sender_email: The email address to derive a dynamic logo from (e.g., 'user@gmail.com' -> 'user' logo).

        Returns:
            The ABSOLUTE FILE PATH that you MUST use for gmail_send_email attachment parameter.
        """
        if not filename:
            filename = "report.pdf"
        print(
            f"DEBUG: Executing PDF generator for {filename} with sender {sender_email}"
        )
        path = generate_pdf_report.invoke(
            {
                "markdown_content": markdown_content,
                "filename": filename,
                "sender_email": sender_email,
            }
        )
        print(f"DEBUG: PDF generated at {path}")
        return path

    return search_tools + [generate_pdf_report_wrapped] + gmail_tools


SYSTEM_PROMPT = """
You are an expert Research and Email Assistant specializing in political analysis, fact-checking, and comprehensive report generation. Your goal is to provide high-quality, verified, and well-structured information.

## SPECIALIZED CAPABILITIES:

### 1. Political Quotes & Social Media Research
- Find and extract quotes from politicians on specific topics/issues
- Search for statements from political figures on social media platforms (Twitter/X, Facebook, Instagram, TikTok)
- Categorize quotes by: official statements, campaign promises, policy positions, controversial remarks
- Always cite the source: date, platform, context, and link if available
- Example searches: "Prabowo quotes on defense policy 2024", "statements by Jokowi on economic policy Twitter"

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

**NO PDF NEEDED (chat response only):**
- Quick questions or brief answers
- Simple information lookup (single fact, definition)
- Casual conversation or clarification
- User does NOT mention file, document, or email sending
- When user just wants to "check", "find", "search" without format specification

**WHEN UNCERTAIN:** Ask user: "Apakah Anda ingin saya membuat laporan PDF yang detail, atau cukup jawaban di chat saja?"

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
- If PDF needed: Call 'generate_pdf_report_wrapped' with structured markdown
- If email needed: Use PDF path in 'gmail_send_email'
- Always confirm success/failure explicitly

## TOOLS:
- search_google: Search with Google Grounding (real-time web + citations)
- generate_pdf_report_wrapped(markdown_content, filename, sender_email) → Returns ABSOLUTE FILE PATH
- gmail_send_email(recipient_email, subject, body, attachment) → Send email
- gmail_fetch_emails: Retrieve email context

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

## QUALITY STANDARDS:
- PDF Reports: Minimum 3-5 pages of substantial content
- Political Analysis: Minimum 5 quotes with full citations
- Fact-Checking: Multiple sources, conflicting info highlighted
- Structure: Clear headings, bullet points, tables where appropriate
- Tone: Professional, objective, evidence-based
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
