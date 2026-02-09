"""
GIPA Document Generator.

Assembles the final GIPA application document from structured data,
jurisdiction config, boilerplate clauses, and AI-generated keyword definitions.

The output follows the strict legal document structure:
  Header -> Legal Standing -> Search Protocol -> Scope & Definitions

Output format is Markdown, suitable for use as an email body.
"""

from datetime import date
from typing import List, Optional
from html import escape as html_escape

from .clarification_engine import GIPARequestData, TargetPerson
from .jurisdiction_config import JurisdictionConfig, get_jurisdiction_config
from .synonym_expander import SynonymExpander
from .templates.boilerplate import (
    build_scope_and_definitions,
    get_fee_reduction_paragraph,
    get_record_definition,
    get_correspondence_definition,
    STANDARD_EXCLUSIONS,
    CONTRACTOR_INCLUSION,
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

    async def generate_html(
        self,
        data: GIPARequestData,
        config: Optional[JurisdictionConfig] = None,
    ) -> str:
        """
        Generate a complete GIPA application as a styled HTML email body.

        This produces Gmail-compatible HTML that renders properly when
        used as the body of a GMAIL_CREATE_EMAIL_DRAFT call with is_html=True.

        Args:
            data: Validated GIPARequestData with all required fields.
            config: Jurisdiction configuration. If None, derived from data.jurisdiction.

        Returns:
            Complete GIPA application as an HTML string ready for Gmail.
        """
        if config is None:
            config = get_jurisdiction_config(data.jurisdiction)

        keyword_definitions = await self._expand_keywords(data.keywords)

        today = date.today().strftime("%-d %B %Y")
        e = html_escape  # shorthand

        # --- Build HTML ---
        html_parts = []

        # Wrapper with inline styles (Gmail strips <style> blocks)
        html_parts.append(
            "<div style=\"font-family: Georgia, 'Times New Roman', serif; "
            "font-size: 14px; line-height: 1.6; color: #1a1a1a; "
            'max-width: 700px; margin: 0 auto;">'
        )

        # Section A: Header & Routing
        html_parts.append(f'<p style="margin-bottom: 4px;">{e(today)}</p>')
        html_parts.append(f'<p style="margin-bottom: 0;">{e(data.agency_name)}')
        if data.agency_email:
            html_parts.append(f"<br>Via email: {e(data.agency_email)}</p>")
        else:
            html_parts.append(
                "<br><em>[GIPA email address to be confirmed before submission]</em></p>"
            )

        html_parts.append(
            f'<p style="margin-top: 16px; margin-bottom: 16px;">'
            f"<strong>RE: {e(config.act_name)} ({e(config.act_short_name)}) "
            f"- Information Request</strong></p>"
        )

        html_parts.append("<p>Dear Right to Information Officer,</p>")

        applicant_line = e(data.applicant_name)
        if data.applicant_organization:
            applicant_line += f"<br>on behalf of {e(data.applicant_organization)}"
        applicant_line += f"<br>seeks access to information under the {e(config.act_short_name)} regarding:"
        html_parts.append(f"<p>{applicant_line}</p>")

        summary = data.summary_sentence or self._generate_summary(data)
        html_parts.append(
            f'<blockquote style="border-left: 3px solid #666; margin: 12px 0; '
            f'padding: 8px 16px; color: #333; background-color: #f9f9f9;">'
            f"{e(summary)}</blockquote>"
        )

        # Section B: Fee Reduction (conditional)
        if data.fee_reduction_eligible:
            fee_text = get_fee_reduction_paragraph(
                config=config,
                applicant_type=data.applicant_type,
                public_interest_justification=data.public_interest_justification,
                applicant_organization=data.applicant_organization or "",
                charity_status=data.charity_status or "",
            )
            html_parts.append(
                '<h2 style="font-size: 16px; border-bottom: 1px solid #ccc; '
                'padding-bottom: 4px; margin-top: 24px;">Fee Reduction Request</h2>'
            )
            # Fee text may have \n\n paragraph breaks
            for para in fee_text.split("\n\n"):
                html_parts.append(f"<p>{e(para.strip())}</p>")

        # Section C: Search Terms
        html_parts.append(
            '<h2 style="font-size: 16px; border-bottom: 1px solid #ccc; '
            'padding-bottom: 4px; margin-top: 24px;">Search Terms</h2>'
        )
        html_parts.append(
            "<p>The Applicant requests access to the following records:</p>"
        )

        html_parts.append('<ol style="padding-left: 20px;">')

        # Date Range
        html_parts.append(
            f'<li style="margin-bottom: 8px;">'
            f"<strong>Date Range:</strong> {e(data.start_date)} to {e(data.end_date)}.</li>"
        )

        # Targets
        if data.targets:
            for target in data.targets:
                target_line = self._format_target(target)
                html_parts.append(
                    f'<li style="margin-bottom: 8px;">{e(target_line)}</li>'
                )
        else:
            html_parts.append(
                f'<li style="margin-bottom: 8px;">'
                f"<strong>Parties:</strong> All officers and staff of {e(data.agency_name)}.</li>"
            )

        # Keywords
        if len(data.keywords) == 1:
            keyword_clause = f"containing the word &ldquo;{e(data.keywords[0])}&rdquo;"
        else:
            formatted_kws = [f"&ldquo;{e(kw)}&rdquo;" for kw in data.keywords]
            keyword_clause = f"containing the words {' AND '.join(formatted_kws)}"
        html_parts.append(
            f'<li style="margin-bottom: 8px;">'
            f"<strong>Keywords:</strong> All correspondence {keyword_clause}.</li>"
        )
        html_parts.append("</ol>")

        # Section D: Scope & Definitions
        html_parts.append(
            '<h2 style="font-size: 16px; border-bottom: 1px solid #ccc; '
            'padding-bottom: 4px; margin-top: 24px;">Scope and Definitions</h2>'
        )
        html_parts.append("<p>The above search terms &mdash;</p>")
        html_parts.append('<ol style="padding-left: 20px;">')

        # Record definition
        html_parts.append(
            f'<li style="margin-bottom: 8px;">{e(get_record_definition(config))}</li>'
        )

        # Standard exclusions
        for exclusion in STANDARD_EXCLUSIONS:
            html_parts.append(f'<li style="margin-bottom: 8px;">{e(exclusion)}</li>')

        # Contractor inclusion
        html_parts.append(
            f'<li style="margin-bottom: 8px;">{e(CONTRACTOR_INCLUSION)}</li>'
        )

        # Keyword definitions
        for definition in keyword_definitions:
            html_parts.append(f'<li style="margin-bottom: 8px;">{e(definition)}</li>')

        # Correspondence definition
        html_parts.append(
            f'<li style="margin-bottom: 8px;">'
            f"{e(get_correspondence_definition(config))}</li>"
        )
        html_parts.append("</ol>")

        # Closing
        html_parts.append(
            '<hr style="border: none; border-top: 1px solid #ccc; margin: 24px 0;">'
        )
        html_parts.append(
            "<p>I look forward to your acknowledgment of this request within "
            "the statutory timeframe.</p>"
        )
        html_parts.append(
            "<p>Should you require any clarification regarding the scope of this "
            "request, please do not hesitate to contact me.</p>"
        )
        html_parts.append("<p>Yours faithfully,</p>")
        html_parts.append(f"<p><strong>{e(data.applicant_name)}</strong>")
        if data.applicant_organization:
            html_parts.append(f"<br>{e(data.applicant_organization)}")
        html_parts.append("</p>")

        # Close wrapper
        html_parts.append("</div>")

        return "\n".join(html_parts)

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
                f"**RE: {config.act_name} ({config.act_short_name}) - Information Request**",
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
        lines.append(f"1. Date Range: {data.start_date} to {data.end_date}.")
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
                f"{item_num}. Parties: All officers and staff of {data.agency_name}."
            )
            lines.append("")
            item_num += 1

        # 3. Keywords (Boolean AND)
        if len(data.keywords) == 1:
            keyword_clause = f'containing the word "{data.keywords[0]}"'
        else:
            formatted_kws = [f'"{kw}"' for kw in data.keywords]
            keyword_clause = f"containing the words {' AND '.join(formatted_kws)}"

        lines.append(f"{item_num}. Keywords: All correspondence {keyword_clause}.")
        lines.append("")

        return "\n".join(lines)

    def _format_target(self, target: TargetPerson) -> str:
        """Format a single target person/role into a search term line."""
        name_str = target.name
        if target.role:
            name_str = f"{target.name} ({target.role})"

        if target.direction == "sender":
            return f"Sender: All correspondence sent from {name_str}."
        elif target.direction == "receiver":
            return f"Receiver: All correspondence sent to {name_str}."
        else:
            return f"Party: All correspondence involving {name_str} (as sender or receiver)."

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
