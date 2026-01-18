# 📚 Complete Gmail Chatbot Project Explanation

Comprehensive documentation in English to understand every file, why it's used, and how it works.

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Gmail Agent (Backend)](#gmail-agent-backend)
4. [Gmail Chatbot UI (Frontend)](#gmail-chatbot-ui-frontend)
5. [How the System Works](#how-the-system-works)

---

## 🎯 Project Overview

This project is an **AI-powered Gmail chatbot** that allows users to:

- ✉️ **Send emails** using natural language commands
- 📝 **Create email drafts** with AI-generated content
- 📬 **Fetch recent emails** from Gmail inbox

### Technologies Used

| Component | Technology | Reason for Use |
|----------|-----------|----------------|
| **Backend** | FastAPI (Python) | Modern, fast web framework for building REST APIs |
| **Frontend** | Next.js 16 (React) | Best React framework for modern web apps with SSR |
| **AI/LLM** | Groq (Llama 3.3 70B) | Ultra-fast and free LLM for parsing user intent |
| **Gmail Integration** | Composio SDK | Platform that simplifies OAuth and Gmail API integration |
| **Styling** | Tailwind CSS 4 | Utility-first CSS framework for fast, consistent styling |

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER (Browser)                               │
│                    localhost:3000                               │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          │ HTTP POST /chat
                          │ {"message": "Send email to..."}
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                  BACKEND (FastAPI)                              │
│                  localhost:8000                                 │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   api.py     │  │  chatbot.py  │  │  actions.py  │          │
│  │  (Routing)   │─▶│  (AI Logic)  │─▶│  (Gmail)     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────┬───────────────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
┌─────────────────────┐      ┌─────────────────────┐
│     Groq API        │      │    Composio API     │
│  (Parse Intent)     │      │  (Execute Gmail)    │
│  Llama 3.3 70B      │      │  OAuth + Tools      │
└─────────────────────┘      └──────────┬──────────┘
                                        │
                                        ▼
                             ┌─────────────────────┐
                             │    Gmail API        │
                             │  (Google)           │
                             └─────────────────────┘
```



---

## 📦 Gmail Agent (Backend)

### Backend Folder Structure

```
gmail-agent/
├── .env                    # API keys configuration (SECRET!)
├── .env.example            # Template for .env
├── .gitignore              # Files ignored by Git
├── Makefile                # Automated commands for setup & run
├── README.md               # Quick backend documentation
├── requirements.txt        # List of required Python libraries
├── test_api.sh             # Script for API testing
└── server/                 # Main code folder
    ├── __init__.py         # Python package marker
    ├── api.py              # ⭐ Main file - routing & endpoints
    ├── actions.py          # Gmail operations (send, fetch, draft)
    ├── auth.py             # Gmail OAuth authentication logic
    ├── chatbot.py          # ⭐ AI logic for command parsing
    ├── dependencies.py     # Dependency injection (Composio client)
    └── models.py           # Data models (request/response)
```

---

### 📄 Backend Files - Detailed Explanation

#### 1️⃣ `server/api.py` - The Backend Heart

**Purpose:** Main file that defines all API endpoints and routing.

**Why Use FastAPI?**
- Extremely fast (on par with NodeJS and Go)
- Auto-generates API documentation (Swagger)
- Built-in type checking with Pydantic
- Async/await support for high performance

**Available Endpoints:**

| Endpoint | Method | Function |
|----------|--------|----------|
| `/` | GET | API info (version, docs link) |
| `/health` | GET | Check if server is alive |
| `/connection/exists` | POST | Check if user has Gmail connection |
| `/connection/create` | POST | Create new Gmail OAuth connection |
| `/connection/status` | POST | Check connection status |
| `/actions/send_email` | POST | Send an email |
| `/actions/fetch_emails` | POST | Fetch emails from inbox |
| `/actions/create_draft` | POST | Create email draft |
| `/chat` | POST | ⭐ **Main endpoint** - Chat with AI |

**How CORS Middleware Works:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Allow frontend to access API
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)
```

**Why Need CORS?**
- Frontend (port 3000) and Backend (port 8000) are different domains
- Browser blocks cross-domain requests by default
- CORS middleware allows frontend to access backend

**Important Function - `validate_user`:**
```python
def validate_user(user_id: str, composio_client) -> str:
    """
    Ensures user has connected Gmail before executing actions
    If not connected, throws 404 error
    """
    if check_connected_account_exists(composio_client, user_id):
        return user_id
    raise HTTPException(status_code=404, detail=f"No connection for user: {user_id}")
```

**Reason:** Prevents errors when user hasn't completed Gmail OAuth.



---

#### 2️⃣ `server/actions.py` - Gmail Executor

**Purpose:** Wrapper functions to execute Gmail operations via Composio SDK.

**Why Use Composio?**
- Simplifies integration with 100+ tools (Gmail, Slack, GitHub, etc.)
- Handles OAuth authentication automatically
- One API for many services
- No need to manually setup Gmail API credentials

**Main Functions:**

```python
def execute_tool(composio_client, user_id, tool_slug, arguments):
    """
    Generic function to execute any Composio tool
    
    Args:
        composio_client: Authenticated Composio client
        user_id: User ID who will execute the tool
        tool_slug: Tool name (example: "GMAIL_SEND_EMAIL")
        arguments: Parameters required by the tool
    
    Returns:
        Dict result from Composio execution
    """
    return composio_client.tools.execute(
        slug=tool_slug,
        arguments=arguments,
        user_id=user_id,
        dangerously_skip_version_check=True  # Skip version check for speed
    )
```

**3 Gmail Functions:**

1. **`send_email()`** - Send Email
```python
def send_email(composio_client, user_id, recipient_email, subject, body):
    return execute_tool(
        composio_client=composio_client,
        user_id=user_id,
        tool_slug="GMAIL_SEND_EMAIL",  # Tool slug from Composio
        arguments={
            "recipient_email": recipient_email,
            "subject": subject,
            "body": body
        }
    )
```

2. **`fetch_emails()`** - Fetch Emails
```python
def fetch_emails(composio_client, user_id, limit=5):
    return execute_tool(
        composio_client=composio_client,
        user_id=user_id,
        tool_slug="GMAIL_FETCH_EMAILS",
        arguments={"limit": limit}  # How many emails to fetch
    )
```

3. **`create_draft()`** - Create Draft
```python
def create_draft(composio_client, user_id, recipient_email, subject, body):
    return execute_tool(
        composio_client=composio_client,
        user_id=user_id,
        tool_slug="GMAIL_CREATE_EMAIL_DRAFT",
        arguments={
            "recipient_email": recipient_email,
            "subject": subject,
            "body": body
        }
    )
```

**Why Use This Pattern?**
- DRY (Don't Repeat Yourself) - one `execute_tool` function for all
- Easy to add new tools (just change `tool_slug`)
- Centralized error handling



---

#### 3️⃣ `server/chatbot.py` - The AI Brain

**Purpose:** Uses Groq LLM to understand user commands and determine actions.

**Why Use Groq?**
- **Extremely fast** - 10x faster than OpenAI
- **Free** - Free API key with high rate limits
- **Llama 3.3 70B** - Powerful open-source model
- **JSON mode** - Can force output in JSON format

**System Prompt - Instructions for AI:**

```python
SYSTEM_PROMPT = """You are an email assistant. Parse user messages and determine the desired action.

Available actions:
- send_email: Send email (needs: recipient_email, subject, body)
- create_draft: Create email draft (needs: recipient_email, subject, body)  
- fetch_emails: Get recent emails (optional: limit)

If user doesn't provide recipient email, ask first. Create professional subject and body.

Respond in JSON:
{
    "action": "send_email|create_draft|fetch_emails",
    "recipient_email": "email@example.com",
    "recipient_name": "Name",
    "subject": "Subject",
    "body": "Email content",
    "limit": 5,
    "need_more_info": false,
    "question": "Question if more info needed"
}
"""
```

**Why Use System Prompt?**
- Provides context and instructions to AI
- Defines desired output format
- Makes AI consistent in responses

**Main Functions:**

1. **`parse_intent_with_groq()`** - Parse User Command

```python
async def parse_intent_with_groq(user_message, groq_api_key, conversation_history):
    """
    Sends user message to Groq API and gets intent in JSON format
    
    Flow:
    1. Create messages array with system prompt + history + user message
    2. Send to Groq API with Llama 3.3 70B model
    3. Force JSON output with response_format
    4. Parse JSON response
    
    Returns:
        Dict with action, recipient_email, subject, body, etc.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {groq_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "temperature": 0.3,  # Low temperature = more consistent
                "response_format": {"type": "json_object"}  # Force JSON
            },
            timeout=30.0
        )
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)
```

**Why Async?**
- API call to Groq can be slow (1-3 seconds)
- Async allows server to handle other requests while waiting
- Better performance for concurrent users



2. **`execute_email_action()`** - Execute Action

```python
async def execute_email_action(intent, user_id, base_url="http://localhost:8000"):
    """
    Executes action based on parsed intent
    
    Flow:
    1. Get action from intent (send_email, create_draft, fetch_emails)
    2. Call appropriate API endpoint with httpx
    3. Return execution result
    """
    action = intent.get("action")
    
    async with httpx.AsyncClient() as client:
        if action == "send_email":
            response = await client.post(f"{base_url}/actions/send_email", json={
                "user_id": user_id,
                "recipient_email": intent["recipient_email"],
                "subject": intent["subject"],
                "body": intent["body"]
            })
        # ... etc for other actions
        
        return response.json()
```

**Why Call Internal API?**
- Separation of concerns - chatbot focuses on AI logic
- Reusable - endpoints can be called from anywhere
- Consistent validation - all requests go through Pydantic models

3. **`chat()`** - Main Chat Function

```python
async def chat(user_message, groq_api_key, user_id, conversation_history, auto_execute=True):
    """
    Main function that combines parsing and execution
    
    Flow:
    1. Parse intent from user message
    2. Check if more info is needed
    3. If auto_execute=True, execute action immediately
    4. Return result
    
    Returns:
        Dict with type (question/action_result/intent_parsed) and data
    """
    # 1. Parse intent
    intent = await parse_intent_with_groq(user_message, groq_api_key, conversation_history)
    
    # 2. Check if more info needed
    if intent.get("need_more_info"):
        return {
            "type": "question",
            "message": intent.get("question", "Can you provide more details?"),
            "intent": intent
        }
    
    # 3. Auto execute if enabled
    if auto_execute and intent.get("action"):
        result = await execute_email_action(intent, user_id)
        return {
            "type": "action_result",
            "action": intent["action"],
            "intent": intent,
            "result": result
        }
    
    # 4. Return parsed intent only
    return {"type": "intent_parsed", "intent": intent}
```

**3 Response Types:**
- `question` - AI needs more info from user
- `action_result` - Action has been executed, here's the result
- `intent_parsed` - Intent has been parsed but not executed yet



---

#### 4️⃣ `server/auth.py` - Gmail Authentication

**Purpose:** Manages OAuth authentication with Gmail via Composio.

**Why Need OAuth?**
- Gmail API requires user permission to access emails
- OAuth is the industry standard for authorization
- Users don't need to give passwords to our app
- More secure - tokens can be revoked anytime

**Functions:**

1. **`fetch_auth_config()`** - Get Auth Configuration

```python
def fetch_auth_config(composio_client):
    """
    Check if there's already an auth config for Gmail in Composio
    
    Returns:
        Auth config object if exists, None if not
    """
    auth_configs = composio_client.auth_configs.list()
    for auth_config in auth_configs.items:
        if auth_config.toolkit == "GMAIL":
            return auth_config
    return None
```

2. **`create_auth_config()`** - Create New Auth Configuration

```python
def create_auth_config(composio_client):
    """
    Creates new auth config with custom Gmail OAuth credentials
    
    Requires:
        - GMAIL_CLIENT_ID (from Google Cloud Console)
        - GMAIL_CLIENT_SECRET (from Google Cloud Console)
    
    Returns:
        Newly created auth config object
    """
    client_id = os.getenv("GMAIL_CLIENT_ID")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        raise ValueError("GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET required")
    
    return composio_client.auth_configs.create(
        toolkit="GMAIL",
        options={
            "name": "default_gmail_auth_config",
            "type": "use_custom_auth",
            "auth_scheme": "OAUTH2",
            "credentials": {
                "client_id": client_id,
                "client_secret": client_secret,
            },
        },
    )
```

**Note:** If custom credentials aren't set, Composio will use their defaults.

3. **`create_connection()`** - Initiate OAuth Flow

```python
def create_connection(composio_client, user_id, auth_config_id=None):
    """
    Starts OAuth flow for user
    
    Flow:
    1. Find or create auth config
    2. Initiate connection with Composio
    3. Return connection object with redirect_url
    4. User clicks redirect_url to authorize
    5. After authorization, connection becomes ACTIVE
    
    Returns:
        Connection object with:
        - id: connection_id for tracking
        - redirect_url: URL for OAuth authorization
    """
    if not auth_config_id:
        auth_config = fetch_auth_config(composio_client)
        if not auth_config:
            try:
                auth_config = create_auth_config(composio_client)
            except ValueError:
                auth_config = None
        if auth_config:
            auth_config_id = auth_config.id
    
    connection_params = {"user_id": user_id}
    if auth_config_id:
        connection_params["auth_config_id"] = auth_config_id
    
    return composio_client.connected_accounts.initiate(**connection_params)
```



4. **`check_connected_account_exists()`** - Check Active Connection

```python
def check_connected_account_exists(composio_client, user_id):
    """
    Checks if user has an active Gmail connection
    
    Returns:
        True if there's an ACTIVE connection, False if not
    """
    connected_accounts = composio_client.connected_accounts.list(
        user_ids=[user_id],
        toolkit_slugs=["GMAIL"],
    )
    for account in connected_accounts.items:
        if account.status == "ACTIVE":
            return True
    return False
```

**Why Check ACTIVE Status?**
- Connection can be in status: INITIATED, ACTIVE, FAILED, REVOKED
- Only ACTIVE can be used to execute tools
- Prevents errors when user hasn't completed OAuth

5. **`get_connection_status()`** - Get Connection Status

```python
def get_connection_status(composio_client, connection_id):
    """
    Gets detailed status of a specific connection
    
    Returns:
        Connection object with status and other details
    """
    return composio_client.connected_accounts.get(connection_id=connection_id)
```

**Use Case:** Polling to check if user has completed OAuth.

---

#### 5️⃣ `server/models.py` - Data Models

**Purpose:** Defines data structures for requests and responses using Pydantic.

**Why Use Pydantic?**
- **Type validation** - automatically validates data types
- **Auto documentation** - FastAPI generates docs from models
- **Serialization** - converts Python objects to JSON automatically
- **IDE support** - autocomplete and type hints

**Request Models:**

```python
class SendEmailRequest(BaseModel):
    """Model for send email request"""
    user_id: str = Field(default="default")
    recipient_email: str  # Required
    subject: str          # Required
    body: str             # Required

class FetchEmailsRequest(BaseModel):
    """Model for fetch emails request"""
    user_id: str = Field(default="default")
    limit: int = Field(default=5, ge=1, le=50)  # Min 1, Max 50

class ChatRequest(BaseModel):
    """Model for chat request"""
    message: str                                    # Required
    user_id: str = Field(default="default")
    auto_execute: bool = Field(default=True)       # Auto execute action
    conversation_history: Optional[List[dict]] = None  # Chat history
```

**Response Models:**

```python
class ToolExecutionResponse(BaseModel):
    """Model for tool execution response"""
    successful: bool              # Success or not
    data: Optional[Any] = None    # Result data if successful
    error: Optional[str] = None   # Error message if failed

class CreateConnectionResponse(BaseModel):
    """Model for create connection response"""
    connection_id: str    # ID for tracking
    redirect_url: str     # URL for OAuth
```

**Benefits of Using Models:**
- Requests are automatically validated before entering handler
- Responses are automatically serialized to JSON
- Clear error messages if data is invalid
- API documentation is auto-generated



---

#### 6️⃣ `server/dependencies.py` - Dependency Injection

**Purpose:** Provides Composio client as a dependency for FastAPI.

**Why Use Dependency Injection?**
- **Singleton pattern** - one client instance for all requests
- **Clean code** - no need to create client in every function
- **Testable** - easy to mock for testing
- **Efficient** - doesn't create new connection every request

```python
_composio_client: Composio | None = None  # Global variable

def provide_composio_client() -> Composio:
    """
    Factory function that returns Composio client
    
    Pattern: Singleton
    - Check if client already exists
    - If not, create new one with API key from .env
    - If yes, return existing one
    
    Returns:
        Composio client instance
    """
    global _composio_client
    if _composio_client is None:
        api_key = os.getenv("COMPOSIO_API_KEY")
        if not api_key:
            raise ValueError("COMPOSIO_API_KEY environment variable is required")
        _composio_client = Composio(api_key=api_key)
    return _composio_client

# Type alias for dependency injection
ComposioClient = Annotated[Composio, Depends(provide_composio_client)]
```

**How to Use in Endpoints:**

```python
@app.post("/connection/exists")
def connection_exists(composio_client: ComposioClient):
    # composio_client is automatically injected by FastAPI
    # No need to manually create or pass it
    exists = check_connected_account_exists(composio_client, "default")
    return {"exists": exists}
```

**Benefits:**
- Cleaner and more readable code
- Single source of truth for client
- Easy to swap implementation for testing

---

#### 7️⃣ `requirements.txt` - Dependencies

**Purpose:** List of all Python libraries required by the project.

```txt
fastapi==0.115.6          # Web framework
uvicorn[standard]==0.34.0 # ASGI server to run FastAPI
composio==0.10.7          # SDK for Gmail integration
python-dotenv==1.0.1      # Load environment variables from .env
pydantic==2.10.5          # Data validation
httpx==0.28.1             # Async HTTP client to call Groq API
```

**Why Use These Libraries?**

| Library | Reason |
|---------|--------|
| `fastapi` | Modern, fast web framework with auto docs |
| `uvicorn` | Production-ready ASGI server for FastAPI |
| `composio` | Simplifies integration with Gmail and other tools |
| `python-dotenv` | Load API keys from .env file (security) |
| `pydantic` | Automatic validation and serialization |
| `httpx` | Async HTTP client to call Groq API |

**Install All:**
```bash
pip install -r requirements.txt
```



---

#### 8️⃣ `Makefile` - Build Automation

**Purpose:** Provides shortcut commands for setup and running the project.

**Why Use Makefile?**
- Simplifies long commands into one word
- Consistent - all developers use the same commands
- Documentation - can see all available commands

**Available Commands:**

```makefile
make env       # Create Python virtual environment
make install   # Install all dependencies
make run       # Run production server
make dev       # Run development server (auto-reload)
make clean     # Remove venv and cache files
```

**Example Implementation:**

```makefile
VENV = .venv
PYTHON = $(VENV)/bin/python
UVICORN = $(VENV)/bin/uvicorn

install: env
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

dev:
	$(UVICORN) server.api:app --host 0.0.0.0 --port 8000 --reload
```

**Benefits:**
- New developers just run `make install` and `make dev`
- No need to memorize long commands
- Can add custom commands (testing, deployment, etc.)

---

#### 9️⃣ `.env` and `.env.example`

**Purpose:** Store secret configuration (API keys).

**.env.example** (Template):
```bash
# Composio API Key (REQUIRED!)
COMPOSIO_API_KEY=your-composio-api-key

# Groq API Key (REQUIRED!)
GROQ_API_KEY=your-groq-api-key

# Gmail OAuth Credentials (OPTIONAL - for custom auth)
# GMAIL_CLIENT_ID=your-gmail-client-id
# GMAIL_CLIENT_SECRET=your-gmail-client-secret
```

**.env** (Actual File - DON'T COMMIT!):
```bash
COMPOSIO_API_KEY=sk_composio_abc123xyz...
GROQ_API_KEY=gsk_groq_def456uvw...
```

**Why Use .env?**
- **Security** - API keys don't go into Git repository
- **Flexibility** - different environments can have different configs
- **Best practice** - industry standard for managing secrets

**How It Works:**
```python
from dotenv import load_dotenv
import os

load_dotenv()  # Load .env file
api_key = os.getenv("COMPOSIO_API_KEY")  # Get value
```

**IMPORTANT:** 
- `.env` must be in `.gitignore`
- Never commit API keys to Git
- Share `.env.example` as a template



---

## 🎨 Gmail Chatbot UI (Frontend)

### Frontend Folder Structure

```
gmail-chatbot-ui/
├── package.json            # Node.js dependencies & scripts
├── next.config.ts          # Next.js configuration
├── tsconfig.json           # TypeScript configuration
├── postcss.config.mjs      # PostCSS config (for Tailwind)
├── eslint.config.mjs       # ESLint configuration (linting)
├── public/                 # Static assets (images, icons)
│   ├── file.svg
│   ├── globe.svg
│   └── ...
└── src/
    └── app/
        ├── globals.css     # Global styles (Tailwind CSS)
        ├── layout.tsx      # Root layout component
        └── page.tsx        # ⭐ Main chat page component
```

---

### 📄 Frontend Files - Detailed Explanation

#### 1️⃣ `src/app/page.tsx` - Main Chat Component

**Purpose:** Main React component that displays the chat interface and handles user interactions.

**Why Use Next.js?**
- **Best React framework** - production-ready
- **Server-side rendering** - SEO friendly
- **File-based routing** - `page.tsx` automatically becomes route `/`
- **Built-in optimization** - image, font, code splitting automatic

**State Management:**

```typescript
interface Message {
  id: string;                    // Unique ID for each message
  role: "user" | "assistant";    // Who sent it
  content: string;               // Message content
  action?: string;               // Action performed (optional)
  success?: boolean;             // Action status (optional)
}

const [messages, setMessages] = useState<Message[]>([...]);  // Chat history
const [input, setInput] = useState("");                       // Current user input
const [isLoading, setIsLoading] = useState(false);           // Loading state
const userId = "pg-test-a199d8f3-e74a-42e0-956b-b1fbb2808b58"; // User ID
```

**Why Use useState?**
- React hooks for managing component state
- Automatic re-render when state changes
- Simple and powerful

**Main Function - `sendMessage()`:**

```typescript
const sendMessage = async () => {
  // 1. Validate input
  if (!input.trim() || isLoading) return;

  // 2. Save input and clear field
  const currentInput = input;
  setInput("");
  
  // 3. Add user message to chat
  setMessages((prev) => [
    ...prev,
    { id: Date.now().toString(), role: "user", content: currentInput }
  ]);
  
  // 4. Set loading state
  setIsLoading(true);

  try {
    // 5. Call backend API
    const response = await fetch("http://localhost:8000/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: currentInput,
        user_id: userId,
        auto_execute: true
      }),
    });

    // 6. Parse response
    const data = await response.json();
    
    // 7. Format message based on response type
    let content = "";
    if (data.type === "action_result") {
      if (data.action === "send_email" && data.result?.successful) {
        content = `✅ Email sent!\n\n📧 ${data.intent.recipient_email}\n📝 ${data.intent.subject}`;
      }
      // ... handle other actions
    }
    
    // 8. Add assistant response to chat
    setMessages((prev) => [
      ...prev,
      { id: (Date.now() + 1).toString(), role: "assistant", content }
    ]);
    
  } catch (error) {
    // 9. Handle error
    setMessages((prev) => [
      ...prev,
      { id: (Date.now() + 1).toString(), role: "assistant", content: `❌ ${error.message}` }
    ]);
  } finally {
    // 10. Clear loading state
    setIsLoading(false);
  }
};
```



**Response Handling - Format Message:**

```typescript
// For send_email success
if (data.action === "send_email" && success) {
  content = `✅ Email sent!\n\n📧 ${data.intent.recipient_email}\n📝 ${data.intent.subject}\n\n${data.intent.body}`;
}

// For fetch_emails success
else if (data.action === "fetch_emails" && success) {
  const emails = data.result?.data?.data?.messages || [];
  if (emails.length > 0) {
    content = `📬 ${emails.length} emails:\n\n`;
    emails.forEach((email, i) => {
      content += `${i + 1}. ${email.subject}\n   ${email.sender}\n\n`;
    });
  } else {
    content = "📭 No emails.";
  }
}

// For error
else {
  content = `❌ Failed: ${data.result?.error || "Unknown error"}`;
}
```

**Auto-scroll to Bottom:**

```typescript
const messagesEndRef = useRef<HTMLDivElement>(null);

useEffect(() => {
  messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
}, [messages]);  // Trigger every time messages change
```

**Why Need This?**
- New chat messages appear at bottom
- User doesn't need to manually scroll
- Better UX

**UI Components:**

1. **Header** - Title and connection status
```tsx
<header className="bg-gray-800 border-b border-gray-700 p-4">
  <h1 className="text-xl font-semibold text-white">📧 Gmail Chatbot</h1>
  <div className="flex items-center gap-2">
    <span className="w-2 h-2 bg-green-500 rounded-full"></span>
    Connected
  </div>
</header>
```

2. **Message List** - Display chat history
```tsx
{messages.map((msg) => (
  <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
    <div className={`rounded-2xl px-4 py-3 ${
      msg.role === "user" 
        ? "bg-blue-600 text-white"           // User message (right, blue)
        : "bg-gray-800 text-gray-100"        // Assistant message (left, gray)
    }`}>
      <pre className="whitespace-pre-wrap">{msg.content}</pre>
    </div>
  </div>
))}
```

3. **Loading Indicator** - Animated dots
```tsx
{isLoading && (
  <div className="flex gap-1">
    <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce"></span>
    <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" 
          style={{ animationDelay: "0.1s" }}></span>
    <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" 
          style={{ animationDelay: "0.2s" }}></span>
  </div>
)}
```

4. **Input Footer** - Text input and send button
```tsx
<footer className="bg-gray-800 border-t border-gray-700 p-4">
  <input
    type="text"
    value={input}
    onChange={(e) => setInput(e.target.value)}
    onKeyDown={(e) => e.key === "Enter" && sendMessage()}
    placeholder="Type a message..."
    disabled={isLoading}
  />
  <button
    onClick={sendMessage}
    disabled={isLoading || !input.trim()}
  >
    Send
  </button>
</footer>
```

**Why Use Tailwind CSS?**
- **Utility-first** - styling directly in JSX
- **Responsive** - mobile-friendly automatically
- **Consistent** - built-in design system
- **Fast** - no need to switch to CSS files



---

#### 2️⃣ `src/app/layout.tsx` - Root Layout

**Purpose:** Layout component that wraps all pages in the application.

```typescript
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

// Load fonts from Google Fonts
const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        {children}  {/* page.tsx will render here */}
      </body>
    </html>
  );
}
```

**Why Use Layout?**
- **Shared structure** - header, footer, fonts for all pages
- **Performance** - fonts loaded only once
- **Consistency** - all pages use same styling

**Font Loading:**
- `next/font/google` - optimizes font loading automatically
- `variable` - creates CSS variable for font
- `antialiased` - smooth text rendering

---

#### 3️⃣ `src/app/globals.css` - Global Styles

**Purpose:** Global CSS for entire application using Tailwind CSS v4.

```css
@import "tailwindcss";  /* Import Tailwind CSS */

/* CSS Variables for theming */
:root {
  --background: #ffffff;
  --foreground: #171717;
}

/* Dark mode (auto-detect from system) */
@media (prefers-color-scheme: dark) {
  :root {
    --background: #0a0a0a;
    --foreground: #ededed;
  }
}

/* Theme configuration for Tailwind */
@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --font-sans: var(--font-geist-sans);
  --font-mono: var(--font-geist-mono);
}

body {
  background: var(--background);
  color: var(--foreground);
  font-family: Arial, Helvetica, sans-serif;
}
```

**Why Use CSS Variables?**
- **Theming** - easy to change colors
- **Dark mode** - automatic support
- **Reusable** - use anywhere

---

#### 4️⃣ `package.json` - Dependencies & Scripts

**Purpose:** Node.js project configuration, dependencies, and scripts.

```json
{
  "name": "gmail-chatbot-ui",
  "version": "0.1.0",
  "scripts": {
    "dev": "next dev",           // Development server
    "build": "next build",       // Build for production
    "start": "next start",       // Run production build
    "lint": "eslint"             // Check code quality
  },
  "dependencies": {
    "next": "16.1.2",            // React framework
    "react": "^19.2.3",          // UI library
    "react-dom": "^19.2.3"       // React DOM renderer
  },
  "devDependencies": {
    "@tailwindcss/postcss": "^4",  // Tailwind CSS processor
    "@types/node": "^20",          // TypeScript types for Node
    "@types/react": "^19",         // TypeScript types for React
    "tailwindcss": "^4",           // CSS framework
    "typescript": "^5"             // Type checking
  }
}
```

**Why Use These Dependencies?**

| Package | Reason |
|---------|--------|
| `next` | Best React framework, production-ready |
| `react` | Most popular UI library |
| `tailwindcss` | Utility-first CSS framework |
| `typescript` | Type safety, catch errors before runtime |

**Scripts:**
```bash
npm run dev    # Start development server (localhost:3000)
npm run build  # Build for production
npm run start  # Run production server
npm run lint   # Check code quality
```



---

#### 5️⃣ `next.config.ts` - Next.js Configuration

**Purpose:** Configuration file to customize Next.js behavior.

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
};

export default nextConfig;
```

**Example Configurations You Can Add:**
```typescript
const nextConfig: NextConfig = {
  reactStrictMode: true,        // Enable strict mode
  images: {
    domains: ['example.com'],   // Allowed image domains
  },
  env: {
    API_URL: 'http://localhost:8000',  // Environment variables
  },
};
```

**Why Need Config File?**
- Customize build process
- Set environment variables
- Configure image optimization
- Add redirects/rewrites

---

#### 6️⃣ `tsconfig.json` - TypeScript Configuration

**Purpose:** TypeScript compiler configuration.

```json
{
  "compilerOptions": {
    "target": "ES2017",              // JavaScript version target
    "lib": ["dom", "dom.iterable", "esnext"],  // Available APIs
    "jsx": "react-jsx",              // JSX transform
    "module": "esnext",              // Module system
    "moduleResolution": "bundler",   // How to resolve modules
    "strict": true,                  // Enable all strict checks
    "paths": {
      "@/*": ["./src/*"]             // Path alias (@/components/...)
    }
  },
  "include": ["**/*.ts", "**/*.tsx"],  // Files to compile
  "exclude": ["node_modules"]          // Files to ignore
}
```

**Why Use TypeScript?**
- **Type safety** - catch errors before runtime
- **Better IDE support** - autocomplete, refactoring
- **Self-documenting** - types serve as documentation
- **Refactoring confidence** - rename/move safely

**Path Alias:**
```typescript
// Without alias
import Button from '../../../components/Button';

// With alias
import Button from '@/components/Button';
```

---

## 🔄 How the System Works End-to-End

### Flow 1: User Sends Chat Message

```
1. USER types: "Send email to john@example.com about tomorrow's meeting"
   └─> Frontend (page.tsx)
       └─> sendMessage() is called
           └─> POST http://localhost:8000/chat
               Body: {
                 "message": "Send email to john@example.com...",
                 "user_id": "default",
                 "auto_execute": true
               }

2. BACKEND receives request
   └─> api.py: @app.post("/chat")
       └─> chatbot.py: chat()
           └─> parse_intent_with_groq()
               └─> Call Groq API
                   └─> Groq LLM (Llama 3.3 70B) parses message
                       └─> Returns JSON:
                           {
                             "action": "send_email",
                             "recipient_email": "john@example.com",
                             "subject": "Tomorrow's Meeting",
                             "body": "Hi John, ..."
                           }

3. BACKEND executes action
   └─> chatbot.py: execute_email_action()
       └─> POST http://localhost:8000/actions/send_email
           └─> api.py: @app.post("/actions/send_email")
               └─> validate_user() - check Gmail connection
                   └─> actions.py: send_email()
                       └─> composio_client.tools.execute("GMAIL_SEND_EMAIL")
                           └─> Composio API
                               └─> Gmail API
                                   └─> ✅ Email sent!

4. BACKEND returns response
   └─> {
         "type": "action_result",
         "action": "send_email",
         "intent": {...},
         "result": {"successful": true, "data": {...}}
       }

5. FRONTEND receives response
   └─> page.tsx: sendMessage()
       └─> Format message: "✅ Email sent! 📧 john@example.com"
           └─> setMessages() - add to chat
               └─> UI updates - message appears in chat
```



### Flow 2: First-Time Gmail Connection

```
1. USER opens app for the first time
   └─> Frontend checks connection
       └─> POST http://localhost:8000/connection/exists
           └─> Backend: check_connected_account_exists()
               └─> Returns: {"exists": false}

2. USER needs to connect Gmail
   └─> Frontend or manual call:
       └─> POST http://localhost:8000/connection/create
           Body: {"user_id": "default"}
           └─> Backend: auth.py: create_connection()
               └─> Composio: initiate connection
                   └─> Returns: {
                         "connection_id": "abc123",
                         "redirect_url": "https://accounts.google.com/oauth/..."
                       }

3. USER clicks redirect_url
   └─> Browser redirects to Google OAuth
       └─> USER logs in and authorizes app
           └─> Google redirects back to Composio
               └─> Composio updates connection status: ACTIVE

4. USER returns to app
   └─> Connection is now ACTIVE
       └─> Can start sending emails, fetching emails, etc.
```

### Flow 3: Fetch Emails

```
1. USER types: "Get my 5 most recent emails"
   └─> Frontend: POST /chat

2. BACKEND parses intent
   └─> Groq LLM returns:
       {
         "action": "fetch_emails",
         "limit": 5
       }

3. BACKEND executes
   └─> actions.py: fetch_emails(limit=5)
       └─> Composio: execute("GMAIL_FETCH_EMAILS")
           └─> Gmail API: get messages
               └─> Returns: [
                     {
                       "subject": "Meeting Reminder",
                       "sender": "boss@company.com",
                       "preview": {...}
                     },
                     ...
                   ]

4. FRONTEND formats and displays
   └─> "📬 5 emails:
        1. Meeting Reminder
           boss@company.com
        2. ..."
```

---

## 🎯 Conclusion

### Why This Architecture is Good

1. **Separation of Concerns**
   - Frontend focuses on UI/UX
   - Backend focuses on business logic
   - AI focuses on intent parsing
   - Composio focuses on Gmail integration

2. **Scalable**
   - Easy to add new actions (delete email, search, etc.)
   - Easy to add other tools (Slack, Calendar, etc.)
   - Easy to add user authentication

3. **Maintainable**
   - Well-organized code
   - Each file has clear responsibility
   - Type safety with TypeScript and Pydantic

4. **Modern Tech Stack**
   - FastAPI - fastest Python framework
   - Next.js - best React framework
   - Groq - fastest LLM
   - Composio - easiest integration

### Key Takeaways

| Component | Technology | Reason |
|----------|-----------|--------|
| **Backend Framework** | FastAPI | Fast, modern, auto docs |
| **Frontend Framework** | Next.js | Production-ready, SEO friendly |
| **AI/LLM** | Groq (Llama 3.3) | Extremely fast, free |
| **Gmail Integration** | Composio | Simplifies OAuth & API calls |
| **Styling** | Tailwind CSS | Utility-first, consistent |
| **Type Safety** | TypeScript + Pydantic | Catch errors early |
| **State Management** | React useState | Simple, built-in |
| **HTTP Client** | httpx (backend), fetch (frontend) | Async, modern |

### Complete Data Flow

```
User Input → Frontend (React) → Backend API (FastAPI) → AI (Groq) → 
Backend Logic → Composio SDK → Gmail API → Response → 
Backend → Frontend → UI Update
```

### Most Important Files

1. **`server/api.py`** - Routing & endpoints
2. **`server/chatbot.py`** - AI logic
3. **`server/actions.py`** - Gmail operations
4. **`src/app/page.tsx`** - Chat UI
5. **`server/auth.py`** - OAuth flow

---

## 📚 Resources

- [FastAPI Docs](https://fastapi.tiangolo.com)
- [Next.js Docs](https://nextjs.org/docs)
- [Composio Docs](https://docs.composio.dev)
- [Groq API Docs](https://console.groq.com/docs)
- [Tailwind CSS Docs](https://tailwindcss.com/docs)

---

**Created with ❤️ to help understand modern full-stack architecture**
