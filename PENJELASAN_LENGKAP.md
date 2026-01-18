# 📚 Penjelasan Lengkap Gmail Chatbot Project

Dokumentasi lengkap dalam Bahasa Indonesia untuk memahami setiap file, alasan penggunaannya, dan cara kerjanya.

---

## 📋 Daftar Isi

1. [Gambaran Umum Proyek](#gambaran-umum-proyek)
2. [Arsitektur Sistem](#arsitektur-sistem)
3. [Gmail Agent (Backend)](#gmail-agent-backend)
4. [Gmail Chatbot UI (Frontend)](#gmail-chatbot-ui-frontend)
5. [Cara Kerja Sistem](#cara-kerja-sistem)

---

## 🎯 Gambaran Umum Proyek

Proyek ini adalah **chatbot Gmail berbasis AI** yang memungkinkan pengguna untuk:

- ✉️ **Mengirim email** menggunakan perintah bahasa natural
- 📝 **Membuat draft email** dengan konten yang dihasilkan AI
- 📬 **Mengambil email terbaru** dari inbox Gmail

### Teknologi yang Digunakan

| Komponen | Teknologi | Alasan Penggunaan |
|----------|-----------|-------------------|
| **Backend** | FastAPI (Python) | Framework web modern, cepat, dan mudah untuk membuat REST API |
| **Frontend** | Next.js 16 (React) | Framework React terbaik untuk aplikasi web modern dengan SSR |
| **AI/LLM** | Groq (Llama 3.3 70B) | LLM yang sangat cepat dan gratis untuk parsing intent pengguna |
| **Gmail Integration** | Composio SDK | Platform yang menyederhanakan integrasi OAuth dan API Gmail |
| **Styling** | Tailwind CSS 4 | Framework CSS utility-first untuk styling yang cepat dan konsisten |

---

## 🏗️ Arsitektur Sistem

```
┌─────────────────────────────────────────────────────────────────┐
│                    PENGGUNA (Browser)                           │
│                    localhost:3000                               │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          │ HTTP POST /chat
                          │ {"message": "Kirim email ke..."}
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

### Struktur Folder Backend

```
gmail-agent/
├── .env                    # File konfigurasi API keys (RAHASIA!)
├── .env.example            # Template untuk .env
├── .gitignore              # File yang diabaikan Git
├── Makefile                # Perintah otomatis untuk setup & run
├── README.md               # Dokumentasi singkat backend
├── requirements.txt        # Daftar library Python yang dibutuhkan
├── test_api.sh             # Script untuk testing API
└── server/                 # Folder kode utama
    ├── __init__.py         # Penanda Python package
    ├── api.py              # ⭐ File utama - routing & endpoints
    ├── actions.py          # Fungsi eksekusi Gmail (kirim, ambil, draft)
    ├── auth.py             # Logika autentikasi OAuth Gmail
    ├── chatbot.py          # ⭐ Logika AI untuk parsing perintah
    ├── dependencies.py     # Dependency injection (Composio client)
    └── models.py           # Model data (request/response)
```

---

### 📄 File-File Backend - Penjelasan Detail



#### 1️⃣ `server/api.py` - Jantung Backend

**Fungsi:** File utama yang mendefinisikan semua endpoint API dan routing.

**Kenapa Pakai FastAPI?**
- Sangat cepat (setara dengan NodeJS dan Go)
- Otomatis generate dokumentasi API (Swagger)
- Type checking bawaan dengan Pydantic
- Async/await support untuk performa tinggi

**Endpoint yang Tersedia:**

| Endpoint | Method | Fungsi |
|----------|--------|--------|
| `/` | GET | Info API (versi, docs link) |
| `/health` | GET | Cek apakah server hidup |
| `/connection/exists` | POST | Cek apakah user sudah connect Gmail |
| `/connection/create` | POST | Buat koneksi OAuth Gmail baru |
| `/connection/status` | POST | Cek status koneksi |
| `/actions/send_email` | POST | Kirim email |
| `/actions/fetch_emails` | POST | Ambil email dari inbox |
| `/actions/create_draft` | POST | Buat draft email |
| `/chat` | POST | ⭐ **Endpoint utama** - Chat dengan AI |

**Cara Kerja CORS Middleware:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Izinkan frontend akses API
    allow_credentials=True,
    allow_methods=["*"],  # Izinkan semua HTTP methods
    allow_headers=["*"],  # Izinkan semua headers
)
```

**Kenapa Butuh CORS?**
- Frontend (port 3000) dan Backend (port 8000) beda domain
- Browser block request lintas domain secara default
- CORS middleware mengizinkan frontend akses backend

**Fungsi Penting - `validate_user`:**
```python
def validate_user(user_id: str, composio_client) -> str:
    """
    Memastikan user sudah connect Gmail sebelum eksekusi aksi
    Jika belum connect, lempar error 404
    """
    if check_connected_account_exists(composio_client, user_id):
        return user_id
    raise HTTPException(status_code=404, detail=f"No connection for user: {user_id}")
```

**Alasan:** Mencegah error saat user belum OAuth Gmail.



---

#### 2️⃣ `server/actions.py` - Eksekutor Gmail

**Fungsi:** Wrapper functions untuk menjalankan operasi Gmail via Composio SDK.

**Kenapa Pakai Composio?**
- Menyederhanakan integrasi dengan 100+ tools (Gmail, Slack, GitHub, dll)
- Handle OAuth authentication otomatis
- Satu API untuk banyak service
- Tidak perlu setup Gmail API credentials manual

**Fungsi Utama:**

```python
def execute_tool(composio_client, user_id, tool_slug, arguments):
    """
    Fungsi generic untuk eksekusi tool apapun di Composio
    
    Args:
        composio_client: Client Composio yang sudah terautentikasi
        user_id: ID user yang akan eksekusi tool
        tool_slug: Nama tool (contoh: "GMAIL_SEND_EMAIL")
        arguments: Parameter yang dibutuhkan tool
    
    Returns:
        Dict hasil eksekusi dari Composio
    """
    return composio_client.tools.execute(
        slug=tool_slug,
        arguments=arguments,
        user_id=user_id,
        dangerously_skip_version_check=True  # Skip version check untuk speed
    )
```

**3 Fungsi Gmail:**

1. **`send_email()`** - Kirim Email
```python
def send_email(composio_client, user_id, recipient_email, subject, body):
    return execute_tool(
        composio_client=composio_client,
        user_id=user_id,
        tool_slug="GMAIL_SEND_EMAIL",  # Tool slug dari Composio
        arguments={
            "recipient_email": recipient_email,
            "subject": subject,
            "body": body
        }
    )
```

2. **`fetch_emails()`** - Ambil Email
```python
def fetch_emails(composio_client, user_id, limit=5):
    return execute_tool(
        composio_client=composio_client,
        user_id=user_id,
        tool_slug="GMAIL_FETCH_EMAILS",
        arguments={"limit": limit}  # Berapa banyak email yang diambil
    )
```

3. **`create_draft()`** - Buat Draft
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

**Kenapa Pakai Pattern Ini?**
- DRY (Don't Repeat Yourself) - satu fungsi `execute_tool` untuk semua
- Mudah tambah tool baru (tinggal ganti `tool_slug`)
- Centralized error handling



---

#### 3️⃣ `server/chatbot.py` - Otak AI

**Fungsi:** Menggunakan Groq LLM untuk memahami perintah user dan menentukan aksi.

**Kenapa Pakai Groq?**
- **Sangat cepat** - 10x lebih cepat dari OpenAI
- **Gratis** - API key gratis dengan rate limit tinggi
- **Llama 3.3 70B** - Model open-source yang powerful
- **JSON mode** - Bisa force output dalam format JSON

**System Prompt - Instruksi untuk AI:**

```python
SYSTEM_PROMPT = """Kamu adalah asisten email. Parse pesan user dan tentukan action yang diinginkan.

Available actions:
- send_email: Kirim email (butuh: recipient_email, subject, body)
- create_draft: Buat draft email (butuh: recipient_email, subject, body)  
- fetch_emails: Ambil email terbaru (optional: limit)

Jika user tidak kasih email penerima, tanya dulu. Buat subject dan body yang profesional.

Respond dalam JSON:
{
    "action": "send_email|create_draft|fetch_emails",
    "recipient_email": "email@example.com",
    "recipient_name": "Nama",
    "subject": "Subject",
    "body": "Isi email",
    "limit": 5,
    "need_more_info": false,
    "question": "Pertanyaan jika butuh info"
}
"""
```

**Kenapa Pakai System Prompt?**
- Memberikan konteks dan instruksi ke AI
- Mendefinisikan format output yang diinginkan
- Membuat AI konsisten dalam response

**Fungsi Utama:**

1. **`parse_intent_with_groq()`** - Parse Perintah User

```python
async def parse_intent_with_groq(user_message, groq_api_key, conversation_history):
    """
    Mengirim pesan user ke Groq API dan mendapat intent dalam format JSON
    
    Flow:
    1. Buat messages array dengan system prompt + history + user message
    2. Kirim ke Groq API dengan model Llama 3.3 70B
    3. Force JSON output dengan response_format
    4. Parse JSON response
    
    Returns:
        Dict dengan action, recipient_email, subject, body, dll
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
                "temperature": 0.3,  # Low temperature = lebih konsisten
                "response_format": {"type": "json_object"}  # Force JSON
            },
            timeout=30.0
        )
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)
```

**Kenapa Async?**
- API call ke Groq bisa lambat (1-3 detik)
- Async memungkinkan server handle request lain sambil menunggu
- Performa lebih baik untuk concurrent users



2. **`execute_email_action()`** - Eksekusi Aksi

```python
async def execute_email_action(intent, user_id, base_url="http://localhost:8000"):
    """
    Mengeksekusi aksi berdasarkan intent yang sudah di-parse
    
    Flow:
    1. Ambil action dari intent (send_email, create_draft, fetch_emails)
    2. Call endpoint API yang sesuai dengan httpx
    3. Return hasil eksekusi
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
        # ... dst untuk action lain
        
        return response.json()
```

**Kenapa Call Internal API?**
- Separation of concerns - chatbot fokus ke AI logic
- Reusable - endpoint bisa dipanggil dari mana saja
- Consistent validation - semua request lewat Pydantic models

3. **`chat()`** - Fungsi Utama Chat

```python
async def chat(user_message, groq_api_key, user_id, conversation_history, auto_execute=True):
    """
    Fungsi utama yang menggabungkan parsing dan eksekusi
    
    Flow:
    1. Parse intent dari user message
    2. Cek apakah butuh info tambahan
    3. Jika auto_execute=True, langsung eksekusi aksi
    4. Return hasil
    
    Returns:
        Dict dengan type (question/action_result/intent_parsed) dan data
    """
    # 1. Parse intent
    intent = await parse_intent_with_groq(user_message, groq_api_key, conversation_history)
    
    # 2. Cek butuh info tambahan
    if intent.get("need_more_info"):
        return {
            "type": "question",
            "message": intent.get("question", "Bisa kasih info lebih detail?"),
            "intent": intent
        }
    
    # 3. Auto execute jika enabled
    if auto_execute and intent.get("action"):
        result = await execute_email_action(intent, user_id)
        return {
            "type": "action_result",
            "action": intent["action"],
            "intent": intent,
            "result": result
        }
    
    # 4. Return parsed intent saja
    return {"type": "intent_parsed", "intent": intent}
```

**3 Tipe Response:**
- `question` - AI butuh info tambahan dari user
- `action_result` - Aksi sudah dieksekusi, ini hasilnya
- `intent_parsed` - Intent sudah di-parse tapi belum dieksekusi



---

#### 4️⃣ `server/auth.py` - Autentikasi Gmail

**Fungsi:** Mengelola OAuth authentication dengan Gmail via Composio.

**Kenapa Butuh OAuth?**
- Gmail API butuh izin user untuk akses email
- OAuth adalah standar industri untuk authorization
- User tidak perlu kasih password ke aplikasi kita
- Lebih aman - token bisa di-revoke kapan saja

**Fungsi-Fungsi:**

1. **`fetch_auth_config()`** - Ambil Konfigurasi Auth

```python
def fetch_auth_config(composio_client):
    """
    Cek apakah sudah ada auth config untuk Gmail di Composio
    
    Returns:
        Auth config object jika ada, None jika tidak
    """
    auth_configs = composio_client.auth_configs.list()
    for auth_config in auth_configs.items:
        if auth_config.toolkit == "GMAIL":
            return auth_config
    return None
```

2. **`create_auth_config()`** - Buat Konfigurasi Auth Baru

```python
def create_auth_config(composio_client):
    """
    Membuat auth config baru dengan custom Gmail OAuth credentials
    
    Butuh:
        - GMAIL_CLIENT_ID (dari Google Cloud Console)
        - GMAIL_CLIENT_SECRET (dari Google Cloud Console)
    
    Returns:
        Auth config object yang baru dibuat
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

**Catatan:** Jika tidak set custom credentials, Composio akan pakai default mereka.

3. **`create_connection()`** - Inisiasi OAuth Flow

```python
def create_connection(composio_client, user_id, auth_config_id=None):
    """
    Memulai OAuth flow untuk user
    
    Flow:
    1. Cari atau buat auth config
    2. Inisiasi connection dengan Composio
    3. Return connection object dengan redirect_url
    4. User klik redirect_url untuk authorize
    5. Setelah authorize, connection jadi ACTIVE
    
    Returns:
        Connection object dengan:
        - id: connection_id untuk tracking
        - redirect_url: URL untuk OAuth authorization
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



4. **`check_connected_account_exists()`** - Cek Koneksi Aktif

```python
def check_connected_account_exists(composio_client, user_id):
    """
    Mengecek apakah user sudah punya koneksi Gmail yang aktif
    
    Returns:
        True jika ada koneksi ACTIVE, False jika tidak
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

**Kenapa Cek Status ACTIVE?**
- Connection bisa dalam status: INITIATED, ACTIVE, FAILED, REVOKED
- Hanya ACTIVE yang bisa dipakai untuk eksekusi tools
- Mencegah error saat user belum complete OAuth

5. **`get_connection_status()`** - Ambil Status Koneksi

```python
def get_connection_status(composio_client, connection_id):
    """
    Mendapatkan detail status dari connection tertentu
    
    Returns:
        Connection object dengan status dan detail lainnya
    """
    return composio_client.connected_accounts.get(connection_id=connection_id)
```

**Use Case:** Polling untuk cek apakah user sudah complete OAuth.

---

#### 5️⃣ `server/models.py` - Data Models

**Fungsi:** Mendefinisikan struktur data untuk request dan response menggunakan Pydantic.

**Kenapa Pakai Pydantic?**
- **Type validation** - otomatis validasi tipe data
- **Auto documentation** - FastAPI generate docs dari models
- **Serialization** - convert Python objects ke JSON otomatis
- **IDE support** - autocomplete dan type hints

**Request Models:**

```python
class SendEmailRequest(BaseModel):
    """Model untuk request kirim email"""
    user_id: str = Field(default="default")
    recipient_email: str  # Required
    subject: str          # Required
    body: str             # Required

class FetchEmailsRequest(BaseModel):
    """Model untuk request ambil email"""
    user_id: str = Field(default="default")
    limit: int = Field(default=5, ge=1, le=50)  # Min 1, Max 50

class ChatRequest(BaseModel):
    """Model untuk request chat"""
    message: str                                    # Required
    user_id: str = Field(default="default")
    auto_execute: bool = Field(default=True)       # Auto eksekusi aksi
    conversation_history: Optional[List[dict]] = None  # Chat history
```

**Response Models:**

```python
class ToolExecutionResponse(BaseModel):
    """Model untuk response eksekusi tool"""
    successful: bool              # Berhasil atau tidak
    data: Optional[Any] = None    # Data hasil jika berhasil
    error: Optional[str] = None   # Error message jika gagal

class CreateConnectionResponse(BaseModel):
    """Model untuk response create connection"""
    connection_id: str    # ID untuk tracking
    redirect_url: str     # URL untuk OAuth
```

**Keuntungan Pakai Models:**
- Request otomatis divalidasi sebelum masuk handler
- Response otomatis di-serialize ke JSON
- Error message jelas jika data tidak valid
- Dokumentasi API otomatis ter-generate



---

#### 6️⃣ `server/dependencies.py` - Dependency Injection

**Fungsi:** Menyediakan Composio client sebagai dependency untuk FastAPI.

**Kenapa Pakai Dependency Injection?**
- **Singleton pattern** - satu instance client untuk semua request
- **Clean code** - tidak perlu create client di setiap function
- **Testable** - mudah mock untuk testing
- **Efficient** - tidak create connection baru setiap request

```python
_composio_client: Composio | None = None  # Global variable

def provide_composio_client() -> Composio:
    """
    Factory function yang return Composio client
    
    Pattern: Singleton
    - Cek apakah client sudah ada
    - Jika belum, create baru dengan API key dari .env
    - Jika sudah, return yang existing
    
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

# Type alias untuk dependency injection
ComposioClient = Annotated[Composio, Depends(provide_composio_client)]
```

**Cara Pakai di Endpoint:**

```python
@app.post("/connection/exists")
def connection_exists(composio_client: ComposioClient):
    # composio_client otomatis di-inject oleh FastAPI
    # Tidak perlu manual create atau pass
    exists = check_connected_account_exists(composio_client, "default")
    return {"exists": exists}
```

**Keuntungan:**
- Code lebih clean dan readable
- Satu source of truth untuk client
- Mudah ganti implementation untuk testing

---

#### 7️⃣ `requirements.txt` - Dependencies

**Fungsi:** Daftar semua library Python yang dibutuhkan project.

```txt
fastapi==0.115.6          # Web framework
uvicorn[standard]==0.34.0 # ASGI server untuk run FastAPI
composio==0.10.7          # SDK untuk Gmail integration
python-dotenv==1.0.1      # Load environment variables dari .env
pydantic==2.10.5          # Data validation
httpx==0.28.1             # Async HTTP client untuk call Groq API
```

**Kenapa Pakai Library Ini?**

| Library | Alasan |
|---------|--------|
| `fastapi` | Framework web modern, cepat, dengan auto docs |
| `uvicorn` | ASGI server production-ready untuk FastAPI |
| `composio` | Simplify integrasi dengan Gmail dan tools lain |
| `python-dotenv` | Load API keys dari .env file (security) |
| `pydantic` | Validation dan serialization otomatis |
| `httpx` | HTTP client async untuk call Groq API |

**Install Semua:**
```bash
pip install -r requirements.txt
```



---

#### 8️⃣ `Makefile` - Build Automation

**Fungsi:** Menyediakan perintah shortcut untuk setup dan run project.

**Kenapa Pakai Makefile?**
- Simplify perintah panjang jadi satu kata
- Konsisten - semua developer pakai perintah yang sama
- Dokumentasi - bisa lihat semua perintah available

**Perintah Available:**

```makefile
make env       # Buat virtual environment Python
make install   # Install semua dependencies
make run       # Run production server
make dev       # Run development server (auto-reload)
make clean     # Hapus venv dan cache files
```

**Contoh Implementation:**

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

**Keuntungan:**
- Developer baru tinggal run `make install` dan `make dev`
- Tidak perlu hafal perintah panjang
- Bisa tambah perintah custom (testing, deployment, dll)

---

#### 9️⃣ `.env` dan `.env.example`

**Fungsi:** Menyimpan konfigurasi rahasia (API keys).

**.env.example** (Template):
```bash
# Composio API Key (WAJIB!)
COMPOSIO_API_KEY=your-composio-api-key

# Groq API Key (WAJIB!)
GROQ_API_KEY=your-groq-api-key

# Gmail OAuth Credentials (OPTIONAL - untuk custom auth)
# GMAIL_CLIENT_ID=your-gmail-client-id
# GMAIL_CLIENT_SECRET=your-gmail-client-secret
```

**.env** (File Actual - JANGAN COMMIT!):
```bash
COMPOSIO_API_KEY=sk_composio_abc123xyz...
GROQ_API_KEY=gsk_groq_def456uvw...
```

**Kenapa Pakai .env?**
- **Security** - API keys tidak masuk Git repository
- **Flexibility** - beda environment bisa beda config
- **Best practice** - standar industri untuk manage secrets

**Cara Kerja:**
```python
from dotenv import load_dotenv
import os

load_dotenv()  # Load .env file
api_key = os.getenv("COMPOSIO_API_KEY")  # Ambil value
```

**PENTING:** 
- `.env` harus ada di `.gitignore`
- Jangan pernah commit API keys ke Git
- Share `.env.example` sebagai template



---

## 🎨 Gmail Chatbot UI (Frontend)

### Struktur Folder Frontend

```
gmail-chatbot-ui/
├── package.json            # Dependencies & scripts Node.js
├── next.config.ts          # Konfigurasi Next.js
├── tsconfig.json           # Konfigurasi TypeScript
├── postcss.config.mjs      # Konfigurasi PostCSS (untuk Tailwind)
├── eslint.config.mjs       # Konfigurasi ESLint (linting)
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

### 📄 File-File Frontend - Penjelasan Detail

#### 1️⃣ `src/app/page.tsx` - Komponen Chat Utama

**Fungsi:** Komponen React utama yang menampilkan interface chat dan handle interaksi user.

**Kenapa Pakai Next.js?**
- **React framework terbaik** - production-ready
- **Server-side rendering** - SEO friendly
- **File-based routing** - `page.tsx` otomatis jadi route `/`
- **Built-in optimization** - image, font, code splitting otomatis

**State Management:**

```typescript
interface Message {
  id: string;                    // Unique ID untuk setiap message
  role: "user" | "assistant";    // Siapa yang kirim
  content: string;               // Isi pesan
  action?: string;               // Aksi yang dilakukan (optional)
  success?: boolean;             // Status aksi (optional)
}

const [messages, setMessages] = useState<Message[]>([...]);  // Chat history
const [input, setInput] = useState("");                       // Input user saat ini
const [isLoading, setIsLoading] = useState(false);           // Loading state
const userId = "pg-test-a199d8f3-e74a-42e0-956b-b1fbb2808b58"; // User ID
```

**Kenapa Pakai useState?**
- React hooks untuk manage component state
- Re-render otomatis saat state berubah
- Simple dan powerful

**Fungsi Utama - `sendMessage()`:**

```typescript
const sendMessage = async () => {
  // 1. Validasi input
  if (!input.trim() || isLoading) return;

  // 2. Simpan input dan clear field
  const currentInput = input;
  setInput("");
  
  // 3. Tambah user message ke chat
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
    
    // 7. Format message berdasarkan response type
    let content = "";
    if (data.type === "action_result") {
      if (data.action === "send_email" && data.result?.successful) {
        content = `✅ Email terkirim!\n\n📧 ${data.intent.recipient_email}\n📝 ${data.intent.subject}`;
      }
      // ... handle action lain
    }
    
    // 8. Tambah assistant response ke chat
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
// Untuk send_email success
if (data.action === "send_email" && success) {
  content = `✅ Email terkirim!\n\n📧 ${data.intent.recipient_email}\n📝 ${data.intent.subject}\n\n${data.intent.body}`;
}

// Untuk fetch_emails success
else if (data.action === "fetch_emails" && success) {
  const emails = data.result?.data?.data?.messages || [];
  if (emails.length > 0) {
    content = `📬 ${emails.length} email:\n\n`;
    emails.forEach((email, i) => {
      content += `${i + 1}. ${email.subject}\n   ${email.sender}\n\n`;
    });
  } else {
    content = "📭 Tidak ada email.";
  }
}

// Untuk error
else {
  content = `❌ Gagal: ${data.result?.error || "Unknown error"}`;
}
```

**Auto-scroll ke Bottom:**

```typescript
const messagesEndRef = useRef<HTMLDivElement>(null);

useEffect(() => {
  messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
}, [messages]);  // Trigger setiap messages berubah
```

**Kenapa Butuh Ini?**
- Chat baru muncul di bottom
- User tidak perlu manual scroll
- UX lebih baik

**UI Components:**

1. **Header** - Judul dan status koneksi
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
        ? "bg-blue-600 text-white"           // User message (kanan, biru)
        : "bg-gray-800 text-gray-100"        // Assistant message (kiri, abu)
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

4. **Input Footer** - Text input dan tombol kirim
```tsx
<footer className="bg-gray-800 border-t border-gray-700 p-4">
  <input
    type="text"
    value={input}
    onChange={(e) => setInput(e.target.value)}
    onKeyDown={(e) => e.key === "Enter" && sendMessage()}
    placeholder="Ketik pesan..."
    disabled={isLoading}
  />
  <button
    onClick={sendMessage}
    disabled={isLoading || !input.trim()}
  >
    Kirim
  </button>
</footer>
```

**Kenapa Pakai Tailwind CSS?**
- **Utility-first** - styling langsung di JSX
- **Responsive** - mobile-friendly otomatis
- **Consistent** - design system built-in
- **Fast** - tidak perlu switch file CSS



---

#### 2️⃣ `src/app/layout.tsx` - Root Layout

**Fungsi:** Layout component yang wrap semua pages di aplikasi.

```typescript
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

// Load fonts dari Google Fonts
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
        {children}  {/* page.tsx akan render di sini */}
      </body>
    </html>
  );
}
```

**Kenapa Pakai Layout?**
- **Shared structure** - header, footer, fonts untuk semua pages
- **Performance** - fonts di-load sekali saja
- **Consistency** - semua pages pakai styling yang sama

**Font Loading:**
- `next/font/google` - optimize font loading otomatis
- `variable` - create CSS variable untuk font
- `antialiased` - smooth text rendering

---

#### 3️⃣ `src/app/globals.css` - Global Styles

**Fungsi:** CSS global untuk seluruh aplikasi menggunakan Tailwind CSS v4.

```css
@import "tailwindcss";  /* Import Tailwind CSS */

/* CSS Variables untuk theming */
:root {
  --background: #ffffff;
  --foreground: #171717;
}

/* Dark mode (otomatis detect dari system) */
@media (prefers-color-scheme: dark) {
  :root {
    --background: #0a0a0a;
    --foreground: #ededed;
  }
}

/* Theme configuration untuk Tailwind */
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

**Kenapa Pakai CSS Variables?**
- **Theming** - ganti warna dengan mudah
- **Dark mode** - support otomatis
- **Reusable** - pakai di mana saja

---

#### 4️⃣ `package.json` - Dependencies & Scripts

**Fungsi:** Konfigurasi project Node.js, dependencies, dan scripts.

```json
{
  "name": "gmail-chatbot-ui",
  "version": "0.1.0",
  "scripts": {
    "dev": "next dev",           // Development server
    "build": "next build",       // Build untuk production
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
    "@types/node": "^20",          // TypeScript types untuk Node
    "@types/react": "^19",         // TypeScript types untuk React
    "tailwindcss": "^4",           // CSS framework
    "typescript": "^5"             // Type checking
  }
}
```

**Kenapa Pakai Dependencies Ini?**

| Package | Alasan |
|---------|--------|
| `next` | Framework React terbaik, production-ready |
| `react` | Library UI paling populer |
| `tailwindcss` | CSS framework utility-first |
| `typescript` | Type safety, catch errors sebelum runtime |

**Scripts:**
```bash
npm run dev    # Start development server (localhost:3000)
npm run build  # Build untuk production
npm run start  # Run production server
npm run lint   # Check code quality
```



---

#### 5️⃣ `next.config.ts` - Konfigurasi Next.js

**Fungsi:** File konfigurasi untuk customize behavior Next.js.

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
};

export default nextConfig;
```

**Contoh Konfigurasi yang Bisa Ditambah:**
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

**Kenapa Butuh Config File?**
- Customize build process
- Set environment variables
- Configure image optimization
- Add redirects/rewrites

---

#### 6️⃣ `tsconfig.json` - Konfigurasi TypeScript

**Fungsi:** Konfigurasi compiler TypeScript.

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

**Kenapa Pakai TypeScript?**
- **Type safety** - catch errors sebelum runtime
- **Better IDE support** - autocomplete, refactoring
- **Self-documenting** - types sebagai dokumentasi
- **Refactoring confidence** - rename/move dengan aman

**Path Alias:**
```typescript
// Tanpa alias
import Button from '../../../components/Button';

// Dengan alias
import Button from '@/components/Button';
```

---

## 🔄 Cara Kerja Sistem End-to-End

### Flow 1: User Kirim Pesan Chat

```
1. USER mengetik: "Kirim email ke john@example.com tentang meeting besok"
   └─> Frontend (page.tsx)
       └─> sendMessage() dipanggil
           └─> POST http://localhost:8000/chat
               Body: {
                 "message": "Kirim email ke john@example.com...",
                 "user_id": "default",
                 "auto_execute": true
               }

2. BACKEND menerima request
   └─> api.py: @app.post("/chat")
       └─> chatbot.py: chat()
           └─> parse_intent_with_groq()
               └─> Call Groq API
                   └─> Groq LLM (Llama 3.3 70B) parse message
                       └─> Return JSON:
                           {
                             "action": "send_email",
                             "recipient_email": "john@example.com",
                             "subject": "Meeting Besok",
                             "body": "Halo John, ..."
                           }

3. BACKEND eksekusi aksi
   └─> chatbot.py: execute_email_action()
       └─> POST http://localhost:8000/actions/send_email
           └─> api.py: @app.post("/actions/send_email")
               └─> validate_user() - cek koneksi Gmail
                   └─> actions.py: send_email()
                       └─> composio_client.tools.execute("GMAIL_SEND_EMAIL")
                           └─> Composio API
                               └─> Gmail API
                                   └─> ✅ Email terkirim!

4. BACKEND return response
   └─> {
         "type": "action_result",
         "action": "send_email",
         "intent": {...},
         "result": {"successful": true, "data": {...}}
       }

5. FRONTEND terima response
   └─> page.tsx: sendMessage()
       └─> Format message: "✅ Email terkirim! 📧 john@example.com"
           └─> setMessages() - tambah ke chat
               └─> UI update - message muncul di chat
```



### Flow 2: First-Time Gmail Connection

```
1. USER pertama kali buka aplikasi
   └─> Frontend check connection
       └─> POST http://localhost:8000/connection/exists
           └─> Backend: check_connected_account_exists()
               └─> Return: {"exists": false}

2. USER perlu connect Gmail
   └─> Frontend atau manual call:
       └─> POST http://localhost:8000/connection/create
           Body: {"user_id": "default"}
           └─> Backend: auth.py: create_connection()
               └─> Composio: initiate connection
                   └─> Return: {
                         "connection_id": "abc123",
                         "redirect_url": "https://accounts.google.com/oauth/..."
                       }

3. USER klik redirect_url
   └─> Browser redirect ke Google OAuth
       └─> USER login dan authorize aplikasi
           └─> Google redirect kembali ke Composio
               └─> Composio update connection status: ACTIVE

4. USER kembali ke aplikasi
   └─> Connection sekarang ACTIVE
       └─> Bisa mulai kirim email, fetch emails, dll
```

### Flow 3: Fetch Emails

```
1. USER mengetik: "Ambil 5 email terbaru"
   └─> Frontend: POST /chat

2. BACKEND parse intent
   └─> Groq LLM return:
       {
         "action": "fetch_emails",
         "limit": 5
       }

3. BACKEND eksekusi
   └─> actions.py: fetch_emails(limit=5)
       └─> Composio: execute("GMAIL_FETCH_EMAILS")
           └─> Gmail API: get messages
               └─> Return: [
                     {
                       "subject": "Meeting Reminder",
                       "sender": "boss@company.com",
                       "preview": {...}
                     },
                     ...
                   ]

4. FRONTEND format dan display
   └─> "📬 5 email:
        1. Meeting Reminder
           boss@company.com
        2. ..."
```

---

## 🎯 Kesimpulan

### Kenapa Arsitektur Ini Bagus?

1. **Separation of Concerns**
   - Frontend fokus ke UI/UX
   - Backend fokus ke business logic
   - AI fokus ke intent parsing
   - Composio fokus ke Gmail integration

2. **Scalable**
   - Mudah tambah action baru (delete email, search, dll)
   - Mudah tambah tool lain (Slack, Calendar, dll)
   - Mudah tambah user authentication

3. **Maintainable**
   - Code terorganisir dengan baik
   - Setiap file punya tanggung jawab jelas
   - Type safety dengan TypeScript dan Pydantic

4. **Modern Tech Stack**
   - FastAPI - framework Python tercepat
   - Next.js - framework React terbaik
   - Groq - LLM tercepat
   - Composio - integrasi termudah

### Key Takeaways

| Komponen | Teknologi | Alasan |
|----------|-----------|--------|
| **Backend Framework** | FastAPI | Cepat, modern, auto docs |
| **Frontend Framework** | Next.js | Production-ready, SEO friendly |
| **AI/LLM** | Groq (Llama 3.3) | Sangat cepat, gratis |
| **Gmail Integration** | Composio | Simplify OAuth & API calls |
| **Styling** | Tailwind CSS | Utility-first, konsisten |
| **Type Safety** | TypeScript + Pydantic | Catch errors early |
| **State Management** | React useState | Simple, built-in |
| **HTTP Client** | httpx (backend), fetch (frontend) | Async, modern |

### Alur Data Lengkap

```
User Input → Frontend (React) → Backend API (FastAPI) → AI (Groq) → 
Backend Logic → Composio SDK → Gmail API → Response → 
Backend → Frontend → UI Update
```

### File Paling Penting

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

**Dibuat dengan ❤️ untuk membantu memahami arsitektur full-stack modern**
