"""
Jurisdiction configuration for information access requests.

Each jurisdiction (NSW, Federal, Victoria) has different legislation,
section references, and terminology. This module provides swappable
config objects so the agent's prompts and templates never need rewriting
when switching jurisdictions.
"""

from dataclasses import dataclass, field
from typing import List


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

    Returns:
        JurisdictionConfig for the specified jurisdiction.

    Raises:
        ValueError: If jurisdiction is not recognized.
    """
    key = jurisdiction.strip().lower()
    config = _JURISDICTION_MAP.get(key)
    if config is None:
        valid = ", ".join(
            sorted(set(c.jurisdiction for c in _JURISDICTION_MAP.values()))
        )
        raise ValueError(
            f"Unknown jurisdiction '{jurisdiction}'. Valid options: {valid}"
        )
    return config
