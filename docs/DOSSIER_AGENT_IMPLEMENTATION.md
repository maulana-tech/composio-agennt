# Dossier Agent - Implementation Guide

Dokumentasi lengkap implementasi **Dossier Agent** untuk pembuatan profil riset komprehensif tentang seseorang sebelum pertemuan bisnis, dengan analisis strategis dan rekomendasi pendekatan.

---

## Overview

Dossier Agent adalah sistem intelligence multi-komponen yang mengotomatisasi pengumpulan data, sintesis riset, dan analisis strategis tentang seseorang. Agent ini menghasilkan dokumen Markdown terstruktur yang berisi profil biografi, sorotan karier, analisis jaringan, dan strategi pertemuan.

### Tujuan

Menghasilkan dossier yang:
- Memberikan gambaran lengkap tentang seseorang berdasarkan data publik (web + LinkedIn)
- Menyintesis data mentah menjadi insight terstruktur menggunakan AI
- Menganalisis strategi meeting: conversation starters, common ground, topik yang harus dihindari
- Mendukung self-lookup (profil sendiri) via Composio LinkedIn API
- Bisa di-update dengan konteks tambahan tanpa mengulang pengumpulan data

---

## Struktur File

```
gmail-agent/server/tools/dossier_agent/
├── __init__.py                  # Exports 28 public symbols
├── dossier_agent.py             # Orchestrator + 5 LangChain tools + session management
├── data_collector.py            # SerperClient + LinkedInScraper + ComposioLinkedInClient + DataCollector
├── research_synthesizer.py      # Gemini 2.0 Flash synthesis (temp=0.1)
├── strategic_analyzer.py        # Gemini 2.0 Flash strategy (temp=0.3)
├── dossier_generator.py         # Markdown document assembly dari 12+ sections
├── exceptions.py                # DossierError hierarchy dengan stage attribute
└── templates/
    ├── __init__.py
    └── dossier_template.py      # Section templates + 12 builder functions
```

**Total:** 2507 baris kode, 14 class, 5 dataclass, ~54 functions/methods, ~23 constants.

---

## Arsitektur & Alur Kerja

```
User: "Buatkan dossier untuk [Nama] sebelum meeting"
     │
     ▼
┌──────────────────────────────────────────┐
│         DossierAgent (Orchestrator)       │  ← dossier_agent.py:110
│         Session Management + Pipeline     │
└────────────┬─────────────────────────────┘
             │
             ├── Stage 1: Data Collection        [status: "collecting"]
             │   │
             │   ▼
             │   ┌───────────────────────────────────────────────┐
             │   │            DataCollector                       │  ← data_collector.py:516
             │   │  (Parallel Async: Serper + LinkedIn)           │
             │   └──────────┬────────────────────────────────────┘
             │              │
             │              ├── SerperClient.search()     → 4 query categories (bio/news/statements/associates)
             │              ├── LinkedInScraper.scrape()   → Profile parsing (OR Composio self-lookup)
             │              ├── 3 Enhanced LinkedIn queries → profile/experience/education via Serper
             │              └── Deduplicate by URL          → CollectedData object
             │
             ├── Stage 2: Research Synthesis     [status: "researching"]
             │   │
             │   ▼
             │   ┌───────────────────────────────────────────────┐
             │   │         ResearchSynthesizer                    │  ← research_synthesizer.py:143
             │   │         (Gemini 2.0 Flash, temp=0.1)           │
             │   └──────────┬────────────────────────────────────┘
             │              │
             │              └── CollectedData → SynthesizedResearch
             │                  (bio, career, statements, associates, topics, personality)
             │
             ├── Stage 3: Strategic Analysis     [status: "analyzing"]
             │   │
             │   ▼
             │   ┌───────────────────────────────────────────────┐
             │   │         StrategicAnalyzer                      │  ← strategic_analyzer.py:150
             │   │         (Gemini 2.0 Flash, temp=0.3)           │
             │   └──────────┬────────────────────────────────────┘
             │              │
             │              └── SynthesizedResearch + meeting_context → StrategicInsights
             │                  (relationship map, conversation starters, common ground, meeting strategy)
             │
             └── Stage 4: Document Generation    [status: "completed"]
                 │
                 ▼
                 ┌───────────────────────────────────────────────┐
                 │         DossierGenerator                       │  ← dossier_generator.py:31
                 │         (Template Assembly: 12+ sections)      │
                 └──────────┬────────────────────────────────────┘
                            │
                            └── SynthesizedResearch + StrategicInsights → Markdown Document
```

### Update Flow (Tanpa Ulang Data Collection)

```
User: "Tambahkan konteks: ini meeting untuk kolaborasi riset"
     │
     ▼
dossier_update(additional_context, dossier_id)
     │
     ├── Skip Stage 1 (gunakan collected_data yang sudah ada)
     ├── Re-run Stage 2: ResearchSynthesizer.synthesize()
     ├── Re-run Stage 3: StrategicAnalyzer.analyze() ← dengan konteks baru
     └── Re-run Stage 4: DossierGenerator.generate()
```

---

## Komponen Detail

### 1. DossierAgent (Orchestrator)

**File:** `dossier_agent.py:110`

Orchestrator utama yang mengelola session state dan mengkoordinasikan seluruh 4-stage pipeline.

#### Session Management

Session disimpan in-memory per-process menggunakan dictionary:

```python
# dossier_agent.py:48
_dossier_sessions: Dict[str, Dict[str, Any]] = {}

# dossier_agent.py:51
SESSION_TTL_SECONDS = 24 * 60 * 60  # 24 jam

# Struktur setiap session:
{
    "name": str,                           # Nama target
    "linkedin_url": str,                   # URL LinkedIn target
    "meeting_context": str,                # Konteks meeting
    "status": str,                         # collecting | researching | analyzing | completed | error
    "document": None | str,                # Generated Markdown document
    "collected_data": None | CollectedData,
    "synthesized_data": None | SynthesizedResearch,
    "strategic_insights": None | StrategicInsights,
    "error": None | str,                   # Error message jika gagal
    "created_at": float,                   # Timestamp untuk TTL
}
```

#### Session Helper Functions

| Function | Line | Deskripsi |
|---|---|---|
| `_get_session(dossier_id)` | 54 | Ambil session, return `None` jika expired atau tidak ada |
| `_create_session(dossier_id, ...)` | 62 | Buat session baru dengan status `"collecting"` |
| `_clear_session(dossier_id)` | 86 | Hapus session dari memory |
| `_cleanup_expired_sessions()` | 91 | Bersihkan semua session yang sudah expired (dipanggil di awal `generate_dossier`) |

#### Lifecycle Methods

| Method | Line | Deskripsi |
|---|---|---|
| `generate_dossier()` | 133 | Full pipeline: collect → synthesize → analyze → generate |
| `get_status()` | 206 | Cek status session + return data parsial jika ada |
| `update_dossier()` | 232 | Re-run stages 2-4 dengan konteks tambahan (skip data collection) |

#### Alur `generate_dossier()`:

```
1. _cleanup_expired_sessions()               ← Bersihkan session kadaluarsa
2. _create_session(dossier_id, ...)          ← Status: "collecting"
3. collector.collect(name, linkedin_url, ...) ← Stage 1
4. session["status"] = "researching"
5. synthesizer.synthesize(collected_data)     ← Stage 2
6. session["status"] = "analyzing"
7. analyzer.analyze(synthesized, context)     ← Stage 3
8. generator.generate(synthesized, insights)  ← Stage 4
9. session["status"] = "completed"
10. Return document string

Error handling:
  - DossierCollectionError  → status = "error", stage = "collecting"
  - DossierSynthesisError   → status = "error", stage = "researching"
  - DossierAnalysisError    → status = "error", stage = "analyzing"
  - DossierGenerationError  → status = "error", stage = "generating"
```

#### Singleton Pattern

Agent di-instantiate sebagai singleton (lazy-initialized):

```python
# dossier_agent.py:289
_agent_instance: Optional[DossierAgent] = None

# dossier_agent.py:292
def _get_agent() -> DossierAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = DossierAgent()
    return _agent_instance
```

---

### 2. DataCollector

**File:** `data_collector.py:516`

Komponen pengumpul data yang menjalankan multiple search queries secara paralel menggunakan `asyncio.gather`.

#### Search Query Categories

**Serper Web Searches** (`SEARCH_QUERIES` — line 536):

| Kategori | Query Template | Deskripsi |
|---|---|---|
| `bio` | `"{name}" biography OR profile OR about` | Info biografi umum |
| `news` | `"{name}" news OR interview OR announcement` | Berita & wawancara terkini |
| `statements` | `"{name}" said OR stated OR believes OR opinion` | Pernyataan & opini publik |
| `associates` | `"{name}" with OR alongside OR partnership OR collaboration` | Jaringan & asosiasi |

**Enhanced LinkedIn Searches** (`LINKEDIN_SEARCH_QUERIES` — line 544):

| Kategori | Query Template | Deskripsi |
|---|---|---|
| `profile` | `site:linkedin.com "{name}" profile` | Profil LinkedIn via Serper |
| `experience` | `site:linkedin.com "{name}" experience` | Pengalaman kerja |
| `education` | `site:linkedin.com "{name}" education` | Riwayat pendidikan |

#### Alur `collect()`:

```
collect(name, linkedin_url, is_self_lookup, composio_user_id)
     │
     ├── Branch A: LinkedIn Profile
     │   │
     │   ├── is_self_lookup = True?
     │   │   └── ComposioLinkedInClient.get_my_profile()  ← Composio LINKEDIN_GET_MY_INFO
     │   │
     │   └── is_self_lookup = False?
     │       └── LinkedInScraper.scrape_profile(linkedin_url)  ← HTTP scraping
     │
     ├── Branch B: Web Searches (Parallel)
     │   │
     │   └── asyncio.gather(
     │         SerperClient.search("bio query"),
     │         SerperClient.search("news query"),
     │         SerperClient.search("statements query"),
     │         SerperClient.search("associates query"),
     │       )
     │
     ├── Branch C: Enhanced LinkedIn Searches (Parallel)
     │   │
     │   └── asyncio.gather(
     │         SerperClient.search("profile query"),
     │         SerperClient.search("experience query"),
     │         SerperClient.search("education query"),
     │       )
     │   │
     │   └── _extract_from_serper_linkedin()  ← Parse snippets ke LinkedInProfile fields
     │
     └── Deduplicate by URL → Return CollectedData
```

#### Sub-Components

##### SerperClient (`data_collector.py:105`)

HTTP client untuk Google Serper API dengan in-memory caching.

| Property | Value |
|---|---|
| Base URL | `https://google.serper.dev/search` |
| Cache TTL | 3600 detik (1 jam) |
| Cache Key | SHA-256 dari `f"{query}:{num_results}"` |
| Default Results | 10 per query |

```python
# data_collector.py:116
def _cache_key(self, query: str, num_results: int) -> str:
    raw = f"{query}:{num_results}"
    return hashlib.sha256(raw.encode()).hexdigest()
```

Cache check terjadi sebelum setiap HTTP request. Jika cache hit dan belum expired, langsung return tanpa network call.

##### LinkedInScraper (`data_collector.py:205`)

HTTP scraper untuk profil LinkedIn publik. Menggunakan rotating user-agent headers.

| Method | Line | Deskripsi |
|---|---|---|
| `scrape_profile()` | 239 | Parse HTML → `LinkedInProfile` object |
| `scrape_profile_text()` | 324 | Ambil raw text dari halaman profil |

##### ComposioLinkedInClient (`data_collector.py:363`)

Client untuk akses LinkedIn via Composio API (digunakan untuk self-lookup).

| Method | Line | Deskripsi |
|---|---|---|
| `get_my_profile()` | 394 | Panggil `LINKEDIN_GET_MY_INFO` action via Composio |
| `_parse_composio_response()` | 429 | Parse response Composio → `LinkedInProfile` |

Digunakan ketika `is_self_lookup=True` — mengambil profil LinkedIn user sendiri tanpa scraping, menggunakan OAuth token dari Composio.

#### Deduplication

Setelah semua search selesai, hasil dideduplikasi berdasarkan URL untuk menghindari data duplikat dari query yang overlap.

---

### 3. ResearchSynthesizer

**File:** `research_synthesizer.py:143`

Menggunakan Gemini 2.0 Flash (temperature=0.1, rendah untuk akurasi) untuk mensintesis data mentah menjadi riset terstruktur.

#### Data Model: `SynthesizedResearch`

**File:** `research_synthesizer.py:31`

```python
@dataclass
class SynthesizedResearch:
    name: str = ""                    # Nama lengkap
    linkedin_url: str = ""            # URL LinkedIn
    current_role: str = ""            # Jabatan saat ini
    organization: str = ""            # Organisasi saat ini
    location: str = ""                # Lokasi
    biographical_summary: str = ""    # Ringkasan biografi (paragraph)
    career_highlights: list = []      # Sorotan karier (list of strings)
    recent_statements: list = []      # Pernyataan publik terkini
    known_associates: list = []       # Orang-orang yang terkait
    key_topics: list = []             # Topik yang sering dibahas
    education_summary: str = ""       # Ringkasan pendidikan
    personality_notes: str = ""       # Catatan kepribadian (dari cara komunikasi publik)
    online_presence: str = ""         # Kehadiran online (platform, aktivitas)
```

Memiliki method `to_dict()` (line 50) dan `from_dict()` classmethod (line 68) untuk serialisasi.

#### SYNTHESIS_PROMPT

**File:** `research_synthesizer.py:90` (spans lines 90-140)

System prompt yang menginstruksikan LLM untuk:
- Bertindak sebagai "intelligence analyst"
- Mengekstrak fakta yang bisa diverifikasi
- Tidak menebak atau mengasumsi
- Output dalam format JSON yang match dengan `SynthesizedResearch` fields
- Menyertakan sumber jika memungkinkan

#### Alur `synthesize()`:

```
CollectedData masuk
     │
     ▼
Build user prompt:
  - collected_data.to_dict() → JSON string
     │
     ▼
Kirim ke Gemini 2.0 Flash (temp=0.1)
  - system: SYNTHESIS_PROMPT
  - user: JSON collected data
     │
     ▼
Parse JSON response → SynthesizedResearch
     │
     ├── Success → Return SynthesizedResearch
     └── Failure → _fallback_synthesis()
```

#### Fallback Synthesis (`research_synthesizer.py:241`)

Jika LLM gagal (error atau response tidak bisa di-parse), menggunakan fallback yang:
- Mengambil `name` dan `linkedin_url` langsung dari `CollectedData`
- Mengambil data dari `LinkedInProfile` jika ada (headline, location, summary, experience, education, skills)
- Mengumpulkan snippets dari web results sebagai `biographical_summary`
- Menghasilkan `SynthesizedResearch` dengan data minimal tapi tetap berguna

---

### 4. StrategicAnalyzer

**File:** `strategic_analyzer.py:150`

Menggunakan Gemini 2.0 Flash (temperature=0.3, sedikit lebih tinggi untuk kreativitas strategis) untuk menganalisis data sintesis dan menghasilkan insight strategis.

#### Data Model: `StrategicInsights`

**File:** `strategic_analyzer.py:28`

```python
@dataclass
class StrategicInsights:
    relationship_map: List[Dict[str, str]] = []    # Peta hubungan (name, role, connection_type)
    conversation_starters: List[str] = []           # Pembuka percakapan yang relevan
    common_ground: List[str] = []                   # Kesamaan yang bisa dimanfaatkan
    topics_to_avoid: List[str] = []                 # Topik sensitif yang harus dihindari
    meeting_strategy: str = ""                      # Strategi meeting keseluruhan (paragraph)
    key_motivations: List[str] = []                 # Motivasi utama target
    negotiation_style: str = ""                     # Gaya negosiasi yang diperkirakan
    recommended_approach: str = ""                   # Pendekatan yang direkomendasikan
```

Memiliki method `to_dict()` (line 41) dan `from_dict()` classmethod (line 54) untuk serialisasi.

#### STRATEGY_PROMPT

**File:** `strategic_analyzer.py:71` (spans lines 71-142)

System prompt yang menginstruksikan LLM untuk:
- Bertindak sebagai "strategic advisor"
- Menganalisis data riset dalam konteks meeting yang diberikan
- Menghasilkan actionable insights
- Output dalam format JSON yang match dengan `StrategicInsights` fields

#### Alur `analyze()`:

```
SynthesizedResearch + meeting_context masuk
     │
     ▼
Build user prompt:
  - synthesized_data.to_dict() → JSON
  - meeting_context string
     │
     ▼
Kirim ke Gemini 2.0 Flash (temp=0.3)
  - system: STRATEGY_PROMPT
  - user: JSON research + meeting context
     │
     ▼
Parse JSON response → StrategicInsights
     │
     ├── Success → Return StrategicInsights
     └── Failure → _fallback_insights()
```

#### Fallback Insights (`strategic_analyzer.py:264`)

Jika LLM gagal, menghasilkan `StrategicInsights` dengan:
- `relationship_map` dari `known_associates`
- `conversation_starters` dari `key_topics`
- Generic `meeting_strategy` dan `recommended_approach`
- Empty `topics_to_avoid` dan `common_ground`

---

### 5. DossierGenerator

**File:** `dossier_generator.py:31`

Generator dokumen yang menyusun Markdown document dari `SynthesizedResearch` + `StrategicInsights` menggunakan template builders.

#### Alur `generate()` (line 37):

```python
async def generate(self, synthesized_data, strategic_insights) -> str:
```

Urutan assembly dokumen:

```
1. CONFIDENTIAL_HEADER               ← Header rahasia
2. DOSSIER_TITLE                     ← Judul dengan nama target
3. SECTION_DIVIDER
4. build_biographical_section()       ← Biografi + role + org + location
5. SECTION_DIVIDER
6. build_career_section()             ← Career highlights (bullet list)
7. build_education_section()          ← Ringkasan pendidikan
8. SECTION_DIVIDER
9. build_statements_section()         ← Pernyataan publik (bullet list)
10. SECTION_DIVIDER
11. build_associates_section()        ← Known associates (bullet list)
12. build_relationship_map_section()  ← Relationship map (table format)
13. SECTION_DIVIDER
14. build_strategic_section()         ← Meeting strategy + negotiation style + approach
15. build_conversation_starters_section()
16. build_common_ground_section()
17. build_topics_to_avoid_section()
18. build_motivations_section()
19. SECTION_DIVIDER
20. build_online_presence_section()   ← Online presence summary
```

Setiap builder function mengecek apakah data tersedia; jika tidak, section tersebut dilewati (return empty string).

---

### 6. Templates

**File:** `templates/dossier_template.py` (262 lines)

Berisi 15 template constants dan 12 builder functions.

#### Template Constants

| Constant | Line | Deskripsi |
|---|---|---|
| `DOSSIER_TITLE` | 14 | `# Dossier: {name}` |
| `SECTION_DIVIDER` | 16 | `---` |
| `CONFIDENTIAL_HEADER` | 18 | Header "CONFIDENTIAL" dengan timestamp |
| `BIOGRAPHICAL_SECTION` | 28 | Template biografi (name, role, org, location, summary) |
| `CAREER_SECTION` | 38 | Template career highlights |
| `EDUCATION_SECTION` | 44 | Template pendidikan |
| `STATEMENTS_SECTION` | 50 | Template pernyataan publik |
| `ASSOCIATES_SECTION` | 56 | Template known associates |
| `RELATIONSHIP_MAP_SECTION` | 62 | Template peta hubungan |
| `STRATEGIC_SECTION` | 68 | Template strategi (strategy + negotiation + approach) |
| `CONVERSATION_STARTERS_SECTION` | 78 | Template pembuka percakapan |
| `COMMON_GROUND_SECTION` | 84 | Template kesamaan |
| `TOPICS_TO_AVOID_SECTION` | 90 | Template topik yang dihindari |
| `MOTIVATIONS_SECTION` | 96 | Template motivasi |
| `ONLINE_PRESENCE_SECTION` | 102 | Template kehadiran online |

#### Builder Functions

| Function | Line | Input | Output |
|---|---|---|---|
| `build_biographical_section(data)` | 114 | `SynthesizedResearch` | Biografi lengkap atau `""` |
| `build_career_section(data)` | 126 | `SynthesizedResearch` | Career highlights list atau `""` |
| `build_education_section(data)` | 135 | `SynthesizedResearch` | Education summary atau `""` |
| `build_statements_section(data)` | 143 | `SynthesizedResearch` | Statements list atau `""` |
| `build_associates_section(data)` | 166 | `SynthesizedResearch` | Associates list atau `""` |
| `build_relationship_map_section(insights)` | 185 | `StrategicInsights` | Relationship table atau `""` |
| `build_strategic_section(insights)` | 209 | `StrategicInsights` | Strategy paragraph atau `""` |
| `build_conversation_starters_section(insights)` | 220 | `StrategicInsights` | Starters list atau `""` |
| `build_common_ground_section(insights)` | 229 | `StrategicInsights` | Common ground list atau `""` |
| `build_topics_to_avoid_section(insights)` | 238 | `StrategicInsights` | Avoid topics list atau `""` |
| `build_motivations_section(insights)` | 247 | `StrategicInsights` | Motivations list atau `""` |
| `build_online_presence_section(data)` | 256 | `SynthesizedResearch` | Online presence atau `""` |

Semua builder functions mengecek keberadaan data terlebih dahulu. Jika data kosong atau `None`, function mengembalikan string kosong sehingga section tidak muncul di dokumen final.

---

### 7. Exception Hierarchy

**File:** `exceptions.py`

Custom exception hierarchy dengan `stage` attribute untuk identifikasi tepat di stage mana error terjadi.

```
DossierError (base)                     ← exceptions.py:10
  │  ├── message: str
  │  └── stage: str
  │
  ├── DossierCollectionError            ← exceptions.py:18    stage = "collecting"
  ├── DossierSynthesisError             ← exceptions.py:25    stage = "researching"
  ├── DossierAnalysisError              ← exceptions.py:32    stage = "analyzing"
  ├── DossierGenerationError            ← exceptions.py:39    stage = "generating"
  └── DossierSessionError               ← exceptions.py:46    stage = "session"
```

Attribute `stage` memungkinkan API layer mengembalikan pesan error yang spesifik:

```python
except DossierError as e:
    return DossierResponse(
        status="error",
        message=f"Error during {e.stage}: {e.message}"
    )
```

---

## LangChain Tools (5 Tools)

Tools yang di-expose ke Main ReAct Agent via `get_dossier_tools()` (line 452):

### `dossier_check_status`

**File:** `dossier_agent.py:301`

Cek status sesi dossier. Dipanggil untuk melihat progress atau apakah dossier sudah selesai.

```python
@tool
async def dossier_check_status(dossier_id: str = "default") -> str:
```

**Return:** JSON string berisi `status`, `name`, `has_document`, partial data jika tersedia.

### `dossier_generate`

**File:** `dossier_agent.py:335`

Generate dossier lengkap. Menjalankan full 4-stage pipeline.

```python
@tool
async def dossier_generate(
    name: str,
    linkedin_url: str = "",
    meeting_context: str = "",
    is_self_lookup: bool = False,
    dossier_id: str = "default"
) -> str:
```

**Parameters:**
- `name` — Nama lengkap target (wajib)
- `linkedin_url` — URL profil LinkedIn (opsional, tapi sangat disarankan)
- `meeting_context` — Konteks meeting, misal "Business partnership discussion" (opsional)
- `is_self_lookup` — Jika `True`, gunakan Composio `LINKEDIN_GET_MY_INFO` alih-alih scraping
- `dossier_id` — ID unik session (default: `"default"`)

### `dossier_update`

**File:** `dossier_agent.py:380`

Update dossier yang sudah ada dengan konteks tambahan. Re-run stages 2-4 tanpa mengulang data collection.

```python
@tool
async def dossier_update(
    additional_context: str,
    dossier_id: str = "default"
) -> str:
```

### `dossier_get_document`

**File:** `dossier_agent.py:404`

Ambil dokumen dossier yang sudah di-generate.

```python
@tool
async def dossier_get_document(dossier_id: str = "default") -> str:
```

**Return:** Markdown document atau error message jika belum selesai.

### `dossier_delete`

**File:** `dossier_agent.py:431`

Hapus session dossier dari memory.

```python
@tool
async def dossier_delete(dossier_id: str = "default") -> str:
```

---

## REST API Endpoints

Semua endpoint didefinisikan di `server/api.py`:

| Method | Path | Line | Request Model | Deskripsi |
|---|---|---|---|---|
| `POST` | `/dossier/status` | 962 | `DossierStatusRequest` | Cek status session |
| `POST` | `/dossier/generate` | 985 | `DossierGenerateRequest` | Generate dossier (full pipeline) |
| `POST` | `/dossier/update` | 1017 | `DossierUpdateRequest` | Update dengan konteks tambahan |
| `GET` | `/dossier/{dossier_id}` | 1039 | Path parameter | Ambil dokumen yang sudah di-generate |
| `DELETE` | `/dossier/{dossier_id}` | 1067 | Path parameter | Hapus session |

### Request Models

**File:** `server/models.py`

```python
# models.py:189
class DossierGenerateRequest(BaseModel):
    name: str
    linkedin_url: str = ""
    meeting_context: str = ""
    dossier_id: str = Field(default="default")
    # Catatan: is_self_lookup TIDAK di-expose via REST API

# models.py:196
class DossierUpdateRequest(BaseModel):
    additional_context: str
    dossier_id: str = Field(default="default")

# models.py:201
class DossierStatusRequest(BaseModel):
    dossier_id: str = Field(default="default")

# models.py:205
class DossierResponse(BaseModel):
    status: str
    message: str
    # ... additional fields depending on endpoint
```

> **Catatan:** Parameter `is_self_lookup` tidak tersedia via REST API (`/dossier/generate`). Self-lookup hanya bisa dipanggil via LangChain tool `dossier_generate` dari chatbot agent.

---

## Session States

| Status | Deskripsi | Next Action | Set By |
|---|---|---|---|
| `collecting` | Sedang mengumpulkan data dari web & LinkedIn | Tunggu — otomatis lanjut ke `researching` | `generate_dossier()` awal |
| `researching` | Sedang mensintesis data dengan Gemini | Tunggu — otomatis lanjut ke `analyzing` | Setelah `collector.collect()` selesai |
| `analyzing` | Sedang menganalisis strategi meeting | Tunggu — otomatis lanjut ke `completed` | Setelah `synthesizer.synthesize()` selesai |
| `completed` | Dossier selesai, dokumen tersedia | `dossier_get_document()` atau `dossier_update()` | Setelah `generator.generate()` selesai |
| `error` | Terjadi error di salah satu stage | Periksa `session["error"]` untuk detail | Catch block di `generate_dossier()` |

---

## Caching Mechanisms

### SerperClient Cache

**File:** `data_collector.py:111-131`

| Property | Value |
|---|---|
| Storage | In-memory dictionary: `self._cache` |
| Key | SHA-256 hash dari `f"{query}:{num_results}"` |
| TTL | 3600 detik (1 jam) |
| Granularity | Per-query |
| Invalidation | Time-based (cek `time.time() - timestamp > CACHE_TTL`) |

```python
# data_collector.py:121
def _get_cached(self, key: str) -> Optional[List[WebSearchResult]]:
    if key in self._cache:
        results, timestamp = self._cache[key]
        if time.time() - timestamp < self.CACHE_TTL:
            return results
    return None
```

### Session TTL

**File:** `dossier_agent.py:51,91`

| Property | Value |
|---|---|
| TTL | 86400 detik (24 jam) |
| Cleanup | Dipanggil di awal `generate_dossier()` |
| Mechanism | Iterasi semua sessions, hapus yang `time.time() - created_at > SESSION_TTL_SECONDS` |

---

## Error Handling Patterns

### Pipeline Error Handling

Setiap stage di `generate_dossier()` wrapped dalam try-except yang menangkap exception spesifik dan menyimpan error ke session:

```python
# Pattern di dossier_agent.py:133-204
async def generate_dossier(self, ...):
    try:
        # Stage 1: Collection
        collected_data = await self.collector.collect(...)
        session["collected_data"] = collected_data
    except Exception as e:
        session["status"] = "error"
        session["error"] = str(e)
        raise DossierCollectionError(str(e))

    try:
        # Stage 2: Synthesis
        session["status"] = "researching"
        synthesized = await self.synthesizer.synthesize(collected_data)
    except Exception as e:
        session["status"] = "error"
        session["error"] = str(e)
        raise DossierSynthesisError(str(e))

    # ... dan seterusnya untuk stage 3 & 4
```

### Fallback Pattern

Kedua LLM-powered components memiliki fallback:

| Component | Fallback Method | Line | Trigger |
|---|---|---|---|
| `ResearchSynthesizer` | `_fallback_synthesis()` | 241 | LLM error atau JSON parse failure |
| `StrategicAnalyzer` | `_fallback_insights()` | 264 | LLM error atau JSON parse failure |

Fallback menghasilkan output yang tetap berguna (walaupun kurang kaya) dari data yang sudah ada, sehingga pipeline tidak gagal total hanya karena LLM bermasalah.

---

## Contoh Alur Penggunaan

```
User: "Buatkan dossier untuk John Smith, LinkedIn nya linkedin.com/in/johnsmith,
       saya mau meeting bahas partnership"
     │
     ▼ Tool: dossier_generate(
             name="John Smith",
             linkedin_url="linkedin.com/in/johnsmith",
             meeting_context="Partnership discussion",
             dossier_id="chat_456"
         )
     │
     ├── [Stage 1: collecting]
     │   ├── SerperClient: 4 web searches (bio, news, statements, associates)
     │   ├── LinkedInScraper: scrape profile
     │   ├── SerperClient: 3 LinkedIn-enhanced searches
     │   └── Deduplicate → CollectedData
     │
     ├── [Stage 2: researching]
     │   └── Gemini 2.0 Flash (temp=0.1) → SynthesizedResearch
     │
     ├── [Stage 3: analyzing]
     │   └── Gemini 2.0 Flash (temp=0.3) → StrategicInsights
     │
     └── [Stage 4: completed]
         └── DossierGenerator → Markdown document (12+ sections)
     │
     ▼
Agent: "Dossier untuk John Smith sudah selesai. [Dokumen Markdown]"
     │
User: "Tambahkan konteks: dia juga investor di bidang AI"
     │
     ▼ Tool: dossier_update(
             additional_context="He is also an AI investor",
             dossier_id="chat_456"
         )
     │
     ├── Skip Stage 1 (gunakan collected_data yang sudah ada)
     ├── Re-run Stage 2: synthesize() ← dengan konteks baru
     ├── Re-run Stage 3: analyze()    ← dengan konteks baru
     └── Re-run Stage 4: generate()
     │
     ▼
Agent: "Dossier sudah di-update dengan konteks tambahan tentang AI investment."
     │
User: "Hapus dossier ini"
     │
     ▼ Tool: dossier_delete(dossier_id="chat_456")
     │
Agent: "Dossier untuk John Smith sudah dihapus."
```

### Self-Lookup Flow

```
User: "Buatkan dossier tentang saya sendiri"
     │
     ▼ Tool: dossier_generate(
             name="Firdaussyah",
             is_self_lookup=True,        ← Gunakan Composio, bukan scraping
             dossier_id="self_lookup"
         )
     │
     ├── [Stage 1: collecting]
     │   ├── ComposioLinkedInClient.get_my_profile()  ← LINKEDIN_GET_MY_INFO via OAuth
     │   ├── SerperClient: 4 web searches
     │   └── Deduplicate → CollectedData
     │
     └── ... (stages 2-4 sama seperti normal flow)
```

---

## Dependencies & Environment Variables

### Dependencies

| Dependency | Kegunaan |
|---|---|
| `langchain_google_genai` | `ChatGoogleGenerativeAI` (Gemini 2.0 Flash) untuk synthesis & analysis |
| `langchain_core` | `@tool` decorator, `HumanMessage`, `SystemMessage` |
| `composio_openai` | `ComposioToolSet` untuk LinkedIn Composio actions |
| `aiohttp` | Async HTTP client untuk Serper API |
| `hashlib` | SHA-256 cache key generation |
| `asyncio` | Parallel execution dengan `asyncio.gather` |
| `dataclasses` | Data models (`@dataclass`) |
| `json` | JSON parsing untuk LLM responses |
| `time` | Cache TTL dan session TTL management |
| `logging` | Structured logging per-component |

### Environment Variables

| Variable | Kegunaan | Digunakan Oleh |
|---|---|---|
| `GOOGLE_API_KEY` | Akses Gemini API | `ResearchSynthesizer`, `StrategicAnalyzer` |
| `SERPER_API_KEY` | Akses Google Serper API | `SerperClient` (via `DataCollector`) |
| `COMPOSIO_API_KEY` | Akses Composio API | `ComposioLinkedInClient` (untuk self-lookup) |

---

## PDF Integration

Dossier Agent terintegrasi dengan PDF generator yang sudah ada di system. PDF generator memiliki logik khusus untuk dossier:

- **Cover page detection:** PDF generator mendeteksi apakah dokumen adalah dossier berdasarkan keberadaan `CONFIDENTIAL_HEADER` atau `DOSSIER_TITLE` pattern
- **Dossier-aware formatting:** Jika terdeteksi sebagai dossier, cover page menggunakan style khusus (bukan template GIPA)
- **Section handling:** Long dossier documents (12+ sections) memiliki page break logic yang berbeda

---

## Perbandingan dengan GIPA Agent

| Aspek | GIPA Agent | Dossier Agent |
|---|---|---|
| **Tujuan** | Generate dokumen hukum GIPA | Generate profil riset seseorang |
| **Input** | Wawancara interaktif (8+ pertanyaan) | Nama + LinkedIn URL + meeting context |
| **Fase** | 2 fase (clarification → generation) | 4 stage pipeline (collect → synthesize → analyze → generate) |
| **LLM Usage** | Extraction (clarification) + keyword expansion | Synthesis (temp=0.1) + strategic analysis (temp=0.3) |
| **External APIs** | Tidak ada (LLM only) | Serper (web search) + LinkedIn (scrape/Composio) |
| **Output** | Email draft (HTML) via Gmail | Markdown document (bisa di-convert ke PDF) |
| **Update** | Tidak ada (generate sekali) | `dossier_update()` tanpa ulang data collection |
| **Session TTL** | Tidak ada TTL | 24 jam |
| **Caching** | Tidak ada | Serper cache (1 jam TTL, SHA-256 keyed) |
