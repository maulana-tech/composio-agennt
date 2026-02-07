"""
Static legal boilerplate clauses for GIPA/FOI applications.

These clauses are standard across all applications and serve as the
"legal shield" - preventing agencies from rejecting requests on
technicalities around scope, definitions, or ambiguity.

Based on established GIPA application best practices (Paddy Pallin example
and NSW Information Commissioner guidance).
"""

from ..jurisdiction_config import JurisdictionConfig


# ---------------------------------------------------------------------------
# Standard Exclusions (reduces processing fees by narrowing scope)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Record Definition
# ---------------------------------------------------------------------------


def get_record_definition(config: JurisdictionConfig) -> str:
    """Generate the record definition clause for the given jurisdiction."""
    return (
        f'Define "record" as per {config.record_definition_reference}, '
        f"to include any document, database entry, file, note, memorandum, "
        f"briefing paper, cabinet submission, minute, report, or any other "
        f"recorded information regardless of its form or medium."
    )


# ---------------------------------------------------------------------------
# Contractor/Consultant Inclusion
# ---------------------------------------------------------------------------

CONTRACTOR_INCLUSION = (
    "The above search terms extend to records held by, or created by, "
    "external contractors, consultants, or secondees performing work on "
    "behalf of the agency during the specified period, including records "
    "held on personal devices where such devices were used for official "
    "business."
)


# ---------------------------------------------------------------------------
# Correspondence Definition (Dynamic based on jurisdiction)
# ---------------------------------------------------------------------------


def get_correspondence_definition(config: JurisdictionConfig) -> str:
    """
    Generate the correspondence definition clause.

    This is critical for modern government transparency - much official
    business now occurs on messaging platforms beyond email.
    """
    platforms = ", ".join(config.correspondence_platforms)
    return (
        f'Define "correspondence" to include all forms of written '
        f"communication, whether formal or informal, including but not "
        f"limited to: {platforms}. This includes messages sent or received "
        f"on both official and personal devices or accounts where such "
        f"communications relate to official business."
    )


# ---------------------------------------------------------------------------
# Fee Reduction Templates
# ---------------------------------------------------------------------------


def get_fee_reduction_paragraph(
    config: JurisdictionConfig,
    applicant_type: str,
    public_interest_justification: str,
    applicant_organization: str = "",
    charity_status: str = "",
) -> str:
    """
    Generate the fee reduction request paragraph.

    Only called when the applicant is eligible (non-profit, journalist, student).
    """
    # Header clause citing the specific legislation
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


# ---------------------------------------------------------------------------
# Full Scope and Definitions Block
# ---------------------------------------------------------------------------


def build_scope_and_definitions(
    config: JurisdictionConfig,
    keyword_definitions: list[str],
) -> str:
    """
    Assemble the complete Scope and Definitions section.

    Args:
        config: Jurisdiction configuration.
        keyword_definitions: List of AI-generated keyword definition strings
            (e.g., 'Define "Koala" to include: Phascolarctos cinereus, ...').

    Returns:
        Formatted Scope and Definitions section as a string.
    """
    lines = ["## Scope and Definitions", "", "The above search terms\u2014", ""]

    # 1. Record definition
    lines.append(f"1. {get_record_definition(config)}")
    lines.append("")

    # 2. Standard exclusions
    for i, exclusion in enumerate(STANDARD_EXCLUSIONS, start=2):
        lines.append(f"{i}. {exclusion}")
        lines.append("")

    next_num = 2 + len(STANDARD_EXCLUSIONS)

    # 3. Contractor inclusion
    lines.append(f"{next_num}. {CONTRACTOR_INCLUSION}")
    lines.append("")
    next_num += 1

    # 4. Dynamic keyword definitions
    for definition in keyword_definitions:
        lines.append(f"{next_num}. {definition}")
        lines.append("")
        next_num += 1

    # 5. Correspondence definition
    lines.append(f"{next_num}. {get_correspondence_definition(config)}")
    lines.append("")

    return "\n".join(lines)
