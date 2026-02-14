# Agent Documentation Index

Complete documentation for all 10 agents in the Gmail Agent system.

---

## 📚 Agent Documentation

### 1. [GIPA Agent](GIPA_AGENT.md)
**Purpose**: Government Information Public Access (GIPA/FOI) request handler  
**Key Features**:
- Multi-turn conversation flow
- 6-field data collection
- Professional document generation
- Gmail draft integration

**Tools**: 4 (start_request, process_answer, generate_document, check_status)

---

### 2. [Dossier Agent](DOSSIER_AGENT.md)
**Purpose**: Meeting preparation and biographical research  
**Key Features**:
- Web research from multiple sources
- Biographical synthesis
- Strategic insights generation
- Professional PDF dossiers

**Tools**: 2 (check_status, generate)

---

### 3. [Email Analyst Agent](EMAIL_ANALYST_AGENT.md)
**Purpose**: Fact-checking and email analysis  
**Key Features**:
- Multi-agent architecture (4 agents)
- Claims extraction and verification
- Google Grounding integration
- Professional PDF reports

**Tools**: 1 (analyze_email_content)

---

### 4. [PDF Agent](PDF_AGENT.md)
**Purpose**: Professional PDF report generation  
**Key Features**:
- Full markdown parsing
- AI quote image generation
- Professional styling
- Table and info box support

**Tools**: 1 (generate_pdf_report_tool)

---

### 5. [Research Agent](RESEARCH_AGENT.md)
**Purpose**: Web research and information gathering  
**Key Features**:
- Serper API search
- Google Grounding fact-checking
- Webpage content extraction
- File downloading

**Tools**: 4 (search_web, search_google_grounding, visit_webpage, download_file)

---

### 6. [Social Media Agent](SOCIAL_MEDIA_AGENT.md)
**Purpose**: Twitter and Facebook posting  
**Key Features**:
- Multi-platform posting
- Auto platform detection
- Image attachments
- Batch posting

**Tools**: 3 (post_to_twitter, post_to_facebook, post_to_all_social_media)

---

### 7. [Gmail Agent](GMAIL_AGENT.md)
**Purpose**: Email management (send, draft, fetch)  
**Key Features**:
- Send emails with attachments
- Create drafts
- Fetch emails with search
- Gmail search syntax support

**Tools**: 3 (gmail_send_email, gmail_create_draft, gmail_fetch_emails)

---

### 8. [LinkedIn Agent](LINKEDIN_AGENT.md)
**Purpose**: LinkedIn profile and posting management  
**Key Features**:
- Profile information fetching
- Post creation (text, images, articles)
- Post deletion
- Professional networking

**Tools**: 3 (linkedin_get_info, linkedin_post, linkedin_delete_post)

---

### 9. [Quote Agent](QUOTE_AGENT.md)
**Purpose**: Visual quote image generation  
**Key Features**:
- AI-powered image generation (Gemini)
- Professional typography
- Indonesian color support (red/white)
- Fallback PIL generation

**Tools**: 2 (generate_quote_image, generate_artistic_quote)

---

### 10. [Strategy Agent](STRATEGY_AGENT.md)
**Purpose**: Strategic analysis and diagram generation  
**Key Features**:
- Goal decomposition
- Mermaid diagram generation
- Multiple diagram types (flowchart, timeline, mindmap, gantt)
- Timeline and resource planning

**Tools**: 2 (analyze_strategy, generate_strategy_diagram)

---

## 📊 Quick Reference

| Agent | Tools | Use Case |
|-------|-------|----------|
| **GIPA** | 4 | Government FOI requests |
| **Dossier** | 2 | Meeting preparation |
| **Email Analyst** | 1 | Email fact-checking |
| **PDF** | 1 | Report generation |
| **Research** | 4 | Web research |
| **Social Media** | 3 | Twitter/Facebook posts |
| **Gmail** | 3 | Email management |
| **LinkedIn** | 3 | Professional networking |
| **Quote** | 2 | Quote image creation |
| **Strategy** | 2 | Strategic planning |

**Total: 10 Agents, 25 Tools**

---

## 🔧 Architecture Overview

All agents follow the pluggable architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Registry                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│   │   GIPA   │  │ Dossier  │  │  Email   │  │   PDF    │  │
│   └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│                                                             │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│   │ Research │  │  Social  │  │  Gmail   │  │ LinkedIn │  │
│   └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│                                                             │
│   ┌──────────┐  ┌──────────┐                               │
│   │  Quote   │  │ Strategy │                               │
│   └──────────┘  └──────────┘                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Getting Started

### Test All Agents
```bash
cd gmail-agent
uv run python test_agents.py
```

### Verify System
```bash
uv run python server/verify_final.py
```

### Use Specific Agent
```python
from server.agents import create_default_registry, AgentContext

registry = create_default_registry()
agent = registry.get("agent_name")

context = AgentContext(user_id="user_123", session_id="session_001")
response = await agent.handle("user message", context)
```

---

## 📁 Files Structure

```
gmail-agent/docs/agents/
├── INDEX.md                    # This file
├── GIPA_AGENT.md              # GIPA Agent documentation
├── DOSSIER_AGENT.md           # Dossier Agent documentation
├── EMAIL_ANALYST_AGENT.md     # Email Analyst documentation
├── PDF_AGENT.md               # PDF Agent documentation
├── RESEARCH_AGENT.md          # Research Agent documentation
├── SOCIAL_MEDIA_AGENT.md      # Social Media documentation
├── GMAIL_AGENT.md             # Gmail Agent documentation
├── LINKEDIN_AGENT.md          # LinkedIn Agent documentation
├── QUOTE_AGENT.md             # Quote Agent documentation
└── STRATEGY_AGENT.md          # Strategy Agent documentation
```

---

## 📝 Documentation Format

Each agent documentation includes:
- ✅ **Overview** - Purpose and description
- ✅ **Architecture** - High-level structure diagram
- ✅ **Flowchart** - Process flow with Mermaid
- ✅ **Agent Structure** - Class definition
- ✅ **Components** - Internal components detail
- ✅ **Tools** - Available tools with examples
- ✅ **Usage Examples** - Code samples
- ✅ **Configuration** - Environment variables
- ✅ **Error Handling** - Common errors and solutions
- ✅ **Integration Points** - Connected systems
- ✅ **Testing** - Test commands
- ✅ **Files Structure** - Directory layout
- ✅ **Summary** - Key features recap

---

## 🔗 Related Documentation

- Main README: `../../README.md`
- API Documentation: `../api.md` (if exists)
- Authentication: `../../server/auth.py`
- Core Classes: `../../server/agents/core/`

---

## 💡 Tips

1. **Read the Overview first** - Understand what each agent does
2. **Check Tools section** - See available capabilities
3. **Review Usage Examples** - Learn how to use the agent
4. **Check Configuration** - Set up required environment variables
5. **Test with test_agents.py** - Verify everything works

---

## 🆘 Support

For issues or questions:
1. Check the specific agent documentation
2. Review error messages in the response
3. Verify environment variables are set
4. Check agent status with test_agents.py

---

**Last Updated**: 2024-02-14  
**Version**: 1.0.0  
**Total Agents**: 10  
**Total Tools**: 25
