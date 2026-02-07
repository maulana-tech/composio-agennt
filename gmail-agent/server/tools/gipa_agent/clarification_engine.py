"""
Clarification Engine for GIPA Request Agent.

Handles the interview/extraction phase: collects all required variables
from the user through conversation, validates completeness, and produces
a structured GIPARequestData object ready for document generation.

The engine uses the LLM to parse free-form user responses into structured
fields, and determines which questions still need to be asked.
"""

import os
import json
import re
from typing import List, Dict, Any, Optional, Tuple, Literal
from pydantic import BaseModel, Field, model_validator
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


class TargetPerson(BaseModel):
    """A person or role that is a sender/receiver in the search query."""

    name: str = Field(description="Full name or role title")
    role: Optional[str] = Field(
        default=None, description="Job title or role (e.g., 'Director of Policy')"
    )
    direction: Literal["sender", "receiver", "both"] = Field(
        default="both",
        description="Whether this person is the sender, receiver, or both",
    )


class GIPARequestData(BaseModel):
    """
    All variables needed to generate a complete GIPA application.

    This model represents the output of the clarification phase.
    Every required field must be populated before document generation can proceed.
    """

    # Target Agency
    agency_name: str = Field(description="Full name of the target government agency")
    agency_email: Optional[str] = Field(
        default=None,
        description="GIPA-specific email address for the agency (differs from general enquiries)",
    )

    # Applicant
    applicant_name: str = Field(
        description="Full name of the person making the request"
    )
    applicant_organization: Optional[str] = Field(
        default=None, description="Organization name if applicable"
    )
    applicant_type: Literal[
        "individual", "nonprofit", "journalist", "student", "other"
    ] = Field(
        default="individual",
        description="Type of applicant (affects fee reduction eligibility)",
    )
    charity_status: Optional[str] = Field(
        default=None,
        description="ABN or charity registration number if nonprofit",
    )

    # Public Interest Hook
    public_interest_justification: str = Field(
        description="Why this information is important to the public interest"
    )

    # Timeframe
    start_date: str = Field(
        description="Start date of the search period (e.g., '1 January 2023')"
    )
    end_date: str = Field(
        description="End date of the search period (e.g., '31 December 2024')"
    )

    # Targets
    targets: List[TargetPerson] = Field(
        default_factory=list,
        description="People or roles whose correspondence is being sought",
    )

    # Keywords
    keywords: List[str] = Field(
        description="Specific words/phrases that must appear in the documents",
        min_length=1,
    )

    # Jurisdiction
    jurisdiction: str = Field(
        default="NSW",
        description="Jurisdiction for the request (NSW, Federal, Victoria)",
    )

    # Computed fields
    fee_reduction_eligible: bool = Field(
        default=False,
        description="Whether the applicant is eligible for fee reduction",
    )
    summary_sentence: str = Field(
        default="",
        description="One-sentence summary of the information request",
    )

    @model_validator(mode="after")
    def compute_fee_eligibility(self):
        """Auto-compute fee reduction eligibility from applicant_type."""
        if self.applicant_type in ("nonprofit", "journalist", "student"):
            self.fee_reduction_eligible = True
        return self


# ---------------------------------------------------------------------------
# Required fields and their question prompts
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = [
    {
        "field": "agency_name",
        "question": "Which government agency are you requesting information from? (e.g., Department of Primary Industries, NSW Police Force, Transport for NSW)",
        "priority": 1,
    },
    {
        "field": "applicant_name",
        "question": "What is your full name (as the applicant)?",
        "priority": 2,
    },
    {
        "field": "applicant_type",
        "question": "What type of applicant are you? (individual, nonprofit organisation, journalist, or student) This is important because non-profit organisations, journalists, and students can request a 50% reduction in processing fees.",
        "priority": 3,
    },
    {
        "field": "public_interest_justification",
        "question": "Why is this information important? Please explain the public interest reason for your request. This is crucial for supporting fee reductions and strengthening the application. For example: 'This information is needed to understand government decision-making on environmental policy affecting communities in the Hunter Valley.'",
        "priority": 4,
    },
    {
        "field": "start_date",
        "question": "What is the START date for the period you want to search? (e.g., '1 January 2023')",
        "priority": 5,
    },
    {
        "field": "end_date",
        "question": "What is the END date for the search period? (e.g., '31 December 2024')",
        "priority": 6,
    },
    {
        "field": "targets",
        "question": "Who are the specific people or roles whose correspondence you want? Please provide names and/or job titles, and whether they are the sender, receiver, or both. For example: 'From Minister for Environment to Director of Policy' or 'All correspondence involving John Smith, Deputy Secretary.'",
        "priority": 7,
    },
    {
        "field": "keywords",
        "question": "What specific keywords or phrases must appear in the documents? These will be used as search terms in the agency's records system. Provide at least one keyword. For example: 'koala habitat', 'development approval', 'water licence'.",
        "priority": 8,
    },
]

# Optional fields to ask about conditionally
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
        "condition_values": None,  # Always ask after agency_name is set
        "question": (
            "Do you know the specific GIPA/Right to Information email address for {agency_name}? "
            "This is usually different from the general enquiries email. "
            "If you don't know it, I'll note that you should find it before submitting. "
            "You can usually find it by searching '{agency_name} GIPA access application' online."
        ),
    },
]


# ---------------------------------------------------------------------------
# Clarification Engine
# ---------------------------------------------------------------------------


class ClarificationEngine:
    """
    Extracts GIPA request variables from conversation through LLM-powered parsing.

    The engine maintains a partial GIPARequestData and determines what questions
    still need to be asked. It uses the LLM to parse free-form user responses
    into structured fields.
    """

    def __init__(self, google_api_key: Optional[str] = None):
        api_key = google_api_key or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is required for ClarificationEngine")
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
        """
        Extract GIPA request variables from the user's message.

        Args:
            user_message: The latest user message to parse.
            current_data: Currently collected data (partial GIPARequestData dict).
            conversation_context: Summary of prior conversation for context.

        Returns:
            Tuple of:
                - Updated data dict with newly extracted fields
                - List of follow-up questions to ask
                - Boolean indicating if all required data is collected
        """
        # Build the extraction prompt
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

            # Parse the LLM's structured response
            parsed = self._parse_extraction_response(response.content)

            # Merge extracted data with current data
            updated_data = {**current_data}
            for key, value in parsed.get("extracted", {}).items():
                if value is not None and value != "" and value != []:
                    updated_data[key] = value

            # Determine missing fields
            missing_questions = self._get_missing_field_questions(updated_data)

            # Check completeness
            is_complete = len(missing_questions) == 0

            return updated_data, missing_questions, is_complete

        except Exception as e:
            print(f"ClarificationEngine extraction error: {e}")
            # Fallback: return current data and all missing questions
            missing_questions = self._get_missing_field_questions(current_data)
            return current_data, missing_questions, False

    def _get_system_prompt(self) -> str:
        return """You are a precise data extraction engine for NSW GIPA (Government Information Public Access) applications.

Your task is to extract structured information from a user's message. You must identify any of the following fields from their response:

FIELDS TO EXTRACT:
- agency_name: The NSW government agency being requested from
- agency_email: The specific GIPA email for that agency (NOT general enquiries)
- applicant_name: The person making the request
- applicant_organization: Their organisation name (if applicable)
- applicant_type: One of: "individual", "nonprofit", "journalist", "student", "other"
- charity_status: ABN or charity registration number
- public_interest_justification: Why this info matters to the public interest
- start_date: Start of the search period (format as natural date like "1 January 2023")
- end_date: End of the search period
- targets: List of people/roles involved. Each target needs: name, role (optional), direction ("sender"/"receiver"/"both")
- keywords: List of specific search terms/phrases
- jurisdiction: "NSW", "Federal", or "Victoria" (default NSW)

RULES:
1. Only extract fields that are CLEARLY stated in the user's message.
2. Do NOT infer or assume values that aren't explicitly provided.
3. For dates, accept flexible formats but normalize to "DD Month YYYY" style.
4. For targets, parse natural language like "from John to Mary" into structured sender/receiver.
5. For keywords, separate distinct terms (don't combine them).
6. Return ONLY the fields you can extract. Leave others out.

Return your response as valid JSON with this structure:
{
    "extracted": {
        "field_name": "value",
        ...
    },
    "notes": "Any observations about ambiguity or things to clarify"
}

For targets, use this structure:
"targets": [{"name": "...", "role": "...", "direction": "sender|receiver|both"}]

For keywords, use a list:
"keywords": ["keyword1", "keyword2"]
"""

    def _build_extraction_prompt(
        self,
        user_message: str,
        current_data: Dict[str, Any],
        conversation_context: str,
    ) -> str:
        current_summary = (
            json.dumps(current_data, indent=2) if current_data else "None collected yet"
        )

        return f"""CURRENTLY COLLECTED DATA:
{current_summary}

CONVERSATION CONTEXT:
{conversation_context if conversation_context else "This is the beginning of the conversation."}

USER'S LATEST MESSAGE:
{user_message}

Extract any GIPA request fields from the user's latest message. Remember: only extract what is clearly stated. Return valid JSON."""

    def _parse_extraction_response(self, content: str) -> Dict[str, Any]:
        """Parse the LLM's JSON response, handling various formats."""
        # Try to find JSON in the response
        # First try: clean JSON block
        json_match = re.search(r"```json\s*([\s\S]*?)\s*```", content)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Second try: raw JSON object
        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Fallback: return empty extraction
        return {"extracted": {}, "notes": "Failed to parse LLM response"}

    def _get_missing_field_questions(self, data: Dict[str, Any]) -> List[str]:
        """
        Determine which required fields are still missing and return their questions.

        Checks both required fields and conditional fields.
        """
        questions = []

        # Check required fields
        for field_info in sorted(REQUIRED_FIELDS, key=lambda x: x["priority"]):
            field_name = field_info["field"]
            value = data.get(field_name)

            # Check if field is missing or empty
            if value is None or value == "" or value == []:
                questions.append(field_info["question"])

        # Check conditional fields
        for cond_info in CONDITIONAL_FIELDS:
            field_name = cond_info["field"]
            condition_field = cond_info["condition_field"]
            condition_values = cond_info["condition_values"]

            # Skip if the conditional field already has a value
            if data.get(field_name):
                continue

            # Check if the condition is met
            condition_value = data.get(condition_field)
            if condition_value is None:
                continue  # Condition field not yet set, skip

            if condition_values is None:
                # Always ask when condition field is set (e.g., agency_email)
                question = cond_info["question"]
                # Template substitution for dynamic questions
                if "{" in question:
                    question = question.format(**data)
                questions.append(question)
            elif condition_value in condition_values:
                questions.append(cond_info["question"])

        return questions

    def validate_data(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate that all required data is present and well-formed.

        Returns:
            Tuple of (is_valid, list of validation errors)
        """
        errors = []

        # Required string fields
        for field_name in [
            "agency_name",
            "applicant_name",
            "public_interest_justification",
            "start_date",
            "end_date",
        ]:
            if not data.get(field_name):
                errors.append(f"Missing required field: {field_name}")

        # Keywords must have at least one
        keywords = data.get("keywords", [])
        if not keywords or len(keywords) == 0:
            errors.append("At least one keyword is required")

        # Applicant type must be valid
        applicant_type = data.get("applicant_type", "individual")
        if applicant_type not in (
            "individual",
            "nonprofit",
            "journalist",
            "student",
            "other",
        ):
            errors.append(f"Invalid applicant_type: {applicant_type}")

        # If nonprofit, should have organization
        if applicant_type == "nonprofit" and not data.get("applicant_organization"):
            errors.append("Non-profit applicants should provide an organisation name")

        # Warn (not error) if agency_email is missing
        warnings = []
        if not data.get("agency_email"):
            warnings.append(
                "WARNING: No GIPA email address provided for the agency. "
                "You should find the specific GIPA email before submitting."
            )

        return len(errors) == 0, errors + warnings

    def build_gipa_request_data(self, data: Dict[str, Any]) -> GIPARequestData:
        """
        Build a validated GIPARequestData from the collected dict.

        Computes derived fields (fee_reduction_eligible, summary_sentence).
        """
        # Ensure targets are TargetPerson objects
        targets = []
        for t in data.get("targets", []):
            if isinstance(t, dict):
                targets.append(TargetPerson(**t))
            elif isinstance(t, TargetPerson):
                targets.append(t)

        # Compute fee reduction eligibility
        applicant_type = data.get("applicant_type", "individual")
        fee_eligible = applicant_type in ("nonprofit", "journalist", "student")

        # Build summary sentence
        agency = data.get("agency_name", "the agency")
        keywords_str = ", ".join(data.get("keywords", []))
        summary = (
            f"All correspondence held by {agency} "
            f"containing references to {keywords_str}, "
            f"for the period {data.get('start_date', '')} to {data.get('end_date', '')}."
        )

        return GIPARequestData(
            agency_name=data["agency_name"],
            agency_email=data.get("agency_email"),
            applicant_name=data["applicant_name"],
            applicant_organization=data.get("applicant_organization"),
            applicant_type=applicant_type,
            charity_status=data.get("charity_status"),
            public_interest_justification=data["public_interest_justification"],
            start_date=data["start_date"],
            end_date=data["end_date"],
            targets=targets,
            keywords=data["keywords"],
            jurisdiction=data.get("jurisdiction", "NSW"),
            fee_reduction_eligible=fee_eligible,
            summary_sentence=summary,
        )
