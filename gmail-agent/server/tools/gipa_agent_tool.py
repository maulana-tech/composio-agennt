"""
GIPA Request Agent - Consolidated Tool.

This module consolidates the GIPA agent functionality into a single file for
easier distribution and integration. It handles the clarification, validation,
and generation of GIPA (Government Information Public Access) applications
for NSW and other jurisdictions.

Components:
1. JurisdictionConfig: Configuration for different jurisdictions (NSW, Federal, VIC)
2. SynonymExpander: AI-powered keyword expansion for legal definitions
3. Boilerplate: Static legal clauses and templates
4. ClarificationEngine: Logic for interviewing the user to collect request data
5. DocumentGenerator: Logic for assembling the final legal document
6. GIPARequestAgent: Orchestrator and LangChain tool exports
"""

import os
import json
import re
import asyncio
from typing import Dict, Any, List, Optional, Tuple, Literal
from datetime import date
from dataclasses import dataclass, field
from html import escape as html_escape

from pydantic import BaseModel, Field, model_validator
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
import httpx
import re
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI

async def find_rti_email(agency_name: str) -> Optional[str]:
    """Search for an agency's RTI/GIPA email using Serper API."""
    serper_api_key = os.environ.get("SERPER_API_KEY")
    if not serper_api_key:
        return None

    try:
        queries = [
            f'"{agency_name}" GIPA RTI email address NSW',
            f'"{agency_name}" right to information email',
        ]
        
        async with httpx.AsyncClient() as client:
            for query in queries:
                print(f"DEBUG: Searching RTI email for: {query}")
                response = await client.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": serper_api_key, "Content-Type": "application/json"},
                    json={"q": query, "num": 5},
                    timeout=10
                )
                if response.status_code != 200:
                    print(f"DEBUG: Serper error: {response.status_code}")
                    continue
                
                data = response.json()
                # 1. Look in snippets
                snippets = " ".join([r.get("snippet", "") for r in data.get("organic", [])])
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.gov\.au', snippets)
                if email_match:
                    print(f"DEBUG: Found email in snippet: {email_match.group(0)}")
                    return email_match.group(0)
                
                # 2. Look in titles
                titles = " ".join([r.get("title", "") for r in data.get("organic", [])])
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.gov\.au', titles)
                if email_match:
                    print(f"DEBUG: Found email in title: {email_match.group(0)}")
                    return email_match.group(0)
                    
        return None
    except Exception as e:
        print(f"DEBUG: RTI Email search error: {e}")
        return None


# ===========================================================================
# 1. JURISDICTION CONFIGURATION
# ===========================================================================

@dataclass(frozen=True)
class JurisdictionConfig:
    """Immutable configuration for a specific jurisdiction's information access laws."""

    # Jurisdiction identifier
    jurisdiction: str

    # Legislation references
    act_name: str
    act_short_name: str
    act_year: int

    # Fee reduction
    fee_reduction_section: str
    fee_regulation_clause: str
    base_application_fee: str
    processing_fee_rate: str

    # Record definition
    record_definition_reference: str

    # Correspondence platforms to include in definitions
    correspondence_platforms: List[str] = field(default_factory=list)

    # Common terminology mapping
    request_term: str = (
        "information request"  # NSW: "information request", Federal: "FOI request"
    )
    applicant_term: str = "applicant"


NSW_CONFIG = JurisdictionConfig(
    jurisdiction="NSW",
    act_name="Government Information (Public Access) Act 2009",
    act_short_name="GIPA Act",
    act_year=2009,
    fee_reduction_section="s.127",
    fee_regulation_clause="clause 9(c) of the Government Information (Public Access) Regulation 2018",
    base_application_fee="$30",
    processing_fee_rate="$30/hr",
    record_definition_reference="Schedule 4, clause 10 of the GIPA Act",
    correspondence_platforms=[
        "email",
        "SMS",
        "WhatsApp",
        "Signal",
        "WeChat",
        "Wickr",
        "Microsoft Teams messages",
        "Slack messages",
    ],
    request_term="information request",
    applicant_term="applicant",
)

FEDERAL_CONFIG = JurisdictionConfig(
    jurisdiction="Federal",
    act_name="Freedom of Information Act 1982",
    act_short_name="FOI Act",
    act_year=1982,
    fee_reduction_section="s.29",
    fee_regulation_clause="regulation 3 of the Freedom of Information (Charges) Regulations 2019",
    base_application_fee="$0",
    processing_fee_rate="$15/hr (after first 5 hours)",
    record_definition_reference="s.4(1) of the FOI Act",
    correspondence_platforms=[
        "email",
        "SMS",
        "WhatsApp",
        "Signal",
        "Microsoft Teams messages",
    ],
    request_term="FOI request",
    applicant_term="applicant",
)

VIC_CONFIG = JurisdictionConfig(
    jurisdiction="Victoria",
    act_name="Freedom of Information Act 1982 (Vic)",
    act_short_name="FOI Act (Vic)",
    act_year=1982,
    fee_reduction_section="s.22",
    fee_regulation_clause="regulation 6 of the Freedom of Information (Access Charges) Regulations 2014",
    base_application_fee="$30.60",
    processing_fee_rate="$22.50/hr",
    record_definition_reference="s.5(1) of the FOI Act (Vic)",
    correspondence_platforms=[
        "email",
        "SMS",
        "WhatsApp",
        "Signal",
        "Microsoft Teams messages",
    ],
    request_term="FOI request",
    applicant_term="applicant",
)

_JURISDICTION_MAP = {
    "nsw": NSW_CONFIG,
    "new south wales": NSW_CONFIG,
    "federal": FEDERAL_CONFIG,
    "commonwealth": FEDERAL_CONFIG,
    "vic": VIC_CONFIG,
    "victoria": VIC_CONFIG,
}


def get_jurisdiction_config(jurisdiction: str) -> JurisdictionConfig:
    """
    Get the configuration for a given jurisdiction.

    Args:
        jurisdiction: Jurisdiction name (case-insensitive). Accepts:
            - "NSW", "New South Wales"
            - "Federal", "Commonwealth"
            - "VIC", "Victoria"
    """
    key = jurisdiction.strip().lower()
    config = _JURISDICTION_MAP.get(key)
    if config is None:
        return NSW_CONFIG  # Default to NSW if unknown
    return config


# ===========================================================================
# 2. SYNONYM EXPANDER
# ===========================================================================

class SynonymExpander:
    """
    AI-powered keyword synonym/definition expansion for GIPA applications.

    Given a keyword like "Koala", generates a legal definition:
    'Define "Koala" to include: Phascolarctos cinereus, native bear,
    arboreal marsupial, koala habitat, koala population.'
    """

    def __init__(self, google_api_key: Optional[str] = None):
        api_key = google_api_key or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            # We allow init without key, but methods will fail or use fallback
            self.llm = None
        else:
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash",
                temperature=0.1,
                google_api_key=api_key,
            )
        self._cache: Dict[str, str] = {}

    async def expand_keyword(self, keyword: str) -> str:
        """
        Expand a single keyword into a legal definition string.
        """
        # Check cache first
        cache_key = keyword.strip().lower()
        if cache_key in self._cache:
            return self._cache[cache_key]

        if not self.llm:
             return self._fallback_expansion(keyword)

        try:
            response = await self.llm.ainvoke(
                [
                    SystemMessage(content=self._get_system_prompt()),
                    HumanMessage(
                        content=f"Expand this keyword for a GIPA legal definition: {keyword}"
                    ),
                ]
            )

            # Parse the response
            expansions = self._parse_expansions(response.content, keyword)

            # Format into definition string
            if expansions:
                expansion_str = ", ".join(expansions)
                result = f'Define "{keyword}" to include: {expansion_str}.'
            else:
                result = self._fallback_expansion(keyword)

            # Cache the result
            self._cache[cache_key] = result
            return result

        except Exception as e:
            print(f"SynonymExpander error for '{keyword}': {e}")
            return self._fallback_expansion(keyword)

    def _fallback_expansion(self, keyword: str) -> str:
        """Basic fallback definition when AI expansion fails."""
        return (
            f'Define "{keyword}" to include all references to {keyword}, '
            f'including abbreviations, acronyms, and alternative spellings.'
        )

    async def expand_keywords(self, keywords: List[str]) -> List[str]:
        """Expand multiple keywords into definition strings."""
        results = []
        for keyword in keywords:
            definition = await self.expand_keyword(keyword)
            results.append(definition)
        return results

    def _get_system_prompt(self) -> str:
        return """You are a legal terminology expansion engine for Australian government information access (GIPA/FOI) applications.

Your task: Given a keyword, generate a comprehensive list of synonyms, alternative names, scientific names, abbreviations, and related terms that a government officer might use when referring to the same concept.

PURPOSE: This definition will be inserted into a formal legal document to prevent the government agency from narrowly interpreting the keyword and excluding relevant records.

RULES:
1. Include scientific/Latin names where applicable (especially for flora/fauna).
2. Include common abbreviations and acronyms.
3. Include Australian-specific colloquialisms and terminology.
4. Include both formal and informal terms government officers might use.
5. Include related program names, policy names, or legislative references if well-known.
6. Keep the list to 5-12 terms maximum - be comprehensive but not absurd.
7. Do NOT include the original keyword itself in the expansion list.
8. Focus on terms that would actually appear in government correspondence.

Return ONLY a JSON array of strings. No explanation, no markdown.
"""

    def _parse_expansions(self, content: str, keyword: str) -> List[str]:
        """Parse the LLM response into a list of expansion terms."""
        content = content.strip()
        
        # Try direct JSON parse
        try:
            result = json.loads(content)
            if isinstance(result, list):
                return [str(item) for item in result if str(item).lower() != keyword.lower()]
        except json.JSONDecodeError:
            pass
            
        # Try extracting JSON array from markdown
        json_match = re.search(r"\[[\s\S]*?\]", content)
        if json_match:
            try:
                result = json.loads(json_match.group())
                if isinstance(result, list):
                    return [str(item) for item in result if str(item).lower() != keyword.lower()]
            except json.JSONDecodeError:
                pass

        # Fallback: try to split by commas
        parts = re.split(r"[,\n]", content)
        expansions = []
        for part in parts:
            cleaned = part.strip().strip('"').strip("'").strip("-").strip("*").strip()
            if cleaned and cleaned.lower() != keyword.lower() and len(cleaned) > 1:
                expansions.append(cleaned)

        return expansions[:12]


# ===========================================================================
# 3. BOILERPLATE TEMPLATES
# ===========================================================================

EXCLUSION_MEDIA_ALERTS = (
    "Exclude all computer-generated daily media alerts, media monitoring "
    "summaries, and automated news digests that are distributed as bulk "
    "communications to multiple recipients."
)

EXCLUSION_DUPLICATES = (
    "Exclude exact duplicates of documents already captured by this request. "
    "Where a document appears in multiple mailboxes or filing systems, only "
    "one copy need be provided."
)

EXCLUSION_AUTOREPLY = (
    "Exclude automated out-of-office replies, delivery receipts, read "
    "receipts, and calendar invitation acceptances/declines."
)

STANDARD_EXCLUSIONS = [
    EXCLUSION_MEDIA_ALERTS,
    EXCLUSION_DUPLICATES,
    EXCLUSION_AUTOREPLY,
]

CONTRACTOR_INCLUSION = (
    "The above search terms extend to records held by, or created by, "
    "external contractors, consultants, or secondees performing work on "
    "behalf of the agency during the specified period, including records "
    "held on personal devices where such devices were used for official "
    "business."
)

def get_record_definition(config: JurisdictionConfig) -> str:
    """Generate the record definition clause for the given jurisdiction."""
    return (
        f'Define "record" as per {config.record_definition_reference}, '
        f"to include any document, database entry, file, note, memorandum, "
        f"briefing paper, cabinet submission, minute, report, or any other "
        f"recorded information regardless of its form or medium."
    )

def get_correspondence_definition(config: JurisdictionConfig) -> str:
    """Generate the correspondence definition clause."""
    platforms = ", ".join(config.correspondence_platforms)
    return (
        f'Define "correspondence" to include all forms of written '
        f"communication, whether formal or informal, including but not "
        f"limited to: {platforms}. This includes messages sent or received "
        f"on both official and personal devices or accounts where such "
        f"communications relate to official business."
    )

def get_fee_reduction_paragraph(
    config: JurisdictionConfig,
    applicant_type: str,
    public_interest_justification: str,
    applicant_organization: str = "",
    charity_status: str = "",
) -> str:
    """Generate the fee reduction request paragraph."""
    # Header clause
    header = (
        f"The Applicant requests, pursuant to {config.fee_reduction_section} of the "
        f"{config.act_short_name} and {config.fee_regulation_clause}, that "
        f"processing fees be reduced by 50%."
    )

    # Build justification based on applicant type
    justification_parts = []

    if applicant_type == "nonprofit":
        org_text = f" ({applicant_organization})" if applicant_organization else ""
        charity_text = (
            f" (registered charity: {charity_status})" if charity_status else ""
        )
        justification_parts.append(
            f"The Applicant is a not-for-profit organisation{org_text}{charity_text} "
            f"and this request is made in the public interest."
        )
    elif applicant_type == "journalist":
        org_text = f", {applicant_organization}" if applicant_organization else ""
        justification_parts.append(
            f"The Applicant is a journalist{org_text} and the information sought "
            f"is for the purpose of disseminating information to the public, "
            f"thereby advancing government transparency and accountability."
        )
    elif applicant_type == "student":
        org_text = f" at {applicant_organization}" if applicant_organization else ""
        justification_parts.append(
            f"The Applicant is a student{org_text} conducting academic research. "
            f"The information sought will contribute to public knowledge and "
            f"scholarly understanding of matters of public importance."
        )

    # Always include the public interest justification
    if public_interest_justification:
        justification_parts.append(f"Specifically, {public_interest_justification}")

    justification = " ".join(justification_parts)

    return f"{header}\n\n{justification}"

def build_scope_and_definitions(
    config: JurisdictionConfig,
    keyword_definitions: list[str],
) -> str:
    """Assemble the complete Scope and Definitions section."""
    lines = ["## Scope and Definitions", "", "The above search terms —", ""]

    # 1. Record definition
    lines.append(get_record_definition(config))
    lines.append("")

    # 2. Standard exclusions
    for exclusion in STANDARD_EXCLUSIONS:
        lines.append(exclusion)
        lines.append("")

    # 3. Contractor inclusion
    lines.append(CONTRACTOR_INCLUSION)
    lines.append("")

    # 4. Dynamic keyword definitions
    for definition in keyword_definitions:
        lines.append(definition)
        lines.append("")

    # 5. Correspondence definition
    lines.append(get_correspondence_definition(config))
    lines.append("")

    return "\n".join(lines)


# ===========================================================================
# 4. CLARIFICATION ENGINE (Data Models & Logic)
# ===========================================================================

class TargetPerson(BaseModel):
    """A person or role that is a sender/receiver in the search query."""
    name: str = Field(description="Full name or role title")
    role: Optional[str] = Field(default=None, description="Job title or role")
    direction: Literal["sender", "receiver", "both"] = Field(
        default="both", description="Whether this person is the sender, receiver, or both"
    )

class GIPARequestData(BaseModel):
    """All variables needed to generate a complete GIPA application."""
    agency_name: str = Field(description="Full name of the target government agency")
    agency_email: Optional[str] = Field(default=None)
    applicant_name: str = Field(description="Full name of the applicant")
    applicant_organization: Optional[str] = Field(default=None)
    applicant_type: Literal["individual", "nonprofit", "journalist", "student", "other"] = Field(default="individual")
    charity_status: Optional[str] = Field(default=None)
    public_interest_justification: str = Field(description="Public interest reason")
    start_date: str = Field(description="Start date")
    end_date: str = Field(description="End date")
    targets: List[TargetPerson] = Field(default_factory=list)
    keywords: List[str] = Field(min_length=1)
    jurisdiction: str = Field(default="NSW")
    fee_reduction_eligible: bool = Field(default=False)
    summary_sentence: str = Field(default="")

    @model_validator(mode="after")
    def compute_fee_eligibility(self):
        if self.applicant_type in ("nonprofit", "journalist", "student"):
            self.fee_reduction_eligible = True
        return self


REQUIRED_FIELDS = [
    {"field": "agency_name", "question": "Which government agency are you requesting information from?", "priority": 1},
    {"field": "applicant_name", "question": "What is your full name (as the applicant)?", "priority": 2},
    {"field": "applicant_type", "question": "What type of applicant are you? (individual, nonprofit, journalist, student)", "priority": 3},
    {"field": "public_interest_justification", "question": "Why is this information important? Please explain the public interest reason.", "priority": 4},
    {"field": "start_date", "question": "What is the START date for the search period?", "priority": 5},
    {"field": "end_date", "question": "What is the END date for the search period?", "priority": 6},
    {"field": "targets", "question": "Who are the specific people or roles whose correspondence you want?", "priority": 7},
    {"field": "keywords", "question": "What specific keywords or phrases must appear in the documents?", "priority": 8},
]

CONDITIONAL_FIELDS = [
    {
        "field": "applicant_organization",
        "condition_field": "applicant_type",
        "condition_values": ["nonprofit", "journalist", "student"],
        "question": "What is the name of your organisation/publication/university?",
    },
    {
        "field": "charity_status",
        "condition_field": "applicant_type",
        "condition_values": ["nonprofit"],
        "question": "What is your charity registration number or ABN?",
    },
    {
        "field": "agency_email",
        "condition_field": "agency_name",
        "condition_values": None,
        "question": "Do you know the specific GIPA/Right to Information email address for {agency_name}?",
    },
]

class ClarificationEngine:
    """Extracts GIPA request variables from conversation."""

    def __init__(self, google_api_key: Optional[str] = None):
        api_key = google_api_key or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            self.llm = None
        else:
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash",
                temperature=0,
                google_api_key=api_key,
            )

    async def extract_variables(
        self,
        user_message: str,
        current_data: Dict[str, Any],
        conversation_context: str = "",
    ) -> Tuple[Dict[str, Any], List[str], bool]:
        """Extract variables and determine missing questions."""
        if not self.llm:
            return current_data, self._get_missing_field_questions(current_data), False

        extraction_prompt = self._build_extraction_prompt(
            user_message, current_data, conversation_context
        )

        try:
            response = await self.llm.ainvoke(
                [
                    SystemMessage(content=self._get_system_prompt()),
                    HumanMessage(content=extraction_prompt),
                ]
            )
            parsed = self._parse_extraction_response(response.content)

            updated_data = {**current_data}
            for key, value in parsed.get("extracted", {}).items():
                if value is not None and value != "" and value != []:
                    updated_data[key] = value

            missing_questions = self._get_missing_field_questions(updated_data)
            is_complete = len(missing_questions) == 0

            return updated_data, missing_questions, is_complete

        except Exception as e:
            print(f"ClarificationEngine extraction error: {e}")
            missing_questions = self._get_missing_field_questions(current_data)
            return current_data, missing_questions, False

    def _get_system_prompt(self) -> str:
        return """You are a data extraction engine for NSW GIPA (Government Information Public Access) applications.
Your task is to extract ALL possible structured information from a user's message.
Return your response as valid JSON with "extracted" object containing fields."""

    def _build_extraction_prompt(self, user_message, current_data, conversation_context):
        return f"""
CURRENTLY COLLECTED: {json.dumps(current_data)}
CONTEXT: {conversation_context}
USER MESSAGE: {user_message}

Extract information for a GIPA (NSW Information Access) application.

FIELDS TO EXTRACT:
- agency_name: The government department (e.g., 'Department of Planning')
- applicant_name: Full name of the requester
- applicant_type: individual, nonprofit, journalist, or student
- applicant_organization: Name of organization/Greenpeace/etc.
- charity_status: Charity registration number or ABN (if nonprofit)
- public_interest_justification: Why the info is needed
- start_date: Start of search period
- end_date: End of search period
- targets: List of people/roles (e.g. [{{"name": "Minister", "role": "Minister for Water"}}])
- keywords: List of topics (e.g. ["water licensing", "Murray-Darling"])
- agency_email: Specific GIPA/RTI email for the agency
- fee_reduction_eligible: boolean (True if nonprofit/journalist)

Return ONLY JSON in format: {{"extracted": {{ "key": "value" }}}}
"""

    def _parse_extraction_response(self, content: str) -> Dict[str, Any]:
        try:
            # Try to find JSON block
            json_match = re.search(r"```json\s*([\s\S]*?)\s*```", content)
            if json_match:
                return json.loads(json_match.group(1))
            # Try raw JSON
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                return json.loads(json_match.group())
        except Exception:
            pass
        return {"extracted": {}}

    def _get_missing_field_questions(self, data: Dict[str, Any]) -> List[str]:
        questions = []
        # Required fields
        for field_info in sorted(REQUIRED_FIELDS, key=lambda x: x["priority"]):
            val = data.get(field_info["field"])
            if val is None or val == "" or val == []:
                questions.append(field_info["question"])

        # Conditional fields
        for cond_info in CONDITIONAL_FIELDS:
            field_name = cond_info["field"]
            if data.get(field_name):
                continue
            
            cond_field = cond_info["condition_field"]
            cond_val = data.get(cond_field)
            
            if cond_val is None:
                continue

            target_vals = cond_info["condition_values"]
            if target_vals is None or cond_val in target_vals:
                q = cond_info["question"]
                if "{" in q:
                    q = q.format(**data)
                questions.append(q)
                
        return questions

    def validate_data(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []
        required = ["agency_name", "applicant_name", "public_interest_justification", "start_date", "end_date"]
        for f in required:
            if not data.get(f):
                errors.append(f"Missing required field: {f}")
        
        if not data.get("keywords"):
             errors.append("At least one keyword is required")
             
        return len(errors) == 0, errors

    def build_gipa_request_data(self, data: Dict[str, Any]) -> GIPARequestData:
        # Transform dict targets to objects if needed
        targets = []
        for t in data.get("targets", []):
            if isinstance(t, dict):
                targets.append(TargetPerson(**t))
            else:
                targets.append(t)
        
        # Build shallow copy to avoid mutation issues
        build_data = data.copy()
        build_data["targets"] = targets
        
        if "applicant_type" not in build_data:
            build_data["applicant_type"] = "individual"

        return GIPARequestData(**build_data)


# ===========================================================================
# 5. DOCUMENT GENERATOR
# ===========================================================================

class GIPADocumentGenerator:
    """Generates the complete GIPA application document."""

    def __init__(self, synonym_expander: Optional[SynonymExpander] = None):
        self.synonym_expander = synonym_expander

    async def generate(self, data: GIPARequestData, config: Optional[JurisdictionConfig] = None) -> str:
        if config is None:
            config = get_jurisdiction_config(data.jurisdiction)

        sections = []
        # Header (Date, Agency, Email, RE, Salutation)
        sections.append(self._build_header(data, config))
        
        # Summary paragraph
        sections.append(self._build_summary(data, config))

        # Fee Reduction (if applicable)
        if data.fee_reduction_eligible:
            fee_section = self._build_fee_reduction(data, config)
            if fee_section:
                sections.append(fee_section)

        # Search Terms
        sections.append(self._build_search_terms(data, config))

        # Scope and Definitions
        keyword_definitions = await self._expand_keywords(data.keywords)
        sections.append(
            build_scope_and_definitions(
                config=config,
                keyword_definitions=keyword_definitions,
            )
        )
        
        # Closing
        sections.append(self._build_closing(data))

        return "\n\n".join(sections)

    async def generate_html(self, data: GIPARequestData, config: Optional[JurisdictionConfig] = None) -> str:
        """Generate HTML version for Gmail."""
        if config is None:
             config = get_jurisdiction_config(data.jurisdiction)
             
        from html import escape as e
        date_str = datetime.now().strftime("%d %B %Y")
        
        html = []
        html.append("<div style='font-family: Arial, sans-serif; font-size: 14px; color: #333; line-height: 1.6; max-width: 800px;'>")
        
        # Header
        html.append(f"<p>{e(date_str)}</p>")
        html.append(f"<p>{e(data.agency_name)}</p>")
        if data.agency_email:
            html.append(f"<p>Via email: <a href='mailto:{e(data.agency_email)}'>{e(data.agency_email)}</a></p>")
        
        html.append(f"<p><strong>RE: {e(config.act_name)} ({e(config.act_short_name)}) - {e(config.request_term.title())}</strong></p>")
        html.append("<p>Dear Right to Information Officer,</p>")
        
        # Summary
        org_clause = f" on behalf of {e(data.applicant_organization)}" if data.applicant_organization else ""
        summary_text = data.summary_sentence or self._generate_summary(data)
        html.append(f"<p>{e(data.applicant_name)}{org_clause} seeks access to information under the {e(config.act_short_name)} regarding:</p>")
        html.append(f"<p>{e(summary_text)}</p>")

        # Search Terms
        html.append("<h2 style='font-size: 16px; border-bottom: 1px solid #eee; padding-bottom: 5px;'>Search Terms</h2>")
        html.append("<p>The Applicant requests access to the following records:</p>")
        html.append("<ul>")
        html.append(f"<li><strong>Date Range:</strong> {e(data.start_date)} to {e(data.end_date)}.</li>")
        
        if data.targets:
             targets_str = " AND ".join(self._format_target(t) for t in data.targets)
             html.append(f"<li><strong>Party:</strong> All correspondence involving {e(targets_str)}.</li>")
        else:
             html.append(f"<li><strong>Parties:</strong> All officers and staff of {e(data.agency_name)}.</li>")
             
        kw_clause = " AND ".join(f'&ldquo;{e(kw)}&rdquo;' for kw in data.keywords)
        html.append(f"<li><strong>Keywords:</strong> All correspondence containing the words {kw_clause}.</li>")
        html.append("</ul>")

        # Scope and Definitions
        html.append("<h2 style='font-size: 16px; border-bottom: 1px solid #eee; padding-bottom: 5px;'>Scope and Definitions</h2>")
        html.append("<p>The above search terms —</p>")
        html.append("<ul style='padding-left: 20px;'>")
        html.append(f"<li>{e(get_record_definition(config))}</li>")
        for exclusion in STANDARD_EXCLUSIONS:
            html.append(f"<li>{e(exclusion)}</li>")
        html.append(f"<li>{e(CONTRACTOR_INCLUSION)}</li>")
        
        keyword_definitions = await self._expand_keywords(data.keywords)
        for definition in keyword_definitions:
            html.append(f"<li>{e(definition)}</li>")
        
        html.append(f"<li>{e(get_correspondence_definition(config))}</li>")
        html.append("</ul>")

        # Closing
        html.append("<p>I look forward to your acknowledgment of this request within the statutory timeframe.</p>")
        html.append("<p>Should you require any clarification regarding the scope of this request, please do not hesitate to contact me.</p>")
        html.append("<br><p>Yours faithfully,</p>")
        html.append(f"<p><strong>{e(data.applicant_name)}</strong>")
        if data.applicant_organization:
            html.append(f"<br>{e(data.applicant_organization)}")
        html.append("</p></div>")
        
        return "\n".join(html)

    def _build_header(self, data, config) -> str:
        date_str = datetime.now().strftime("%d %B %Y")
        email_line = f"Via email: {data.agency_email}" if data.agency_email else ""
        return f"{date_str}\n{data.agency_name}\n{email_line}\n\nRE: {config.act_name} ({config.act_short_name}) - {config.request_term.title()}\n\nDear Right to Information Officer,"

    def _build_summary(self, data, config) -> str:
        org_clause = f" on behalf of {data.applicant_organization}" if data.applicant_organization else ""
        summary_text = data.summary_sentence or self._generate_summary(data)
        return f"{data.applicant_name}{org_clause} seeks access to information under the {config.act_short_name} regarding:\n{summary_text}"

    def _build_fee_reduction(self, data, config) -> Optional[str]:
        if not data.fee_reduction_eligible:
            return None
        return "## Fee Reduction Request\n\n" + get_fee_reduction_paragraph(
            config, data.applicant_type, data.public_interest_justification,
            data.applicant_organization or "", data.charity_status or ""
        )

    def _build_search_terms(self, data, config) -> str:
        lines = ["## Search Terms", "", "The Applicant requests access to the following records:", ""]
        lines.append(f"Date Range: {data.start_date} to {data.end_date}.")
        
        if data.targets:
             targets_str = " AND ".join(self._format_target(t) for t in data.targets)
             lines.append(f"Party: All correspondence involving {targets_str}.")
        else:
             lines.append(f"Parties: All officers and staff of {data.agency_name}.")
             
        kw_clause = " AND ".join(f'"{kw}"' for kw in data.keywords)
        lines.append(f"Keywords: All correspondence containing the words {kw_clause}.")
        lines.append("")
        return "\n".join(lines)

    def _format_target(self, target: TargetPerson) -> str:
        name = f"{target.name} ({target.role})" if target.role else target.name
        return name

    def _build_closing(self, data) -> str:
        org_line = f"\n{data.applicant_organization}" if data.applicant_organization else ""
        return f"I look forward to your acknowledgment of this request within the statutory timeframe.\nShould you require any clarification regarding the scope of this request, please do not hesitate to contact me.\n\nYours faithfully,\n\n{data.applicant_name}{org_line}"

    def _generate_summary(self, data) -> str:
        return f"All correspondence held by {data.agency_name} containing references to {', '.join(data.keywords)}, for the period {data.start_date} to {data.end_date}."

    async def _expand_keywords(self, keywords: List[str]) -> List[str]:
        if self.synonym_expander:
            return await self.synonym_expander.expand_keywords(keywords)
        return [f'Define "{k}" to include all references to {k}.' for k in keywords]


# ===========================================================================
# 6. ORCHESTRATOR AGENT
# ===========================================================================

# Session Store
_gipa_sessions: Dict[str, Dict[str, Any]] = {}

def _get_or_create_session(session_id: str) -> Dict[str, Any]:
    if session_id not in _gipa_sessions:
        _gipa_sessions[session_id] = {
            "data": {},
            "context": "",
            "status": "collecting",
            "document": None,
        }
    return _gipa_sessions[session_id]

class GIPARequestAgent:
    """Orchestrates the GIPA workflow."""

    def __init__(self, google_api_key: Optional[str] = None):
        api_key = google_api_key or os.environ.get("GOOGLE_API_KEY")
        self.clarification_engine = ClarificationEngine(google_api_key=api_key)
        self.synonym_expander = SynonymExpander(google_api_key=api_key)
        self.document_generator = GIPADocumentGenerator(synonym_expander=self.synonym_expander)

    async def start_request(self, session_id: str) -> str:
        session = _get_or_create_session(session_id)
        session["data"] = {}
        session["context"] = ""
        session["status"] = "collecting"
        
        return (
            "I'll help you prepare a formal GIPA application. "
            "Let's start: **Which government agency are you requesting information from?**"
        )

    async def process_answer(self, session_id: str, user_message: str) -> str:
        session = _get_or_create_session(session_id)
        
        if session["status"] == "generated":
            return "Document already generated. Use start command to begin new request."

        updated_data, missing_questions, is_complete = await self.clarification_engine.extract_variables(
            user_message, session["data"], session["context"]
        )
        
        session["data"] = updated_data
        session["context"] += f"\nUser: {user_message}\n"

        # Attempt to find RTI email if missing and we have agency name
        if "agency_name" in updated_data and not updated_data.get("agency_email"):
            found_email = await find_rti_email(updated_data["agency_name"])
            if found_email:
                updated_data["agency_email"] = found_email
                session["data"] = updated_data
                session["context"] += f"\n(Found RTI email via search: {found_email})"
                # Re-calculate completion if email was the only thing missing
                _, _, is_complete = await self.clarification_engine.extract_variables(
                    "", updated_data, session["context"]
                )

        if is_complete:
            session["status"] = "ready"
            return self._build_summary(updated_data)
        
        return missing_questions[0]

    async def generate_document(self, session_id: str) -> str:
        session = _get_or_create_session(session_id)
        
        is_valid, errors = self.clarification_engine.validate_data(session["data"])
        if not is_valid:
            return f"Missing info: {', '.join(errors)}"

        try:
            gipa_data = self.clarification_engine.build_gipa_request_data(session["data"])
            config = get_jurisdiction_config(gipa_data.jurisdiction)
            
            document = await self.document_generator.generate(gipa_data, config)
            html_body = await self.document_generator.generate_html(gipa_data, config)
            
            session["status"] = "generated"
            session["document"] = document
            session["html_body"] = html_body
            
            # Email draft instructions
            draft_instruction = (
                f"\n\n---\n**EMAIL DRAFT INSTRUCTIONS:**\n"
                f"Create a draft to `{gipa_data.agency_email}` with subject "
                f"`RE: {config.act_name} - Information Request`.\n"
                f"Use this HTML body:\n```html\n{html_body}\n```"
            )
            
            return document + draft_instruction
            
        except Exception as e:
            return f"Error generating document: {e}"

    def _build_summary(self, data: Dict[str, Any]) -> str:
        return (
            f"I have all the info. Agency: {data.get('agency_name')}. "
            f"Applicant: {data.get('applicant_name')}. "
            f"Ready to generate document?"
        )

# Singleton
_agent_instance: Optional[GIPARequestAgent] = None

def _get_agent() -> GIPARequestAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = GIPARequestAgent()
    return _agent_instance

# Tools
@tool
async def gipa_start_request(session_id: str = "default") -> str:
    """Start a new GIPA request session."""
    return await _get_agent().start_request(session_id)

@tool
async def gipa_process_answer(user_answer: str, session_id: str = "default") -> str:
    """Process user answer for GIPA request."""
    return await _get_agent().process_answer(session_id, user_answer)

@tool
async def gipa_generate_document(session_id: str = "default") -> str:
    """Generate final GIPA document and email draft."""
    return await _get_agent().generate_document(session_id)

@tool
async def gipa_check_status(session_id: str = "default") -> str:
    """Check GIPA session status."""
    session = _gipa_sessions.get(session_id)
    if not session:
        return "No active session."
    return f"Status: {session.get('status', 'unknown')}"

@tool
async def gipa_expand_keywords(keywords: str) -> str:
    """Expand keywords into legal definitions."""
    agent = _get_agent()
    defs = await agent.synonym_expander.expand_keywords(keywords.split(","))
    return "\n".join(defs)

def get_gipa_tools() -> list:
    return [
        gipa_start_request,
        gipa_process_answer,
        gipa_generate_document,
        gipa_check_status,
        gipa_expand_keywords,
    ]
