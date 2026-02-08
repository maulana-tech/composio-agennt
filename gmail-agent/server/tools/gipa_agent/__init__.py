"""
GIPA Request Agent - Automated Government Information (Public Access) Application Generator.

Generates legally robust GIPA applications for New South Wales (with future support
for Federal FOI and Victorian FOI).

Usage:
    The agent operates in two phases:
    1. Clarification - Interviews the user to collect all required variables
    2. Generation - Assembles the formal GIPA application document

Modules:
    - gipa_agent: Orchestrator and LangChain tool exports
    - clarification_engine: Variable extraction and validation
    - document_generator: Template assembly and legal formatting
    - synonym_expander: AI-powered keyword definition expansion
    - jurisdiction_config: Jurisdiction-specific legal references
    - templates.boilerplate: Static legal clauses and exclusions
"""

from .gipa_agent import (
    GIPARequestAgent,
    gipa_check_status,
    gipa_start_request,
    gipa_process_answer,
    gipa_generate_document,
    gipa_expand_keywords,
    get_gipa_tools,
)
from .clarification_engine import ClarificationEngine, GIPARequestData, TargetPerson
from .document_generator import GIPADocumentGenerator
from .synonym_expander import SynonymExpander
from .jurisdiction_config import (
    JurisdictionConfig,
    NSW_CONFIG,
    FEDERAL_CONFIG,
    VIC_CONFIG,
    get_jurisdiction_config,
)

__all__ = [
    "GIPARequestAgent",
    "gipa_check_status",
    "gipa_start_request",
    "gipa_process_answer",
    "gipa_generate_document",
    "gipa_expand_keywords",
    "get_gipa_tools",
    "ClarificationEngine",
    "GIPARequestData",
    "TargetPerson",
    "GIPADocumentGenerator",
    "SynonymExpander",
    "JurisdictionConfig",
    "NSW_CONFIG",
    "FEDERAL_CONFIG",
    "VIC_CONFIG",
    "get_jurisdiction_config",
]
