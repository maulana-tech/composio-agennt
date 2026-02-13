# Diana Agent Integration Guide

Welcome! This guide outlines how to integrate the **Diana Agent ecosystem** into your systems with maximum efficiency.

## 🚀 Integration Options

### 1. Python SDK (Direct Integration)
The easiest way to use Diana is via the unified SDK. This is ideal if your system is built with Python and LangChain.

```python
from server.sdk import initialize_sdk

# 1. Initialize
sdk = initialize_sdk(google_api_key="your_key")

# 2. Use autonomous routing (Diana handles the logic)
response = await sdk.chat("Buatkan GIPA request untuk NSW Health", user_id="client_01")
print(response.message)

# 3. Or use the tools individually in your own LangChain Agent
tools = sdk.get_langchain_tools()
# ... plug into your AgentExecutor
```

### 2. REST API (Language Agnostic)
If you are using Node.js, Go, or a frontend framework, you can use the FastAPI backend.

- **Base URL**: `http://your-server-ip:8000`
- **Endpoints**:
    - `POST /chat`: General autonomous chat.
    - `POST /gipa/start`: Specialized GIPA workflow.
    - `POST /dossier/generate`: specialized research.
    - `GET /connections/{user_id}`: Manage user integrations (Gmail, Social).

### 3. Modular Tool Injection
You can import specific tool groups if you only need certain features:

```python
from server.tools import get_gipa_tools, get_social_media_tools

gipa_tools = get_gipa_tools()
social_tools = get_social_media_tools()
```

## 🛠 Prerequisites

1. **Environment Variables**: Ensure the following are set on your server:
   - `GOOGLE_API_KEY`: For Gemini models.
   - `GROQ_API_KEY`: (Optional) For high-speed llama3 models.
   - `COMPOSIO_API_KEY`: For tool execution.
   - `SERPER_API_KEY`: For web research.

2. **Dependencies**: Use `uv` for fast installation:
   ```bash
   uv sync
   ```

## 🔒 Security & Scaling
- **Session ID**: Always provide a `session_id` in `/chat` to maintain multi-turn context.
- **User ID**: Pass unique `user_id` to ensure workers use the correct account credentials.
- **Stateless**: The agents are designed to be stateless (persisted in DB), allowing easy horizontal scaling.

---
*Diana Agent System - Optimized for maulana-tech.*
