import os
import json
import re
from typing import Dict, Any, List, Optional, Tuple, Literal
from dataclasses import dataclass, field
from datetime import datetime
import httpx
from pydantic import BaseModel, Field, model_validator
from langchain_core.messages import HumanMessage, SystemMessage
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

@dataclass(frozen=True)
class JurisdictionConfig:
    jurisdiction: str
    act_name: str
    act_short_name: str
    act_year: int
    fee_reduction_section: str
    fee_regulation_clause: str
    base_application_fee: str
    processing_fee_rate: str
    record_definition_reference: str
    correspondence_platforms: List[str] = field(default_factory=list)
    request_term: str = "information request"
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
    correspondence_platforms=["email", "SMS", "WhatsApp", "Signal", "WeChat", "Wickr", "Microsoft Teams messages", "Slack messages"],
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
    correspondence_platforms=["email", "SMS", "WhatsApp", "Signal", "Microsoft Teams messages"],
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
    correspondence_platforms=["email", "SMS", "WhatsApp", "Signal", "Microsoft Teams messages"],
    request_term="FOI request",
    applicant_term="applicant",
)

_JURISDICTION_MAP = {
    "nsw": NSW_CONFIG, "new south wales": NSW_CONFIG,
    "federal": FEDERAL_CONFIG, "commonwealth": FEDERAL_CONFIG,
    "vic": VIC_CONFIG, "victoria": VIC_CONFIG,
}

def get_jurisdiction_config(jurisdiction: str) -> JurisdictionConfig:
    key = jurisdiction.strip().lower()
    return _JURISDICTION_MAP.get(key, NSW_CONFIG)

class SynonymExpander:
    def __init__(self, google_api_key: Optional[str] = None):
        api_key = google_api_key or os.environ.get("GOOGLE_API_KEY")
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.1, google_api_key=api_key) if api_key else None
        self._cache: Dict[str, str] = {}

    async def expand_keyword(self, keyword: str) -> str:
        cache_key = keyword.strip().lower()
        if cache_key in self._cache: return self._cache[cache_key]
        if not self.llm: return self._fallback_expansion(keyword)
        try:
            response = await self.llm.ainvoke([SystemMessage(content=self._get_system_prompt()), HumanMessage(content=f"Expand this keyword for a GIPA legal definition: {keyword}")])
            expansions = self._parse_expansions(response.content, keyword)
            result = f'Define "{keyword}" to include: {", ".join(expansions)}.' if expansions else self._fallback_expansion(keyword)
            self._cache[cache_key] = result
            return result
        except Exception: return self._fallback_expansion(keyword)

    def _fallback_expansion(self, keyword: str) -> str:
        return f'Define "{keyword}" to include all references to {keyword}, including abbreviations, acronyms, and alternative spellings.'

    async def expand_keywords(self, keywords: List[str]) -> List[str]:
        return [await self.expand_keyword(k) for k in keywords]

    def _get_system_prompt(self) -> str:
        return "You are a legal terminology expansion engine for Australian government information access..."

    def _parse_expansions(self, content: str, keyword: str) -> List[str]:
        content = content.strip()
        try:
            result = json.loads(content)
            if isinstance(result, list): return [str(item) for item in result if str(item).lower() != keyword.lower()]
        except: pass
        parts = re.split(r"[,\n]", content)
        return [p.strip() for p in parts if p.strip().lower() != keyword.lower()][:12]

EXCLUSION_MEDIA_ALERTS = "Exclude all computer-generated daily media alerts, media monitoring summaries, and automated news digests..."
EXCLUSION_DUPLICATES = "Exclude exact duplicates of documents already captured by this request..."
EXCLUSION_AUTOREPLY = "Exclude automated out-of-office replies, delivery receipts, read receipts, and calendar invitation acceptances/declines."
STANDARD_EXCLUSIONS = [EXCLUSION_MEDIA_ALERTS, EXCLUSION_DUPLICATES, EXCLUSION_AUTOREPLY]
CONTRACTOR_INCLUSION = "The above search terms extend to records held by, or created by, external contractors..."

def get_record_definition(config: JurisdictionConfig) -> str:
    return f'Define "record" as per {config.record_definition_reference}, to include any document...'

def get_correspondence_definition(config: JurisdictionConfig) -> str:
    platforms = ", ".join(config.correspondence_platforms)
    return f'Define "correspondence" to include all forms of written communication... including: {platforms}.'

def get_fee_reduction_paragraph(config, applicant_type, justification, org="", charity="") -> str:
    header = f"The Applicant requests, pursuant to {config.fee_reduction_section}..."
    just = f"Applicant is {applicant_type} {org} {charity}. {justification}"
    return f"{header}\n\n{just}"

def build_scope_and_definitions(config, keyword_definitions) -> str:
    lines = ["## Scope and Definitions", "", "The above search terms —", "", get_record_definition(config), ""]
    lines.extend([ex + "\n" for ex in STANDARD_EXCLUSIONS])
    lines.append(CONTRACTOR_INCLUSION + "\n")
    lines.extend([d + "\n" for d in keyword_definitions])
    lines.append(get_correspondence_definition(config))
    return "\n".join(lines)

class TargetPerson(BaseModel):
    name: str; role: Optional[str] = None; direction: Literal["sender", "receiver", "both"] = "both"

class GIPARequestData(BaseModel):
    agency_name: str; agency_email: Optional[str] = None; applicant_name: str; applicant_organization: Optional[str] = None
    applicant_type: Literal["individual", "nonprofit", "journalist", "student", "other"] = "individual"
    charity_status: Optional[str] = None; public_interest_justification: str; start_date: str; end_date: str
    targets: List[TargetPerson] = Field(default_factory=list); keywords: List[str] = Field(min_length=1)
    jurisdiction: str = "NSW"; fee_reduction_eligible: bool = False; summary_sentence: str = ""

    @model_validator(mode="after")
    def compute_fee_eligibility(self):
        if self.applicant_type in ("nonprofit", "journalist", "student"): self.fee_reduction_eligible = True
        return self

REQUIRED_FIELDS = [
    {"field": "agency_name", "question": "Which government agency are you requesting information from?", "priority": 1},
    {"field": "applicant_name", "question": "What is your full name (as the applicant)?", "priority": 2},
    {"field": "applicant_type", "question": "What type of applicant are you?", "priority": 3},
    {"field": "public_interest_justification", "question": "Why is this information important?", "priority": 4},
    {"field": "start_date", "question": "What is the START date?", "priority": 5},
    {"field": "end_date", "question": "What is the END date?", "priority": 6},
    {"field": "targets", "question": "Who are the specific people or roles?", "priority": 7},
    {"field": "keywords", "question": "What specific keywords?", "priority": 8},
]

CONDITIONAL_FIELDS = [
    {"field": "applicant_organization", "condition_field": "applicant_type", "condition_values": ["nonprofit", "journalist", "student"], "question": "Organization name?"},
    {"field": "charity_status", "condition_field": "applicant_type", "condition_values": ["nonprofit"], "question": "ABN/Charity number?"},
    {"field": "agency_email", "condition_field": "agency_name", "condition_values": None, "question": "Agency email address?"},
]

class ClarificationEngine:
    def __init__(self, google_api_key: Optional[str] = None):
        api_key = google_api_key or os.environ.get("GOOGLE_API_KEY")
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0, google_api_key=api_key) if api_key else None

    async def extract_variables(self, user_message, current_data, context="") -> Tuple[Dict, List, bool]:
        if not self.llm: return current_data, self._get_missing_field_questions(current_data), False
        try:
            prompt = f"Extract GIPA info from: {user_message}\nCurrent: {current_data}\nContext: {context}"
            response = await self.llm.ainvoke([SystemMessage(content="Extract JSON"), HumanMessage(content=prompt)])
            parsed = self._parse_json(response.content)
            updated = {**current_data, **parsed.get("extracted", {})}
            miss = self._get_missing_field_questions(updated)
            return updated, miss, len(miss) == 0
        except: return current_data, self._get_missing_field_questions(current_data), False

    def _get_missing_field_questions(self, data) -> List[str]:
        miss = [f["question"] for f in REQUIRED_FIELDS if not data.get(f["field"])]
        for c in CONDITIONAL_FIELDS:
            if not data.get(c["field"]) and data.get(c["condition_field"]) in (c["condition_values"] or [data.get(c["condition_field"])]):
                miss.append(c["question"])
        return miss

    def _parse_json(self, content):
        try: return json.loads(re.search(r"\{[\s\S]*\}", content).group())
        except: return {"extracted": {}}

    def validate_data(self, data):
        req = ["agency_name", "applicant_name", "public_interest_justification", "start_date", "end_date"]
        errs = [f"Missing {f}" for f in req if not data.get(f)]
        if not data.get("keywords"): errs.append("Missing keywords")
        return len(errs) == 0, errs

    def build_gipa_request_data(self, data):
        return GIPARequestData(**{**data, "targets": [TargetPerson(**t) if isinstance(t, dict) else t for t in data.get("targets", [])]})

class GIPADocumentGenerator:
    def __init__(self, expander=None): self.expander = expander

    async def generate(self, data, config=None):
        config = config or get_jurisdiction_config(data.jurisdiction)
        defs = await self.expander.expand_keywords(data.keywords) if self.expander else []
        sections = [
            f"{datetime.now().strftime('%d %B %Y')}\n{data.agency_name}\nRE: {config.act_name}",
            f"{data.applicant_name} seeks info regarding:\n{data.summary_sentence or ', '.join(data.keywords)}",
            f"## Search Terms\nRange: {data.start_date} to {data.end_date}\nKeywords: {', '.join(data.keywords)}",
            build_scope_and_definitions(config, defs),
            f"Yours faithfully,\n{data.applicant_name}"
        ]
        return "\n\n".join(sections)

    async def generate_html(self, data, config=None):
        return f"<div><h1>GIPA Request</h1><p>{await self.generate(data, config)}</p></div>"

_gipa_sessions: Dict[str, Dict[str, Any]] = {}

class GIPARequestAgent:
    def __init__(self, google_api_key=None):
        self.engine = ClarificationEngine(google_api_key)
        self.expander = SynonymExpander(google_api_key)
        self.gen = GIPADocumentGenerator(self.expander)

    async def start_request(self, sid):
        _gipa_sessions[sid] = {"data": {}, "status": "collecting"}
        return "Which agency?"

    async def process_answer(self, sid, msg):
        sess = _gipa_sessions.setdefault(sid, {"data": {}, "status": "collecting"})
        data, miss, done = await self.engine.extract_variables(msg, sess["data"])
        sess["data"] = data
        if "agency_name" in data and not data.get("agency_email"):
             data["agency_email"] = await find_rti_email(data["agency_name"])
        if done: sess["status"] = "ready"; return "Ready to generate?"
        return miss[0] if miss else "Tell me more."

    async def generate_document(self, sid):
        sess = _gipa_sessions.get(sid)
        if not sess: return "No session."
        doc = await self.gen.generate(self.engine.build_gipa_request_data(sess["data"]))
        sess["status"] = "generated"; sess["document"] = doc
        return doc
