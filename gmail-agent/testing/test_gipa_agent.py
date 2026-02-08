"""
Tests for GIPA Request Agent.

Covers:
  - Jurisdiction config lookup and data integrity
  - Boilerplate template generation (exclusions, fee reduction, scope)
  - Clarification engine (field validation, missing field detection, data building)
  - Synonym expander (parsing, caching, fallback)
  - Document generator (section assembly, conditional fee section, search terms)
  - Orchestrator session management
  - Full end-to-end generation with mock LLM

Run with:
    .venv/bin/python -m pytest testing/test_gipa_agent.py -v
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------
from server.tools.gipa_agent.jurisdiction_config import (
    JurisdictionConfig,
    NSW_CONFIG,
    FEDERAL_CONFIG,
    VIC_CONFIG,
    get_jurisdiction_config,
)
from server.tools.gipa_agent.templates.boilerplate import (
    STANDARD_EXCLUSIONS,
    EXCLUSION_MEDIA_ALERTS,
    EXCLUSION_DUPLICATES,
    EXCLUSION_AUTOREPLY,
    CONTRACTOR_INCLUSION,
    get_record_definition,
    get_correspondence_definition,
    get_fee_reduction_paragraph,
    build_scope_and_definitions,
)
from server.tools.gipa_agent.clarification_engine import (
    ClarificationEngine,
    GIPARequestData,
    TargetPerson,
    REQUIRED_FIELDS,
    CONDITIONAL_FIELDS,
)
from server.tools.gipa_agent.synonym_expander import SynonymExpander
from server.tools.gipa_agent.document_generator import GIPADocumentGenerator
from server.tools.gipa_agent.gipa_agent import (
    GIPARequestAgent,
    _gipa_sessions,
    _get_or_create_session,
    _clear_session,
    get_gipa_tools,
    gipa_check_status,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_complete_data() -> dict:
    """A complete set of GIPA request data (as dict) for testing."""
    return {
        "agency_name": "Department of Primary Industries",
        "agency_email": "gipa@dpi.nsw.gov.au",
        "applicant_name": "Jane Doe",
        "applicant_organization": "Environment Defenders Office",
        "applicant_type": "nonprofit",
        "charity_status": "ABN 123456789",
        "public_interest_justification": (
            "This information is needed to understand government "
            "decision-making on koala habitat conservation."
        ),
        "start_date": "1 January 2023",
        "end_date": "31 December 2024",
        "targets": [
            {"name": "John Smith", "role": "Director of Policy", "direction": "sender"},
            {"name": "Mary Jones", "role": None, "direction": "both"},
        ],
        "keywords": ["koala", "habitat", "development approval"],
        "jurisdiction": "NSW",
    }


@pytest.fixture
def sample_individual_data() -> dict:
    """A complete set of GIPA request data for an individual (no fee reduction)."""
    return {
        "agency_name": "Transport for NSW",
        "applicant_name": "Bob Builder",
        "applicant_type": "individual",
        "public_interest_justification": "Road safety concerns in my area.",
        "start_date": "1 March 2024",
        "end_date": "30 June 2024",
        "targets": [],
        "keywords": ["road safety"],
        "jurisdiction": "NSW",
    }


@pytest.fixture
def nsw_config():
    return NSW_CONFIG


@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear all GIPA sessions before each test."""
    _gipa_sessions.clear()
    yield
    _gipa_sessions.clear()


# ============================================================================
# 1. Jurisdiction Config Tests
# ============================================================================


class TestJurisdictionConfig:
    def test_nsw_config_fields(self):
        cfg = NSW_CONFIG
        assert cfg.jurisdiction == "NSW"
        assert "GIPA" in cfg.act_short_name
        assert cfg.act_year == 2009
        assert cfg.fee_reduction_section == "s.127"
        assert cfg.base_application_fee == "$30"
        assert len(cfg.correspondence_platforms) >= 6
        assert "email" in cfg.correspondence_platforms
        assert "WhatsApp" in cfg.correspondence_platforms

    def test_federal_config_fields(self):
        cfg = FEDERAL_CONFIG
        assert cfg.jurisdiction == "Federal"
        assert "FOI" in cfg.act_short_name
        assert cfg.act_year == 1982
        assert cfg.base_application_fee == "$0"
        assert cfg.request_term == "FOI request"

    def test_vic_config_fields(self):
        cfg = VIC_CONFIG
        assert cfg.jurisdiction == "Victoria"
        assert "(Vic)" in cfg.act_short_name
        assert cfg.fee_reduction_section == "s.22"

    def test_get_jurisdiction_config_nsw(self):
        assert get_jurisdiction_config("nsw") is NSW_CONFIG
        assert get_jurisdiction_config("NSW") is NSW_CONFIG
        assert get_jurisdiction_config("new south wales") is NSW_CONFIG
        assert get_jurisdiction_config("  NSW  ") is NSW_CONFIG

    def test_get_jurisdiction_config_federal(self):
        assert get_jurisdiction_config("federal") is FEDERAL_CONFIG
        assert get_jurisdiction_config("commonwealth") is FEDERAL_CONFIG

    def test_get_jurisdiction_config_vic(self):
        assert get_jurisdiction_config("vic") is VIC_CONFIG
        assert get_jurisdiction_config("victoria") is VIC_CONFIG

    def test_get_jurisdiction_config_invalid(self):
        with pytest.raises(ValueError, match="Unknown jurisdiction"):
            get_jurisdiction_config("Queensland")

    def test_config_is_frozen(self):
        with pytest.raises(AttributeError):
            NSW_CONFIG.jurisdiction = "something else"


# ============================================================================
# 2. Boilerplate Template Tests
# ============================================================================


class TestBoilerplateTemplates:
    def test_standard_exclusions_count(self):
        assert len(STANDARD_EXCLUSIONS) == 3

    def test_exclusions_contain_key_phrases(self):
        assert "media alerts" in EXCLUSION_MEDIA_ALERTS.lower()
        assert "duplicates" in EXCLUSION_DUPLICATES.lower()
        assert "out-of-office" in EXCLUSION_AUTOREPLY.lower()

    def test_contractor_inclusion_mentions_personal_devices(self):
        assert "personal devices" in CONTRACTOR_INCLUSION.lower()

    def test_record_definition_cites_act(self, nsw_config):
        result = get_record_definition(nsw_config)
        assert "Schedule 4" in result
        assert "GIPA Act" in result
        assert "memorandum" in result

    def test_correspondence_definition_lists_platforms(self, nsw_config):
        result = get_correspondence_definition(nsw_config)
        assert "WhatsApp" in result
        assert "Signal" in result
        assert "Slack" in result
        assert "personal devices" in result

    def test_fee_reduction_nonprofit(self, nsw_config):
        result = get_fee_reduction_paragraph(
            config=nsw_config,
            applicant_type="nonprofit",
            public_interest_justification="Environmental transparency",
            applicant_organization="EDO",
            charity_status="ABN 12345",
        )
        assert "s.127" in result
        assert "50%" in result
        assert "not-for-profit" in result
        assert "EDO" in result
        assert "ABN 12345" in result
        assert "Environmental transparency" in result

    def test_fee_reduction_journalist(self, nsw_config):
        result = get_fee_reduction_paragraph(
            config=nsw_config,
            applicant_type="journalist",
            public_interest_justification="Public accountability",
            applicant_organization="The Guardian",
        )
        assert "journalist" in result
        assert "The Guardian" in result
        assert "disseminating information" in result

    def test_fee_reduction_student(self, nsw_config):
        result = get_fee_reduction_paragraph(
            config=nsw_config,
            applicant_type="student",
            public_interest_justification="Academic research",
            applicant_organization="UNSW",
        )
        assert "student" in result
        assert "UNSW" in result
        assert "academic research" in result.lower()

    def test_fee_reduction_federal_jurisdiction(self):
        result = get_fee_reduction_paragraph(
            config=FEDERAL_CONFIG,
            applicant_type="nonprofit",
            public_interest_justification="Test",
        )
        assert "s.29" in result
        assert "FOI Act" in result

    def test_build_scope_and_definitions(self, nsw_config):
        keyword_defs = [
            'Define "Koala" to include: Phascolarctos cinereus, native bear.',
            'Define "Habitat" to include: koala habitat area, SEPP 44.',
        ]
        result = build_scope_and_definitions(nsw_config, keyword_defs)

        assert "## Scope and Definitions" in result
        assert "Schedule 4" in result  # record definition
        assert "media alerts" in result.lower()  # exclusion
        assert "duplicates" in result.lower()  # exclusion
        assert "out-of-office" in result.lower()  # exclusion
        assert "contractors" in result.lower() or "contractor" in result.lower()
        assert "Koala" in result
        assert "Habitat" in result
        assert "WhatsApp" in result  # correspondence definition

    def test_scope_definitions_numbering_is_sequential(self, nsw_config):
        keyword_defs = ['Define "Test" to include: variants.']
        result = build_scope_and_definitions(nsw_config, keyword_defs)
        lines = result.split("\n")
        numbered_lines = [l for l in lines if l and l[0].isdigit()]
        # Extract the leading numbers
        numbers = [int(l.split(".")[0]) for l in numbered_lines]
        # Should be sequential starting from 1
        assert numbers == list(range(1, len(numbers) + 1))


# ============================================================================
# 3. Clarification Engine Tests
# ============================================================================


class TestTargetPerson:
    def test_create_target_person(self):
        t = TargetPerson(name="John Smith", role="Director", direction="sender")
        assert t.name == "John Smith"
        assert t.role == "Director"
        assert t.direction == "sender"

    def test_target_person_defaults(self):
        t = TargetPerson(name="Jane")
        assert t.role is None
        assert t.direction == "both"

    def test_target_person_invalid_direction(self):
        with pytest.raises(Exception):
            TargetPerson(name="Jane", direction="unknown")


class TestGIPARequestData:
    def test_create_from_complete_data(self, sample_complete_data):
        # Convert target dicts to TargetPerson objects
        data = sample_complete_data.copy()
        data["targets"] = [TargetPerson(**t) for t in data["targets"]]
        data["fee_reduction_eligible"] = True
        data["summary_sentence"] = "Test summary"
        grd = GIPARequestData(**data)
        assert grd.agency_name == "Department of Primary Industries"
        assert len(grd.targets) == 2
        assert grd.fee_reduction_eligible is True

    def test_fee_reduction_auto_computed_nonprofit(self):
        grd = GIPARequestData(
            agency_name="Test",
            applicant_name="Test",
            applicant_type="nonprofit",
            public_interest_justification="Test",
            start_date="1 Jan 2024",
            end_date="31 Dec 2024",
            keywords=["test"],
        )
        assert grd.fee_reduction_eligible is True

    def test_fee_reduction_auto_computed_individual(self):
        grd = GIPARequestData(
            agency_name="Test",
            applicant_name="Test",
            applicant_type="individual",
            public_interest_justification="Test",
            start_date="1 Jan 2024",
            end_date="31 Dec 2024",
            keywords=["test"],
        )
        assert grd.fee_reduction_eligible is False

    def test_keywords_min_length(self):
        with pytest.raises(Exception):
            GIPARequestData(
                agency_name="Test",
                applicant_name="Test",
                public_interest_justification="Test",
                start_date="1 Jan 2024",
                end_date="31 Dec 2024",
                keywords=[],  # must have at least 1
            )


class TestRequiredFields:
    def test_required_fields_count(self):
        assert len(REQUIRED_FIELDS) == 8

    def test_required_fields_have_priorities(self):
        priorities = [f["priority"] for f in REQUIRED_FIELDS]
        # Priorities should be unique
        assert len(priorities) == len(set(priorities))

    def test_agency_name_is_first_priority(self):
        first = min(REQUIRED_FIELDS, key=lambda f: f["priority"])
        assert first["field"] == "agency_name"

    def test_all_required_fields_have_questions(self):
        for field in REQUIRED_FIELDS:
            assert "question" in field
            assert len(field["question"]) > 10


class TestClarificationEngineValidation:
    """Tests for ClarificationEngine methods that don't require LLM calls."""

    @patch("server.tools.gipa_agent.clarification_engine.ChatGoogleGenerativeAI")
    def setup_method(self, method, mock_llm_class):
        """Create engine with mocked LLM."""
        mock_llm_class.return_value = MagicMock()
        self.engine = ClarificationEngine(google_api_key="fake-key")

    def test_validate_complete_data(self, sample_complete_data):
        is_valid, errors = self.engine.validate_data(sample_complete_data)
        assert is_valid is True
        # Should only have a warning about agency email (it IS present in fixture)
        # Actually, agency_email is present, so no warnings
        assert all("WARNING" not in e for e in errors if not e.startswith("WARNING"))

    def test_validate_missing_agency(self, sample_complete_data):
        data = sample_complete_data.copy()
        del data["agency_name"]
        is_valid, errors = self.engine.validate_data(data)
        assert is_valid is False
        assert any("agency_name" in e for e in errors)

    def test_validate_missing_keywords(self, sample_complete_data):
        data = sample_complete_data.copy()
        data["keywords"] = []
        is_valid, errors = self.engine.validate_data(data)
        assert is_valid is False
        assert any("keyword" in e.lower() for e in errors)

    def test_validate_invalid_applicant_type(self, sample_complete_data):
        data = sample_complete_data.copy()
        data["applicant_type"] = "alien"
        is_valid, errors = self.engine.validate_data(data)
        assert is_valid is False
        assert any("applicant_type" in e for e in errors)

    def test_validate_nonprofit_without_org(self, sample_complete_data):
        data = sample_complete_data.copy()
        data["applicant_type"] = "nonprofit"
        data["applicant_organization"] = None
        is_valid, errors = self.engine.validate_data(data)
        # Should have a validation error for missing org
        assert any("organisation" in e.lower() for e in errors)

    def test_validate_warns_missing_email(self, sample_complete_data):
        data = sample_complete_data.copy()
        data["agency_email"] = None
        is_valid, errors = self.engine.validate_data(data)
        # Still valid, but should warn
        assert is_valid is True
        assert any("WARNING" in e for e in errors)

    def test_get_missing_field_questions_empty_data(self):
        questions = self.engine._get_missing_field_questions({})
        # All 8 required fields should be missing
        assert len(questions) >= 8

    def test_get_missing_field_questions_partial_data(self):
        data = {"agency_name": "DPI", "applicant_name": "Jane"}
        questions = self.engine._get_missing_field_questions(data)
        # Should have fewer questions now (minus 2 answered + conditional for agency_email)
        assert len(questions) < 8 + len(CONDITIONAL_FIELDS)
        # agency_name question should NOT be in the list
        assert not any("which government agency" in q.lower() for q in questions)

    def test_conditional_field_triggered_nonprofit(self):
        data = {"agency_name": "DPI", "applicant_type": "nonprofit"}
        questions = self.engine._get_missing_field_questions(data)
        # Should include the organization question
        assert any(
            "organisation" in q.lower() or "organization" in q.lower()
            for q in questions
        )
        # Should include charity question
        assert any("charity" in q.lower() or "abn" in q.lower() for q in questions)

    def test_conditional_field_not_triggered_individual(self):
        data = {"agency_name": "DPI", "applicant_type": "individual"}
        questions = self.engine._get_missing_field_questions(data)
        # Should NOT include the charity question
        assert not any("charity registration" in q.lower() for q in questions)

    def test_build_gipa_request_data(self, sample_complete_data):
        result = self.engine.build_gipa_request_data(sample_complete_data)
        assert isinstance(result, GIPARequestData)
        assert result.agency_name == "Department of Primary Industries"
        assert len(result.targets) == 2
        assert isinstance(result.targets[0], TargetPerson)
        assert result.targets[0].direction == "sender"
        assert result.fee_reduction_eligible is True
        assert "koala" in result.summary_sentence.lower()

    def test_build_gipa_request_data_individual(self, sample_individual_data):
        result = self.engine.build_gipa_request_data(sample_individual_data)
        assert result.fee_reduction_eligible is False
        assert result.jurisdiction == "NSW"

    def test_parse_extraction_response_json_block(self):
        content = '```json\n{"extracted": {"agency_name": "DPI"}, "notes": ""}\n```'
        result = self.engine._parse_extraction_response(content)
        assert result["extracted"]["agency_name"] == "DPI"

    def test_parse_extraction_response_raw_json(self):
        content = '{"extracted": {"applicant_name": "Jane"}, "notes": ""}'
        result = self.engine._parse_extraction_response(content)
        assert result["extracted"]["applicant_name"] == "Jane"

    def test_parse_extraction_response_fallback(self):
        content = "This is not JSON at all"
        result = self.engine._parse_extraction_response(content)
        assert result["extracted"] == {}


# ============================================================================
# 4. Synonym Expander Tests
# ============================================================================


class TestSynonymExpander:
    @patch("server.tools.gipa_agent.synonym_expander.ChatGoogleGenerativeAI")
    def setup_method(self, method, mock_llm_class):
        self.mock_llm = MagicMock()
        mock_llm_class.return_value = self.mock_llm
        self.expander = SynonymExpander(google_api_key="fake-key")

    def test_parse_expansions_json_array(self):
        content = '["Phascolarctos cinereus", "native bear", "arboreal marsupial"]'
        result = self.expander._parse_expansions(content, "Koala")
        assert len(result) == 3
        assert "Phascolarctos cinereus" in result

    def test_parse_expansions_markdown_json(self):
        content = '```json\n["wild dog", "Canis lupus dingo"]\n```'
        result = self.expander._parse_expansions(content, "Dingo")
        assert len(result) == 2
        assert "wild dog" in result

    def test_parse_expansions_excludes_original_keyword(self):
        content = '["Koala", "native bear", "marsupial"]'
        result = self.expander._parse_expansions(content, "Koala")
        assert "Koala" not in result
        assert len(result) == 2

    def test_parse_expansions_fallback_comma_split(self):
        content = "wild dog, native canid, dingo management"
        result = self.expander._parse_expansions(content, "Dingo")
        assert len(result) >= 2

    def test_parse_expansions_caps_at_12(self):
        terms = [f"term{i}" for i in range(20)]
        content = ", ".join(terms)
        result = self.expander._parse_expansions(content, "something")
        assert len(result) <= 12

    @pytest.mark.asyncio
    async def test_expand_keyword_caching(self):
        # Set up the mock to return a response
        mock_response = MagicMock()
        mock_response.content = '["native bear", "marsupial"]'
        self.mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        # First call should invoke LLM
        result1 = await self.expander.expand_keyword("Koala")
        assert "native bear" in result1
        assert self.mock_llm.ainvoke.call_count == 1

        # Second call should hit cache
        result2 = await self.expander.expand_keyword("Koala")
        assert result2 == result1
        assert self.mock_llm.ainvoke.call_count == 1  # Not called again

    @pytest.mark.asyncio
    async def test_expand_keyword_case_insensitive_cache(self):
        mock_response = MagicMock()
        mock_response.content = '["marsupial"]'
        self.mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        await self.expander.expand_keyword("koala")
        await self.expander.expand_keyword("KOALA")
        assert self.mock_llm.ainvoke.call_count == 1

    def test_clear_cache(self):
        self.expander._cache["test"] = "cached value"
        self.expander.clear_cache()
        assert len(self.expander._cache) == 0

    @pytest.mark.asyncio
    async def test_expand_keyword_llm_error_fallback(self):
        self.mock_llm.ainvoke = AsyncMock(side_effect=Exception("API error"))
        result = await self.expander.expand_keyword("Dingo")
        assert 'Define "Dingo"' in result
        assert "abbreviations" in result  # fallback text

    @pytest.mark.asyncio
    async def test_expand_keywords_multiple(self):
        call_count = 0

        async def mock_invoke(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            response.content = f'["term{call_count}a", "term{call_count}b"]'
            return response

        self.mock_llm.ainvoke = mock_invoke
        results = await self.expander.expand_keywords(["koala", "dingo"])
        assert len(results) == 2
        assert 'Define "koala"' in results[0]
        assert 'Define "dingo"' in results[1]


# ============================================================================
# 5. Document Generator Tests
# ============================================================================


class TestDocumentGenerator:
    def setup_method(self, method):
        self.generator = GIPADocumentGenerator(synonym_expander=None)

    def _make_gipa_data(self, **overrides) -> GIPARequestData:
        """Helper to create GIPARequestData with defaults."""
        defaults = {
            "agency_name": "Department of Primary Industries",
            "applicant_name": "Jane Doe",
            "applicant_type": "individual",
            "public_interest_justification": "Environmental transparency",
            "start_date": "1 January 2023",
            "end_date": "31 December 2024",
            "keywords": ["koala", "habitat"],
            "jurisdiction": "NSW",
        }
        defaults.update(overrides)
        return GIPARequestData(**defaults)

    def test_format_target_sender(self):
        t = TargetPerson(name="John", role="Director", direction="sender")
        result = self.generator._format_target(t)
        assert "from" in result
        assert "John" in result
        assert "Director" in result

    def test_format_target_receiver(self):
        t = TargetPerson(name="Mary", direction="receiver")
        result = self.generator._format_target(t)
        assert "to" in result

    def test_format_target_both(self):
        t = TargetPerson(name="Jane", direction="both")
        result = self.generator._format_target(t)
        assert "involving" in result

    def test_generate_summary_with_targets(self):
        data = self._make_gipa_data(
            targets=[TargetPerson(name="John Smith", direction="both")],
        )
        result = self.generator._generate_summary(data)
        assert "John Smith" in result
        assert "koala" in result

    def test_generate_summary_without_targets(self):
        data = self._make_gipa_data()
        result = self.generator._generate_summary(data)
        assert "Department of Primary Industries" in result
        assert "koala" in result

    @pytest.mark.asyncio
    async def test_generate_individual_no_fee_section(self):
        data = self._make_gipa_data(applicant_type="individual")
        doc = await self.generator.generate(data, NSW_CONFIG)
        assert "## Fee Reduction Request" not in doc

    @pytest.mark.asyncio
    async def test_generate_nonprofit_has_fee_section(self):
        data = self._make_gipa_data(
            applicant_type="nonprofit",
            fee_reduction_eligible=True,
            applicant_organization="EDO",
        )
        doc = await self.generator.generate(data, NSW_CONFIG)
        assert "## Fee Reduction Request" in doc
        assert "s.127" in doc

    @pytest.mark.asyncio
    async def test_generate_contains_all_sections(self):
        data = self._make_gipa_data()
        doc = await self.generator.generate(data, NSW_CONFIG)

        # Header section
        assert "Department of Primary Industries" in doc
        assert "GIPA Act" in doc
        assert "Jane Doe" in doc

        # Search terms
        assert "## Search Terms" in doc
        assert "1 January 2023" in doc
        assert "31 December 2024" in doc

        # Keywords
        assert "koala" in doc
        assert "habitat" in doc

        # Scope & Definitions
        assert "## Scope and Definitions" in doc

        # Closing
        assert "Yours faithfully" in doc
        assert "**Jane Doe**" in doc

    @pytest.mark.asyncio
    async def test_generate_single_keyword(self):
        data = self._make_gipa_data(keywords=["water licence"])
        doc = await self.generator.generate(data, NSW_CONFIG)
        assert '"water licence"' in doc
        assert "AND" not in doc  # Single keyword, no AND

    @pytest.mark.asyncio
    async def test_generate_multiple_keywords_boolean_and(self):
        data = self._make_gipa_data(keywords=["koala", "habitat", "conservation"])
        doc = await self.generator.generate(data, NSW_CONFIG)
        assert "AND" in doc

    @pytest.mark.asyncio
    async def test_generate_no_targets_uses_all_staff(self):
        data = self._make_gipa_data(targets=[])
        doc = await self.generator.generate(data, NSW_CONFIG)
        assert "All officers and staff" in doc

    @pytest.mark.asyncio
    async def test_generate_with_targets(self):
        data = self._make_gipa_data(
            targets=[
                TargetPerson(
                    name="John Smith", role="Director of Policy", direction="sender"
                ),
                TargetPerson(name="Mary Jones", direction="receiver"),
            ],
        )
        doc = await self.generator.generate(data, NSW_CONFIG)
        assert "John Smith" in doc
        assert "Director of Policy" in doc
        assert "Mary Jones" in doc

    @pytest.mark.asyncio
    async def test_generate_missing_agency_email(self):
        data = self._make_gipa_data(agency_email=None)
        doc = await self.generator.generate(data, NSW_CONFIG)
        assert "to be confirmed" in doc.lower()

    @pytest.mark.asyncio
    async def test_generate_with_agency_email(self):
        data = self._make_gipa_data(agency_email="gipa@dpi.nsw.gov.au")
        doc = await self.generator.generate(data, NSW_CONFIG)
        assert "gipa@dpi.nsw.gov.au" in doc

    @pytest.mark.asyncio
    async def test_generate_with_organization(self):
        data = self._make_gipa_data(
            applicant_organization="EDO",
        )
        doc = await self.generator.generate(data, NSW_CONFIG)
        assert "on behalf of EDO" in doc

    @pytest.mark.asyncio
    async def test_generate_federal_jurisdiction(self):
        data = self._make_gipa_data(jurisdiction="Federal")
        doc = await self.generator.generate(data, FEDERAL_CONFIG)
        assert "FOI Act" in doc

    @pytest.mark.asyncio
    async def test_generate_fallback_keyword_definitions(self):
        """Without a SynonymExpander, should use basic fallback definitions."""
        data = self._make_gipa_data(keywords=["koala"])
        doc = await self.generator.generate(data, NSW_CONFIG)
        assert 'Define "koala"' in doc
        assert "abbreviations" in doc  # fallback text

    @pytest.mark.asyncio
    async def test_generate_with_synonym_expander(self):
        """With a mock SynonymExpander, should use AI-expanded definitions."""
        mock_expander = MagicMock()
        mock_expander.expand_keywords = AsyncMock(
            return_value=[
                'Define "koala" to include: Phascolarctos cinereus, native bear.'
            ]
        )
        generator = GIPADocumentGenerator(synonym_expander=mock_expander)
        data = self._make_gipa_data(keywords=["koala"])
        doc = await generator.generate(data, NSW_CONFIG)
        assert "Phascolarctos cinereus" in doc


# ============================================================================
# 6. Session Management Tests
# ============================================================================


class TestSessionManagement:
    def test_get_or_create_session_new(self):
        session = _get_or_create_session("test-1")
        assert session["status"] == "collecting"
        assert session["data"] == {}
        assert session["document"] is None

    def test_get_or_create_session_existing(self):
        session1 = _get_or_create_session("test-2")
        session1["data"]["agency_name"] = "DPI"
        session2 = _get_or_create_session("test-2")
        assert session2["data"]["agency_name"] == "DPI"

    def test_clear_session(self):
        _get_or_create_session("test-3")
        assert "test-3" in _gipa_sessions
        _clear_session("test-3")
        assert "test-3" not in _gipa_sessions

    def test_clear_nonexistent_session(self):
        # Should not raise
        _clear_session("nonexistent")


# ============================================================================
# 7. GIPARequestAgent Orchestrator Tests
# ============================================================================


class TestGIPARequestAgent:
    @patch("server.tools.gipa_agent.gipa_agent.SynonymExpander")
    @patch("server.tools.gipa_agent.gipa_agent.ClarificationEngine")
    def setup_method(self, method, mock_engine_cls, mock_expander_cls):
        self.mock_engine = MagicMock()
        self.mock_expander = MagicMock()
        mock_engine_cls.return_value = self.mock_engine
        mock_expander_cls.return_value = self.mock_expander
        self.agent = GIPARequestAgent(google_api_key="fake-key")

    @pytest.mark.asyncio
    async def test_start_request(self):
        result = await self.agent.start_request("sess-1")
        assert "GIPA" in result
        assert "government" in result.lower() or "Government" in result
        session = _gipa_sessions["sess-1"]
        assert session["status"] == "collecting"

    @pytest.mark.asyncio
    async def test_process_answer_extracts_and_asks_next(self):
        await self.agent.start_request("sess-2")

        self.mock_engine.extract_variables = AsyncMock(
            return_value=(
                {"agency_name": "DPI"},
                ["What is your full name?", "What type of applicant?"],
                False,
            )
        )

        result = await self.agent.process_answer("sess-2", "DPI please")
        assert "full name" in result.lower()
        assert "1 more question" in result.lower()

    @pytest.mark.asyncio
    async def test_process_answer_complete_returns_summary(self, sample_complete_data):
        await self.agent.start_request("sess-3")

        self.mock_engine.extract_variables = AsyncMock(
            return_value=(sample_complete_data, [], True)
        )

        result = await self.agent.process_answer("sess-3", "all data")
        assert "summary" in result.lower() or "correct" in result.lower()
        assert _gipa_sessions["sess-3"]["status"] == "ready"

    @pytest.mark.asyncio
    async def test_process_answer_already_generated(self):
        _get_or_create_session("sess-4")
        _gipa_sessions["sess-4"]["status"] = "generated"

        result = await self.agent.process_answer("sess-4", "more info")
        assert "already been generated" in result

    @pytest.mark.asyncio
    async def test_generate_document_not_ready(self):
        _get_or_create_session("sess-5")
        _gipa_sessions["sess-5"]["data"] = {}

        self.mock_engine.validate_data.return_value = (
            False,
            ["Missing required field: agency_name"],
        )

        result = await self.agent.generate_document("sess-5")
        assert "Cannot generate" in result
        assert "agency_name" in result


# ============================================================================
# 8. Tool Exports Tests
# ============================================================================


class TestToolExports:
    def test_get_gipa_tools_returns_five(self):
        tools = get_gipa_tools()
        assert len(tools) == 5

    def test_tool_names(self):
        tools = get_gipa_tools()
        names = {t.name for t in tools}
        assert names == {
            "gipa_check_status",
            "gipa_start_request",
            "gipa_process_answer",
            "gipa_generate_document",
            "gipa_expand_keywords",
        }

    def test_tools_have_descriptions(self):
        tools = get_gipa_tools()
        for t in tools:
            assert t.description and len(t.description) > 20


# ============================================================================
# 8b. Check Status Tool Tests
# ============================================================================


class TestCheckStatusTool:
    """Tests for gipa_check_status tool."""

    def setup_method(self):
        _gipa_sessions.clear()

    @pytest.mark.asyncio
    async def test_no_session_returns_no_active(self):
        result = await gipa_check_status.ainvoke({"session_id": "nonexistent"})
        assert "No active GIPA session" in result

    @pytest.mark.asyncio
    async def test_collecting_session(self):
        _gipa_sessions["s1"] = {
            "data": {"agency_name": "DPI"},
            "context": "",
            "status": "collecting",
            "document": None,
        }
        result = await gipa_check_status.ainvoke({"session_id": "s1"})
        assert "COLLECTING" in result
        assert "agency_name" in result

    @pytest.mark.asyncio
    async def test_ready_session(self):
        _gipa_sessions["s2"] = {
            "data": {
                "agency_name": "DPI",
                "applicant_name": "Jane",
                "keywords": ["koala", "habitat"],
            },
            "context": "",
            "status": "ready",
            "document": None,
        }
        result = await gipa_check_status.ainvoke({"session_id": "s2"})
        assert "READY" in result
        assert "gipa_generate_document" in result
        assert "DPI" in result
        assert "Jane" in result
        assert "koala" in result

    @pytest.mark.asyncio
    async def test_generated_session(self):
        _gipa_sessions["s3"] = {
            "data": {},
            "context": "",
            "status": "generated",
            "document": "# GIPA Application\nFull document here...",
        }
        result = await gipa_check_status.ainvoke({"session_id": "s3"})
        assert "GENERATED" in result
        assert "GIPA Application" in result

    @pytest.mark.asyncio
    async def test_collecting_no_fields(self):
        _gipa_sessions["s4"] = {
            "data": {},
            "context": "",
            "status": "collecting",
            "document": None,
        }
        result = await gipa_check_status.ainvoke({"session_id": "s4"})
        assert "COLLECTING" in result
        assert "none" in result


# ============================================================================
# 9. Confirmation Summary Tests
# ============================================================================


class TestConfirmationSummary:
    @patch("server.tools.gipa_agent.gipa_agent.SynonymExpander")
    @patch("server.tools.gipa_agent.gipa_agent.ClarificationEngine")
    def setup_method(self, method, mock_engine_cls, mock_expander_cls):
        mock_engine_cls.return_value = MagicMock()
        mock_expander_cls.return_value = MagicMock()
        self.agent = GIPARequestAgent(google_api_key="fake-key")

    def test_summary_contains_all_fields(self, sample_complete_data):
        result = self.agent._build_confirmation_summary(sample_complete_data)
        assert "Department of Primary Industries" in result
        assert "gipa@dpi.nsw.gov.au" in result
        assert "Jane Doe" in result
        assert "Environment Defenders Office" in result
        assert "nonprofit" in result
        assert "50%" in result or "Fee Reduction" in result
        assert "1 January 2023" in result
        assert "31 December 2024" in result
        assert "John Smith" in result
        assert "koala" in result

    def test_summary_missing_email_warns(self, sample_complete_data):
        data = sample_complete_data.copy()
        data["agency_email"] = None
        result = self.agent._build_confirmation_summary(data)
        assert "Not provided" in result or "find this" in result

    def test_summary_individual_no_fee_line(self, sample_individual_data):
        result = self.agent._build_confirmation_summary(sample_individual_data)
        assert "50%" not in result


# ============================================================================
# 10. Edge Cases
# ============================================================================


class TestEdgeCases:
    def test_jurisdiction_config_all_have_platforms(self):
        for config in [NSW_CONFIG, FEDERAL_CONFIG, VIC_CONFIG]:
            assert len(config.correspondence_platforms) >= 4
            assert "email" in config.correspondence_platforms

    def test_required_fields_cover_gipa_data_essentials(self):
        required_field_names = {f["field"] for f in REQUIRED_FIELDS}
        essentials = {
            "agency_name",
            "applicant_name",
            "applicant_type",
            "public_interest_justification",
            "start_date",
            "end_date",
            "targets",
            "keywords",
        }
        assert essentials == required_field_names

    @pytest.mark.asyncio
    async def test_document_generator_derives_jurisdiction_from_data(self):
        """When config is None, generator should derive it from data.jurisdiction."""
        gen = GIPADocumentGenerator(synonym_expander=None)
        data = GIPARequestData(
            agency_name="Test Agency",
            applicant_name="Test Person",
            public_interest_justification="Test",
            start_date="1 Jan 2024",
            end_date="31 Dec 2024",
            keywords=["test"],
            jurisdiction="Federal",
        )
        doc = await gen.generate(data, config=None)
        assert "FOI Act" in doc

    def test_target_person_json_roundtrip(self):
        t = TargetPerson(name="John", role="Director", direction="sender")
        json_str = t.model_dump_json()
        t2 = TargetPerson.model_validate_json(json_str)
        assert t2.name == t.name
        assert t2.role == t.role
        assert t2.direction == t.direction

    def test_gipa_request_data_json_roundtrip(self):
        data = GIPARequestData(
            agency_name="Test",
            applicant_name="Test",
            public_interest_justification="Test",
            start_date="1 Jan 2024",
            end_date="31 Dec 2024",
            keywords=["test"],
            targets=[TargetPerson(name="A", direction="both")],
        )
        json_str = data.model_dump_json()
        data2 = GIPARequestData.model_validate_json(json_str)
        assert data2.agency_name == data.agency_name
        assert len(data2.targets) == 1
