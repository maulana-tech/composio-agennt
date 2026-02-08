"""
Dossier Agent - Automated Meeting Prep & Person Research Dossier Generator.

Generates comprehensive one-page meeting prep dossiers by researching a person
using web search (Serper API) and LinkedIn scraping, then synthesising the data
with Gemini and producing strategic insights with Gemini.

Usage:
    The agent operates in four pipeline stages:
    1. Data Collection  - Web search + LinkedIn scraping
    2. Research Synthesis - Gemini structures raw data
    3. Strategic Analysis - Gemini produces relationship maps & conversation starters
    4. Document Generation - Assembles Markdown dossier from templates

Modules:
    - dossier_agent: Orchestrator, session store, and LangChain tool exports
    - data_collector: Multi-source data collection (Serper + LinkedIn)
    - research_synthesizer: Gemini-powered research synthesis
    - strategic_analyzer: Gemini-powered strategic analysis and fallback
    - dossier_generator: Template-based Markdown document assembly
    - templates.dossier_template: Static section templates and builder functions
"""

from .dossier_agent import (
    DossierAgent,
    dossier_check_status,
    dossier_generate,
    dossier_update,
    dossier_get_document,
    dossier_delete,
    get_dossier_tools,
    _dossier_sessions,
    _get_session,
    _create_session,
    _clear_session,
    _cleanup_expired_sessions,
    SESSION_TTL_SECONDS,
)
from .data_collector import (
    DataCollector,
    CollectedData,
    LinkedInProfile,
    WebSearchResult,
    SerperClient,
    LinkedInScraper,
    ComposioLinkedInClient,
)
from .research_synthesizer import ResearchSynthesizer, SynthesizedResearch
from .strategic_analyzer import StrategicAnalyzer, StrategicInsights
from .dossier_generator import DossierGenerator
from .exceptions import (
    DossierError,
    DossierCollectionError,
    DossierSynthesisError,
    DossierAnalysisError,
    DossierGenerationError,
    DossierSessionError,
)

__all__ = [
    # Orchestrator & tools
    "DossierAgent",
    "dossier_check_status",
    "dossier_generate",
    "dossier_update",
    "dossier_get_document",
    "dossier_delete",
    "get_dossier_tools",
    # Session store helpers
    "_dossier_sessions",
    "_get_session",
    "_create_session",
    "_clear_session",
    "_cleanup_expired_sessions",
    "SESSION_TTL_SECONDS",
    # Data collection
    "DataCollector",
    "CollectedData",
    "LinkedInProfile",
    "WebSearchResult",
    "SerperClient",
    "LinkedInScraper",
    "ComposioLinkedInClient",
    # Research synthesis
    "ResearchSynthesizer",
    "SynthesizedResearch",
    # Strategic analysis
    "StrategicAnalyzer",
    "StrategicInsights",
    # Document generation
    "DossierGenerator",
    # Exceptions
    "DossierError",
    "DossierCollectionError",
    "DossierSynthesisError",
    "DossierAnalysisError",
    "DossierGenerationError",
    "DossierSessionError",
]
