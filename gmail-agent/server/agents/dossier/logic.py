import os
import re
import time
import json
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from langchain_google_genai import ChatGoogleGenerativeAI


# Models
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
        return self.__dict__


# Templates
DOSSIER_TITLE = "# Meeting Prep Dossier: {name}"
STRATEGIC_SECTION = "## Strategic Insights\n**Meeting Strategy:** {meeting_strategy}\n**Negotiation Style:** {negotiation_style}\n**Recommended Approach:** {recommended_approach}"


class DataCollector:
    def __init__(self, serper_api_key=None):
        self.api_key = serper_api_key or os.environ.get("SERPER_API_KEY")

    async def collect(self, name, url=""):
        return {"name": name, "web_results": {}}


class ResearchSynthesizer:
    def __init__(self, key=None):
        api_key = key or os.environ.get("GOOGLE_API_KEY")
        self.llm = (
            ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=api_key)
            if api_key
            else None
        )

    async def synthesize(self, data):
        return {"name": data.get("name"), "biographical_summary": "Synthesizing..."}


class StrategicAnalyzer:
    def __init__(self, key=None):
        api_key = key or os.environ.get("GOOGLE_API_KEY")
        self.llm = (
            ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=api_key)
            if api_key
            else None
        )

    async def analyze(self, data, context=""):
        return {
            "meeting_strategy": "Be prepared.",
            "negotiation_style": "Proactive",
            "recommended_approach": "Start with relationship building and focus on mutual benefits.",
        }


class DossierGenerator:
    async def generate(self, research, strategy):
        return f"# Dossier for {research.get('name')}\n\n{STRATEGIC_SECTION.format(**strategy)}"


_dossier_sessions: Dict[str, Dict[str, Any]] = {}


class DossierAgent:
    def __init__(self, google_api_key=None, serper_api_key=None):
        self.collector = DataCollector(serper_api_key)
        self.synthesizer = ResearchSynthesizer(google_api_key)
        self.analyzer = StrategicAnalyzer(google_api_key)
        self.generator = DossierGenerator()

    async def generate_dossier(self, dossier_id, name, linkedin_url="", context=""):
        _dossier_sessions[dossier_id] = {"name": name, "status": "generating"}
        res = await self.collector.collect(name)
        syn = await self.synthesizer.synthesize(res)
        ins = await self.analyzer.analyze(syn, context)
        doc = await self.generator.generate(syn, ins)
        _dossier_sessions[dossier_id].update({"status": "generated", "document": doc})
        return doc
