# Gmail Agent - Complete Documentation

A full-stack AI-powered Gmail assistant application built with **FastAPI** (Python backend) and **Next.js** (React frontend), using **Composio** for Gmail integration and **Groq LLM** for natural language processing.

---

## 📑 Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Gmail Agent (Backend)](#gmail-agent-backend)
   - [File Structure](#backend-file-structure)
   - [Code Explanation](#backend-code-explanation)
4. [Gmail Chatbot UI (Frontend)](#gmail-chatbot-ui-frontend)
   - [File Structure](#frontend-file-structure)
   - [Code Explanation](#frontend-code-explanation)
5. [API Reference](#api-reference)
6. [Setup & Installation](#setup--installation)
7. [Screenshots & Demo](#screenshots--demo)

---

## Project Overview

This project is an **AI-powered Gmail chatbot** that allows users to:

- ✉️ **Send emails** via natural language commands
- 📝 **Create email drafts** with AI-generated content
- 📬 **Fetch recent emails** from Gmail inbox

The system uses:
- **Composio** - For Gmail OAuth authentication and tool execution
- **Groq LLM (Llama 3.3 70B)** - For understanding user intent and parsing commands
- **FastAPI** - Python web framework for the backend API
- **Next.js 16** - React framework for the frontend chat interface

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface                          │
│                    (Next.js React Frontend)                     │
│                    localhost:3000                               │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTP POST /chat
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                            │
│                    localhost:8000                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   api.py     │  │  chatbot.py  │  │  actions.py  │          │
│  │  (Routes)    │  │  (AI Logic)  │  │  (Gmail)     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────┬───────────────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
┌─────────────────────┐      ┌─────────────────────┐
│     Groq API        │      │    Composio API     │
│  (LLM Processing)   │      │  (Gmail Actions)    │
│  Llama 3.3 70B      │      │  OAuth + Tools      │
└─────────────────────┘      └─────────────────────┘
                                      │
                                      ▼
                             ┌─────────────────────┐
                             │    Gmail API        │
                             │  (Google)           │
                             └─────────────────────┘
```

---

## Gmail Agent (Backend)

### Backend File Structure

```
gmail-agent/
├── .env                    # Environment variables (API keys)
├── .env.example            # Example environment file
├── .gitignore              # Git ignore rules
├── Makefile                # Build automation commands
├── README.md               # Quick start guide
├── requirements.txt        # Python dependencies
├── test_api.sh             # API testing script
└── server/
    ├── __init__.py         # Package initializer
    ├── api.py              # FastAPI application & routes
    ├── actions.py          # Gmail tool execution functions
    ├── auth.py             # Composio authentication logic
    ├── chatbot.py          # AI/LLM intent parsing logic
    ├── dependencies.py     # Dependency injection (Composio client)
    └── models.py           # Pydantic data models
```

### Backend Code Explanation

---

#### 📄 `server/api.py` - Main API Application

**Purpose:** Main FastAPI application that defines all HTTP endpoints/routes.

```python
# Key Components:

def create_app() -> FastAPI:
    """Factory function that creates and configures the FastAPI application"""
    
    # CORS middleware - allows frontend (localhost:3000) to call backend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        ...
    )
```

**Endpoints Defined:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Root endpoint - returns API info |
| `/health` | GET | Health check endpoint |
| `/connection/exists` | POST | Check if user has active Gmail connection |
| `/connection/create` | POST | Initiate new Gmail OAuth connection |
| `/connection/status` | POST | Get status of a connection |
| `/actions/send_email` | POST | Send an email |
| `/actions/fetch_emails` | POST | Fetch recent emails |
| `/actions/create_draft` | POST | Create an email draft |
| `/chat` | POST | AI chatbot endpoint (main feature) |

**Key Function - `validate_user`:**
```python
def validate_user(user_id: str, composio_client) -> str:
    """Validates that a user has an active Gmail connection before executing actions"""
    if check_connected_account_exists(composio_client, user_id):
        return user_id
    raise HTTPException(status_code=404, detail=f"No connection for user: {user_id}")
```

---

#### 📄 `server/actions.py` - Gmail Tool Execution

**Purpose:** Wrapper functions that execute Gmail operations via Composio SDK.

```python
def execute_tool(composio_client, user_id, tool_slug, arguments):
    """Generic function to execute any Composio tool"""
    return composio_client.tools.execute(
        slug=tool_slug,
        arguments=arguments,
        user_id=user_id,
        dangerously_skip_version_check=True
    )
```

**Available Actions:**

| Function | Tool Slug | Description |
|----------|-----------|-------------|
| `send_email()` | `GMAIL_SEND_EMAIL` | Sends an email to specified recipient |
| `fetch_emails()` | `GMAIL_FETCH_EMAILS` | Retrieves recent emails from inbox |
| `create_draft()` | `GMAIL_CREATE_EMAIL_DRAFT` | Creates a draft email |

**Example - Send Email Function:**
```python
def send_email(composio_client, user_id, recipient_email, subject, body):
    return execute_tool(
        composio_client=composio_client,
        user_id=user_id,
        tool_slug="GMAIL_SEND_EMAIL",
        arguments={
            "recipient_email": recipient_email,
            "subject": subject,
            "body": body
        }
    )
```

---

#### 📄 `server/auth.py` - Authentication Logic

**Purpose:** Handles Composio OAuth authentication and connection management for Gmail.

**Key Functions:**

| Function | Description |
|----------|-------------|
| `fetch_auth_config()` | Retrieves existing Gmail auth configuration from Composio |
| `create_auth_config()` | Creates new Gmail OAuth config with custom credentials |
| `create_connection()` | Initiates OAuth flow, returns redirect URL for user authorization |
| `check_connected_account_exists()` | Checks if user already has active Gmail connection |
| `get_connection_status()` | Gets the current status of a connection |

**OAuth Flow Explained:**
```python
def create_connection(composio_client, user_id, auth_config_id=None):
    """
    1. First tries to find existing auth config
    2. If not found and credentials exist, creates new auth config
    3. Initiates connection with Composio
    4. Returns connection object with redirect_url for OAuth
    """
    # ... implementation
    return composio_client.connected_accounts.initiate(**connection_params)
```

---

#### 📄 `server/chatbot.py` - AI Intent Parsing

**Purpose:** Uses Groq's Llama 3.3 70B model to understand user messages and determine email actions.

**System Prompt:**
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
    "subject": "Subject",
    "body": "Email body",
    "limit": 5,
    "need_more_info": false,
    "question": "Question if more info needed"
}
"""
```

**Key Functions:**

| Function | Description |
|----------|-------------|
| `parse_intent_with_groq()` | Calls Groq API to parse user message into structured intent |
| `execute_email_action()` | Executes the determined action by calling internal API |
| `chat()` | Main chat function - parses intent and optionally auto-executes |

**Chat Flow:**
```python
async def chat(user_message, groq_api_key, user_id, conversation_history, auto_execute):
    # 1. Parse user intent using LLM
    intent = await parse_intent_with_groq(user_message, groq_api_key, conversation_history)
    
    # 2. If need more info, return question
    if intent.get("need_more_info"):
        return {"type": "question", "message": intent.get("question")}
    
    # 3. If auto_execute enabled, perform the action
    if auto_execute and intent.get("action"):
        result = await execute_email_action(intent, user_id)
        return {"type": "action_result", "action": intent["action"], "result": result}
    
    # 4. Otherwise just return parsed intent
    return {"type": "intent_parsed", "intent": intent}
```

---

#### 📄 `server/models.py` - Data Models

**Purpose:** Pydantic models for request/response validation and serialization.

**Request Models:**

| Model | Fields | Description |
|-------|--------|-------------|
| `CreateConnectionRequest` | `user_id`, `auth_config_id?` | Create new connection |
| `ConnectionStatusRequest` | `user_id`, `connection_id` | Check connection status |
| `SendEmailRequest` | `user_id`, `recipient_email`, `subject`, `body` | Send email |
| `FetchEmailsRequest` | `user_id`, `limit` | Fetch emails |
| `CreateDraftRequest` | `user_id`, `recipient_email`, `subject`, `body` | Create draft |
| `ChatRequest` | `message`, `user_id`, `auto_execute`, `conversation_history?` | Chat message |

**Response Models:**

| Model | Fields | Description |
|-------|--------|-------------|
| `CreateConnectionResponse` | `connection_id`, `redirect_url` | OAuth redirect info |
| `ConnectionStatusResponse` | `status`, `connected` | Connection state |
| `ConnectionExistsResponse` | `exists`, `user_id` | Check result |
| `ToolExecutionResponse` | `successful`, `data?`, `error?` | Action result |

---

#### 📄 `server/dependencies.py` - Dependency Injection

**Purpose:** Provides the Composio client as a FastAPI dependency.

```python
_composio_client: Composio | None = None

def provide_composio_client() -> Composio:
    """Singleton pattern - creates Composio client once and reuses"""
    global _composio_client
    if _composio_client is None:
        api_key = os.getenv("COMPOSIO_API_KEY")
        _composio_client = Composio(api_key=api_key)
    return _composio_client

# Type alias for dependency injection
ComposioClient = Annotated[Composio, Depends(provide_composio_client)]
```

**Usage in Routes:**
```python
@app.post("/connection/exists")
def connection_exists(composio_client: ComposioClient):
    # composio_client is automatically injected by FastAPI
    ...
```

---

#### 📄 `requirements.txt` - Python Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | 0.115.6 | Web framework |
| `uvicorn[standard]` | 0.34.0 | ASGI server |
| `composio` | 0.10.7 | Gmail integration SDK |
| `python-dotenv` | 1.0.1 | Environment variable loading |
| `pydantic` | 2.10.5 | Data validation |
| `httpx` | 0.28.1 | Async HTTP client (for Groq API) |

---

#### 📄 `Makefile` - Build Commands

| Command | Description |
|---------|-------------|
| `make env` | Create Python virtual environment |
| `make install` | Install all dependencies |
| `make run` | Run production server |
| `make dev` | Run development server with auto-reload |
| `make clean` | Remove venv and cache files |

---

## Gmail Chatbot UI (Frontend)

### Frontend File Structure

```
gmail-chatbot-ui/
├── package.json            # Node.js dependencies
├── next.config.ts          # Next.js configuration
├── tsconfig.json           # TypeScript configuration
├── postcss.config.mjs      # PostCSS (Tailwind) config
├── eslint.config.mjs       # ESLint configuration
├── public/                 # Static assets
└── src/
    └── app/
        ├── globals.css     # Global styles (Tailwind)
        ├── layout.tsx      # Root layout component
        └── page.tsx        # Main chat page component
```

### Frontend Code Explanation

---

#### 📄 `src/app/page.tsx` - Main Chat Component

**Purpose:** The main chat interface component that handles user interactions and displays messages.

**State Management:**
```typescript
interface Message {
  id: string;
  role: "user" | "assistant";  // Who sent the message
  content: string;              // Message text
  action?: string;              // Action performed (send_email, etc.)
  success?: boolean;            // Whether action succeeded
}

// Component state
const [messages, setMessages] = useState<Message[]>([...]);  // Chat history
const [input, setInput] = useState("");                       // Current input
const [isLoading, setIsLoading] = useState(false);           // Loading state
const userId = "pg-test-a199d8f3-e74a-42e0-956b-b1fbb2808b58"; // User ID
```

**Core Function - `sendMessage`:**
```typescript
const sendMessage = async () => {
  // 1. Validate input
  if (!input.trim() || isLoading) return;
  
  // 2. Add user message to chat
  setMessages(prev => [...prev, { role: "user", content: input }]);
  
  // 3. Call backend API
  const response = await fetch("http://localhost:8000/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: input,
      user_id: userId,
      auto_execute: true
    }),
  });
  
  // 4. Process response and format message
  const data = await response.json();
  
  // 5. Handle different response types
  if (data.type === "action_result") {
    // Format success/error message based on action
  } else if (data.type === "question") {
    // AI needs more information
  }
  
  // 6. Add assistant response to chat
  setMessages(prev => [...prev, { role: "assistant", content }]);
};
```

**Response Handling:**
```typescript
// For send_email success
content = `✅ Email sent!\n\n📧 ${data.intent.recipient_email}\n📝 ${data.intent.subject}`;

// For fetch_emails success
const emails = data.result?.data?.data?.messages || [];
content = `📬 ${emails.length} emails:\n\n`;
emails.forEach((email, i) => {
  content += `${i + 1}. ${email.subject}\n   ${email.sender}\n\n`;
});

// For errors
content = `❌ Failed: ${data.result?.error}`;
```

**UI Components:**

1. **Header** - Shows title and connection status
2. **Message List** - Displays chat history with different styles for user/assistant
3. **Loading Indicator** - Animated dots while waiting for response
4. **Input Footer** - Text input and send button

**Styling (Tailwind CSS):**
```tsx
// User message (right-aligned, blue)
<div className="bg-blue-600 text-white rounded-2xl px-4 py-3">

// Assistant message (left-aligned, dark gray)
<div className="bg-gray-800 text-gray-100 border border-gray-700 rounded-2xl">

// Success indicator
<div className="text-green-400">

// Error indicator
<div className="text-red-400">
```

---

#### 📄 `src/app/layout.tsx` - Root Layout

**Purpose:** Root layout component that wraps all pages.

```typescript
export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        {children}
      </body>
    </html>
  );
}
```

**Features:**
- Imports Geist fonts from Google Fonts
- Sets up CSS variables for fonts
- Applies antialiasing for smoother text

---

#### 📄 `src/app/globals.css` - Global Styles

**Purpose:** Global CSS styles using Tailwind CSS v4.

```css
@import "tailwindcss";

:root {
  --background: #ffffff;
  --foreground: #171717;
}

@media (prefers-color-scheme: dark) {
  :root {
    --background: #0a0a0a;
    --foreground: #ededed;
  }
}
```

**Features:**
- Imports Tailwind CSS
- Defines CSS variables for theming
- Supports light/dark mode based on system preference

---

#### 📄 `package.json` - Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `next` | 16.1.2 | React framework |
| `react` | ^19.2.3 | UI library |
| `react-dom` | ^19.2.3 | React DOM renderer |
| `tailwindcss` | ^4 | CSS framework |
| `typescript` | ^5 | Type checking |

**Scripts:**
| Script | Command | Description |
|--------|---------|-------------|
| `dev` | `next dev` | Start development server |
| `build` | `next build` | Build for production |
| `start` | `next start` | Start production server |
| `lint` | `eslint` | Run linter |

---

## API Reference

### Base URL
```
http://localhost:8000
```

### Endpoints

#### Health Check
```http
GET /health
```
**Response:**
```json
{"status": "healthy"}
```

---

#### Check Connection Exists
```http
POST /connection/exists
```
**Response:**
```json
{
  "exists": true,
  "user_id": "default"
}
```

---

#### Create Connection
```http
POST /connection/create
Content-Type: application/json

{
  "user_id": "default",
  "auth_config_id": null
}
```
**Response:**
```json
{
  "connection_id": "abc123",
  "redirect_url": "https://accounts.google.com/oauth/..."
}
```

---

#### Send Email
```http
POST /actions/send_email
Content-Type: application/json

{
  "user_id": "default",
  "recipient_email": "recipient@example.com",
  "subject": "Hello",
  "body": "Email content here"
}
```
**Response:**
```json
{
  "successful": true,
  "data": {...}
}
```

---

#### Fetch Emails
```http
POST /actions/fetch_emails
Content-Type: application/json

{
  "user_id": "default",
  "limit": 5
}
```
**Response:**
```json
{
  "successful": true,
  "data": {
    "messages": [
      {
        "subject": "Email Subject",
        "sender": "sender@example.com",
        "preview": {...}
      }
    ]
  }
}
```

---

#### Chat (Main Feature)
```http
POST /chat
Content-Type: application/json

{
  "message": "Send email to john@example.com about the meeting tomorrow",
  "user_id": "default",
  "auto_execute": true,
  "conversation_history": []
}
```

**Response Types:**

1. **Action Result** (auto_execute=true, action performed):
```json
{
  "type": "action_result",
  "action": "send_email",
  "intent": {
    "action": "send_email",
    "recipient_email": "john@example.com",
    "subject": "Meeting Tomorrow",
    "body": "..."
  },
  "result": {
    "successful": true,
    "data": {...}
  }
}
```

2. **Question** (need more information):
```json
{
  "type": "question",
  "message": "What is the recipient's email address?",
  "intent": {...}
}
```

3. **Intent Parsed** (auto_execute=false):
```json
{
  "type": "intent_parsed",
  "intent": {...}
}
```

---

## Setup & Installation

### Prerequisites
- Python 3.11+
- Node.js 18+
- Composio API Key
- Groq API Key

### Backend Setup

```bash
# Navigate to backend directory
cd gmail-agent

# Copy environment file
cp .env.example .env

# Edit .env with your API keys
# COMPOSIO_API_KEY=your-key
# GROQ_API_KEY=your-key

# Create virtual environment and install dependencies
make install

# Run development server
make dev

# Server runs at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### Frontend Setup

```bash
# Navigate to frontend directory
cd gmail-chatbot-ui

# Install dependencies
npm install

# Run development server
npm run dev

# App runs at http://localhost:3000
```

### First-Time Gmail Connection

1. Start both backend and frontend servers
2. Open http://localhost:3000
3. The app will check for existing connection
4. If no connection, call `/connection/create` to get OAuth URL
5. Complete Google OAuth flow
6. Connection is now active, you can use the chatbot

---

## Screenshots & Demo

> **Note:** Add your screenshots and video links here.

### Screenshots

| Screenshot | Description |
|------------|-------------|
| `screenshot-1.png` | Main chat interface |
| `screenshot-2.png` | Sending an email via chat |
| `screenshot-3.png` | Email sent confirmation |
| `screenshot-4.png` | Fetching recent emails |
| `screenshot-5.png` | API documentation (Swagger) |

### Demo Video

> Add your video link here: `[Demo Video](link-to-video)`

---

## License

This project is for educational purposes.

---

## Author

Created as part of the Composio Agent project.
