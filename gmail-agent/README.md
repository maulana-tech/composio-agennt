# Gmail Agent API

Gmail API menggunakan Composio + Groq (tanpa OpenAI).

## Setup

```bash
cp .env.example .env
# Set COMPOSIO_API_KEY dan GROQ_API_KEY

uv venv
uv pip install -r requirements.txt
uvicorn server.api:app --reload
```

## Endpoints

### Connection
- `POST /connection/exists` - Cek koneksi
- `POST /connection/create` - Buat koneksi baru
- `POST /connection/status` - Status koneksi

### Actions
- `POST /actions/send_email` - Kirim email
- `POST /actions/fetch_emails` - Ambil email
- `POST /actions/create_draft` - Buat draft

### Chat
- `POST /chat` - Chat dengan AI

## Example

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Kirim email ke test@example.com tentang meeting", "user_id": "default"}'
```

Docs: http://localhost:8000/docs
