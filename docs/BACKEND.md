# Gmail Agent - Backend Documentation

Detailed documentation for the Gmail Agent Python backend.

---

## Overview

The Gmail Agent backend is a **FastAPI** application that provides:
- REST API endpoints for Gmail operations
- AI-powered chat interface using Groq LLM
- Gmail integration via Composio SDK

---

## File Reference

### 📁 Project Structure

```
gmail-agent/
├── server/
│   ├── __init__.py         # Package marker
│   ├── api.py              # FastAPI app & routes
│   ├── actions.py          # Gmail tool functions
│   ├── auth.py             # OAuth authentication
│   ├── chatbot.py          # AI chat logic
│   ├── dependencies.py     # Dependency injection
│   └── models.py           # Pydantic schemas
├── .env                    # Environment variables
├── .env.example            # Example env file
├── Makefile                # Build commands
├── requirements.txt        # Python packages
└── README.md               # Quick guide
```

---

## Core Files Explained

### 1️⃣ `server/api.py` - API Routes

**Role:** Defines all HTTP endpoints using FastAPI.

#### Application Factory

```python
def create_app() -> FastAPI:
    """Creates configured FastAPI application"""
    app = FastAPI(title="Gmail Agent API", version="2.0.0")
    
    # Enable CORS for frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Define routes here...
    return app

app = create_app()  # Module-level instance for uvicorn
```

#### Route Categories

**Connection Management:**
```python
@app.post("/connection/exists")
def connection_exists(composio_client: ComposioClient):
    """Check if user has active Gmail connection"""

@app.post("/connection/create")
def _create_connection(request: CreateConnectionRequest, ...):
    """Initiate new OAuth connection"""

@app.post("/connection/status")
def _connection_status(request: ConnectionStatusRequest, ...):
    """Get connection state"""
```

**Email Actions:**
```python
@app.post("/actions/send_email")
def _send_email(request: SendEmailRequest, ...):
    """Send email to recipient"""

@app.post("/actions/fetch_emails")
def _fetch_emails(request: FetchEmailsRequest, ...):
    """Retrieve recent emails"""

@app.post("/actions/create_draft")
def _create_draft(request: CreateDraftRequest, ...):
    """Create email draft"""
```

**AI Chat:**
```python
@app.post("/chat")
async def _chat(request: ChatRequest, ...):
    """AI chatbot endpoint - parses intent and executes actions"""
```

---

### 2️⃣ `server/actions.py` - Gmail Operations

**Role:** Wrapper functions for Composio Gmail tools.

#### Base Executor

```python
def execute_tool(composio_client, user_id, tool_slug, arguments):
    """
    Generic tool executor for Composio
    
    Args:
        composio_client: Composio SDK instance
        user_id: User identifier for the connection
        tool_slug: Composio tool identifier (e.g., GMAIL_SEND_EMAIL)
        arguments: Dict of parameters for the tool
    
    Returns:
        Dict with tool execution result
    """
    return composio_client.tools.execute(
        slug=tool_slug,
        arguments=arguments,
        user_id=user_id,
        dangerously_skip_version_check=True
    )
```

#### Available Tools

| Function | Composio Tool | Parameters |
|----------|--------------|------------|
| `send_email()` | `GMAIL_SEND_EMAIL` | `recipient_email`, `subject`, `body` |
| `fetch_emails()` | `GMAIL_FETCH_EMAILS` | `limit` |
| `create_draft()` | `GMAIL_CREATE_EMAIL_DRAFT` | `recipient_email`, `subject`, `body` |

---

### 3️⃣ `server/auth.py` - Authentication

**Role:** Manages Composio OAuth connections for Gmail.

#### Auth Configuration

```python
def fetch_auth_config(composio_client):
    """Find existing Gmail auth config in Composio"""
    auth_configs = composio_client.auth_configs.list()
    for auth_config in auth_configs.items:
        if auth_config.toolkit == "GMAIL":
            return auth_config
    return None

def create_auth_config(composio_client):
    """Create new Gmail OAuth config with custom credentials"""
    return composio_client.auth_configs.create(
        toolkit="GMAIL",
        options={
            "name": "default_gmail_auth_config",
            "type": "use_custom_auth",
            "auth_scheme": "OAUTH2",
            "credentials": {
                "client_id": os.getenv("GMAIL_CLIENT_ID"),
                "client_secret": os.getenv("GMAIL_CLIENT_SECRET"),
            },
        },
    )
```

#### Connection Management

```python
def create_connection(composio_client, user_id, auth_config_id=None):
    """
    Initiate OAuth connection flow
    
    Returns:
        Connection object with:
        - id: Connection identifier
        - redirect_url: URL for user to complete OAuth
    """

def check_connected_account_exists(composio_client, user_id):
    """Check if user has ACTIVE Gmail connection"""
    connected_accounts = composio_client.connected_accounts.list(
        user_ids=[user_id],
        toolkit_slugs=["GMAIL"],
    )
    for account in connected_accounts.items:
        if account.status == "ACTIVE":
            return True
    return False

def get_connection_status(composio_client, connection_id):
    """Get current status of specific connection"""
```

---

### 4️⃣ `server/chatbot.py` - AI Logic

**Role:** Natural language processing with Groq LLM.

#### System Prompt

The AI is configured with this prompt:

```
You are an email assistant. Parse user messages and determine the desired action.

Available actions:
- send_email: Send email (needs: recipient_email, subject, body)
- create_draft: Create email draft (needs: recipient_email, subject, body)  
- fetch_emails: Get recent emails (optional: limit)

If user doesn't provide recipient email, ask first.
Create professional subject and body.

Respond in JSON format.
```

#### Intent Parsing

```python
async def parse_intent_with_groq(user_message, groq_api_key, conversation_history):
    """
    Use Llama 3.3 70B to parse user message into structured intent
    
    Returns JSON like:
    {
        "action": "send_email",
        "recipient_email": "john@example.com",
        "subject": "Meeting Tomorrow",
        "body": "Hi John...",
        "need_more_info": false
    }
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {groq_api_key}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "temperature": 0.3,
                "response_format": {"type": "json_object"}
            }
        )
```

#### Chat Flow

```python
async def chat(user_message, groq_api_key, user_id, conversation_history, auto_execute):
    """
    Main chat function
    
    Flow:
    1. Parse user intent with LLM
    2. If need_more_info, return question
    3. If auto_execute, perform action
    4. Return result
    """
```

**Response Types:**

| Type | Condition | Contains |
|------|-----------|----------|
| `question` | `need_more_info=true` | Question to ask user |
| `action_result` | `auto_execute=true` | Action + result |
| `intent_parsed` | `auto_execute=false` | Parsed intent only |

---

### 5️⃣ `server/models.py` - Data Models

**Role:** Pydantic models for request/response validation.

#### Request Models

```python
class SendEmailRequest(BaseModel):
    user_id: str = Field(default="default")
    recipient_email: str
    subject: str
    body: str

class ChatRequest(BaseModel):
    message: str
    user_id: str = Field(default="default")
    auto_execute: bool = Field(default=True)
    conversation_history: Optional[List[dict]] = None
```

#### Response Models

```python
class ToolExecutionResponse(BaseModel):
    successful: bool
    data: Optional[Any] = None
    error: Optional[str] = None
```

---

### 6️⃣ `server/dependencies.py` - Dependency Injection

**Role:** Singleton Composio client provider.

```python
_composio_client: Composio | None = None

def provide_composio_client() -> Composio:
    global _composio_client
    if _composio_client is None:
        api_key = os.getenv("COMPOSIO_API_KEY")
        _composio_client = Composio(api_key=api_key)
    return _composio_client

# FastAPI dependency annotation
ComposioClient = Annotated[Composio, Depends(provide_composio_client)]
```

**Benefits:**
- Single instance across all requests
- Automatic injection in route handlers
- Easy testing/mocking

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `COMPOSIO_API_KEY` | ✅ Yes | Composio platform API key |
| `GROQ_API_KEY` | ✅ Yes | Groq LLM API key |
| `GMAIL_CLIENT_ID` | ❌ Optional | Custom Gmail OAuth client ID |
| `GMAIL_CLIENT_SECRET` | ❌ Optional | Custom Gmail OAuth client secret |

---

## Running the Server

```bash
# Development (with auto-reload)
make dev
# or
uvicorn server.api:app --reload --port 8000

# Production
make run
# or
uvicorn server.api:app --host 0.0.0.0 --port 8000
```

**Swagger Docs:** http://localhost:8000/docs

---

## Error Handling

The API uses standard HTTP status codes:

| Code | Meaning |
|------|---------|
| 200 | Success |
| 404 | User not found / No connection |
| 500 | Internal error (API key missing, etc.) |

Error response format:
```json
{
    "detail": "Error message here"
}
```
