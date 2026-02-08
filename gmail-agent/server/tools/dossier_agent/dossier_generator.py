"""
Dossier Agent - Document Generator.

Assembles the final one-page meeting prep dossier in Markdown format
from synthesized research and strategic insights.
"""

from typing import Dict, Any
from datetime import datetime

from .templates.dossier_template import (
    DOSSIER_TITLE,
    SECTION_DIVIDER,
    CONFIDENTIAL_HEADER,
    build_biographical_section,
    build_career_section,
    build_education_section,
    build_statements_section,
    build_associates_section,
    build_relationship_map_section,
    build_strategic_section,
    build_conversation_starters_section,
    build_common_ground_section,
    build_topics_to_avoid_section,
    build_motivations_section,
    build_online_presence_section,
)


class DossierGenerator:
    """
    Assembles synthesized research and strategic insights into a
    one-page Markdown meeting prep dossier.
    """

    async def generate(
        self,
        synthesized_data: Dict[str, Any],
        strategic_insights: Dict[str, Any],
    ) -> str:
        """
        Generate the complete dossier document.

        Args:
            synthesized_data: Output of SynthesizedResearch.to_dict()
            strategic_insights: Output of StrategicInsights.to_dict()

        Returns:
            Complete dossier as Markdown string.
        """
        name = synthesized_data.get("name", "Unknown Person")
        date_str = datetime.now().strftime("%d %B %Y")

        sections = []

        # Title & header
        sections.append(DOSSIER_TITLE.format(name=name))
        sections.append(CONFIDENTIAL_HEADER.format(date=date_str))

        # LinkedIn URL if available
        linkedin_url = synthesized_data.get("linkedin_url", "")
        if linkedin_url:
            sections.append(f"\n**LinkedIn:** {linkedin_url}")

        sections.append(SECTION_DIVIDER)

        # Biography
        sections.append(build_biographical_section(synthesized_data))

        # Career highlights
        career = build_career_section(synthesized_data)
        if career:
            sections.append(career)

        # Education
        education = build_education_section(synthesized_data)
        if education:
            sections.append(education)

        sections.append(SECTION_DIVIDER)

        # Recent statements
        statements = build_statements_section(synthesized_data)
        if statements:
            sections.append(statements)

        # Associates
        associates = build_associates_section(synthesized_data)
        if associates:
            sections.append(associates)

        sections.append(SECTION_DIVIDER)

        # Strategic sections
        sections.append(build_strategic_section(strategic_insights))

        # Relationship map
        rel_map = build_relationship_map_section(strategic_insights)
        if rel_map:
            sections.append(rel_map)

        # Conversation starters
        starters = build_conversation_starters_section(strategic_insights)
        if starters:
            sections.append(starters)

        # Common ground
        common = build_common_ground_section(strategic_insights)
        if common:
            sections.append(common)

        # Motivations
        motivations = build_motivations_section(strategic_insights)
        if motivations:
            sections.append(motivations)

        sections.append(SECTION_DIVIDER)

        # Topics to avoid
        avoid = build_topics_to_avoid_section(strategic_insights)
        if avoid:
            sections.append(avoid)

        # Online presence
        presence = build_online_presence_section(synthesized_data)
        if presence:
            sections.append(presence)

        # Footer
        sections.append(SECTION_DIVIDER)
        sections.append(
            f"*This dossier was generated on {date_str} using automated research. "
            f"Verify critical information before the meeting.*"
        )

        return "\n".join(sections)
