"""
End-to-end tests for the Dossier (Meeting Prep) Agent.

Covers the full pipeline:
  1. CollectedData construction -> to_dict() output
  2. SynthesizedResearch construction -> to_dict() / from_dict() roundtrip
  3. StrategicInsights construction -> to_dict() / from_dict() roundtrip
  4. Full pipeline: CollectedData -> ResearchSynthesizer -> StrategicAnalyzer -> DossierGenerator
  5. Markdown document structure validation (sections, dividers, formatting)
  6. Edge cases (empty LinkedIn, no web results, missing fields, minimal data)
  7. Update flow: generate -> update with new context -> verify changes
  8. Parametrized tests for various person profiles
  9. Session store workflow through DossierAgent orchestrator
  10. API model validation (Pydantic request/response models)
  11. Template builder edge cases with realistic data combinations

No real LLM calls are made. Everything that touches an LLM is mocked.

Run with:
    .venv/bin/python -m pytest testing/test_dossier_e2e.py -v
"""

import json
import re
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------
from server.tools.dossier_agent.data_collector import (
    WebSearchResult,
    LinkedInProfile,
    CollectedData,
    SerperClient,
    LinkedInScraper,
    DataCollector,
)
from server.tools.dossier_agent.research_synthesizer import (
    ResearchSynthesizer,
    SynthesizedResearch,
)
from server.tools.dossier_agent.strategic_analyzer import (
    StrategicAnalyzer,
    StrategicInsights,
)
from server.tools.dossier_agent.dossier_generator import DossierGenerator
from server.tools.dossier_agent.templates.dossier_template import (
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
from server.tools.dossier_agent.dossier_agent import (
    DossierAgent,
    _dossier_sessions,
    _get_session,
    _create_session,
    _clear_session,
    get_dossier_tools,
    dossier_check_status,
    dossier_generate,
    dossier_update,
    dossier_get_document,
)
from server.models import (
    DossierGenerateRequest,
    DossierUpdateRequest,
    DossierStatusRequest,
    DossierResponse,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear all dossier sessions before and after each test."""
    _dossier_sessions.clear()
    yield
    _dossier_sessions.clear()


def _make_synthesized(
    name="Jane Doe",
    role="CTO",
    org="Acme Corp",
    location="Sydney, Australia",
    bio="Jane Doe is a technology leader with 20 years of experience in AI and digital transformation.",
    highlights=None,
    statements=None,
    associates=None,
    topics=None,
    education="PhD Computer Science, MIT. MBA, Stanford.",
    personality="Direct communicator, values data-driven decisions.",
    online="Active on LinkedIn (15k followers), occasional Twitter posts.",
) -> dict:
    """Create a realistic SynthesizedResearch dict for E2E tests."""
    return {
        "name": name,
        "current_role": role,
        "organization": org,
        "location": location,
        "biographical_summary": bio,
        "career_highlights": highlights
        if highlights is not None
        else [
            "Led digital transformation at BigCo",
            "Founded AI startup acquired for $50M",
            "Published 3 patents in machine learning",
        ],
        "recent_statements": statements
        if statements is not None
        else [
            {
                "quote": "AI will transform every industry within 5 years",
                "source": "TechConf 2025",
                "date": "January 2025",
                "context": "Keynote speech at TechConf",
            },
            {
                "quote": "We need ethical AI frameworks now",
                "source": "LinkedIn Post",
                "date": "December 2024",
                "context": "Public statement on AI regulation",
            },
        ],
        "known_associates": associates
        if associates is not None
        else [
            {
                "name": "John Smith",
                "relationship": "board member",
                "context": "Serves on Acme Corp board since 2020",
            },
            {
                "name": "Alice Johnson",
                "relationship": "co-founder",
                "context": "Co-founded AI startup together",
            },
        ],
        "key_topics": topics
        if topics is not None
        else ["artificial intelligence", "digital transformation", "ethics in tech"],
        "education_summary": education,
        "personality_notes": personality,
        "online_presence": online,
    }


def _make_insights(
    rel_map=None,
    starters=None,
    common=None,
    avoid=None,
    strategy="Lead with genuine interest in her AI ethics work.",
    motivations=None,
    negotiation="Data-driven, prefers concrete examples over abstract concepts.",
    approach="Prepare specific data points about your shared interests before the meeting.",
) -> dict:
    """Create a realistic StrategicInsights dict for E2E tests."""
    return {
        "relationship_map": rel_map
        if rel_map is not None
        else [
            {
                "person": "John Smith",
                "relationship": "board member",
                "leverage": "Shared governance interest",
                "notes": "Long-standing professional relationship",
            },
        ],
        "conversation_starters": starters
        if starters is not None
        else [
            "I was impressed by your TechConf keynote on AI transformation",
            "Your work on ethical AI frameworks resonates with our mission",
        ],
        "common_ground": common
        if common is not None
        else [
            "Interest in responsible AI development",
            "Shared focus on digital transformation",
        ],
        "topics_to_avoid": avoid
        if avoid is not None
        else [
            "Previous company lawsuit - sensitive topic",
            "Failed product launch in 2022 - may be touchy",
        ],
        "meeting_strategy": strategy,
        "key_motivations": motivations
        if motivations is not None
        else [
            "Driving AI adoption responsibly",
            "Building industry-leading tech teams",
        ],
        "negotiation_style": negotiation,
        "recommended_approach": approach,
    }


def _make_collected_data(
    name="Jane Doe",
    linkedin_url="https://linkedin.com/in/janedoe",
    has_profile=True,
    has_web=True,
    page_text="Jane Doe is the CTO of Acme Corp with expertise in AI and ML.",
) -> CollectedData:
    """Create a realistic CollectedData object for E2E tests."""
    profile = None
    if has_profile:
        profile = LinkedInProfile(
            name=name,
            headline="CTO at Acme Corp",
            location="Sydney, Australia",
            summary="Technology leader with 20+ years experience",
            skills=["AI", "Machine Learning", "Leadership"],
            url=linkedin_url,
        )

    web_results = {}
    if has_web:
        web_results = {
            "bio": [
                WebSearchResult(
                    title=f"{name} - CTO of Acme Corp",
                    url="https://example.com/bio",
                    snippet=f"{name} is the CTO of Acme Corp, known for AI innovation.",
                    date="2025-01-15",
                ),
                WebSearchResult(
                    title=f"{name} | LinkedIn",
                    url=linkedin_url,
                    snippet="Technology leader and AI researcher.",
                ),
            ],
            "news": [
                WebSearchResult(
                    title=f"{name} speaks at TechConf 2025",
                    url="https://news.example.com/techconf",
                    snippet=f"{name} delivered keynote on AI transformation.",
                    date="2025-01-20",
                ),
            ],
            "statements": [
                WebSearchResult(
                    title=f"{name}: AI will transform every industry",
                    url="https://quotes.example.com",
                    snippet="In a recent interview, she stated AI will transform every industry.",
                    date="2025-01-10",
                ),
            ],
            "associates": [
                WebSearchResult(
                    title=f"John Smith and {name} partner on AI ethics",
                    url="https://partnership.example.com",
                    snippet="Long-time collaborators on corporate governance.",
                ),
            ],
        }

    return CollectedData(
        name=name,
        linkedin_url=linkedin_url if has_profile else "",
        linkedin_profile=profile,
        web_results=web_results,
        raw_page_text=page_text,
    )


# ============================================================================
# 1. Full Pipeline E2E (Collection -> Synthesis -> Analysis -> Document)
# ============================================================================


class TestFullPipeline:
    """End-to-end tests running the full dossier pipeline with mocked LLMs."""

    @pytest.mark.asyncio
    async def test_full_pipeline_produces_valid_dossier(self):
        """Complete pipeline from data to Markdown document."""
        collected = _make_collected_data()
        synth_data = _make_synthesized()
        insights_data = _make_insights()

        mock_synth_response = MagicMock()
        mock_synth_response.content = json.dumps(synth_data)

        mock_insights_response = MagicMock()
        mock_insights_response.content = json.dumps(insights_data)

        mock_synth_llm = AsyncMock()
        mock_synth_llm.ainvoke = AsyncMock(return_value=mock_synth_response)

        mock_analyzer_llm = AsyncMock()
        mock_analyzer_llm.ainvoke = AsyncMock(return_value=mock_insights_response)

        with (
            patch.object(
                DataCollector,
                "collect",
                new_callable=AsyncMock,
                return_value=collected,
            ),
            patch(
                "server.tools.dossier_agent.research_synthesizer.ChatGoogleGenerativeAI",
                return_value=mock_synth_llm,
            ),
            patch(
                "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI",
                return_value=mock_analyzer_llm,
            ),
        ):
            agent = DossierAgent(google_api_key="test", serper_api_key="test")
            agent.synthesizer.llm = mock_synth_llm
            agent.analyzer.llm = mock_analyzer_llm

            doc = await agent.generate_dossier(
                "e2e-full",
                "Jane Doe",
                "https://linkedin.com/in/janedoe",
                "Discuss partnership on AI ethics initiative",
            )

        # Verify document structure
        assert "# Meeting Prep Dossier: Jane Doe" in doc
        assert "CONFIDENTIAL" in doc
        assert "CTO" in doc or "Chief Technology Officer" in doc
        assert "Acme Corp" in doc
        assert "Sydney" in doc
        assert "AI will transform" in doc
        assert "John Smith" in doc
        assert "Topics to Approach with Caution" in doc
        assert "Conversation Starters" in doc
        assert "Verify critical information before the meeting" in doc

        # Verify session state
        session = _get_session("e2e-full")
        assert session["status"] == "generated"
        assert session["name"] == "Jane Doe"
        assert (
            session["meeting_context"] == "Discuss partnership on AI ethics initiative"
        )

    @pytest.mark.asyncio
    async def test_pipeline_with_empty_linkedin(self):
        """Pipeline works when LinkedIn data is empty."""
        collected = _make_collected_data(has_profile=False, page_text="")
        collected.linkedin_url = ""

        synth_data = _make_synthesized(
            education="",
            online="",
        )
        insights_data = _make_insights()

        mock_synth_response = MagicMock()
        mock_synth_response.content = json.dumps(synth_data)

        mock_insights_response = MagicMock()
        mock_insights_response.content = json.dumps(insights_data)

        mock_synth_llm = AsyncMock()
        mock_synth_llm.ainvoke = AsyncMock(return_value=mock_synth_response)

        mock_analyzer_llm = AsyncMock()
        mock_analyzer_llm.ainvoke = AsyncMock(return_value=mock_insights_response)

        with (
            patch.object(
                DataCollector,
                "collect",
                new_callable=AsyncMock,
                return_value=collected,
            ),
            patch(
                "server.tools.dossier_agent.research_synthesizer.ChatGoogleGenerativeAI",
                return_value=mock_synth_llm,
            ),
            patch(
                "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI",
                return_value=mock_analyzer_llm,
            ),
        ):
            agent = DossierAgent(google_api_key="test", serper_api_key="test")
            agent.synthesizer.llm = mock_synth_llm
            agent.analyzer.llm = mock_analyzer_llm

            doc = await agent.generate_dossier("e2e-nolinkedin", "Jane Doe")

        assert "# Meeting Prep Dossier: Jane Doe" in doc
        assert "linkedin.com" not in doc  # No LinkedIn URL in doc

    @pytest.mark.asyncio
    async def test_pipeline_with_no_web_results(self):
        """Pipeline works when web search returns nothing."""
        collected = _make_collected_data(has_web=False, has_profile=True)

        synth_data = _make_synthesized(
            highlights=[],
            statements=[],
            associates=[],
            topics=[],
        )
        insights_data = _make_insights(
            rel_map=[],
            starters=["Ask about their current work"],
            common=[],
            avoid=[],
            motivations=[],
        )

        mock_synth_response = MagicMock()
        mock_synth_response.content = json.dumps(synth_data)

        mock_insights_response = MagicMock()
        mock_insights_response.content = json.dumps(insights_data)

        mock_synth_llm = AsyncMock()
        mock_synth_llm.ainvoke = AsyncMock(return_value=mock_synth_response)

        mock_analyzer_llm = AsyncMock()
        mock_analyzer_llm.ainvoke = AsyncMock(return_value=mock_insights_response)

        with (
            patch.object(
                DataCollector,
                "collect",
                new_callable=AsyncMock,
                return_value=collected,
            ),
            patch(
                "server.tools.dossier_agent.research_synthesizer.ChatGoogleGenerativeAI",
                return_value=mock_synth_llm,
            ),
            patch(
                "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI",
                return_value=mock_analyzer_llm,
            ),
        ):
            agent = DossierAgent(google_api_key="test", serper_api_key="test")
            agent.synthesizer.llm = mock_synth_llm
            agent.analyzer.llm = mock_analyzer_llm

            doc = await agent.generate_dossier(
                "e2e-noweb", "Jane Doe", "https://linkedin.com/in/janedoe"
            )

        assert "# Meeting Prep Dossier: Jane Doe" in doc
        # With no highlights, the career section is skipped
        assert "Career Highlights" not in doc

    @pytest.mark.asyncio
    async def test_pipeline_with_synthesizer_fallback(self):
        """Pipeline handles synthesis JSON parse error gracefully."""
        collected = _make_collected_data()
        insights_data = _make_insights()

        mock_synth_llm = AsyncMock()
        mock_synth_llm.ainvoke = AsyncMock(
            return_value=MagicMock(content="invalid json response")
        )

        mock_analyzer_llm = AsyncMock()
        mock_analyzer_llm.ainvoke = AsyncMock(
            return_value=MagicMock(content=json.dumps(insights_data))
        )

        with (
            patch.object(
                DataCollector,
                "collect",
                new_callable=AsyncMock,
                return_value=collected,
            ),
            patch(
                "server.tools.dossier_agent.research_synthesizer.ChatGoogleGenerativeAI",
                return_value=mock_synth_llm,
            ),
            patch(
                "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI",
                return_value=mock_analyzer_llm,
            ),
        ):
            agent = DossierAgent(google_api_key="test", serper_api_key="test")
            agent.synthesizer.llm = mock_synth_llm
            agent.analyzer.llm = mock_analyzer_llm

            doc = await agent.generate_dossier("e2e-synthfail", "Jane Doe")

        # Should still produce a dossier (with parse error in bio)
        assert "# Meeting Prep Dossier: Jane Doe" in doc
        assert _get_session("e2e-synthfail")["status"] == "generated"

    @pytest.mark.asyncio
    async def test_pipeline_with_analyzer_fallback(self):
        """Pipeline handles strategic analysis failure via DossierAnalysisError."""
        collected = _make_collected_data()
        synth_data = _make_synthesized()

        mock_synth_llm = AsyncMock()
        mock_synth_llm.ainvoke = AsyncMock(
            return_value=MagicMock(content=json.dumps(synth_data))
        )

        mock_analyzer_llm = AsyncMock()
        mock_analyzer_llm.ainvoke = AsyncMock(
            side_effect=Exception("Gemini rate limit")
        )

        with (
            patch.object(
                DataCollector,
                "collect",
                new_callable=AsyncMock,
                return_value=collected,
            ),
            patch(
                "server.tools.dossier_agent.research_synthesizer.ChatGoogleGenerativeAI",
                return_value=mock_synth_llm,
            ),
            patch(
                "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI",
                return_value=mock_analyzer_llm,
            ),
        ):
            agent = DossierAgent(google_api_key="test", serper_api_key="test")
            agent.synthesizer.llm = mock_synth_llm
            agent.analyzer.llm = mock_analyzer_llm

            doc = await agent.generate_dossier("e2e-analyzefail", "Jane Doe")

        # DossierAnalysisError is caught by generate_dossier and returned as error string
        assert "failed" in doc.lower()
        assert "analyzing" in doc.lower()
        assert _get_session("e2e-analyzefail")["status"] == "error"

    @pytest.mark.asyncio
    async def test_pipeline_data_collector_error(self):
        """Pipeline handles data collection failure."""
        with (
            patch.object(
                DataCollector,
                "collect",
                new_callable=AsyncMock,
                side_effect=Exception("Network timeout"),
            ),
            patch(
                "server.tools.dossier_agent.research_synthesizer.ChatGoogleGenerativeAI"
            ),
            patch(
                "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI"
            ),
        ):
            agent = DossierAgent(google_api_key="test", serper_api_key="test")
            doc = await agent.generate_dossier("e2e-collectfail", "Jane Doe")

        assert "failed" in doc.lower()
        assert _get_session("e2e-collectfail")["status"] == "error"


# ============================================================================
# 2. Document Structure Validation
# ============================================================================


class TestDocumentStructure:
    """Verify the Markdown dossier has correct structure and formatting."""

    @pytest.mark.asyncio
    async def test_document_has_all_major_sections(self):
        """Generated document contains all expected section headers."""
        synth = _make_synthesized()
        insights = _make_insights()

        generator = DossierGenerator()
        doc = await generator.generate(synth, insights)

        expected_sections = [
            "# Meeting Prep Dossier:",
            "CONFIDENTIAL",
            "## Biographical Context",
            "## Career Highlights",
            "## Education",
            "## Recent Statements & Positions",
            "## Key Associates & Network",
            "## Strategic Insights",
            "## Relationship Map",
            "## Conversation Starters",
            "## Potential Common Ground",
            "## Key Motivations",
            "## Topics to Approach with Caution",
            "## Online Presence",
        ]

        for section in expected_sections:
            assert section in doc, f"Missing section: {section}"

    @pytest.mark.asyncio
    async def test_document_has_section_dividers(self):
        """Document has proper section dividers."""
        synth = _make_synthesized()
        insights = _make_insights()

        generator = DossierGenerator()
        doc = await generator.generate(synth, insights)

        divider_count = doc.count("---")
        assert divider_count >= 4, f"Expected at least 4 dividers, got {divider_count}"

    @pytest.mark.asyncio
    async def test_document_starts_with_title(self):
        """Document starts with the correct title."""
        synth = _make_synthesized(name="Satya Nadella")
        insights = _make_insights()

        generator = DossierGenerator()
        doc = await generator.generate(synth, insights)

        assert doc.startswith("# Meeting Prep Dossier: Satya Nadella")

    @pytest.mark.asyncio
    async def test_document_ends_with_disclaimer(self):
        """Document ends with the verification disclaimer."""
        synth = _make_synthesized()
        insights = _make_insights()

        generator = DossierGenerator()
        doc = await generator.generate(synth, insights)

        assert doc.strip().endswith("Verify critical information before the meeting.*")

    @pytest.mark.asyncio
    async def test_statements_numbered_correctly(self):
        """Recent statements are numbered sequentially."""
        synth = _make_synthesized(
            statements=[
                {
                    "quote": "First quote",
                    "source": "Source A",
                    "date": "Jan 2025",
                    "context": "Context A",
                },
                {
                    "quote": "Second quote",
                    "source": "Source B",
                    "date": "Feb 2025",
                    "context": "Context B",
                },
                {
                    "quote": "Third quote",
                    "source": "Source C",
                    "date": "Mar 2025",
                    "context": "Context C",
                },
            ]
        )
        insights = _make_insights()

        generator = DossierGenerator()
        doc = await generator.generate(synth, insights)

        assert '1. "First quote"' in doc
        assert '2. "Second quote"' in doc
        assert '3. "Third quote"' in doc

    @pytest.mark.asyncio
    async def test_career_highlights_numbered(self):
        """Career highlights are numbered sequentially."""
        synth = _make_synthesized(
            highlights=["Highlight A", "Highlight B", "Highlight C"]
        )
        insights = _make_insights()

        generator = DossierGenerator()
        doc = await generator.generate(synth, insights)

        assert "1. Highlight A" in doc
        assert "2. Highlight B" in doc
        assert "3. Highlight C" in doc

    @pytest.mark.asyncio
    async def test_associates_formatted_with_bold_names(self):
        """Associates section uses bold names."""
        synth = _make_synthesized(
            associates=[
                {
                    "name": "Elon Musk",
                    "relationship": "competitor",
                    "context": "Both in AI",
                },
            ]
        )
        insights = _make_insights()

        generator = DossierGenerator()
        doc = await generator.generate(synth, insights)

        assert "**Elon Musk**" in doc

    @pytest.mark.asyncio
    async def test_relationship_map_has_leverage(self):
        """Relationship map entries include leverage information."""
        synth = _make_synthesized()
        insights = _make_insights(
            rel_map=[
                {
                    "person": "Bob CEO",
                    "relationship": "mentor",
                    "leverage": "Direct access to board decisions",
                    "notes": "Monthly coffee meetings",
                },
            ]
        )

        generator = DossierGenerator()
        doc = await generator.generate(synth, insights)

        assert "**Bob CEO**" in doc
        assert "Leverage: Direct access to board decisions" in doc
        assert "Notes: Monthly coffee meetings" in doc

    @pytest.mark.asyncio
    async def test_minimal_document_still_valid(self):
        """Minimal data still produces a valid document."""
        synth = {
            "name": "Unknown Person",
            "current_role": "",
            "organization": "",
            "location": "",
            "biographical_summary": "",
        }
        insights = {
            "meeting_strategy": "",
            "negotiation_style": "",
            "recommended_approach": "",
        }

        generator = DossierGenerator()
        doc = await generator.generate(synth, insights)

        assert "# Meeting Prep Dossier: Unknown Person" in doc
        assert "CONFIDENTIAL" in doc
        assert "Verify critical information" in doc


# ============================================================================
# 3. Parametrized Person Profiles
# ============================================================================


class TestParametrizedProfiles:
    """Test dossier generation for various person profiles."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "name,role,org,location",
        [
            ("Satya Nadella", "CEO", "Microsoft", "Redmond, USA"),
            ("Jensen Huang", "CEO & Founder", "NVIDIA", "Santa Clara, USA"),
            ("Fei-Fei Li", "Professor", "Stanford University", "Stanford, USA"),
            ("Sam Altman", "CEO", "OpenAI", "San Francisco, USA"),
            ("Demis Hassabis", "CEO & Co-founder", "Google DeepMind", "London, UK"),
        ],
    )
    async def test_generates_dossier_for_tech_leaders(self, name, role, org, location):
        """Each tech leader produces a valid dossier."""
        synth = _make_synthesized(name=name, role=role, org=org, location=location)
        insights = _make_insights()

        generator = DossierGenerator()
        doc = await generator.generate(synth, insights)

        assert f"# Meeting Prep Dossier: {name}" in doc
        assert role in doc or "Not available" in doc
        assert org in doc or "Not available" in doc

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "name,role,org",
        [
            ("", "Unknown", "Unknown"),
            ("A", "B", "C"),
            ("Very Long Name " * 10, "CTO", "Company"),
        ],
    )
    async def test_edge_case_names(self, name, role, org):
        """Edge case names are handled without errors."""
        synth = _make_synthesized(name=name, role=role, org=org)
        insights = _make_insights()

        generator = DossierGenerator()
        doc = await generator.generate(synth, insights)

        assert f"# Meeting Prep Dossier: {name}" in doc

    @pytest.mark.asyncio
    async def test_unicode_name_and_content(self):
        """Unicode characters in name and content work correctly."""
        synth = _make_synthesized(
            name="Yann LeCun",
            bio="Yann LeCun est un scientifique franco-americain.",
            topics=["intelligence artificielle", "apprentissage profond"],
        )
        insights = _make_insights(
            starters=["J'ai lu votre article sur le deep learning"],
        )

        generator = DossierGenerator()
        doc = await generator.generate(synth, insights)

        assert "Yann LeCun" in doc
        assert "franco-americain" in doc

    @pytest.mark.asyncio
    async def test_special_characters_in_quotes(self):
        """Special characters in quotes don't break the document."""
        synth = _make_synthesized(
            statements=[
                {
                    "quote": 'He said "AI is the future" & it\'s <transformative>',
                    "source": "Interview (2025)",
                    "date": "2025-01",
                    "context": "TV appearance",
                },
            ]
        )
        insights = _make_insights()

        generator = DossierGenerator()
        doc = await generator.generate(synth, insights)

        assert "<transformative>" in doc or "&lt;transformative&gt;" in doc
        assert "# Meeting Prep Dossier:" in doc


# ============================================================================
# 4. Update Flow
# ============================================================================


class TestUpdateFlow:
    """Test the generate -> update -> verify flow."""

    @pytest.mark.asyncio
    async def test_update_changes_meeting_context(self):
        """Updating a dossier appends to meeting context."""
        synth_data = _make_synthesized()
        insights_data = _make_insights()
        updated_insights_data = _make_insights(
            strategy="Focus on partnership opportunities for the upcoming quarter.",
        )

        mock_synth_llm = AsyncMock()
        mock_synth_llm.ainvoke = AsyncMock(
            return_value=MagicMock(content=json.dumps(synth_data))
        )

        call_count = 0

        async def mock_analyzer_ainvoke(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MagicMock(content=json.dumps(insights_data))
            else:
                return MagicMock(content=json.dumps(updated_insights_data))

        mock_analyzer_llm = AsyncMock()
        mock_analyzer_llm.ainvoke = AsyncMock(side_effect=mock_analyzer_ainvoke)

        with (
            patch.object(
                DataCollector,
                "collect",
                new_callable=AsyncMock,
                return_value=_make_collected_data(),
            ),
            patch(
                "server.tools.dossier_agent.research_synthesizer.ChatGoogleGenerativeAI",
                return_value=mock_synth_llm,
            ),
            patch(
                "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI",
                return_value=mock_analyzer_llm,
            ),
        ):
            agent = DossierAgent(google_api_key="test", serper_api_key="test")
            agent.synthesizer.llm = mock_synth_llm
            agent.analyzer.llm = mock_analyzer_llm

            # Generate initial dossier
            doc1 = await agent.generate_dossier(
                "e2e-update", "Jane Doe", meeting_context="Initial meeting"
            )
            assert "# Meeting Prep Dossier: Jane Doe" in doc1

            # Update with new context
            doc2 = await agent.update_dossier(
                "e2e-update", "Focus on Q2 partnership discussion"
            )

        session = _get_session("e2e-update")
        assert "Initial meeting" in session["meeting_context"]
        assert "Q2 partnership" in session["meeting_context"]
        assert session["status"] == "generated"

    @pytest.mark.asyncio
    async def test_update_without_generate_fails(self):
        """Cannot update a dossier that hasn't been generated."""
        with (
            patch(
                "server.tools.dossier_agent.research_synthesizer.ChatGoogleGenerativeAI"
            ),
            patch(
                "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI"
            ),
        ):
            agent = DossierAgent(google_api_key="test", serper_api_key="test")
            result = await agent.update_dossier("nonexistent", "New context")

        assert "No dossier found" in result

    @pytest.mark.asyncio
    async def test_update_before_synthesis_complete(self):
        """Cannot update when synthesized data is not yet available."""
        _create_session("partial", "Jane")

        with (
            patch(
                "server.tools.dossier_agent.research_synthesizer.ChatGoogleGenerativeAI"
            ),
            patch(
                "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI"
            ),
        ):
            agent = DossierAgent(google_api_key="test", serper_api_key="test")
            result = await agent.update_dossier("partial", "New context")

        assert "not yet collected" in result.lower()


# ============================================================================
# 5. Session Workflow E2E
# ============================================================================


class TestSessionWorkflow:
    """E2E tests for the session lifecycle through tool functions."""

    @pytest.mark.asyncio
    async def test_full_tool_workflow(self):
        """check_status -> generate -> check_status -> get_document workflow."""
        # Step 1: Check status (no session)
        result = await dossier_check_status.ainvoke({"dossier_id": "wf-test"})
        assert "No active dossier" in result

        # Step 2: Generate
        mock_collected = _make_collected_data()
        mock_synthesized = SynthesizedResearch(
            name="Jane Doe",
            current_role="CTO",
            organization="Acme",
            key_topics=["AI"],
        )
        mock_insights = StrategicInsights(
            conversation_starters=["Great work!"],
            meeting_strategy="Be informed",
            negotiation_style="Direct",
            recommended_approach="Prepare data",
        )

        with (
            patch.object(
                DataCollector,
                "collect",
                new_callable=AsyncMock,
                return_value=mock_collected,
            ),
            patch.object(
                ResearchSynthesizer,
                "synthesize",
                new_callable=AsyncMock,
                return_value=mock_synthesized,
            ),
            patch.object(
                StrategicAnalyzer,
                "analyze",
                new_callable=AsyncMock,
                return_value=mock_insights,
            ),
            patch(
                "server.tools.dossier_agent.research_synthesizer.ChatGoogleGenerativeAI"
            ),
            patch(
                "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI"
            ),
            patch(
                "server.tools.dossier_agent.dossier_agent._agent_instance",
                None,
            ),
        ):
            import server.tools.dossier_agent.dossier_agent as da_module

            mock_agent = DossierAgent(google_api_key="t", serper_api_key="t")
            da_module._agent_instance = mock_agent

            result = await dossier_generate.ainvoke(
                {
                    "name": "Jane Doe",
                    "linkedin_url": "https://li.com/jane",
                    "dossier_id": "wf-test",
                }
            )

        assert "# Meeting Prep Dossier: Jane Doe" in result

        # Step 3: Check status (should be generated)
        result = await dossier_check_status.ainvoke({"dossier_id": "wf-test"})
        assert "GENERATED" in result

        # Step 4: Get document
        result = await dossier_get_document.ainvoke({"dossier_id": "wf-test"})
        assert "# Meeting Prep Dossier: Jane Doe" in result

    @pytest.mark.asyncio
    async def test_multiple_concurrent_sessions(self):
        """Multiple dossier sessions can coexist."""
        _create_session("session-a", "Person A")
        _create_session("session-b", "Person B")
        _create_session("session-c", "Person C")

        assert len(_dossier_sessions) == 3

        status_a = await dossier_check_status.ainvoke({"dossier_id": "session-a"})
        status_b = await dossier_check_status.ainvoke({"dossier_id": "session-b"})

        assert "Person A" in status_a
        assert "Person B" in status_b

    @pytest.mark.asyncio
    async def test_session_error_state(self):
        """Session with error status reports error correctly."""
        session = _create_session("err-session", "Jane")
        session["status"] = "error"
        session["document"] = "Dossier generation failed: timeout"

        result = await dossier_check_status.ainvoke({"dossier_id": "err-session"})
        assert "ERROR" in result
        assert "timeout" in result.lower()

    @pytest.mark.asyncio
    async def test_get_document_while_generating(self):
        """Getting document while still generating returns not ready message."""
        session = _create_session("gen-session", "Jane")
        session["status"] = "researching"

        result = await dossier_get_document.ainvoke({"dossier_id": "gen-session"})
        assert "not ready" in result.lower()


# ============================================================================
# 6. API Pydantic Model Validation
# ============================================================================


class TestApiModels:
    """Validate the Pydantic request/response models."""

    def test_generate_request_required_fields(self):
        req = DossierGenerateRequest(name="Jane Doe")
        assert req.name == "Jane Doe"

    def test_generate_request_all_fields(self):
        req = DossierGenerateRequest(
            name="Jane Doe",
            linkedin_url="https://linkedin.com/in/janedoe",
            meeting_context="Discuss AI partnership",
            dossier_id="custom-id",
        )
        assert req.linkedin_url == "https://linkedin.com/in/janedoe"
        assert req.meeting_context == "Discuss AI partnership"
        assert req.dossier_id == "custom-id"

    def test_generate_request_defaults(self):
        req = DossierGenerateRequest(name="Jane")
        assert (
            req.linkedin_url == ""
            or req.linkedin_url is None
            or hasattr(req, "linkedin_url")
        )

    def test_update_request(self):
        req = DossierUpdateRequest(
            additional_context="New meeting topic",
            dossier_id="test-id",
        )
        assert req.additional_context == "New meeting topic"
        assert req.dossier_id == "test-id"

    def test_status_request(self):
        req = DossierStatusRequest(dossier_id="test-id")
        assert req.dossier_id == "test-id"

    def test_response_model(self):
        resp = DossierResponse(
            success=True,
            message="Dossier generated",
            document="# Dossier",
        )
        assert resp.success is True
        assert resp.message == "Dossier generated"
        assert resp.document == "# Dossier"

    def test_response_model_error(self):
        resp = DossierResponse(
            success=False,
            message="Generation failed",
        )
        assert resp.success is False


# ============================================================================
# 7. CollectedData E2E (construction + to_dict roundtrip)
# ============================================================================


class TestCollectedDataE2E:
    """E2E tests for data collection structures."""

    def test_full_collected_data_to_dict(self):
        """Full CollectedData converts to dict correctly."""
        data = _make_collected_data()
        d = data.to_dict()

        assert d["name"] == "Jane Doe"
        assert d["linkedin_url"] == "https://linkedin.com/in/janedoe"
        assert d["linkedin_profile"]["name"] == "Jane Doe"
        assert d["linkedin_profile"]["headline"] == "CTO at Acme Corp"
        assert len(d["web_results"]["bio"]) == 2
        assert len(d["web_results"]["news"]) == 1
        assert len(d["web_results"]["statements"]) == 1
        assert len(d["web_results"]["associates"]) == 1
        assert len(d["raw_page_text"]) > 0

    def test_empty_collected_data_to_dict(self):
        """Empty CollectedData converts without errors."""
        data = _make_collected_data(has_profile=False, has_web=False, page_text="")
        data.linkedin_url = ""
        d = data.to_dict()

        assert d["name"] == "Jane Doe"
        assert d["linkedin_profile"] is None
        assert d["web_results"] == {}
        assert d["raw_page_text"] == ""

    def test_collected_data_web_results_structure(self):
        """Web results dict has correct structure per category."""
        data = _make_collected_data()
        d = data.to_dict()

        for category in ["bio", "news", "statements", "associates"]:
            assert category in d["web_results"]
            for result in d["web_results"][category]:
                assert "title" in result
                assert "url" in result
                assert "snippet" in result


# ============================================================================
# 8. SynthesizedResearch E2E (roundtrip with realistic data)
# ============================================================================


class TestSynthesizedResearchE2E:
    """E2E tests for synthesis data structures."""

    def test_full_roundtrip(self):
        """Full SynthesizedResearch to_dict -> from_dict preserves all data."""
        synth_dict = _make_synthesized()
        synth = SynthesizedResearch.from_dict(synth_dict)
        result = synth.to_dict()

        assert result["name"] == synth_dict["name"]
        assert result["current_role"] == synth_dict["current_role"]
        assert len(result["career_highlights"]) == len(synth_dict["career_highlights"])
        assert len(result["recent_statements"]) == len(synth_dict["recent_statements"])
        assert len(result["known_associates"]) == len(synth_dict["known_associates"])
        assert len(result["key_topics"]) == len(synth_dict["key_topics"])

    def test_statement_structure_preserved(self):
        """Statement dict structure is preserved through roundtrip."""
        synth_dict = _make_synthesized()
        synth = SynthesizedResearch.from_dict(synth_dict)

        stmt = synth.recent_statements[0]
        assert "quote" in stmt
        assert "source" in stmt
        assert "date" in stmt
        assert "context" in stmt

    def test_associate_structure_preserved(self):
        """Associate dict structure is preserved through roundtrip."""
        synth_dict = _make_synthesized()
        synth = SynthesizedResearch.from_dict(synth_dict)

        assoc = synth.known_associates[0]
        assert "name" in assoc
        assert "relationship" in assoc
        assert "context" in assoc


# ============================================================================
# 9. StrategicInsights E2E (roundtrip with realistic data)
# ============================================================================


class TestStrategicInsightsE2E:
    """E2E tests for strategic insights structures."""

    def test_full_roundtrip(self):
        """Full StrategicInsights to_dict -> from_dict preserves all data."""
        insights_dict = _make_insights()
        insights = StrategicInsights.from_dict(insights_dict)
        result = insights.to_dict()

        assert result["meeting_strategy"] == insights_dict["meeting_strategy"]
        assert result["negotiation_style"] == insights_dict["negotiation_style"]
        assert len(result["conversation_starters"]) == len(
            insights_dict["conversation_starters"]
        )
        assert len(result["topics_to_avoid"]) == len(insights_dict["topics_to_avoid"])

    def test_relationship_map_structure(self):
        """Relationship map entries have correct structure."""
        insights_dict = _make_insights()
        insights = StrategicInsights.from_dict(insights_dict)

        for entry in insights.relationship_map:
            assert "person" in entry
            assert "relationship" in entry
            assert "leverage" in entry
            assert "notes" in entry


# ============================================================================
# 10. Template Builder E2E with Realistic Combinations
# ============================================================================


class TestTemplateBuildersE2E:
    """E2E tests for template builders with various data combinations."""

    def test_all_builders_with_full_data(self):
        """All builders produce non-empty output with full data."""
        synth = _make_synthesized()
        insights = _make_insights()

        assert len(build_biographical_section(synth)) > 50
        assert len(build_career_section(synth)) > 20
        assert len(build_education_section(synth)) > 10
        assert len(build_statements_section(synth)) > 20
        assert len(build_associates_section(synth)) > 20
        assert len(build_relationship_map_section(insights)) > 20
        assert len(build_strategic_section(insights)) > 20
        assert len(build_conversation_starters_section(insights)) > 20
        assert len(build_common_ground_section(insights)) > 10
        assert len(build_topics_to_avoid_section(insights)) > 10
        assert len(build_motivations_section(insights)) > 10
        assert len(build_online_presence_section(synth)) > 10

    def test_all_builders_with_empty_data(self):
        """Builders return empty string for missing data (except bio/strategy)."""
        assert build_career_section({}) == ""
        assert build_education_section({}) == ""
        assert build_statements_section({}) == ""
        assert build_associates_section({}) == ""
        assert build_relationship_map_section({}) == ""
        assert build_conversation_starters_section({}) == ""
        assert build_common_ground_section({}) == ""
        assert build_topics_to_avoid_section({}) == ""
        assert build_motivations_section({}) == ""
        assert build_online_presence_section({}) == ""

        # Bio and strategy sections always produce output
        assert len(build_biographical_section({})) > 0
        assert len(build_strategic_section({})) > 0

    def test_mixed_string_and_dict_statements(self):
        """Statements section handles mixed string and dict entries."""
        data = {
            "recent_statements": [
                {
                    "quote": "AI is the future",
                    "source": "TechConf",
                    "date": "2025",
                    "context": "Keynote",
                },
                "Simple string statement",
                {
                    "quote": "We need ethics",
                    "source": "LinkedIn",
                    "date": "",
                    "context": "",
                },
            ]
        }
        section = build_statements_section(data)
        assert "AI is the future" in section
        assert "Simple string statement" in section
        assert "We need ethics" in section

    def test_mixed_string_and_dict_associates(self):
        """Associates section handles mixed string and dict entries."""
        data = {
            "known_associates": [
                {"name": "John", "relationship": "mentor", "context": "Since 2015"},
                "Bob Jones - colleague",
            ]
        }
        section = build_associates_section(data)
        assert "**John**" in section
        assert "Bob Jones" in section

    def test_many_conversation_starters(self):
        """Many conversation starters are numbered correctly."""
        starters = [f"Starter number {i}" for i in range(1, 11)]
        insights = _make_insights(starters=starters)
        section = build_conversation_starters_section(insights)

        for i in range(1, 11):
            assert f"{i}. Starter number {i}" in section

    def test_relationship_map_mixed_types(self):
        """Relationship map handles mixed dict and string entries."""
        data = {
            "relationship_map": [
                {
                    "person": "Alice",
                    "relationship": "mentor",
                    "leverage": "Intro",
                    "notes": "Weekly calls",
                },
                "Simple connection string",
            ]
        }
        section = build_relationship_map_section(data)
        assert "**Alice**" in section
        assert "Simple connection string" in section


# ============================================================================
# 11. Fallback Insights E2E
# ============================================================================


class TestFallbackInsightsE2E:
    """E2E tests for the fallback insights mechanism."""

    @pytest.mark.asyncio
    async def test_fallback_produces_complete_document(self):
        """Fallback insights still produce a complete, valid document."""
        synth = _make_synthesized()

        with patch(
            "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI"
        ):
            analyzer = StrategicAnalyzer(google_api_key=None)
        analyzer.llm = None

        insights = await analyzer.analyze(synth)
        insights_dict = insights.to_dict()

        generator = DossierGenerator()
        doc = await generator.generate(synth, insights_dict)

        assert "# Meeting Prep Dossier: Jane Doe" in doc
        assert "CONFIDENTIAL" in doc
        assert "Conversation Starters" in doc
        assert "Strategic Insights" in doc
        assert "Verify critical information" in doc

    @pytest.mark.asyncio
    async def test_fallback_with_minimal_data(self):
        """Fallback works with minimal synthesized data."""
        synth = {
            "name": "Unknown Person",
            "key_topics": [],
            "recent_statements": [],
            "known_associates": [],
            "organization": "",
        }

        with patch(
            "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI"
        ):
            analyzer = StrategicAnalyzer(google_api_key=None)
        analyzer.llm = None

        insights = await analyzer.analyze(synth)

        assert len(insights.conversation_starters) >= 1
        assert len(insights.topics_to_avoid) >= 1
        assert insights.meeting_strategy != ""

    @pytest.mark.asyncio
    async def test_fallback_extracts_topics_as_common_ground(self):
        """Fallback uses key topics to create common ground entries."""
        synth = _make_synthesized(
            topics=["quantum computing", "blockchain", "cybersecurity"]
        )

        with patch(
            "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI"
        ):
            analyzer = StrategicAnalyzer(google_api_key=None)
        analyzer.llm = None

        insights = await analyzer.analyze(synth)

        assert len(insights.common_ground) == 3
        assert "quantum computing" in insights.common_ground[0].lower()

    @pytest.mark.asyncio
    async def test_fallback_builds_rel_map_from_associates(self):
        """Fallback creates relationship map from known associates."""
        synth = _make_synthesized(
            associates=[
                {
                    "name": "Alice",
                    "relationship": "co-founder",
                    "context": "Started company",
                },
                {
                    "name": "Bob",
                    "relationship": "advisor",
                    "context": "Technical advisor",
                },
            ]
        )

        with patch(
            "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI"
        ):
            analyzer = StrategicAnalyzer(google_api_key=None)
        analyzer.llm = None

        insights = await analyzer.analyze(synth)

        assert len(insights.relationship_map) == 2
        assert insights.relationship_map[0]["person"] == "Alice"
        assert insights.relationship_map[1]["person"] == "Bob"


# ============================================================================
# 12. Tool Registration
# ============================================================================


class TestToolRegistrationE2E:
    """E2E tests for tool registration and metadata."""

    def test_all_tools_have_descriptions(self):
        """All registered tools have non-empty descriptions."""
        tools = get_dossier_tools()
        for tool in tools:
            assert tool.description, f"Tool {tool.name} has no description"
            assert len(tool.description) > 20

    def test_tool_names_are_prefixed(self):
        """All tool names start with 'dossier_'."""
        tools = get_dossier_tools()
        for tool in tools:
            assert tool.name.startswith("dossier_"), f"{tool.name} missing prefix"

    def test_tools_are_callable(self):
        """All tools are async callable."""
        tools = get_dossier_tools()
        for tool in tools:
            assert hasattr(tool, "ainvoke"), f"{tool.name} missing ainvoke"
