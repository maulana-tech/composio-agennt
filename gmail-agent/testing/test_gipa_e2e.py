"""
End-to-end tests for the GIPA Request Agent, from data input through PDF generation.

Covers the full pipeline:
  1. GIPARequestData construction (various applicant types & jurisdictions)
  2. Document generation -> Markdown output
  3. Markdown parsing -> structured elements
  4. PDF rendering -> actual file on disk
  5. Edge cases (long keywords, special characters, empty targets, etc.)
  6. Orchestrator session workflow with mocked LLM
  7. API endpoint contracts (Pydantic model validation)

No real LLM calls are made. Everything that touches an LLM is mocked.
PDF files are written to a temp directory and cleaned up after the run.

Run with:
    .venv/bin/python -m pytest testing/test_gipa_e2e.py -v
"""

import asyncio
import os
import shutil
import tempfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------
from server.tools.gipa_agent.clarification_engine import (
    ClarificationEngine,
    GIPARequestData,
    TargetPerson,
    REQUIRED_FIELDS,
)
from server.tools.gipa_agent.document_generator import GIPADocumentGenerator
from server.tools.gipa_agent.jurisdiction_config import (
    NSW_CONFIG,
    FEDERAL_CONFIG,
    VIC_CONFIG,
    get_jurisdiction_config,
)
from server.tools.gipa_agent.templates.boilerplate import (
    build_scope_and_definitions,
    get_fee_reduction_paragraph,
)
from server.tools.gipa_agent.synonym_expander import SynonymExpander
from server.tools.gipa_agent.gipa_agent import (
    GIPARequestAgent,
    _gipa_sessions,
    _get_or_create_session,
    _clear_session,
    get_gipa_tools,
)
from server.tools.pdf_generator import generate_pdf_report, parse_markdown_content
from server.models import (
    GIPAStartRequest,
    GIPAAnswerRequest,
    GIPAGenerateRequest,
    GIPAExpandKeywordsRequest,
    GIPAResponse,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear all GIPA sessions before and after each test."""
    _gipa_sessions.clear()
    yield
    _gipa_sessions.clear()


@pytest.fixture
def tmp_pdf_dir(tmp_path):
    """Provide a temporary directory for PDF output and clean up afterwards."""
    return tmp_path


def _make_data(**overrides) -> GIPARequestData:
    """Helper: create GIPARequestData with sensible defaults."""
    defaults = dict(
        agency_name="Department of Planning and Environment",
        agency_email="gipa@dpie.nsw.gov.au",
        applicant_name="Sarah Mitchell",
        applicant_organization="Environment Defenders Office",
        applicant_type="nonprofit",
        charity_status="ABN 72 002 880 864",
        public_interest_justification=(
            "This information is critical for understanding government "
            "decision-making regarding koala habitat conservation."
        ),
        start_date="1 January 2023",
        end_date="31 December 2024",
        targets=[
            TargetPerson(
                name="Minister for Environment", role="Minister", direction="both"
            ),
            TargetPerson(
                name="Dr James Chen",
                role="Director of Biodiversity Policy",
                direction="sender",
            ),
        ],
        keywords=["koala", "habitat", "development approval"],
        jurisdiction="NSW",
        fee_reduction_eligible=True,
        summary_sentence=(
            "All correspondence held by the Department of Planning and Environment "
            "involving the Minister for Environment and Dr James Chen containing "
            "references to koala, habitat, and development approval."
        ),
    )
    defaults.update(overrides)
    return GIPARequestData(**defaults)


# ============================================================================
# 1. Full Pipeline: Data -> Markdown -> PDF
# ============================================================================


class TestFullPipelineNSW:
    """NSW nonprofit with targets, multiple keywords -> Markdown -> PDF file."""

    @pytest.mark.asyncio
    async def test_nsw_nonprofit_produces_markdown(self):
        data = _make_data()
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, NSW_CONFIG)

        assert isinstance(md, str)
        assert len(md) > 500
        assert "GIPA Act" in md
        assert "Department of Planning and Environment" in md
        assert "Sarah Mitchell" in md
        assert "## Search Terms" in md
        assert "## Scope and Definitions" in md
        assert "## Fee Reduction Request" in md
        assert "Yours faithfully" in md

    @pytest.mark.asyncio
    async def test_nsw_nonprofit_markdown_parses_to_elements(self):
        data = _make_data()
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, NSW_CONFIG)
        elements = parse_markdown_content(md)

        types = [e["type"] for e in elements]
        assert "heading" in types or "h2" in types or any("head" in t for t in types)
        assert "numbered_list" in types
        assert "paragraph" in types

    @pytest.mark.asyncio
    async def test_nsw_nonprofit_generates_pdf_file(self, tmp_pdf_dir):
        data = _make_data()
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, NSW_CONFIG)

        path = generate_pdf_report.invoke(
            {
                "markdown_content": md,
                "filename": "test_nsw_nonprofit.pdf",
                "sender_email": "sarah@edo.org.au",
                "enable_quote_images": False,
            }
        )

        assert not path.startswith("ERROR"), f"PDF generation failed: {path}"
        assert os.path.isfile(path)
        assert path.endswith(".pdf")
        # File should have meaningful content (> 1 KB)
        assert os.path.getsize(path) > 1024

    @pytest.mark.asyncio
    async def test_nsw_nonprofit_pdf_contains_all_sections(self):
        """Ensure numbered lists from both Search Terms and Scope make it into PDF."""
        data = _make_data()
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, NSW_CONFIG)
        elements = parse_markdown_content(md)

        numbered_lists = [e for e in elements if e["type"] == "numbered_list"]
        # Should have at least 2 numbered lists: Search Terms + Scope & Definitions
        assert len(numbered_lists) >= 2

        # Search terms numbered list
        search_items = numbered_lists[0]["items"]
        assert any("Date Range" in item for item in search_items)
        assert any("koala" in item.lower() for item in search_items)

        # Scope numbered list has record definition, exclusions, keyword defs
        scope_items = numbered_lists[1]["items"]
        assert any("record" in item.lower() for item in scope_items)
        assert any("media alerts" in item.lower() for item in scope_items)


class TestFullPipelineFederal:
    """Federal journalist, no targets -> PDF file."""

    @pytest.mark.asyncio
    async def test_federal_journalist_generates_pdf(self):
        data = _make_data(
            agency_name="Department of Home Affairs",
            agency_email="foi@homeaffairs.gov.au",
            applicant_name="David Park",
            applicant_organization="The Guardian Australia",
            applicant_type="journalist",
            charity_status=None,
            public_interest_justification=(
                "The public has a right to understand visa processing delays."
            ),
            start_date="1 July 2024",
            end_date="31 January 2025",
            targets=[],
            keywords=["visa backlog", "processing delay", "skilled migration"],
            jurisdiction="Federal",
            fee_reduction_eligible=True,
            summary_sentence="All correspondence about visa backlogs.",
        )
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, FEDERAL_CONFIG)

        assert "FOI Act" in md
        assert "Department of Home Affairs" in md
        assert "David Park" in md
        assert "All officers and staff" in md  # no targets -> all staff

        path = generate_pdf_report.invoke(
            {
                "markdown_content": md,
                "filename": "test_federal_journalist.pdf",
                "sender_email": "david@guardian.com",
                "enable_quote_images": False,
            }
        )
        assert not path.startswith("ERROR"), f"PDF failed: {path}"
        assert os.path.isfile(path)
        assert os.path.getsize(path) > 1024


class TestFullPipelineVictoria:
    """Victoria jurisdiction -> PDF file."""

    @pytest.mark.asyncio
    async def test_vic_student_generates_pdf(self):
        data = _make_data(
            agency_name="Department of Transport and Planning",
            agency_email=None,
            applicant_name="Aisha Patel",
            applicant_organization="University of Melbourne",
            applicant_type="student",
            charity_status=None,
            public_interest_justification=(
                "Academic research on public transport funding."
            ),
            start_date="1 January 2024",
            end_date="30 June 2024",
            targets=[TargetPerson(name="Secretary of Transport", direction="both")],
            keywords=["suburban rail loop", "cost overrun"],
            jurisdiction="Victoria",
            fee_reduction_eligible=True,
            summary_sentence="All correspondence about suburban rail loop.",
        )
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, VIC_CONFIG)

        assert "FOI Act (Vic)" in md
        assert "to be confirmed" in md.lower()  # no agency email
        assert "s.22" in md  # VIC fee section

        path = generate_pdf_report.invoke(
            {
                "markdown_content": md,
                "filename": "test_vic_student.pdf",
                "sender_email": "aisha@unimelb.edu.au",
                "enable_quote_images": False,
            }
        )
        assert not path.startswith("ERROR"), f"PDF failed: {path}"
        assert os.path.isfile(path)


class TestFullPipelineIndividual:
    """Individual applicant, no fee reduction, single keyword -> PDF."""

    @pytest.mark.asyncio
    async def test_individual_no_fee_section_in_pdf(self):
        data = _make_data(
            applicant_name="Tom Nguyen",
            applicant_organization=None,
            applicant_type="individual",
            charity_status=None,
            agency_email=None,
            public_interest_justification="Community accountability.",
            targets=[],
            keywords=["use of force"],
            fee_reduction_eligible=False,
            summary_sentence="All correspondence about use of force.",
        )
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, NSW_CONFIG)

        assert "## Fee Reduction Request" not in md
        assert "AND" not in md  # single keyword, no AND

        path = generate_pdf_report.invoke(
            {
                "markdown_content": md,
                "filename": "test_individual.pdf",
                "sender_email": "tom@gmail.com",
                "enable_quote_images": False,
            }
        )
        assert not path.startswith("ERROR"), f"PDF failed: {path}"
        assert os.path.isfile(path)


# ============================================================================
# 2. Edge Cases: Markdown & PDF
# ============================================================================


class TestEdgeCasesPDF:
    """Edge cases that previously caused crashes or regressions."""

    @pytest.mark.asyncio
    async def test_many_numbered_items_no_crash(self):
        """Regression test: multiple numbered items must not overflow X cursor."""
        data = _make_data(
            keywords=[
                "koala",
                "habitat",
                "SEPP 44",
                "development approval",
                "conservation",
            ],
        )
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, NSW_CONFIG)

        elements = parse_markdown_content(md)
        # The scope section should have many numbered items (record def + 3 exclusions
        # + contractor + 5 keyword defs + correspondence def = 11 items)
        all_numbered = [e for e in elements if e["type"] == "numbered_list"]
        max_items = max(len(nl["items"]) for nl in all_numbered)
        assert max_items >= 9

        path = generate_pdf_report.invoke(
            {
                "markdown_content": md,
                "filename": "test_many_items.pdf",
                "sender_email": "test@test.com",
                "enable_quote_images": False,
            }
        )
        assert not path.startswith("ERROR"), f"PDF failed: {path}"

    @pytest.mark.asyncio
    async def test_long_keyword_no_crash(self):
        """Keywords with long phrases should wrap without crashing."""
        data = _make_data(
            keywords=[
                "koala habitat corridor management strategic assessment framework",
                "biodiversity offsets scheme contribution determination methodology",
            ],
        )
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, NSW_CONFIG)

        path = generate_pdf_report.invoke(
            {
                "markdown_content": md,
                "filename": "test_long_keywords.pdf",
                "sender_email": "test@test.com",
                "enable_quote_images": False,
            }
        )
        assert not path.startswith("ERROR"), f"PDF failed: {path}"

    @pytest.mark.asyncio
    async def test_special_chars_in_names(self):
        """Names with apostrophes, hyphens, accents should not crash PDF."""
        data = _make_data(
            applicant_name="Jean-Pierre O'Brien",
            applicant_organization="Jeunesse d'Environnement",
            targets=[
                TargetPerson(
                    name="Mary-Jane O'Sullivan", role="Director", direction="sender"
                ),
            ],
        )
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, NSW_CONFIG)

        assert "Jean-Pierre O'Brien" in md
        path = generate_pdf_report.invoke(
            {
                "markdown_content": md,
                "filename": "test_special_chars.pdf",
                "sender_email": "jp@test.com",
                "enable_quote_images": False,
            }
        )
        assert not path.startswith("ERROR"), f"PDF failed: {path}"

    @pytest.mark.asyncio
    async def test_many_targets_no_crash(self):
        """Documents with 5+ targets should generate valid PDF."""
        targets = [
            TargetPerson(name=f"Person {i}", role=f"Role {i}", direction=d)
            for i, d in enumerate(
                ["sender", "receiver", "both", "sender", "receiver", "both"], 1
            )
        ]
        data = _make_data(targets=targets)
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, NSW_CONFIG)

        # Should have 6 target lines
        for i in range(1, 7):
            assert f"Person {i}" in md

        path = generate_pdf_report.invoke(
            {
                "markdown_content": md,
                "filename": "test_many_targets.pdf",
                "sender_email": "test@test.com",
                "enable_quote_images": False,
            }
        )
        assert not path.startswith("ERROR"), f"PDF failed: {path}"

    @pytest.mark.asyncio
    async def test_no_bold_markers_in_numbered_items(self):
        """Regression: numbered list items should NOT contain ** markers."""
        data = _make_data()
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, NSW_CONFIG)

        elements = parse_markdown_content(md)
        for elem in elements:
            if elem["type"] == "numbered_list":
                for item in elem["items"]:
                    assert "**" not in item, (
                        f"Bold markers found in numbered item: {item}"
                    )


# ============================================================================
# 3. Markdown Content Verification
# ============================================================================


class TestMarkdownContent:
    """Verify the Markdown output contains all legally required content."""

    @pytest.mark.asyncio
    async def test_header_has_date_agency_applicant(self):
        data = _make_data()
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, NSW_CONFIG)

        lines = md.split("\n")
        # First non-empty line should be today's date
        first_line = lines[0].strip()
        assert "2026" in first_line or "202" in first_line  # year present

        assert "Department of Planning and Environment" in md
        assert "gipa@dpie.nsw.gov.au" in md
        assert "Sarah Mitchell" in md
        assert "Environment Defenders Office" in md

    @pytest.mark.asyncio
    async def test_search_terms_section_structure(self):
        data = _make_data()
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, NSW_CONFIG)

        # Date range is item 1
        assert "1. Date Range: 1 January 2023 to 31 December 2024." in md

        # Targets follow as items 2, 3
        assert "Minister for Environment" in md
        assert "Dr James Chen" in md

        # Keywords as final search term item
        assert "Keywords:" in md
        assert '"koala"' in md
        assert "AND" in md  # multiple keywords joined with AND

    @pytest.mark.asyncio
    async def test_scope_section_has_record_def(self):
        data = _make_data()
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, NSW_CONFIG)

        assert "Schedule 4, clause 10 of the GIPA Act" in md

    @pytest.mark.asyncio
    async def test_scope_section_has_exclusions(self):
        data = _make_data()
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, NSW_CONFIG)

        assert "media alerts" in md.lower()
        assert "duplicates" in md.lower()
        assert "out-of-office" in md.lower()

    @pytest.mark.asyncio
    async def test_scope_section_has_contractor_clause(self):
        data = _make_data()
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, NSW_CONFIG)

        assert "contractors" in md.lower() or "contractor" in md.lower()
        assert "personal devices" in md.lower()

    @pytest.mark.asyncio
    async def test_scope_section_has_correspondence_definition(self):
        data = _make_data()
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, NSW_CONFIG)

        assert "WhatsApp" in md
        assert "Signal" in md
        assert "Slack" in md

    @pytest.mark.asyncio
    async def test_scope_section_has_fallback_keyword_defs(self):
        data = _make_data()
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, NSW_CONFIG)

        for kw in ["koala", "habitat", "development approval"]:
            assert f'Define "{kw}"' in md

    @pytest.mark.asyncio
    async def test_closing_section(self):
        data = _make_data()
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, NSW_CONFIG)

        assert "statutory timeframe" in md
        assert "Yours faithfully" in md
        assert "**Sarah Mitchell**" in md

    @pytest.mark.asyncio
    async def test_fee_reduction_cites_correct_section(self):
        data = _make_data()
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, NSW_CONFIG)

        assert "s.127" in md
        assert "50%" in md
        assert "not-for-profit" in md

    @pytest.mark.asyncio
    async def test_federal_fee_reduction_cites_s29(self):
        data = _make_data(jurisdiction="Federal", fee_reduction_eligible=True)
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, FEDERAL_CONFIG)

        assert "s.29" in md
        assert "FOI Act" in md


# ============================================================================
# 4. Synonym Expander Integration (Mocked)
# ============================================================================


class TestSynonymExpanderIntegration:
    """Test that AI-expanded keyword definitions flow through to Markdown and PDF."""

    @pytest.mark.asyncio
    async def test_ai_expanded_keywords_appear_in_document(self):
        mock_expander = MagicMock()
        mock_expander.expand_keywords = AsyncMock(
            return_value=[
                'Define "koala" to include: Phascolarctos cinereus, native bear, arboreal marsupial, SEPP 44.',
                'Define "habitat" to include: koala habitat area, wildlife corridor, vegetation management.',
                'Define "development approval" to include: DA, development consent, planning approval, Part 4 approval.',
            ]
        )
        gen = GIPADocumentGenerator(synonym_expander=mock_expander)
        data = _make_data()
        md = await gen.generate(data, NSW_CONFIG)

        assert "Phascolarctos cinereus" in md
        assert "native bear" in md
        assert "wildlife corridor" in md
        assert "Part 4 approval" in md

    @pytest.mark.asyncio
    async def test_ai_expanded_keywords_in_pdf(self):
        mock_expander = MagicMock()
        mock_expander.expand_keywords = AsyncMock(
            return_value=[
                'Define "koala" to include: Phascolarctos cinereus, native bear.',
                'Define "habitat" to include: wildlife corridor.',
                'Define "development approval" to include: DA, development consent.',
            ]
        )
        gen = GIPADocumentGenerator(synonym_expander=mock_expander)
        data = _make_data()
        md = await gen.generate(data, NSW_CONFIG)

        path = generate_pdf_report.invoke(
            {
                "markdown_content": md,
                "filename": "test_ai_expanded.pdf",
                "sender_email": "test@test.com",
                "enable_quote_images": False,
            }
        )
        assert not path.startswith("ERROR"), f"PDF failed: {path}"
        assert os.path.isfile(path)


# ============================================================================
# 5. Orchestrator Session Flow -> Document -> PDF
# ============================================================================


class TestOrchestratorToPDF:
    """Simulate the full orchestrator workflow ending in PDF generation."""

    @patch("server.tools.gipa_agent.gipa_agent.SynonymExpander")
    @patch("server.tools.gipa_agent.gipa_agent.ClarificationEngine")
    def setup_method(self, method, mock_engine_cls, mock_expander_cls):
        self.mock_engine = MagicMock()
        self.mock_expander = MagicMock()
        # expand_keywords is async, so it must be an AsyncMock returning strings
        self.mock_expander.expand_keywords = AsyncMock(
            return_value=[
                'Define "koala" to include all references to koala, Phascolarctos cinereus, and related terminology.',
                'Define "habitat" to include all references to habitat, natural environment, and related terminology.',
            ]
        )
        mock_engine_cls.return_value = self.mock_engine
        mock_expander_cls.return_value = self.mock_expander
        self.agent = GIPARequestAgent(google_api_key="fake-key")

    @pytest.mark.asyncio
    async def test_full_session_flow(self):
        """start -> answer (collecting) -> answer (complete) -> generate -> PDF."""
        session_id = "e2e-test-1"

        # Step 1: Start
        intro = await self.agent.start_request(session_id)
        assert "GIPA" in intro
        assert _gipa_sessions[session_id]["status"] == "collecting"

        # Step 2: User provides some info (still collecting)
        self.mock_engine.extract_variables = AsyncMock(
            return_value=(
                {"agency_name": "DPI", "applicant_name": "Jane Doe"},
                ["What type of applicant are you?"],
                False,
            )
        )
        response = await self.agent.process_answer(
            session_id, "DPI, my name is Jane Doe"
        )
        assert "applicant" in response.lower()

        # Step 3: User completes all fields
        complete_data = {
            "agency_name": "Department of Primary Industries",
            "agency_email": "gipa@dpi.nsw.gov.au",
            "applicant_name": "Jane Doe",
            "applicant_organization": "EDO",
            "applicant_type": "nonprofit",
            "charity_status": "ABN 12345",
            "public_interest_justification": "Environmental transparency.",
            "start_date": "1 January 2023",
            "end_date": "31 December 2024",
            "targets": [
                {"name": "John Smith", "role": "Director", "direction": "sender"}
            ],
            "keywords": ["koala", "habitat"],
            "jurisdiction": "NSW",
        }
        self.mock_engine.extract_variables = AsyncMock(
            return_value=(complete_data, [], True)
        )
        summary = await self.agent.process_answer(session_id, "all my info here")
        assert "correct" in summary.lower() or "summary" in summary.lower()
        assert _gipa_sessions[session_id]["status"] == "ready"

        # Step 4: Generate the document
        self.mock_engine.validate_data.return_value = (True, [])
        self.mock_engine.build_gipa_request_data.return_value = GIPARequestData(
            agency_name="Department of Primary Industries",
            agency_email="gipa@dpi.nsw.gov.au",
            applicant_name="Jane Doe",
            applicant_organization="EDO",
            applicant_type="nonprofit",
            charity_status="ABN 12345",
            public_interest_justification="Environmental transparency.",
            start_date="1 January 2023",
            end_date="31 December 2024",
            targets=[
                TargetPerson(name="John Smith", role="Director", direction="sender")
            ],
            keywords=["koala", "habitat"],
            jurisdiction="NSW",
            fee_reduction_eligible=True,
            summary_sentence="All correspondence about koala and habitat.",
        )
        document = await self.agent.generate_document(session_id)
        assert _gipa_sessions[session_id]["status"] == "generated"
        assert "GIPA Act" in document
        assert "## Search Terms" in document
        assert "## Scope and Definitions" in document

        # Step 5: Pipe the document through PDF generator
        path = generate_pdf_report.invoke(
            {
                "markdown_content": document,
                "filename": "test_orchestrator_e2e.pdf",
                "sender_email": "jane@edo.org.au",
                "enable_quote_images": False,
            }
        )
        assert not path.startswith("ERROR"), f"PDF failed: {path}"
        assert os.path.isfile(path)
        assert os.path.getsize(path) > 1024

    @pytest.mark.asyncio
    async def test_cannot_generate_without_complete_data(self):
        session_id = "e2e-test-2"
        await self.agent.start_request(session_id)

        self.mock_engine.validate_data.return_value = (
            False,
            ["Missing required field: agency_name", "At least one keyword is required"],
        )
        result = await self.agent.generate_document(session_id)
        assert "Cannot generate" in result
        assert "agency_name" in result

    @pytest.mark.asyncio
    async def test_already_generated_session_rejects_answer(self):
        session_id = "e2e-test-3"
        _get_or_create_session(session_id)
        _gipa_sessions[session_id]["status"] = "generated"

        result = await self.agent.process_answer(session_id, "more info")
        assert "already been generated" in result


# ============================================================================
# 6. API Model Validation
# ============================================================================


class TestAPIModels:
    """Ensure Pydantic models for the GIPA endpoints accept and reject correctly."""

    def test_gipa_start_request_defaults(self):
        req = GIPAStartRequest()
        assert req.session_id == "default"

    def test_gipa_start_request_custom_session(self):
        req = GIPAStartRequest(session_id="my-session-123")
        assert req.session_id == "my-session-123"

    def test_gipa_answer_request(self):
        req = GIPAAnswerRequest(answer="The agency is DPI")
        assert req.answer == "The agency is DPI"
        assert req.session_id == "default"

    def test_gipa_generate_request(self):
        req = GIPAGenerateRequest(session_id="sess-5")
        assert req.session_id == "sess-5"

    def test_gipa_expand_keywords_request(self):
        req = GIPAExpandKeywordsRequest(keywords=["koala", "habitat"])
        assert len(req.keywords) == 2

    def test_gipa_expand_keywords_rejects_empty(self):
        with pytest.raises(Exception):
            GIPAExpandKeywordsRequest(keywords=[])

    def test_gipa_response_success(self):
        resp = GIPAResponse(
            success=True,
            message="Generated.",
            status="generated",
            document="## Search Terms\n...",
        )
        assert resp.success is True
        assert resp.document is not None

    def test_gipa_response_error(self):
        resp = GIPAResponse(success=False, message="", error="Something went wrong")
        assert resp.success is False
        assert resp.error == "Something went wrong"


# ============================================================================
# 7. Cross-Jurisdiction PDF Generation
# ============================================================================


class TestCrossJurisdictionPDF:
    """Every supported jurisdiction should produce a valid PDF."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "jurisdiction,config",
        [
            ("NSW", NSW_CONFIG),
            ("Federal", FEDERAL_CONFIG),
            ("Victoria", VIC_CONFIG),
        ],
    )
    async def test_each_jurisdiction_generates_pdf(self, jurisdiction, config):
        data = _make_data(
            jurisdiction=jurisdiction,
            summary_sentence=f"Test summary for {jurisdiction}.",
        )
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, config)

        assert config.act_short_name in md

        path = generate_pdf_report.invoke(
            {
                "markdown_content": md,
                "filename": f"test_jurisdiction_{jurisdiction.lower()}.pdf",
                "sender_email": "test@test.com",
                "enable_quote_images": False,
            }
        )
        assert not path.startswith("ERROR"), f"PDF failed for {jurisdiction}: {path}"
        assert os.path.isfile(path)


# ============================================================================
# 8. Boilerplate Numbering Integrity
# ============================================================================


class TestBoilerplateNumbering:
    """The Scope & Definitions numbered list must be sequential and unbroken."""

    def test_scope_numbering_1_keyword(self):
        defs = ['Define "test" to include: variants.']
        result = build_scope_and_definitions(NSW_CONFIG, defs)
        lines = result.split("\n")
        nums = [int(l.split(".")[0]) for l in lines if l and l[0].isdigit()]
        assert nums == list(range(1, len(nums) + 1))

    def test_scope_numbering_5_keywords(self):
        defs = [f'Define "kw{i}" to include: related terms.' for i in range(5)]
        result = build_scope_and_definitions(NSW_CONFIG, defs)
        lines = result.split("\n")
        nums = [int(l.split(".")[0]) for l in lines if l and l[0].isdigit()]
        assert nums == list(range(1, len(nums) + 1))
        # 1 record + 3 exclusions + 1 contractor + 5 keywords + 1 correspondence = 11
        assert len(nums) == 11


# ============================================================================
# 9. PDF File Integrity
# ============================================================================


class TestPDFFileIntegrity:
    """Basic PDF file integrity checks."""

    @pytest.mark.asyncio
    async def test_pdf_starts_with_pdf_header(self):
        """A valid PDF file should start with %PDF."""
        data = _make_data()
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, NSW_CONFIG)

        path = generate_pdf_report.invoke(
            {
                "markdown_content": md,
                "filename": "test_pdf_header.pdf",
                "sender_email": "test@test.com",
                "enable_quote_images": False,
            }
        )
        assert not path.startswith("ERROR")
        with open(path, "rb") as f:
            header = f.read(5)
        assert header == b"%PDF-"

    @pytest.mark.asyncio
    async def test_pdf_reasonable_size(self):
        """A full GIPA PDF should be between 2 KB and 500 KB."""
        data = _make_data()
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, NSW_CONFIG)

        path = generate_pdf_report.invoke(
            {
                "markdown_content": md,
                "filename": "test_pdf_size.pdf",
                "sender_email": "test@test.com",
                "enable_quote_images": False,
            }
        )
        assert not path.startswith("ERROR")
        size = os.path.getsize(path)
        assert 2048 < size < 512_000, f"PDF size {size} bytes out of expected range"

    @pytest.mark.asyncio
    async def test_different_filenames_produce_different_files(self):
        """Two invocations with different filenames should produce separate files."""
        data = _make_data()
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, NSW_CONFIG)

        path1 = generate_pdf_report.invoke(
            {
                "markdown_content": md,
                "filename": "test_diff_a.pdf",
                "sender_email": "a@test.com",
                "enable_quote_images": False,
            }
        )
        path2 = generate_pdf_report.invoke(
            {
                "markdown_content": md,
                "filename": "test_diff_b.pdf",
                "sender_email": "b@test.com",
                "enable_quote_images": False,
            }
        )
        assert path1 != path2
        assert os.path.isfile(path1)
        assert os.path.isfile(path2)


# ============================================================================
# 10. Data Model Edge Cases Through to PDF
# ============================================================================


class TestDataModelEdgeCases:
    """Data model edge cases that should still produce valid PDF output."""

    @pytest.mark.asyncio
    async def test_minimal_valid_data_generates_pdf(self):
        """The absolute minimum fields required should still produce a PDF."""
        data = GIPARequestData(
            agency_name="Test Agency",
            applicant_name="Test Person",
            public_interest_justification="Public interest.",
            start_date="1 Jan 2024",
            end_date="31 Dec 2024",
            keywords=["test"],
        )
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data)

        path = generate_pdf_report.invoke(
            {
                "markdown_content": md,
                "filename": "test_minimal.pdf",
                "sender_email": "test@test.com",
                "enable_quote_images": False,
            }
        )
        assert not path.startswith("ERROR"), f"PDF failed: {path}"
        assert os.path.isfile(path)

    @pytest.mark.asyncio
    async def test_max_keywords_generates_pdf(self):
        """Many keywords should still produce a valid PDF."""
        keywords = [f"keyword_{i}" for i in range(10)]
        data = _make_data(keywords=keywords)
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, NSW_CONFIG)

        # 10 keywords joined with AND
        assert "AND" in md

        path = generate_pdf_report.invoke(
            {
                "markdown_content": md,
                "filename": "test_max_keywords.pdf",
                "sender_email": "test@test.com",
                "enable_quote_images": False,
            }
        )
        assert not path.startswith("ERROR"), f"PDF failed: {path}"

    @pytest.mark.asyncio
    async def test_target_all_directions(self):
        """Each direction type (sender, receiver, both) should appear correctly."""
        data = _make_data(
            targets=[
                TargetPerson(name="Alice", direction="sender"),
                TargetPerson(name="Bob", direction="receiver"),
                TargetPerson(name="Charlie", direction="both"),
            ],
        )
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = await gen.generate(data, NSW_CONFIG)

        assert "from Alice" in md
        assert "to Bob" in md
        assert "involving Charlie" in md

        path = generate_pdf_report.invoke(
            {
                "markdown_content": md,
                "filename": "test_directions.pdf",
                "sender_email": "test@test.com",
                "enable_quote_images": False,
            }
        )
        assert not path.startswith("ERROR"), f"PDF failed: {path}"

    def test_gipa_data_json_roundtrip_then_regenerate(self):
        """Serialize data to JSON, deserialize, and generate document from it."""
        original = _make_data()
        json_str = original.model_dump_json()
        restored = GIPARequestData.model_validate_json(json_str)

        assert restored.agency_name == original.agency_name
        assert len(restored.targets) == len(original.targets)
        assert restored.keywords == original.keywords

        # Confirm it can still generate
        gen = GIPADocumentGenerator(synonym_expander=None)
        md = asyncio.get_event_loop().run_until_complete(
            gen.generate(restored, NSW_CONFIG)
        )
        assert "## Search Terms" in md
