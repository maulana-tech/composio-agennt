# Gmail Agent API

AI Agent untuk Gmail + Social Media menggunakan Composio + Groq.

## Features

✅ **Email Management** - Send, fetch, create drafts via Gmail
✅ **Social Media Posting** - Twitter, Facebook, Instagram integration  
✅ **Image Generation** - Quote generator with custom designs
✅ **AI Chat** - Natural language interface with streaming
✅ **Multi-Agent Analysis** - Fact-checking and research capabilities

---

## Setup

```bash
# 1. Install dependencies
uv venv
uv pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Set: COMPOSIO_API_KEY, GROQ_API_KEY, GOOGLE_API_KEY, SERPER_API_KEY

# 3. Run server
uvicorn server.api:app --reload
```

**Server:** http://localhost:8000  
**Docs:** http://localhost:8000/docs

---

## API Endpoints

### 📧 Email (Gmail)
- `POST /actions/send_email` - Kirim email
- `POST /actions/fetch_emails` - Ambil email
- `POST /actions/create_draft` - Buat draft

### 🔗 Connection Management
- `POST /connection/exists` - Cek koneksi Gmail
- `POST /connection/create` - Buat koneksi baru
- `POST /connection/status` - Status koneksi

### 📱 Social Media Authentication
- `GET /toolkits/{user_id}/status` - Cek status semua platform
- `POST /toolkits/{user_id}/authorize/{toolkit}` - Authorize platform (twitter/facebook/instagram)

### 💬 Chat Interface
- `POST /chat` - Chat dengan AI (non-streaming)
- `POST /chat/stream` - Chat dengan streaming response

### 📊 Session Management
- `POST /sessions` - Create chat session
- `GET /sessions/{user_id}` - List user sessions
- `GET /session/{session_id}` - Get session with messages
- `DELETE /session/{session_id}` - Delete session

---

## Quick Examples

### Email
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Kirim email ke test@example.com tentang meeting",
    "user_id": "default",
    "auto_execute": true
  }'
```

### Social Media
```bash
# Create quote and post to Twitter
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Buat quote tentang leadership dan posting ke Twitter",
    "user_id": "default",
    "auto_execute": true
  }'

# Check social media connection status
curl http://localhost:8000/toolkits/default/status

# Authorize Twitter
curl -X POST http://localhost:8000/toolkits/default/authorize/twitter
```

---

## Documentation

📖 **[Social Media Authentication Guide](docs/SOCIAL_MEDIA_AUTH.md)**  
- In-chat vs Manual authentication
- OAuth flow
- Connection management
- Frontend integration examples

📖 **[Media Posting Guide](docs/MEDIA_POSTING_GUIDE.md)**  
- Twitter image/video posting
- Facebook photo posts  
- Instagram media upload
- Automatic file handling
- Complete examples

📖 **[Composio Auth Patterns](docs/COMPOSIO-AUTH.md)**  
- Manual authentication
- Session management
- Pre-verification patterns

---

## Testing

### Test Authentication
```bash
cd /Users/em/web/AI-Agent/composio-agent/gmail-agent
uv run python testing/test_auth.py
```

### Interactive Chat
```bash
uv run python testing/test_chat.py
```

---

## Tech Stack

- **AI/LLM**: Groq (Llama 3.3 70B)
- **Integrations**: Composio (Gmail, Twitter, Facebook, Instagram)
- **Framework**: FastAPI, LangChain
- **Search**: Google Custom Search, Serper
- **Image Gen**: Pillow, Google Gemini

---

## Environment Variables

```env
COMPOSIO_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here  # For Gemini image gen
SERPER_API_KEY=your_key_here  # For web search
```

---

## Agent Capabilities

The AI agent can:
- ✅ Send/manage emails via Gmail
- ✅ Generate custom quote images
- ✅ Post to Twitter with images
- ✅ Post to Facebook Pages with photos
- ✅ Post to Instagram (Business accounts)
- ✅ Search the web for current information
- ✅ Generate PDF reports
- ✅ Multi-agent fact-checking and research
- ✅ Maintain conversation context across sessions
