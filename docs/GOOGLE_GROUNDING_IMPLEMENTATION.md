# Dokumentasi Implementasi Google Gemini Grounding

## Ringkasan

Dokumentasi lengkap implementasi Google Gemini Grounding dengan Search untuk sistem AI Agent. Fitur ini menggantikan SERPER API dengan kemampuan real-time web search dan citations yang lebih akurat.

## Daftar Isi

1. [Apa itu Google Grounding?](#apa-itu-google-grounding)
2. [Arsitektur Sistem](#arsitektur-sistem)
3. [File yang Dimodifikasi](#file-yang-dimodifikasi)
4. [Implementasi Detail](#implementasi-detail)
5. [Konfigurasi](#konfigurasi)
6. [Penggunaan](#penggunaan)
7. [Fitur-fitur](#fitur-fitur)
8. [Troubleshooting](#troubleshooting)

---

## Apa itu Google Grounding?

Google Grounding adalah fitur Gemini API yang menghubungkan model AI dengan konten web real-time. Ini memungkinkan:

- **Real-time Information**: Akses data terbaru dari internet
- **Factual Accuracy**: Mengurangi halusinasi dengan grounding pada data web
- **Citations**: Setiap jawaban disertai sumber yang dapat diverifikasi
- **Automatic Search**: Model menentukan sendiri kapan perlu melakukan pencarian

### Keunggulan dibanding SERPER:

| Fitur | SERPER | Google Grounding |
|-------|--------|------------------|
| Real-time | Ya | Ya |
| Citations Otomatis | Tidak | Ya |
| Query Generation | Manual | Otomatis |
| Response Synthesis | Manual | Otomatis |
| Source Quality | Bervariasi | Prioritas authoritative |
| Pricing | Per query | Per search yang dieksekusi |

---

## Arsitektur Sistem

```
User Request
     ↓
Chatbot Agent
     ↓
Google Grounding Tool (google_search)
     ↓
Gemini API dengan Search
     ↓
Real-time Web Search
     ↓
Synthesized Response + Metadata
     ↓
Formatted Output (Chat/PDF/Email)
```

### Alur Kerja:

1. **User Prompt** → Agent menerima request
2. **Prompt Analysis** → Gemini menentukan apakah perlu search
3. **Google Search** → Otomatis generate & execute search queries
4. **Result Processing** → Sintesis informasi dari hasil pencarian
5. **Grounded Response** → Output dengan citations dan sources
6. **groundingMetadata** → Structured data dengan web results

---

## File yang Dimodifikasi

### 1. `gmail-agent/server/chatbot.py`

**Fungsi Baru:**
- `create_grounding_tools()` - Menggantikan `create_serper_tools()`
- `search_google()` - Tool untuk search dengan grounding

**Perubahan Utama:**
```python
# Sebelum (SERPER)
def create_serper_tools():
    serper_api_key = os.environ.get("SERPER_API_KEY")
    # HTTP request ke google.serper.dev

# Sesudah (Google Grounding)
def create_grounding_tools():
    from google import genai
    from google.genai import types
    
    grounding_tool = types.Tool(
        google_search=types.GoogleSearch()
    )
    
    config = types.GenerateContentConfig(
        tools=[grounding_tool]
    )
```

### 2. `gmail-agent/server/email_analysis_agents.py`

**WebResearchAgent yang Diperbarui:**

```python
class WebResearchAgent:
    def __init__(self, google_api_key: str):
        self.llm = ChatGoogleGenerativeAI(...)
        # Hapus: self.serper_api_key
        # Tambah: Google Grounding client
        
    async def conduct_research(self, research_plan: Dict) -> Dict:
        # Hapus: HTTP request ke Serper
        # Tambah: Gemini with grounding_tool
```

### 3. `gmail-agent/.env.example`

**Konfigurasi Environment:**

```bash
# Sebelum
SERPER_API_KEY=your-serper-api-key

# Sesudah  
GOOGLE_API_KEY=your-google-api-key  # WAJIB untuk Grounding
```

### 4. `gmail-agent/requirements.txt`

**Dependency Baru:**

```
google-genai>=1.0.0
```

---

## Implementasi Detail

### 1. Setup Google Grounding Client

```python
from google import genai
from google.genai import types

def create_grounding_tools():
    google_api_key = os.environ.get("GOOGLE_API_KEY")
    
    @tool
    def search_google(query: str) -> str:
        # Initialize Gemini client
        client = genai.Client(api_key=google_api_key)
        
        # Create grounding tool
        grounding_tool = types.Tool(
            google_search=types.GoogleSearch()
        )
        
        # Configure generation
        config = types.GenerateContentConfig(
            tools=[grounding_tool]
        )
        
        # Generate with grounding
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=query,
            config=config,
        )
        
        return response.text
```

### 2. Extract Citations dari Metadata

```python
if response.candidates[0].grounding_metadata:
    metadata = response.candidates[0].grounding_metadata
    
    # Search queries yang digunakan
    web_search_queries = metadata.web_search_queries
    
    # Web sources
    grounding_chunks = metadata.grounding_chunks
    for chunk in grounding_chunks:
        if chunk.web:
            uri = chunk.web.uri
            title = chunk.web.title
    
    # Text segments dengan citations
    grounding_supports = metadata.grounding_supports
    for support in grounding_supports:
        segment_text = support.segment.text
        chunk_indices = support.grounding_chunk_indices
```

### 3. Format Response dengan Citations

```python
def add_citations(response):
    text = response.text
    supports = response.candidates[0].grounding_metadata.grounding_supports
    chunks = response.candidates[0].grounding_metadata.grounding_chunks
    
    for support in supports:
        end_index = support.segment.end_index
        citation_links = []
        
        for i in support.grounding_chunk_indices:
            if i < len(chunks):
                uri = chunks[i].web.uri
                citation_links.append(f"[{i + 1}]({uri})")
        
        citation_string = ", ".join(citation_links)
        text = text[:end_index] + citation_string + text[end_index:]
    
    return text
```

---

## Konfigurasi

### 1. Environment Variables

Tambahkan ke file `.env`:

```bash
# Google API Key (WAJIB)
GOOGLE_API_KEY=your-google-api-key-here

# Model Configuration (Optional)
GEMINI_MODEL=gemini-2.0-flash  # Default model for grounding
```

### 2. Mendapatkan Google API Key

1. Kunjungi [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Login dengan akun Google
3. Klik "Create API Key"
4. Copy API key ke file `.env`

### 3. Model yang Didukung

| Model | Grounding Support | Notes |
|-------|-------------------|-------|
| gemini-2.0-flash | ✅ | Recommended, fastest |
| gemini-2.5-flash | ✅ | Newer version |
| gemini-2.5-pro | ✅ | Higher quality |

**Catatan:** Gunakan `google_search` tool (bukan `google_search_retrieval` yang deprecated)

---

## Penggunaan

### 1. Basic Search

```python
# Tool akan otomatis tersedia di agent
response = search_google("Who won the euro 2024?")
```

Output akan mencakup:
- Jawaban faktual
- Citations [1], [2], [3]
- Links ke sources

### 2. Political Quotes Research

```python
query = "Prabowo quotes on defense policy 2024"
response = search_google(query)

# Output format:
"Spain won Euro 2024, defeating England 2-1 in the final.[1](https://...), [2](https://...)"
```

### 3. Web Research Agent

```python
# Inisialisasi dengan Google API Key
research_agent = WebResearchAgent(google_api_key="your-key")

# Conduct research dengan grounding
results = await research_agent.conduct_research({
    "search_queries": [
        "Prabowo economic policy 2024",
        "Indonesia defense budget latest"
    ]
})
```

---

## Fitur-fitur

### 1. Automatic Query Generation

Gemini secara otomatis memutuskan:
- Apakah perlu melakukan search
- Query apa yang perlu dijalankan
- Berapa banyak query (biasanya 1-3 untuk satu prompt)

### 2. Real-Time Web Content

Akses informasi terbaru:
- Berita terkini
- Update politik real-time
- Data ekonomi terbaru
- Social media posts

### 3. Structured Citations

Setiap response mencakup:
```json
{
  "groundingMetadata": {
    "webSearchQueries": ["query 1", "query 2"],
    "groundingChunks": [
      {
        "web": {
          "uri": "https://example.com",
          "title": "Source Title"
        }
      }
    ],
    "groundingSupports": [
      {
        "segment": {
          "startIndex": 0,
          "endIndex": 100,
          "text": "Factual statement"
        },
        "groundingChunkIndices": [0, 1]
      }
    ]
  }
}
```

### 4. Source Quality Prioritization

Google secara otomatis memprioritaskan:
- Domain authoritative (.gov, .edu)
- News outlets kredibel
- Official sources
- Fact-checking sites

### 5. Multi-Language Support

Grounding bekerja dengan semua bahasa yang didukung Gemini, termasuk:
- Bahasa Indonesia
- English
- Chinese
- Japanese
- Dan lainnya

---

## Pricing

### Gemini 3 Models:
- **Billing**: Per search query yang dieksekusi
- **Multiple Queries**: Jika model menjalankan 2 search dalam satu request = 2 billable uses
- **Empty Queries**: Tidak dihitung dalam billing

### Gemini 2.5 atau Lebih Lama:
- **Billing**: Per prompt (tidak peduli berapa banyak search)

### Perkiraan Biaya:
- 1,000 search queries ≈ $35-50 USD (Gemini 3)
- Cek [Gemini API Pricing](https://ai.google.dev/gemini-api/docs/pricing) untuk update terbaru

---

## Troubleshooting

### 1. Error: "GOOGLE_API_KEY not found"

**Solusi:**
```bash
# Cek environment variable
echo $GOOGLE_API_KEY

# Set manual
export GOOGLE_API_KEY="your-key-here"
```

### 2. Error: "google_search tool not available"

**Penyebab:** Model yang digunakan tidak support grounding

**Solusi:**
```python
# Gunakan model yang kompatibel
model="gemini-2.0-flash"  # ✅ Support grounding

# Hindari model experimental/preview untuk production
```

### 3. Response tidak ada citations

**Penyebab:** 
- Query tidak memerlukan factual search
- Model menentukan tidak perlu search

**Cek:**
```python
if response.candidates[0].grounding_metadata:
    print("Grounding used")
else:
    print("No grounding - model answered from training data")
```

### 4. Slow Response Time

**Optimasi:**
- Gunakan `gemini-2.0-flash` (paling cepat)
- Limit jumlah query dalam satu request
- Cache hasil search untuk query berulang

### 5. Inaccurate Results

**Improvement:**
- Buat query lebih spesifik
- Tambahkan constraint seperti "latest", "official", "verified"
- Cross-check dengan multiple sources

---

## Best Practices

### 1. Query Optimization

```python
# ❌ Vague query
search_google("tell me about politics")

# ✅ Specific query  
search_google("Prabowo Subianto official statements on defense policy December 2024")
```

### 2. Error Handling

```python
@tool
def search_google(query: str) -> str:
    try:
        client = genai.Client(api_key=api_key)
        # ... setup grounding tool ...
        response = client.models.generate_content(...)
        
        # Check grounding
        if not response.candidates[0].grounding_metadata:
            return f"Response (no web search): {response.text}"
        
        return format_with_citations(response)
        
    except Exception as e:
        return f"Search error: {str(e)}"
```

### 3. Caching Strategy

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_search(query: str) -> str:
    return search_google(query)
```

---

## Perbandingan dengan SERPER

### SERPER (Sebelum):
```python
# Manual query construction
url = "https://google.serper.dev/search"
payload = {"q": query}
response = requests.post(url, json=payload, headers=headers)
results = response.json()

# Manual parsing
organic = results["organic"]
for item in organic:
    title = item["title"]
    link = item["link"]
    snippet = item["snippet"]

# Manual synthesis ke LLM
```

### Google Grounding (Sesudah):
```python
# Otomatis grounding_tool = types.Tool(google_search=types.GoogleSearch())
config = types.GenerateContentConfig(tools=[grounding_tool])

# Single API call, semua otomatis
response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=query,
    config=config
)

# Response sudah include citations
```

---

## Referensi

- [Google Grounding Documentation](https://ai.google.dev/gemini-api/docs/grounding)
- [Gemini API Pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Google AI Studio](https://makersuite.google.com/)
- [Gemini Cookbook - Search Grounding](https://colab.research.google.com/github/google-gemini/cookbook/blob/main/quickstarts/Search_Grounding.ipynb)

---

## Changelog

### v1.0.0 - Initial Implementation
- Menggantikan SERPER dengan Google Grounding
- Implementasi di chatbot.py dan email_analysis_agents.py
- Support untuk real-time web search
- Automatic citations dan source attribution

### v1.1.0 - Enhanced Features
- Political quotes research dengan social media
- PDF generation dengan structured formatting
- Email formatting dengan visual structure
- AI-generated quote images untuk PDF

---

**Dokumen ini diupdate terakhir:** February 2026

**Author:** AI Assistant
**Project:** Composio Gmail Agent dengan Google Grounding
