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
                model="llama-3.1-8b-instant",
                temperature=0,
                groq_api_key=groq_api_key
            )
            return llm, "groq"
        except Exception as e:
            print(f"Groq init failed: {e}")
    
    # Fallback: Google Gemini
    if google_api_key:
        try:
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash",
                temperature=0,
                google_api_key=google_api_key
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
                model="llama-3.1-8b-instant",
                temperature=0,
                groq_api_key=groq_api_key
            )
            agent = agent_factory(llm, "groq")
            state = await agent.ainvoke(inputs)
            return state, "groq"
        except Exception as e:
            error_str = str(e)
            # Check if it's a rate limit error (413 or rate_limit_exceeded)
            if "413" in error_str or "rate_limit" in error_str.lower() or "tokens" in error_str.lower():
                print(f"Groq rate limit hit, falling back to Gemini: {e}")
            else:
                raise e
    
    # Fallback to Gemini
    if google_api_key:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            temperature=0,
            google_api_key=google_api_key
        )
        agent = agent_factory(llm, "gemini")
        state = await agent.ainvoke(inputs)
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
                include_answer=True
            )
            
            output = []
            if result.get("answer"):
                output.append(f"**Answer:** {result['answer']}\n")
            
            output.append(f"**Found {len(result.get('results', []))} results:**\n")
            
            for i, r in enumerate(result.get("results", []), 1):
                output.append(f"\n{i}. **{r.get('title', 'No title')}**")
                output.append(f"   URL: {r.get('url', 'N/A')}")
                output.append(f"   {r.get('content', 'No content')[:500]}...")
                
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
                url=url,
                max_depth=2,
                max_breadth=10,
                limit=min(limit, 20)
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
                url=url,
                max_depth=2,
                max_breadth=20,
                limit=min(limit, 50)
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


def create_serper_tools():
    """Create Serper tools for search and visiting webpages."""
    
    serper_api_key = os.environ.get("SERPER_API_KEY")
    
    @tool
    def search_google(query: str) -> str:
        """
        Search Google using Serper API.
        
        Args:
            query: The search query.
            
        Returns:
            Search results with titles, links, and snippets.
        """
        if not serper_api_key:
            return "Error: SERPER_API_KEY not found in environment variables."
            
        url = "https://google.serper.dev/search"
        payload = json.dumps({"q": query})
        headers = {
            'X-API-KEY': serper_api_key,
            'Content-Type': 'application/json'
        }
        
        try:
            with httpx.Client(timeout=10) as client:
                response = client.post(url, headers=headers, data=payload)
                response.raise_for_status()
                results = response.json()
            
            output = []
            if "organic" in results:
                for i, r in enumerate(results["organic"][:7], 1):
                    output.append(f"{i}. **{r.get('title')}**")
                    output.append(f"   Link: {r.get('link')}")
                    output.append(f"   Snippet: {r.get('snippet')}\n")
            else:
                output.append("No results found.")
                
            return "\n".join(output)
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
            
            with httpx.Client(timeout=30, follow_redirects=True, verify=False) as client:
                response = client.get(url, headers=headers)
                
                if response.status_code == 403:
                    return f"Error: Access forbidden (403) for {url}. Try another source."
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
                if "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in content_type or url.lower().endswith(".docx"):
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
            for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                element.decompose()
                
            text = soup.get_text(separator="\n", strip=True)
            
            # Clean up excessive newlines
            text = re.sub(r'\n{3,}', '\n\n', text)
            
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
            
            with httpx.Client(timeout=60, follow_redirects=True, verify=False) as client:
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
                        ext = ".pdf" # default assumption safest
                        content_type = response.headers.get("content-type", "").lower()
                        if "word" in content_type: ext = ".docx"
                        elif "pdf" in content_type: ext = ".pdf"
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
    def gmail_send_email(recipient_email: str, subject: str, body: str, attachment: str = "") -> str:
        """
        Send an email using Gmail.
        
        Args:
            recipient_email: The email address of the recipient
            subject: The subject line of the email
            body: The content/body of the email
            attachment: Absolute path to a file to attach (optional). MUST be a real path returned by other tools.
        """
        try:
            print(f"DEBUG: sending email to {recipient_email}")
            
            # Validation
            if not recipient_email or "@" not in str(recipient_email):
               return "ERROR: 'recipient_email' is missing or invalid. You MUST provide a valid email address."
            
            # Relaxed path check
            if attachment and "Place holder" in str(attachment):
               return "ERROR: You are using a placeholder path. You MUST call 'generate_pdf_report_wrapped' first."

            # Race condition fix: Wait for file to exist if it was just generated
            if attachment:
                import time
                import os
                
                # Check if it's a filename only, and resolve to abs path if needed
                if not os.path.isabs(attachment):
                     attachment = os.path.abspath(attachment)

                print(f"DEBUG: Checking for attachment: {attachment}")
                retries = 20 # 10 seconds (0.5s sleep)
                while retries > 0:
                    if os.path.exists(attachment):
                        print(f"DEBUG: Attachment found!")
                        break
                    print(f"DEBUG: Attachment not found yet, waiting... ({retries})")
                    time.sleep(0.5)
                    retries -= 1
                
                if not os.path.exists(attachment):
                     return f"ERROR: Attachment file not found at {attachment}. Did you generate it properly?"

            args = {
                "recipient_email": recipient_email,
                "subject": subject,
                "body": body,
                "is_html": True
            }
            if attachment:
                args["attachment"] = attachment
                
            return composio_client.tools.execute(slug="GMAIL_SEND_EMAIL", arguments=args, user_id=user_id, dangerously_skip_version_check=True)
        except Exception as e:
            return f"Error sending email: {str(e)}"

    @tool("GMAIL_CREATE_EMAIL_DRAFT")
    def gmail_create_draft(recipient_email: str, subject: str, body: str, attachment: str = "") -> str:
        """Create an email draft in Gmail without sending it."""
        try:
            args = {
                "recipient_email": recipient_email,
                "subject": subject,
                "body": body,
                "is_html": True
            }
            if attachment:
                args["attachment"] = attachment
            
            return composio_client.tools.execute(slug="GMAIL_CREATE_EMAIL_DRAFT", arguments=args, user_id=user_id, dangerously_skip_version_check=True)
        except Exception as e:
            return f"Error creating draft: {str(e)}"

    @tool("GMAIL_FETCH_EMAILS")
    def gmail_fetch_emails(limit: int = 5, query: str = "") -> str:
        """Fetch recent emails from Gmail."""
        try:
            args = {"limit": limit}
            if query:
                args["query"] = query
            return composio_client.tools.execute(slug="GMAIL_FETCH_EMAILS", arguments=args, user_id=user_id, dangerously_skip_version_check=True)
        except Exception as e:
            return f"Error fetching emails: {str(e)}"
            
    gmail_tools = [gmail_send_email, gmail_create_draft, gmail_fetch_emails]
    
    # Search Tools (Serper)
    search_tools = create_serper_tools()
    
    # PDF Generator
    @tool
    def generate_pdf_report_wrapped(markdown_content: str, filename: str) -> str:
        """
        Generate a professional PDF report from Markdown content.
        Returns the ABSOLUTE FILE PATH. You MUST use this path for GMAIL_SEND_EMAIL.
        """
        print(f"DEBUG: Executing PDF generator for {filename}")
        path = generate_pdf_report.invoke({"markdown_content": markdown_content, "filename": filename})
        print(f"DEBUG: PDF generated at {path}")
        return path
    
    return search_tools + [generate_pdf_report_wrapped] + gmail_tools

# System Prompt
SYSTEM_PROMPT = """You are a powerful Research & Email Robot with multiple capabilities.

AVAILABLE TOOLS:

1. **WEB SEARCH** (search_google):
   - Search Google for information, articles, or documents (UU/Perpu)
   - Inputs: query (string)
   - Returns top results with titles, links, and snippets

2. **VISIT WEBPAGE** (visit_webpage):
   - Read full content of a webpage (HTML/PDF/DOCX) to get details for the report
   - Inputs: url (string)
   - USE THIS when you want to summarize content into a NEW report.

3. **DOWNLOAD FILE** (download_file):
   - Download the actual file (PDF/DOCX) from a URL.
   - Inputs: url (string), filename (string - optional)
   - Returns: absolute file path
   - USE THIS when the user wants the ORIGINAL document sent to them.

4. **PDF GENERATION** (generate_pdf_report_wrapped):
   - Create professional PDF reports from markdown
   - Inputs: markdown_content (string), filename (string)
   - Returns absolute file path
   - USE THIS when you are summarizing findings (e.g. "Create a report about...").

6. **EMAIL** (gmail_send_email, gmail_create_draft, gmail_fetch_emails):
   - Send emails with attachments
   - Create drafts
   - Fetch recent emails

WORKFLOW EXAMPLES:

Research & Report (Summary):
1. search_google -> find relevant links
2. visit_webpage -> read content from HTML/PDF/DOCX
3. generate_pdf_report_wrapped -> create summary PDF
4. gmail_send_email -> send summary

Get Original Document:
1. search_google -> find document link (PDF/DOCX)
2. download_file -> save the file locally
3. gmail_send_email -> send the downloaded file as attachment

CRITICAL RULES:
- **NEVER** batch "generate_pdf_report" and "gmail_send_email" in the same turn.
- You MUST wait for 'generate_pdf_report_wrapped' to return the **Actual File Path** (it will look like `/Users/.../filename.pdf`).
- ONLY THEN call 'gmail_send_email' using that exact path.
- Do not guess the path.
- If 'visit_webpage' fails (403/404), do NOT create an empty report. Try visiting another link.
- To READ a PDF/DOCX content for a summary: use 'visit_webpage'.
- To SEND the PDF/DOCX file itself: use 'download_file'.
- For emails, always verify recipient_email has @
"""


async def chat(user_message: str, groq_api_key: str, user_id: str, conversation_history: list = None, auto_execute: bool = True) -> dict:
    """
    LangGraph-based Agent Chat (Blocking).
    """
    
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
        state, provider_used = await run_agent_with_fallback(create_agent, inputs, groq_api_key)
        
        last_message = state["messages"][-1]
        response_message = last_message.content
        if provider_used == "gemini":
            response_message = f"*[Using Gemini - Groq rate limited]*\n\n{response_message}"
        
    except Exception as e:
        response_message = f"Error executing task: {str(e)}"
        
    return {
        "type": "final_result",
        "message": response_message,
        "intent": {"action": "autonomous_agent", "query": user_message} 
    }
async def run_agent_stream_with_fallback(agent_factory, inputs: dict, groq_api_key: str):
    """Run agent stream with fallback."""
    google_api_key = os.environ.get("GOOGLE_API_KEY")

    async def iterate_events(agent, provider):
        async for event in agent.astream_events(inputs, version="v1"):
            yield event, provider

    # Try Groq
    if groq_api_key:
        try:
            llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0, groq_api_key=groq_api_key)
            agent = agent_factory(llm, "groq")
            async for event, prov in iterate_events(agent, "groq"):
                yield event, prov
            return
        except Exception as e:
             if "413" in str(e) or "rate_limit" in str(e).lower():
                 print(f"Groq rate limit (stream), falling back to Gemini.")
             else:
                 raise e
    
    # Fallback Gemini
    if google_api_key:
        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0, google_api_key=google_api_key)
        agent = agent_factory(llm, "gemini")
        async for event, prov in iterate_events(agent, "gemini"):
            yield event, prov

async def chat_stream(user_message: str, groq_api_key: str, user_id: str, conversation_history: list = None):
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
        async for event, provider in run_agent_stream_with_fallback(create_agent, inputs, groq_api_key):
            event_type = event["event"]
            
            # Log Tool Usage
            if event_type == "on_tool_start":
                tool_name = event["name"]
                tool_input = event["data"].get("input")
                yield json.dumps({
                    "type": "log", 
                    "status": "running", 
                    "title": f"Using Tool: {tool_name}", 
                    "detail": str(tool_input)[:200]
                }) + "\n"
            
            elif event_type == "on_tool_end":
                tool_name = event["name"]
                output = event["data"].get("output")
                yield json.dumps({
                    "type": "log",
                     "status": "success", 
                     "title": f"Using Tool: {tool_name}", 
                     "detail": f"Completed. Output: {str(output)[:100]}..."
                }) + "\n"
            
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
