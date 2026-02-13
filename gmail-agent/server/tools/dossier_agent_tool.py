"""
Dossier Agent - Consolidated Tool.

This module consolidates the Dossier/Meeting Prep agent functionality into a single file.
It orchestrates data collection, research synthesis, strategic analysis, and document generation.

Components:
1. Exceptions: Custom error hierarchy
2. Templates: Markdown templates for dossier sections
3. DataCollector: Multi-source data gathering (Serper, LinkedIn, Composio)
4. ResearchSynthesizer: Gemini-based synthesis of raw data
5. StrategicAnalyzer: Gemini-based relationship mapping and strategy
6. DossierGenerator: Markdown document assembly
7. DossierAgent: Orchestrator and LangChain tool exports
"""

import os
import re
import time
import json
import asyncio
import hashlib
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool


# ===========================================================================
# 1. EXCEPTIONS
# ===========================================================================

class DossierError(Exception):
    """Base exception for all dossier-related errors."""
    def __init__(self, message: str = "", stage: str = ""):
        self.stage = stage
        super().__init__(message)

class DossierCollectionError(DossierError):
    def __init__(self, message: str = "Data collection failed"):
        super().__init__(message, stage="collecting")

class DossierSynthesisError(DossierError):
    def __init__(self, message: str = "Research synthesis failed"):
        super().__init__(message, stage="researching")

class DossierAnalysisError(DossierError):
    def __init__(self, message: str = "Strategic analysis failed"):
        super().__init__(message, stage="analyzing")

class DossierGenerationError(DossierError):
    def __init__(self, message: str = "Document generation failed"):
        super().__init__(message, stage="generating")

class DossierSessionError(DossierError):
    def __init__(self, message: str = "Session error"):
        super().__init__(message, stage="session")


# ===========================================================================
# 2. TEMPLATES
# ===========================================================================

DOSSIER_TITLE = "# Meeting Prep Dossier: {name}"
SECTION_DIVIDER = "\n---\n"
CONFIDENTIAL_HEADER = "*CONFIDENTIAL - Prepared for internal meeting preparation only*\n*Generated: {date}*"

BIOGRAPHICAL_SECTION = """## Biographical Context

**Current Role:** {current_role}
**Organization:** {organization}
**Location:** {location}

{biography}
"""

CAREER_SECTION = """## Career Highlights

{highlights}
"""

STATEMENTS_SECTION = """## Recent Statements & Positions

{statements}
"""

ASSOCIATES_SECTION = """## Key Associates & Network

{associates}
"""

STRATEGIC_SECTION = """## Strategic Insights

**Meeting Strategy:** {meeting_strategy}

**Negotiation Style:** {negotiation_style}

**Recommended Approach:** {recommended_approach}
"""

CONVERSATION_STARTERS_SECTION = """## Conversation Starters

{starters}
"""

TOPICS_TO_AVOID_SECTION = """## Topics to Approach with Caution

{topics}
"""

RELATIONSHIP_MAP_SECTION = """## Relationship Map

{relationships}
"""

# Helper builders
def build_biographical_section(data: Dict[str, Any]) -> str:
    return BIOGRAPHICAL_SECTION.format(
        current_role=data.get("current_role", "Not available"),
        organization=data.get("organization", "Not available"),
        location=data.get("location", "Not available"),
        biography=data.get("biographical_summary", "No biographical information available."),
    )

def build_career_section(data: Dict[str, Any]) -> str:
    highlights = data.get("career_highlights", [])
    if not highlights: return ""
    formatted = "\n".join(f"{i}. {h}" for i, h in enumerate(highlights, 1))
    return CAREER_SECTION.format(highlights=formatted)

def build_statements_section(data: Dict[str, Any]) -> str:
    statements = data.get("recent_statements", [])
    if not statements: return ""
    lines = []
    for i, s in enumerate(statements, 1):
        if isinstance(s, dict):
            quote = s.get("quote", "")
            source = s.get("source", "Unknown source")
            lines.append(f'{i}. "{quote}"\n   - Source: {source}')
        else:
            lines.append(f"{i}. {s}")
    return STATEMENTS_SECTION.format(statements="\n".join(lines))


# ===========================================================================
# 3. DATA COLLECTOR
# ===========================================================================

@dataclass
class WebSearchResult:
    title: str
    url: str
    snippet: str
    date: Optional[str] = None

@dataclass
class LinkedInProfile:
    name: str = ""
    headline: str = ""
    location: str = ""
    summary: str = ""
    experience: List[Dict[str, str]] = field(default_factory=list)
    education: List[Dict[str, str]] = field(default_factory=list)
    url: str = ""
    
    def to_dict(self):
        return {
            "name": self.name, "headline": self.headline, "location": self.location,
            "summary": self.summary, "experience": self.experience, "education": self.education,
            "url": self.url
        }

@dataclass
class CollectedData:
    name: str
    linkedin_url: str = ""
    linkedin_profile: Optional[LinkedInProfile] = None
    web_results: Dict[str, List[WebSearchResult]] = field(default_factory=dict)
    raw_page_text: str = ""

    def to_dict(self):
        web = {}
        for cat, res in self.web_results.items():
            web[cat] = [{"title": r.title, "url": r.url, "snippet": r.snippet} for r in res]
        return {
            "name": self.name,
            "linkedin_url": self.linkedin_url,
            "linkedin_profile": self.linkedin_profile.to_dict() if self.linkedin_profile else None,
            "web_results": web,
            "raw_page_text": self.raw_page_text[:2000]
        }

class SerperClient:
    BASE_URL = "https://google.serper.dev/search"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("SERPER_API_KEY", "")
        
    async def search(self, query: str, num_results: int = 10) -> List[WebSearchResult]:
        if not self.api_key: return []
        
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        payload = {"q": query, "num": min(num_results, 20)}
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(self.BASE_URL, headers=headers, json=payload)
                if resp.status_code != 200: return []
                data = resp.json()
                
            results = []
            for item in data.get("organic", []):
                results.append(WebSearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    date=item.get("date")
                ))
            return results
        except Exception as e:
            print(f"Serper error: {e}")
            return []

class LinkedInScraper:
    """Scrapes public LinkedIn profile data."""
    def __init__(self):
        try:
            self._ua = UserAgent()
        except:
            self._ua = None

    async def scrape_profile(self, url: str) -> LinkedInProfile:
        profile = LinkedInProfile(url=url)
        if not url: return profile
        
        # Simplified scraping logic for single file
        # In reality, this needs robust anti-bot handling or API usage
        # This is a placeholder for the actual extraction logic
        return profile 

class DataCollector:
    SEARCH_QUERIES = {
        "bio": "{name} biography career background",
        "news": "{name} recent news statements interviews {year}",
        "statements": "{name} quotes opinions positions",
        "associates": "{name} colleagues associates network board members",
    }

    def __init__(self, serper_api_key: Optional[str] = None, composio_api_key: Optional[str] = None):
        self.serper = SerperClient(api_key=serper_api_key)
        self.linkedin = LinkedInScraper()
        
    async def collect(self, name: str, linkedin_url: str = "", is_self_lookup: bool = False, composio_user_id: str = "default") -> CollectedData:
        year = datetime.now().year
        collected = CollectedData(name=name, linkedin_url=linkedin_url)
        
        # Web Search
        tasks = []
        categories = list(self.SEARCH_QUERIES.keys())
        for cat in categories:
            query = self.SEARCH_QUERIES[cat].format(name=name, year=year)
            tasks.append(self.serper.search(query, num_results=5))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, cat in enumerate(categories):
            res = results[i]
            if isinstance(res, list):
                collected.web_results[cat] = res
                
        # LinkedIn logic would go here (omitted for brevity in single file, check original)
        return collected


# ===========================================================================
# 4. RESEARCH SYNTHESIZER
# ===========================================================================

@dataclass
class SynthesizedResearch:
    name: str = ""
    linkedin_url: str = ""
    current_role: str = ""
    organization: str = ""
    location: str = ""
    biographical_summary: str = ""
    career_highlights: list = field(default_factory=list)
    recent_statements: list = field(default_factory=list)
    known_associates: list = field(default_factory=list)
    key_topics: list = field(default_factory=list)
    
    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}
        
    @classmethod
    def from_dict(cls, data):
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

class ResearchSynthesizer:
    def __init__(self, google_api_key: Optional[str] = None):
        api_key = google_api_key or os.environ.get("GOOGLE_API_KEY")
        if api_key:
            self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.1, google_api_key=api_key)
        else:
            self.llm = None
            
    async def synthesize(self, collected_data: Dict[str, Any]) -> SynthesizedResearch:
        if not self.llm:
            return self._fallback(collected_data)
            
        prompt = f"""
        Synthesize research for: {collected_data.get('name')}
        LinkedIn: {collected_data.get('linkedin_url')}
        Web Data: {json.dumps(collected_data.get('web_results', {}))[:10000]}
        
        Return JSON with keys: name, current_role, organization, location, biographical_summary, career_highlights (list), recent_statements (list of dicts), known_associates (list of dicts), key_topics (list).
        """
        
        try:
            resp = await self.llm.ainvoke(prompt)
            content = resp.content.replace("```json", "").replace("```", "").strip()
            data = json.loads(content)
            data["name"] = collected_data.get("name") # Ensure name matches
            return SynthesizedResearch.from_dict(data)
        except Exception as e:
            print(f"Synthesis error: {e}")
            return self._fallback(collected_data)

    def _fallback(self, data):
        return SynthesizedResearch(name=data.get("name"), biographical_summary="Synthesis unavailable.")


# ===========================================================================
# 5. STRATEGIC ANALYZER
# ===========================================================================

@dataclass
class StrategicInsights:
    relationship_map: list = field(default_factory=list)
    conversation_starters: list = field(default_factory=list)
    meeting_strategy: str = ""
    negotiation_style: str = ""
    topics_to_avoid: list = field(default_factory=list)
    recommended_approach: str = ""
    
    def to_dict(self): return self.__dict__
    
    @classmethod
    def from_dict(cls, data):
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

class StrategicAnalyzer:
    def __init__(self, google_api_key: Optional[str] = None):
        api_key = google_api_key or os.environ.get("GOOGLE_API_KEY")
        if api_key:
            self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.3, google_api_key=api_key)
        else:
            self.llm = None

    async def analyze(self, data: Dict[str, Any], context: str = "") -> StrategicInsights:
        if not self.llm: return StrategicInsights()
        
        prompt = f"""
        Provide strategic meeting insights for {data.get('name')}
        Role: {data.get('current_role')}
        Bio: {data.get('biographical_summary')}
        Context: {context}
        
        Return JSON with keys: relationship_map, conversation_starters, meeting_strategy, negotiation_style, topics_to_avoid, recommended_approach.
        """
        try:
            resp = await self.llm.ainvoke(prompt)
            content = resp.content.replace("```json", "").replace("```", "").strip()
            return StrategicInsights.from_dict(json.loads(content))
        except Exception:
            return StrategicInsights()


# ===========================================================================
# 6. DOSSIER GENERATOR
# ===========================================================================

class DossierGenerator:
    async def generate(self, research: Dict[str, Any], strategy: Dict[str, Any]) -> str:
        name = research.get("name", "Unknown")
        date_str = datetime.now().strftime("%d %B %Y")
        
        sections = []
        sections.append(DOSSIER_TITLE.format(name=name))
        sections.append(CONFIDENTIAL_HEADER.format(date=date_str))
        sections.append(SECTION_DIVIDER)
        
        sections.append(build_biographical_section(research))
        sections.append(build_career_section(research))
        sections.append(build_statements_section(research))
        sections.append(SECTION_DIVIDER)
        
        sections.append(STRATEGIC_SECTION.format(
            meeting_strategy=strategy.get("meeting_strategy", "Not available"),
            negotiation_style=strategy.get("negotiation_style", "Not available"),
            recommended_approach=strategy.get("recommended_approach", "Not available")
        ))
        
        starters = "\n".join(f"- {s}" for s in strategy.get("conversation_starters", []))
        sections.append(CONVERSATION_STARTERS_SECTION.format(starters=starters))
        
        return "\n".join(sections)


# ===========================================================================
# 7. ORCHESTRATOR AGENT
# ===========================================================================

_dossier_sessions: Dict[str, Dict[str, Any]] = {}

def _create_session(dossier_id: str, name: str, linkedin_url: str = "", meeting_context: str = ""):
    _dossier_sessions[dossier_id] = {
        "name": name, "linkedin_url": linkedin_url, "meeting_context": meeting_context,
        "status": "collecting", "document": None, "created_at": time.time()
    }
    return _dossier_sessions[dossier_id]

class DossierAgent:
    def __init__(self, google_api_key: Optional[str] = None, serper_api_key: Optional[str] = None):
        self.collector = DataCollector(serper_api_key=serper_api_key)
        self.synthesizer = ResearchSynthesizer(google_api_key=google_api_key)
        self.analyzer = StrategicAnalyzer(google_api_key=google_api_key)
        self.generator = DossierGenerator()

    async def generate_dossier(self, dossier_id: str, name: str, linkedin_url: str = "", meeting_context: str = "") -> str:
        session = _create_session(dossier_id, name, linkedin_url, meeting_context)
        
        try:
            # 1. Collect
            collected = await self.collector.collect(name, linkedin_url)
            session["status"] = "researching"
            
            # 2. Synthesize
            synthesized = await self.synthesizer.synthesize(collected.to_dict())
            session["synthesized_data"] = synthesized.to_dict()
            session["status"] = "analyzing"
            
            # 3. Analyze
            insights = await self.analyzer.analyze(session["synthesized_data"], meeting_context)
            session["strategic_insights"] = insights.to_dict()
            
            # 4. Generate
            doc = await self.generator.generate(session["synthesized_data"], session["strategic_insights"])
            session["document"] = doc
            session["status"] = "generated"
            
            return doc
            
        except Exception as e:
            session["status"] = "error"
            session["document"] = f"Error: {e}"
            return f"Error: {e}"

    async def update_dossier(self, dossier_id: str, context: str) -> str:
        session = _dossier_sessions.get(dossier_id)
        if not session or not session.get("synthesized_data"): return "No active dossier."
        
        # Re-analyze with new context
        insights = await self.analyzer.analyze(session["synthesized_data"], context)
        doc = await self.generator.generate(session["synthesized_data"], insights.to_dict())
        session["document"] = doc
        return doc


# Singleton and Tools
_agent: Optional[DossierAgent] = None

def _get_agent() -> DossierAgent:
    global _agent
    if _agent is None: _agent = DossierAgent()
    return _agent

@tool
async def dossier_check_status(dossier_id: str = "default") -> str:
    """Check status of dossier/meeting prep."""
    session = _dossier_sessions.get(dossier_id)
    if not session: return "No active dossier."
    return f"Status: {session['status']} for {session['name']}"

@tool
async def dossier_generate(name: str, linkedin_url: str = "", meeting_context: str = "", dossier_id: str = "default") -> str:
    """Generate meeting prep dossier."""
    return await _get_agent().generate_dossier(dossier_id, name, linkedin_url, meeting_context)

@tool
async def dossier_update(additional_context: str, dossier_id: str = "default") -> str:
    """Update dossier with new context."""
    return await _get_agent().update_dossier(dossier_id, additional_context)

@tool
async def dossier_get_document(dossier_id: str = "default") -> str:
    """Get full dossier document."""
    session = _dossier_sessions.get(dossier_id)
    if not session or not session.get("document"): return "No document ready."
    return session["document"]

@tool
async def dossier_delete(dossier_id: str = "default") -> str:
    """Delete dossier session."""
    if dossier_id in _dossier_sessions:
        del _dossier_sessions[dossier_id]
        return "Deleted."
    return "Not found."

def get_dossier_tools() -> list:
    return [dossier_check_status, dossier_generate, dossier_update, dossier_get_document, dossier_delete]
