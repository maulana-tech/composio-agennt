# Agents & Tools Reference

Dokumentasi lengkap semua agent dan tools yang tersedia di project **composio-agent**.

---

## Agents (8 Agent Utama)

### 1. Main ReAct Agent

- **File:** `gmail-agent/server/chatbot.py` (line ~58)
- **Deskripsi:** Agent utama percakapan yang menggunakan LangGraph `create_react_agent` dengan model Groq (llama-3.1-8b-instant) atau Google Gemini (gemini-2.0-flash) sebagai fallback. Memiliki akses ke seluruh 42+ tools yang tersedia.

### 2. EmailAnalysisAgent

- **File:** `gmail-agent/server/email_analysis_agents.py` (line 14)
- **Deskripsi:** Menganalisis konten email untuk mengekstrak klaim faktual yang perlu diverifikasi. Menggunakan Gemini 2.0 Flash.

### 3. ResearchPlanningAgent

- **File:** `gmail-agent/server/email_analysis_agents.py` (line 100)
- **Deskripsi:** Membuat strategi riset berdasarkan analisis email. Menyarankan search queries dan prioritas sumber.

### 4. WebResearchAgent

- **File:** `gmail-agent/server/email_analysis_agents.py` (line 178)
- **Deskripsi:** Melakukan riset web menggunakan Google Grounding with Search. Menjalankan search queries secara paralel dan menganalisis temuan.

### 5. ReportGenerationAgent

- **File:** `gmail-agent/server/email_analysis_agents.py` (line 355)
- **Deskripsi:** Menghasilkan laporan fact-checking komprehensif dalam format Markdown dari hasil riset.

### 6. MultiAgentEmailAnalyzer (Orchestrator)

- **File:** `gmail-agent/server/email_analysis_agents.py` (line 444)
- **Deskripsi:** Orkestrator pipeline multi-agent: EmailAnalysis -> ResearchPlanning -> WebResearch -> ReportGeneration -> optional PDF. Digunakan oleh endpoint `/email-analysis` dan `/analyze-and-reply`.

### 7. GIPARequestAgent

- **File:** `gmail-agent/server/tools/gipa_agent/gipa_agent.py` (line 55)
- **Deskripsi:** Mengorkestrasikan alur kerja pembuatan aplikasi GIPA/FOI (Government Information Public Access / Freedom of Information). Dua fase: wawancara klarifikasi untuk mengumpulkan variabel, kemudian pembuatan dokumen hukum formal.

### 8. DossierAgent

- **File:** `gmail-agent/server/tools/dossier_agent/dossier_agent.py` (line 110)
- **Deskripsi:** Mengorkestrasikan pembuatan dossier persiapan meeting melalui 4-stage pipeline: DataCollector (Serper + LinkedIn) -> ResearchSynthesizer (Gemini) -> StrategicAnalyzer (Gemini) -> DossierGenerator (Markdown templates).

---

## Sub-components (Agent-like Classes)

### DossierAgent Sub-components

| Sub-component | File | Deskripsi |
|---|---|---|
| DataCollector | `gmail-agent/server/tools/dossier_agent/data_collector.py` | Multi-source data collection (Serper + LinkedIn scraping) |
| ResearchSynthesizer | `gmail-agent/server/tools/dossier_agent/research_synthesizer.py` | Gemini-powered research synthesis |
| StrategicAnalyzer | `gmail-agent/server/tools/dossier_agent/strategic_analyzer.py` | Gemini-powered strategic analysis |
| DossierGenerator | `gmail-agent/server/tools/dossier_agent/dossier_generator.py` | Template-based Markdown document assembly |

### GIPAAgent Sub-components

| Sub-component | File | Deskripsi |
|---|---|---|
| ClarificationEngine | `gmail-agent/server/tools/gipa_agent/clarification_engine.py` | Variable extraction dan validation |
| GIPADocumentGenerator | `gmail-agent/server/tools/gipa_agent/document_generator.py` | Template assembly dan legal formatting |
| SynonymExpander | `gmail-agent/server/tools/gipa_agent/synonym_expander.py` | AI-powered keyword definition expansion |

---

## Tools (42 LangChain Tools)

### Search Tools (7)

Semua didefinisikan di `gmail-agent/server/chatbot.py`.

| # | Tool | Line | Deskripsi |
|---|---|---|---|
| 1 | `serper_search` | 129 | Web search menggunakan Serper (Google Search API) |
| 2 | `serper_news_search` | 221 | News search menggunakan Serper |
| 3 | `serper_images_search` | 275 | Image search menggunakan Serper |
| 4 | `serper_videos_search` | 326 | Video search menggunakan Serper |
| 5 | `search_google` | 390 | Google search via Gemini Grounding (real-time web search dengan citations) |
| 6 | `visit_webpage` | 448 | Kunjungi URL dan ekstrak teks (mendukung HTML, PDF, DOCX) |
| 7 | `download_file` | 542 | Download file dari URL ke local server |

### Gmail Tools (3)

Didefinisikan di `gmail-agent/server/chatbot.py` dalam fungsi `get_agent_tools()`.

| # | Tool | Line | Deskripsi |
|---|---|---|---|
| 8 | `GMAIL_SEND_EMAIL` | 611 | Kirim email via Gmail dengan optional attachment |
| 9 | `GMAIL_CREATE_EMAIL_DRAFT` | 661 | Buat draft email di Gmail |
| 10 | `GMAIL_FETCH_EMAILS` | 685 | Ambil email terbaru dari Gmail |

### LinkedIn Tools (4)

Didefinisikan di `gmail-agent/server/chatbot.py` dalam fungsi `get_agent_tools()`.

| # | Tool | Line | Deskripsi |
|---|---|---|---|
| 11 | `LINKEDIN_GET_MY_INFO` | 732 | Ambil profil LinkedIn user yang terautentikasi |
| 12 | `LINKEDIN_CREATE_POST` | 745 | Buat post di LinkedIn |
| 13 | `LINKEDIN_DELETE_POST` | 766 | Hapus post di LinkedIn |
| 14 | `LINKEDIN_GET_COMPANY_INFO` | 779 | Ambil info perusahaan/organisasi LinkedIn |

### PDF Tool (1)

| # | Tool | File | Line | Deskripsi |
|---|---|---|---|---|
| 15 | `generate_pdf_report` | `gmail-agent/server/tools/pdf_generator.py` | 784 | Generate PDF profesional dari Markdown dengan parsing, quote images, dan title pages |

> Tool ini di-wrap sebagai `generate_pdf_report_wrapped` di `chatbot.py` line 805.

### Quote Image Tools (4)

| # | Tool | File | Line | Deskripsi |
|---|---|---|---|---|
| 16 | `generate_quote_image_tool` | `tools/pillow_quote_generator.py` | 257 | Quote image via Pillow (100% akurat, tanpa AI typos) |
| 17 | `generate_and_send_quote_email` | `tools/pillow_quote_generator.py` | 303 | Generate quote image + kirim via email dalam satu langkah |
| 18 | `generate_dalle_quote_image_tool` | `tools/dalle_quote_generator.py` | 233 | Quote image via DALL-E 3 (AI-generated) |
| 19 | `generate_quote_with_person_photo` | `tools/avatar_quote_generator.py` | 318 | Quote image dengan foto orang sebagai background (search via Serper) |

### Social Media Tools (5)

Semua didefinisikan di `gmail-agent/server/tools/social_media_poster.py`.

| # | Tool | Line | Deskripsi |
|---|---|---|---|
| 20 | `upload_media_to_twitter` | 21 | Upload media ke Twitter |
| 21 | `post_to_twitter` | 49 | Post ke Twitter/X dengan optional image |
| 22 | `get_facebook_page_id` | 134 | Ambil default Facebook Page ID |
| 23 | `post_to_facebook` | 170 | Post ke Facebook Page dengan optional image |
| 24 | `post_to_all_platforms` | 261 | Post ke semua platform secara bersamaan |

### Strategy Diagram Tools (8)

Semua didefinisikan di `gmail-agent/server/tools/strategy_diagram_agent.py`.

| # | Tool | Line | Deskripsi |
|---|---|---|---|
| 25 | `analyze_strategic_prompt` | 105 | Analisis prompt strategis untuk stakeholders/relationships |
| 26 | `generate_mermaid_diagram` | 143 | Generate kode Mermaid.js |
| 27 | `generate_graphviz_diagram` | 288 | Generate kode Graphviz DOT |
| 28 | `validate_diagram_code` | 335 | Validasi kode diagram |
| 29 | `create_strategy_diagram` | 374 | Full workflow: analyze -> generate -> validate diagram |
| 30 | `preview_mermaid_diagram` | 487 | Preview info diagram Mermaid |
| 31 | `convert_mermaid_to_image` | 508 | Konversi Mermaid ke PNG/SVG image |
| 32 | `render_mermaid_online` | 668 | Dapatkan URL rendering online |

### GIPA Tools (5)

Semua didefinisikan di `gmail-agent/server/tools/gipa_agent/gipa_agent.py`.

| # | Tool | Line | Deskripsi |
|---|---|---|---|
| 33 | `gipa_start_request` | 282 | Mulai sesi GIPA request baru |
| 34 | `gipa_process_answer` | 300 | Proses jawaban user selama klarifikasi |
| 35 | `gipa_generate_document` | 322 | Generate dokumen aplikasi GIPA formal |
| 36 | `gipa_check_status` | 347 | Cek status sesi GIPA |
| 37 | `gipa_expand_keywords` | 401 | Ekspansi keywords ke definisi hukum |

### Dossier Tools (5)

Semua didefinisikan di `gmail-agent/server/tools/dossier_agent/dossier_agent.py`.

| # | Tool | Line | Deskripsi |
|---|---|---|---|
| 38 | `dossier_generate` | 334 | Generate dossier persiapan meeting komprehensif |
| 39 | `dossier_check_status` | 300 | Cek status sesi dossier |
| 40 | `dossier_update` | 379 | Update dossier yang sudah ada dengan konteks baru |
| 41 | `dossier_get_document` | 403 | Ambil dokumen dossier yang sudah di-generate |
| 42 | `dossier_delete` | 430 | Hapus sesi dossier |

---

## Tool Assembly

Semua 42 tools digabungkan di fungsi `get_agent_tools()` dalam `chatbot.py` (line 607):

```python
return (
    serper_tools          # 4 tools
    + search_tools        # 3 tools (search_google, visit_webpage, download_file)
    + [generate_pdf_report_wrapped]  # 1 tool
    + quote_tools         # 4 tools
    + social_media_tools  # 5 tools
    + strategy_tools      # 8 tools
    + gipa_tools          # 5 tools
    + dossier_tools       # 5 tools
    + gmail_tools         # 3 tools
    + linkedin_tools      # 4 tools
)
```

---

## Composio External Tool Slugs

Tools eksternal yang dieksekusi melalui `composio_client.tools.execute()`:

| Platform | Slug |
|---|---|
| Gmail | `GMAIL_SEND_EMAIL`, `GMAIL_CREATE_EMAIL_DRAFT`, `GMAIL_FETCH_EMAILS`, `GMAIL_GET_EMAIL` |
| LinkedIn | `LINKEDIN_CREATE_LINKED_IN_POST`, `LINKEDIN_DELETE_LINKED_IN_POST`, `LINKEDIN_GET_MY_INFO`, `LINKEDIN_GET_COMPANY_INFO` |
| Twitter | `TWITTER_CREATION_OF_A_POST`, `TWITTER_UPLOAD_MEDIA` |
| Facebook | `FACEBOOK_CREATE_POST`, `FACEBOOK_CREATE_PHOTO_POST`, `FACEBOOK_LIST_MANAGED_PAGES` |

---

## Ringkasan

| Kategori | Jumlah |
|---|---|
| Agents utama | **8** |
| Sub-components (agent-like) | **7** |
| LangChain Tools | **42** |
| Composio External Slugs | **13** |
| **Total** | **70** |
