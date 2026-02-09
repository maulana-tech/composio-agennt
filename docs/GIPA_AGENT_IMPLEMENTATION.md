# GIPA Agent - Implementation Guide

Dokumentasi lengkap implementasi **GIPA (Government Information Public Access) Request Agent** untuk pembuatan aplikasi akses informasi pemerintah NSW secara otomatis.

---

## Overview

GIPA Agent adalah sistem multi-komponen yang mengotomatisasi pembuatan dokumen hukum formal untuk meminta akses informasi dari instansi pemerintah New South Wales (Australia). Agent ini bekerja dalam dua fase:

1. **Clarification Phase** - Wawancara interaktif untuk mengumpulkan semua variabel yang diperlukan
2. **Generation Phase** - Menyusun dokumen aplikasi GIPA formal yang lengkap secara hukum

### Tujuan

Menghasilkan dokumen GIPA yang:
- Tidak bisa ditolak karena alasan "terlalu kabur" atau "tidak jelas"
- Menggunakan Boolean search terms yang presisi
- Memiliki definisi keyword yang komprehensif (legal shield)
- Menyertakan pengurangan biaya jika pemohon memenuhi syarat

---

## Struktur File

```
gmail-agent/server/tools/gipa_agent/
├── __init__.py                  # Exports semua public API
├── gipa_agent.py                # Orchestrator utama + LangChain tools
├── clarification_engine.py      # Ekstraksi variabel dari percakapan
├── document_generator.py        # Penyusunan dokumen GIPA
├── synonym_expander.py          # Ekspansi keyword ke definisi hukum
├── jurisdiction_config.py       # Konfigurasi per-jurisdiksi (NSW/Federal/VIC)
└── templates/
    ├── __init__.py
    └── boilerplate.py           # Klausul hukum standar & exclusions
```

---

## Arsitektur & Alur Kerja

```
User Message
     │
     ▼
┌─────────────────────────────┐
│    GIPARequestAgent         │  ← Orchestrator (gipa_agent.py:55)
│    (Session Management)     │
└─────────┬───────────────────┘
          │
          ├── Phase 1: Clarification
          │   │
          │   ▼
          │   ┌───────────────────────┐
          │   │  ClarificationEngine  │  ← LLM-powered extraction (clarification_engine.py:201)
          │   │  (Gemini 2.0 Flash)   │
          │   └───────────┬───────────┘
          │               │
          │               ├── extract_variables()  → Parse user message ke structured data
          │               ├── validate_data()       → Validasi kelengkapan
          │               └── build_gipa_request_data() → Bangun GIPARequestData object
          │
          └── Phase 2: Generation
              │
              ▼
              ┌───────────────────────────┐
              │   GIPADocumentGenerator   │  ← Template assembly (document_generator.py:25)
              └───────────┬───────────────┘
                          │
                          ├── Section A: Header & Routing
                          ├── Section B: Fee Reduction (conditional)
                          ├── Section C: Search Terms (Boolean query)
                          ├── Section D: Scope & Definitions (legal shield)
                          │   │
                          │   ├── SynonymExpander  ← AI keyword expansion (synonym_expander.py:21)
                          │   └── Boilerplate      ← Static legal clauses (templates/boilerplate.py)
                          │
                          └── Closing
```

---

## Komponen Detail

### 1. GIPARequestAgent (Orchestrator)

**File:** `gipa_agent.py:55`

Orchestrator utama yang mengelola session state dan mengkoordinasikan seluruh pipeline.

#### Session Management

Session disimpan in-memory per-process menggunakan dictionary:

```python
# gipa_agent.py:30
_gipa_sessions: Dict[str, Dict[str, Any]] = {}

# Struktur setiap session:
{
    "data": {},          # Collected variables (partial GIPARequestData)
    "context": "",       # Conversation history
    "status": "collecting",  # collecting | ready | generated
    "document": None,    # Generated document (after generation)
}
```

#### Lifecycle Methods

| Method | Line | Deskripsi |
|---|---|---|
| `start_request()` | 71 | Inisialisasi session baru, return pertanyaan pertama |
| `process_answer()` | 96 | Proses jawaban user, extract variabel, return pertanyaan berikutnya atau konfirmasi |
| `generate_document()` | 149 | Generate dokumen GIPA formal dari data yang terkumpul |
| `_build_confirmation_summary()` | 194 | Bangun ringkasan konfirmasi sebelum generate |

#### Alur `process_answer()`:

```
User answer masuk
     │
     ▼
ClarificationEngine.extract_variables()
     │
     ├── LLM parse free-form text → structured fields
     ├── Merge dengan data yang sudah ada
     └── Cek missing fields
          │
          ├── Masih ada yang kurang → Return pertanyaan berikutnya
          └── Semua lengkap → Set status "ready", return confirmation summary
```

#### Singleton Pattern

Agent di-instantiate sebagai singleton (lazy-initialized):

```python
# gipa_agent.py:270
_agent_instance: Optional[GIPARequestAgent] = None

def _get_agent() -> GIPARequestAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = GIPARequestAgent()
    return _agent_instance
```

---

### 2. ClarificationEngine

**File:** `clarification_engine.py:201`

Engine yang menggunakan Gemini 2.0 Flash untuk mengekstrak variabel terstruktur dari percakapan free-form.

#### Data Model: `GIPARequestData`

**File:** `clarification_engine.py:39`

```python
class GIPARequestData(BaseModel):
    # Target Agency
    agency_name: str                         # Nama instansi pemerintah
    agency_email: Optional[str]              # Email GIPA spesifik

    # Applicant
    applicant_name: str                      # Nama lengkap pemohon
    applicant_organization: Optional[str]    # Nama organisasi (jika ada)
    applicant_type: Literal["individual", "nonprofit", "journalist", "student", "other"]
    charity_status: Optional[str]            # ABN / nomor registrasi

    # Request Details
    public_interest_justification: str       # Alasan kepentingan publik
    start_date: str                          # Awal periode pencarian
    end_date: str                            # Akhir periode pencarian
    targets: List[TargetPerson]              # Orang/peran yang dicari korespondensinya
    keywords: List[str]                      # Kata kunci pencarian
    jurisdiction: str                        # NSW / Federal / Victoria

    # Computed
    fee_reduction_eligible: bool             # Auto-computed dari applicant_type
    summary_sentence: str                    # Ringkasan satu kalimat
```

#### Data Model: `TargetPerson`

**File:** `clarification_engine.py:26`

```python
class TargetPerson(BaseModel):
    name: str                                           # Nama lengkap atau jabatan
    role: Optional[str]                                 # Jabatan (opsional)
    direction: Literal["sender", "receiver", "both"]    # Arah korespondensi
```

#### Required Fields & Questions

**File:** `clarification_engine.py:125`

Engine memiliki daftar field wajib dengan prioritas dan pertanyaan yang sudah ditentukan:

| Prioritas | Field | Pertanyaan |
|---|---|---|
| 1 | `agency_name` | Instansi pemerintah mana yang ingin dimintai informasi? |
| 2 | `applicant_name` | Siapa nama lengkap Anda (sebagai pemohon)? |
| 3 | `applicant_type` | Jenis pemohon? (individual/nonprofit/journalist/student) |
| 4 | `public_interest_justification` | Mengapa informasi ini penting untuk kepentingan publik? |
| 5 | `start_date` | Tanggal MULAI periode pencarian? |
| 6 | `end_date` | Tanggal AKHIR periode pencarian? |
| 7 | `targets` | Siapa orang/peran yang korespondensinya dicari? |
| 8 | `keywords` | Kata kunci spesifik apa yang harus ada di dokumen? |

#### Conditional Fields

**File:** `clarification_engine.py:169`

Field tambahan yang ditanyakan secara kondisional:

| Field | Kondisi | Pertanyaan |
|---|---|---|
| `applicant_organization` | `applicant_type` = nonprofit/journalist/student | Nama organisasi/publikasi/universitas? |
| `charity_status` | `applicant_type` = nonprofit | Nomor registrasi amal atau ABN? |
| `agency_email` | Setelah `agency_name` terisi | Email GIPA spesifik untuk instansi tersebut? |

#### Cara Kerja Extraction

**File:** `clarification_engine.py:220`

```
1. User message masuk
2. Build extraction prompt (current data + context + user message)
3. Kirim ke Gemini 2.0 Flash dengan system prompt extraction
4. LLM return JSON: { "extracted": { field: value }, "notes": "..." }
5. Parse JSON response (coba ```json block, lalu raw JSON, lalu fallback)
6. Merge extracted fields ke current_data
7. Cek missing fields → return daftar pertanyaan yang belum terjawab
```

System prompt LLM berfungsi sebagai "data extraction engine" yang hanya mengekstrak field yang JELAS disebutkan user, tanpa menebak atau mengasumsi.

---

### 3. GIPADocumentGenerator

**File:** `document_generator.py:25`

Generator dokumen yang menyusun aplikasi GIPA formal dari data terstruktur.

#### Struktur Dokumen Output

Dokumen yang dihasilkan mengikuti arsitektur hukum yang ketat:

```
Section A: Header & Routing
  - Tanggal
  - Nama instansi + email GIPA
  - RE: GIPA Act - Information Request
  - Dear Right to Information Officer
  - Nama pemohon + organisasi
  - Summary sentence

Section B: Fee Reduction (kondisional - hanya jika eligible)
  - Kutipan pasal undang-undang spesifik
  - Justifikasi berdasarkan tipe pemohon
  - Alasan kepentingan publik

Section C: Search Terms (Boolean query)
  - Date Range
  - Sender/Receiver specifications per target
  - Keywords (Boolean AND)

Section D: Scope & Definitions (legal shield)
  - Definisi "record"
  - Exclusion: media alerts
  - Exclusion: duplicates
  - Exclusion: auto-replies
  - Contractor/consultant inclusion
  - AI-expanded keyword definitions
  - Definisi "correspondence" (termasuk platform modern)

Closing
  - Penutup formal
  - Tanda tangan
```

#### Format Target Person

```python
# document_generator.py:194
# direction = "sender"  → "Sender: All correspondence sent from John Smith (Director)."
# direction = "receiver" → "Receiver: All correspondence sent to John Smith (Director)."
# direction = "both"    → "Party: All correspondence involving John Smith (Director)."
```

---

### 4. SynonymExpander

**File:** `synonym_expander.py:21`

Menggunakan Gemini 2.0 Flash untuk mengekspansi keyword sederhana menjadi definisi hukum yang komprehensif.

#### Tujuan

Mencegah instansi menolak permintaan dengan alasan ambigu. Contoh:

**Input:** `"Koala"`

**Output:**
> Define "Koala" to include: Phascolarctos cinereus, native bear, arboreal marsupial, koala habitat, koala population, SEPP 44, koala management area.

**Input:** `"water licence"`

**Output:**
> Define "water licence" to include: water access licence, WAL, water sharing plan, water allocation, water entitlement, water extraction permit, bore licence, groundwater licence.

#### Fitur

- **Caching:** Hasil ekspansi di-cache per keyword untuk menghindari LLM call berulang
- **Fallback:** Jika LLM gagal, menggunakan definisi minimal standar
- **Cap:** Maksimal 12 terms per keyword
- **Parsing robust:** Coba JSON direct, lalu markdown JSON block, lalu comma/newline split

---

### 5. JurisdictionConfig

**File:** `jurisdiction_config.py:14`

Konfigurasi per-jurisdiksi menggunakan frozen dataclass. Mendukung 3 jurisdiksi:

| Config | Jurisdiksi | Undang-undang | Biaya Dasar | Fee Rate |
|---|---|---|---|---|
| `NSW_CONFIG` | New South Wales | GIPA Act 2009 | $30 | $30/hr |
| `FEDERAL_CONFIG` | Federal/Commonwealth | FOI Act 1982 | $0 | $15/hr (setelah 5 jam pertama) |
| `VIC_CONFIG` | Victoria | FOI Act 1982 (Vic) | $30.60 | $22.50/hr |

Setiap config berisi:
- Referensi undang-undang (`act_name`, `act_short_name`, `act_year`)
- Pasal pengurangan biaya (`fee_reduction_section`)
- Regulasi biaya (`fee_regulation_clause`)
- Definisi "record" (`record_definition_reference`)
- Platform korespondensi yang termasuk dalam definisi (email, SMS, WhatsApp, Signal, WeChat, Wickr, Teams, Slack)

---

### 6. Boilerplate Templates

**File:** `templates/boilerplate.py`

Klausul hukum statis yang menjadi "legal shield" dalam setiap aplikasi.

#### Standard Exclusions

Exclusion ini mengurangi cakupan pencarian sehingga menurunkan biaya pemrosesan:

| Exclusion | Deskripsi |
|---|---|
| Media Alerts | Exclude alert media harian otomatis dan digest berita massal |
| Duplicates | Exclude duplikat dokumen yang sudah ditangkap |
| Auto-replies | Exclude out-of-office, delivery/read receipts, calendar responses |

#### Clause Generators

| Function | Deskripsi |
|---|---|
| `get_record_definition()` | Definisi "record" sesuai jurisdiksi |
| `get_correspondence_definition()` | Definisi "correspondence" termasuk platform modern |
| `get_fee_reduction_paragraph()` | Paragraf pengurangan biaya berdasarkan tipe pemohon |
| `build_scope_and_definitions()` | Susun Section D lengkap (record + exclusions + contractor + keywords + correspondence) |

#### Fee Reduction Logic

Pengurangan biaya 50% otomatis di-request untuk:
- **Nonprofit:** Menyertakan nama organisasi + charity registration
- **Journalist:** Menyertakan justifikasi transparansi pemerintah
- **Student:** Menyertakan justifikasi riset akademik

---

## LangChain Tools (5 Tools)

Tools yang di-expose ke Main ReAct Agent:

### `gipa_start_request`
**File:** `gipa_agent.py:282`

Memulai sesi GIPA baru. Menginisialisasi session dan mengembalikan teks pengantar + pertanyaan pertama.

```python
@tool
async def gipa_start_request(session_id: str = "default") -> str:
```

### `gipa_process_answer`
**File:** `gipa_agent.py:300`

Memproses jawaban user selama fase klarifikasi. Mengekstrak data terstruktur dan mengembalikan pertanyaan berikutnya atau ringkasan konfirmasi.

```python
@tool
async def gipa_process_answer(user_answer: str, session_id: str = "default") -> str:
```

### `gipa_generate_document`
**File:** `gipa_agent.py:322`

Menghasilkan dokumen aplikasi GIPA formal setelah semua data terkumpul dan dikonfirmasi user.

```python
@tool
async def gipa_generate_document(session_id: str = "default") -> str:
```

### `gipa_check_status`
**File:** `gipa_agent.py:347`

Mengecek status sesi GIPA. Dipanggil lebih dulu ketika user menyebut GIPA dan mungkin sudah ada sesi aktif.

```python
@tool
async def gipa_check_status(session_id: str = "default") -> str:
```

### `gipa_expand_keywords`
**File:** `gipa_agent.py:401`

Mengekspansi keywords menjadi definisi hukum. Bisa digunakan standalone tanpa memulai sesi GIPA penuh.

```python
@tool
async def gipa_expand_keywords(keywords: str) -> str:
```

---

## Contoh Alur Penggunaan

```
User: "Saya ingin membuat GIPA request"
     │
     ▼ Tool: gipa_start_request(session_id="chat_123")
     │
Agent: "Instansi pemerintah mana yang ingin dimintai informasi?"
     │
User: "Department of Primary Industries"
     │
     ▼ Tool: gipa_process_answer("Department of Primary Industries", "chat_123")
     │  └── ClarificationEngine extracts: agency_name = "Department of Primary Industries"
     │
Agent: "Siapa nama lengkap Anda?"
     │
User: "John Smith, saya journalist dari Sydney Morning Herald"
     │
     ▼ Tool: gipa_process_answer("John Smith, journalist dari SMH", "chat_123")
     │  └── Extracts: applicant_name = "John Smith"
     │               applicant_type = "journalist"
     │               applicant_organization = "Sydney Morning Herald"
     │
Agent: "Mengapa informasi ini penting untuk kepentingan publik?"
     │
     ... (lanjut sampai semua field terisi) ...
     │
Agent: "Semua informasi sudah terkumpul. [Confirmation Summary]. Apakah sudah benar?"
     │
User: "Ya, benar"
     │
     ▼ Tool: gipa_generate_document("chat_123")
     │  └── GIPADocumentGenerator.generate()
     │       ├── _build_header()
     │       ├── _build_fee_reduction()  ← 50% karena journalist
     │       ├── _build_search_terms()
     │       ├── SynonymExpander.expand_keywords()
     │       ├── build_scope_and_definitions()
     │       └── _build_closing()
     │
Agent: [Dokumen GIPA formal dalam format Markdown]
```

---

## Dependencies

| Dependency | Kegunaan |
|---|---|
| `langchain_google_genai` | ChatGoogleGenerativeAI (Gemini 2.0 Flash) |
| `langchain_core` | `@tool` decorator, `HumanMessage`, `SystemMessage` |
| `pydantic` | Data validation (`BaseModel`, `Field`, `model_validator`) |
| `GOOGLE_API_KEY` | Environment variable untuk akses Gemini API |

---

## Session States

| Status | Deskripsi | Next Action |
|---|---|---|
| `collecting` | Masih mengumpulkan informasi dari user | `gipa_process_answer()` |
| `ready` | Semua data lengkap, menunggu konfirmasi user | `gipa_generate_document()` |
| `generated` | Dokumen sudah di-generate | Mulai sesi baru dengan `gipa_start_request()` |
