"""
Dossier Agent - Dossier Section Templates.

Static templates and section builders for the one-page meeting prep dossier.
"""

from typing import Dict, Any, List


# ---------------------------------------------------------------------------
# Section Headers
# ---------------------------------------------------------------------------

DOSSIER_TITLE = "# Meeting Prep Dossier: {name}"

SECTION_DIVIDER = "\n---\n"

CONFIDENTIAL_HEADER = (
    "*CONFIDENTIAL - Prepared for internal meeting preparation only*\n"
    "*Generated: {date}*"
)


# ---------------------------------------------------------------------------
# Section Templates
# ---------------------------------------------------------------------------

BIOGRAPHICAL_SECTION = """\
## Biographical Context

**Current Role:** {current_role}
**Organization:** {organization}
**Location:** {location}

{biography}
"""

CAREER_SECTION = """\
## Career Highlights

{highlights}
"""

EDUCATION_SECTION = """\
## Education

{education}
"""

STATEMENTS_SECTION = """\
## Recent Statements & Positions

{statements}
"""

ASSOCIATES_SECTION = """\
## Key Associates & Network

{associates}
"""

RELATIONSHIP_MAP_SECTION = """\
## Relationship Map

{relationships}
"""

STRATEGIC_SECTION = """\
## Strategic Insights

**Meeting Strategy:** {meeting_strategy}

**Negotiation Style:** {negotiation_style}

**Recommended Approach:** {recommended_approach}
"""

CONVERSATION_STARTERS_SECTION = """\
## Conversation Starters

{starters}
"""

COMMON_GROUND_SECTION = """\
## Potential Common Ground

{common_ground}
"""

TOPICS_TO_AVOID_SECTION = """\
## Topics to Approach with Caution

{topics}
"""

MOTIVATIONS_SECTION = """\
## Key Motivations

{motivations}
"""

ONLINE_PRESENCE_SECTION = """\
## Online Presence

{presence}
"""


# ---------------------------------------------------------------------------
# Builder Functions
# ---------------------------------------------------------------------------


def build_biographical_section(data: Dict[str, Any]) -> str:
    """Build the biography section from synthesized data."""
    return BIOGRAPHICAL_SECTION.format(
        current_role=data.get("current_role", "Not available"),
        organization=data.get("organization", "Not available"),
        location=data.get("location", "Not available"),
        biography=data.get(
            "biographical_summary", "No biographical information available."
        ),
    )


def build_career_section(data: Dict[str, Any]) -> str:
    """Build career highlights as a numbered list."""
    highlights = data.get("career_highlights", [])
    if not highlights:
        return ""
    formatted = "\n".join(f"{i}. {h}" for i, h in enumerate(highlights, 1))
    return CAREER_SECTION.format(highlights=formatted)


def build_education_section(data: Dict[str, Any]) -> str:
    """Build education summary."""
    education = data.get("education_summary", "")
    if not education:
        return ""
    return EDUCATION_SECTION.format(education=education)


def build_statements_section(data: Dict[str, Any]) -> str:
    """Build recent statements section."""
    statements = data.get("recent_statements", [])
    if not statements:
        return ""

    lines = []
    for i, s in enumerate(statements, 1):
        if isinstance(s, dict):
            quote = s.get("quote", "")
            source = s.get("source", "Unknown source")
            date = s.get("date", "")
            context = s.get("context", "")
            date_str = f" ({date})" if date else ""
            lines.append(f'{i}. "{quote}"\n   - Source: {source}{date_str}')
            if context:
                lines.append(f"   - Context: {context}")
        else:
            lines.append(f"{i}. {s}")

    return STATEMENTS_SECTION.format(statements="\n".join(lines))


def build_associates_section(data: Dict[str, Any]) -> str:
    """Build known associates section."""
    associates = data.get("known_associates", [])
    if not associates:
        return ""

    lines = []
    for a in associates:
        if isinstance(a, dict):
            name = a.get("name", "Unknown")
            rel = a.get("relationship", "")
            ctx = a.get("context", "")
            lines.append(f"- **{name}** ({rel}): {ctx}")
        else:
            lines.append(f"- {a}")

    return ASSOCIATES_SECTION.format(associates="\n".join(lines))


def build_relationship_map_section(insights: Dict[str, Any]) -> str:
    """Build relationship map from strategic insights."""
    rel_map = insights.get("relationship_map", [])
    if not rel_map:
        return ""

    lines = []
    for r in rel_map:
        if isinstance(r, dict):
            person = r.get("person", "Unknown")
            rel = r.get("relationship", "")
            leverage = r.get("leverage", "")
            notes = r.get("notes", "")
            lines.append(f"- **{person}** ({rel})")
            if leverage:
                lines.append(f"  - Leverage: {leverage}")
            if notes:
                lines.append(f"  - Notes: {notes}")
        else:
            lines.append(f"- {r}")

    return RELATIONSHIP_MAP_SECTION.format(relationships="\n".join(lines))


def build_strategic_section(insights: Dict[str, Any]) -> str:
    """Build strategic insights section."""
    return STRATEGIC_SECTION.format(
        meeting_strategy=insights.get("meeting_strategy", "No strategy available."),
        negotiation_style=insights.get("negotiation_style", "Not assessed."),
        recommended_approach=insights.get(
            "recommended_approach", "No specific recommendation."
        ),
    )


def build_conversation_starters_section(insights: Dict[str, Any]) -> str:
    """Build conversation starters as a numbered list."""
    starters = insights.get("conversation_starters", [])
    if not starters:
        return ""
    formatted = "\n".join(f"{i}. {s}" for i, s in enumerate(starters, 1))
    return CONVERSATION_STARTERS_SECTION.format(starters=formatted)


def build_common_ground_section(insights: Dict[str, Any]) -> str:
    """Build common ground section."""
    common = insights.get("common_ground", [])
    if not common:
        return ""
    formatted = "\n".join(f"- {c}" for c in common)
    return COMMON_GROUND_SECTION.format(common_ground=formatted)


def build_topics_to_avoid_section(insights: Dict[str, Any]) -> str:
    """Build topics to avoid section."""
    topics = insights.get("topics_to_avoid", [])
    if not topics:
        return ""
    formatted = "\n".join(f"- {t}" for t in topics)
    return TOPICS_TO_AVOID_SECTION.format(topics=formatted)


def build_motivations_section(insights: Dict[str, Any]) -> str:
    """Build key motivations section."""
    motivations = insights.get("key_motivations", [])
    if not motivations:
        return ""
    formatted = "\n".join(f"- {m}" for m in motivations)
    return MOTIVATIONS_SECTION.format(motivations=formatted)


def build_online_presence_section(data: Dict[str, Any]) -> str:
    """Build online presence section."""
    presence = data.get("online_presence", "")
    if not presence:
        return ""
    return ONLINE_PRESENCE_SECTION.format(presence=presence)
