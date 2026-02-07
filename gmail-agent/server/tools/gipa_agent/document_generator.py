"""
GIPA Document Generator.

Assembles the final GIPA application document from structured data,
jurisdiction config, boilerplate clauses, and AI-generated keyword definitions.

The output follows the strict legal document structure:
  Header -> Legal Standing -> Search Protocol -> Scope & Definitions

Output format is Markdown, compatible with the existing PDF generator.
"""

from datetime import date
from typing import List, Optional

from .clarification_engine import GIPARequestData, TargetPerson
from .jurisdiction_config import JurisdictionConfig, get_jurisdiction_config
from .synonym_expander import SynonymExpander
from .templates.boilerplate import (
    build_scope_and_definitions,
    get_fee_reduction_paragraph,
)


class GIPADocumentGenerator:
    """
    Generates a complete GIPA application document from structured data.

    The generator follows the strict document architecture:
        Section A: Header & Routing
        Section B: Fee Reduction (conditional)
        Section C: Search Terms (Boolean query)
        Section D: Scope & Definitions (legal shield)
    """

    def __init__(self, synonym_expander: Optional[SynonymExpander] = None):
        self.synonym_expander = synonym_expander

    async def generate(
        self,
        data: GIPARequestData,
        config: Optional[JurisdictionConfig] = None,
    ) -> str:
        """
        Generate a complete GIPA application document.

        Args:
            data: Validated GIPARequestData with all required fields.
            config: Jurisdiction configuration. If None, derived from data.jurisdiction.

        Returns:
            Complete GIPA application as a Markdown string.
        """
        if config is None:
            config = get_jurisdiction_config(data.jurisdiction)

        sections = []

        # Section A: Header & Routing
        sections.append(self._build_header(data, config))

        # Section B: Fee Reduction (conditional)
        fee_section = self._build_fee_reduction(data, config)
        if fee_section:
            sections.append(fee_section)

        # Section C: Search Terms
        sections.append(self._build_search_terms(data, config))

        # Section D: Scope & Definitions
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

    def _build_header(self, data: GIPARequestData, config: JurisdictionConfig) -> str:
        """Build Section A: Header & Routing."""
        today = date.today().strftime("%-d %B %Y")

        lines = [
            today,
            "",
            data.agency_name,
        ]

        if data.agency_email:
            lines.append(f"Via email: {data.agency_email}")
        else:
            lines.append("*[GIPA email address to be confirmed before submission]*")

        lines.extend(
            [
                "",
                f"**RE: {config.act_name} ({config.act_short_name}) \u2014 Information Request**",
                "",
                "Dear Right to Information Officer,",
                "",
                f"{data.applicant_name}",
            ]
        )

        if data.applicant_organization:
            lines.append(f"on behalf of {data.applicant_organization}")

        # Summary sentence
        summary = data.summary_sentence or self._generate_summary(data)
        lines.extend(
            [
                f"seeks access to information under the {config.act_short_name} regarding:",
                "",
                f"> {summary}",
            ]
        )

        return "\n".join(lines)

    def _build_fee_reduction(
        self, data: GIPARequestData, config: JurisdictionConfig
    ) -> Optional[str]:
        """Build Section B: Fee Reduction (only if eligible)."""
        if not data.fee_reduction_eligible:
            return None

        lines = [
            "## Fee Reduction Request",
            "",
            get_fee_reduction_paragraph(
                config=config,
                applicant_type=data.applicant_type,
                public_interest_justification=data.public_interest_justification,
                applicant_organization=data.applicant_organization or "",
                charity_status=data.charity_status or "",
            ),
        ]

        return "\n".join(lines)

    def _build_search_terms(
        self, data: GIPARequestData, config: JurisdictionConfig
    ) -> str:
        """
        Build Section C: Search Terms (Boolean query).

        This is the most important section - it tells the government IT department
        exactly what to type into their email archive search bar.
        """
        lines = [
            "## Search Terms",
            "",
            "The Applicant requests access to the following records:",
            "",
        ]

        # 1. Date Range
        lines.append(f"1. **Date Range:** {data.start_date} to {data.end_date}.")
        lines.append("")

        item_num = 2

        # 2. Sender/Receiver specifications
        if data.targets:
            for target in data.targets:
                target_line = self._format_target(target)
                lines.append(f"{item_num}. {target_line}")
                lines.append("")
                item_num += 1
        else:
            lines.append(
                f"{item_num}. **Parties:** All officers and staff of {data.agency_name}."
            )
            lines.append("")
            item_num += 1

        # 3. Keywords (Boolean AND)
        if len(data.keywords) == 1:
            keyword_clause = f'containing the word **"{data.keywords[0]}"**'
        else:
            formatted_kws = [f'"{kw}"' for kw in data.keywords]
            keyword_clause = f"containing the words **{' AND '.join(formatted_kws)}**"

        lines.append(f"{item_num}. **Keywords:** All correspondence {keyword_clause}.")
        lines.append("")

        return "\n".join(lines)

    def _format_target(self, target: TargetPerson) -> str:
        """Format a single target person/role into a search term line."""
        name_str = target.name
        if target.role:
            name_str = f"{target.name} ({target.role})"

        if target.direction == "sender":
            return f"**Sender:** All correspondence sent **from** {name_str}."
        elif target.direction == "receiver":
            return f"**Receiver:** All correspondence sent **to** {name_str}."
        else:
            return f"**Party:** All correspondence involving {name_str} (as sender or receiver)."

    def _build_closing(self, data: GIPARequestData) -> str:
        """Build the closing section of the document."""
        lines = [
            "---",
            "",
            "I look forward to your acknowledgment of this request within "
            "the statutory timeframe.",
            "",
            "Should you require any clarification regarding the scope of this "
            "request, please do not hesitate to contact me.",
            "",
            "Yours faithfully,",
            "",
            f"**{data.applicant_name}**",
        ]

        if data.applicant_organization:
            lines.append(data.applicant_organization)

        return "\n".join(lines)

    def _generate_summary(self, data: GIPARequestData) -> str:
        """Generate a one-sentence summary if not already provided."""
        keywords_str = ", ".join(data.keywords)

        if data.targets:
            target_names = [t.name for t in data.targets]
            targets_str = " and ".join(target_names)
            return (
                f"All correspondence between {targets_str} held by "
                f"{data.agency_name}, containing references to {keywords_str}, "
                f"for the period {data.start_date} to {data.end_date}."
            )
        else:
            return (
                f"All correspondence held by {data.agency_name} "
                f"containing references to {keywords_str}, "
                f"for the period {data.start_date} to {data.end_date}."
            )

    async def _expand_keywords(self, keywords: List[str]) -> List[str]:
        """
        Expand keywords into legal definition strings using the SynonymExpander.

        Falls back to basic definitions if no expander is available.
        """
        if self.synonym_expander:
            return await self.synonym_expander.expand_keywords(keywords)
        else:
            # Basic fallback without AI expansion
            definitions = []
            for kw in keywords:
                definitions.append(
                    f'Define "{kw}" to include all references to {kw}, '
                    f"including abbreviations, acronyms, alternative spellings, "
                    f"and related terminology."
                )
            return definitions
