# Gmail Chatbot Project

An AI-powered Gmail assistant with a modern chat interface. Send emails, create drafts, and fetch your inbox using natural language commands.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com)

## ✨ Features

- 📧 **Send Emails** - Send emails using natural language commands
- 📝 **Create Drafts** - Create email drafts with AI-generated content
- 📬 **Fetch Emails** - Retrieve recent emails from your inbox
- 🤖 **AI-Powered** - Uses Groq's Llama 3.3 70B for intent parsing
- 🔐 **OAuth Integration** - Secure Gmail authentication via Composio

## 🏗️ Architecture

```
┌─────────────────────┐     ┌─────────────────────┐
│   Next.js Frontend  │────▶│   FastAPI Backend   │
│   (localhost:3000)  │     │   (localhost:8000)  │
└─────────────────────┘     └──────────┬──────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    ▼                                     ▼
           ┌─────────────────┐                 ┌─────────────────┐
           │    Groq LLM     │                 │   Composio API  │
           │ (Intent Parse)  │                 │  (Gmail Tools)  │
           └─────────────────┘                 └─────────────────┘
```

## 📁 Project Structure

```
composio-agent/
├── gmail-agent/              # Backend API (Python/FastAPI)
│   ├── server/
│   │   ├── api.py           # API routes
│   │   ├── actions.py       # Gmail operations
│   │   ├── auth.py          # OAuth authentication
│   │   ├── chatbot.py       # AI chat logic
│   │   ├── models.py        # Pydantic schemas
│   │   └── dependencies.py  # Dependency injection
│   ├── requirements.txt
│   └── Makefile
├── gmail-chatbot-ui/         # Frontend UI (Next.js)
│   └── src/app/
│       ├── page.tsx         # Chat interface
│       ├── layout.tsx       # Root layout
│       └── globals.css      # Tailwind styles
└── docs/                     # Documentation
    ├── README.md            # Full documentation
    ├── BACKEND.md           # Backend details
    ├── FRONTEND.md          # Frontend details
    ├── API.md               # API reference
    └── SETUP.md             # Setup guide
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **Composio API Key** - [Get it here](https://app.composio.dev)
- **Groq API Key** - [Get it here](https://console.groq.com)

### 1. Backend Setup

```bash
cd gmail-agent

# Copy environment file
cp .env.example .env
# Edit .env and add your COMPOSIO_API_KEY and GROQ_API_KEY

# Install and run (using Make)
make install
make dev

# Or manually:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn server.api:app --reload
```

Backend runs at: http://localhost:8000

### 2. Frontend Setup

```bash
cd gmail-chatbot-ui

npm install
npm run dev
```

Frontend runs at: http://localhost:3000

### 3. Connect Gmail

Before using the chatbot, connect your Gmail account:

```bash
# Check if connected
curl -X POST http://localhost:8000/connection/exists

# If not connected, create connection and follow the OAuth URL
curl -X POST http://localhost:8000/connection/create \
  -H "Content-Type: application/json" \
  -d '{"user_id": "default"}'
```

## 💬 Usage Examples

Open http://localhost:3000 and try these commands:

| Command | Action |
|---------|--------|
| "Send email to john@example.com about the meeting tomorrow" | Sends an email |
| "Create a draft for sarah@company.com regarding project update" | Creates a draft |
| "Show me my recent emails" | Fetches inbox |
| "Get the last 10 emails" | Fetches 10 emails |

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/connection/exists` | POST | Check Gmail connection |
| `/connection/create` | POST | Create new connection |
| `/connection/status` | POST | Get connection status |
| `/actions/send_email` | POST | Send an email |
| `/actions/fetch_emails` | POST | Fetch recent emails |
| `/actions/create_draft` | POST | Create email draft |
| `/chat` | POST | AI chat endpoint |

📖 Full API docs: http://localhost:8000/docs

## 📚 Documentation

For detailed documentation, see the [docs/](docs/) folder:

- [📖 Full Documentation](docs/README.md) - Complete project documentation
- [🔧 Backend Guide](docs/BACKEND.md) - Python backend details
- [🎨 Frontend Guide](docs/FRONTEND.md) - Next.js frontend details
- [📡 API Reference](docs/API.md) - Complete API documentation
- [⚙️ Setup Guide](docs/SETUP.md) - Detailed installation instructions
- [📸 Screenshots & Demo](docs/SCREENSHOTS.md) - Visual documentation

## 🛠️ Tech Stack

**Backend:**
- FastAPI - Web framework
- Composio - Gmail integration
- Groq - LLM API (Llama 3.3 70B)
- Pydantic - Data validation

**Frontend:**
- Next.js 16 - React framework
- React 19 - UI library
- Tailwind CSS 4 - Styling
- TypeScript - Type safety

## 📄 License

This project is for educational purposes.

## 🙏 Acknowledgments

- [Composio](https://composio.dev) - For the amazing tool integration platform
- [Groq](https://groq.com) - For fast LLM inference
- [FastAPI](https://fastapi.tiangolo.com) - For the excellent Python web framework
- [Next.js](https://nextjs.org) - For the React framework
