"""
Tests for Dossier (Meeting Prep) Agent.

Covers:
  - Data models (WebSearchResult, LinkedInProfile, CollectedData)
  - SerperClient (search with mocked httpx, empty API key, error handling)
  - LinkedInScraper (profile scraping, various HTML structures, errors)
  - DataCollector (full parallel collection with mocked components)
  - SynthesizedResearch (to_dict, from_dict, defaults)
  - ResearchSynthesizer (Gemini synthesis with mocked LLM, JSON parse, fallback)
  - StrategicInsights (to_dict, from_dict, defaults)
  - StrategicAnalyzer (Gemini analysis, fallback, no API key)
  - DossierGenerator (full document assembly)
  - Template builder functions (each builder in dossier_template.py)
  - DossierAgent orchestrator (generate, status, update)
  - Tool functions and tool registration
  - Session store helpers

Run with:
    .venv/bin/python -m pytest testing/test_dossier_agent.py -v
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from dataclasses import fields as dataclass_fields

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
    ComposioLinkedInClient,
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
from server.tools.dossier_agent.exceptions import (
    DossierSynthesisError,
    DossierAnalysisError,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_synthesized_data() -> dict:
    """Sample SynthesizedResearch.to_dict() output."""
    return {
        "name": "Jane Doe",
        "current_role": "Chief Technology Officer",
        "organization": "Acme Corp",
        "location": "Sydney, Australia",
        "biographical_summary": "Jane Doe is a technology leader with 20 years of experience.",
        "career_highlights": [
            "Led digital transformation at BigCo",
            "Founded AI startup acquired for $50M",
            "Published 3 patents in machine learning",
        ],
        "recent_statements": [
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
        "known_associates": [
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
        "key_topics": [
            "artificial intelligence",
            "digital transformation",
            "ethics in tech",
        ],
        "education_summary": "PhD Computer Science, MIT. MBA, Stanford.",
        "personality_notes": "Direct communicator, values data-driven decisions.",
        "online_presence": "Active on LinkedIn (15k followers), occasional Twitter posts.",
    }


@pytest.fixture
def sample_strategic_insights() -> dict:
    """Sample StrategicInsights.to_dict() output."""
    return {
        "relationship_map": [
            {
                "person": "John Smith",
                "relationship": "board member",
                "leverage": "Shared governance interest",
                "notes": "Long-standing professional relationship",
            },
        ],
        "conversation_starters": [
            "I was impressed by your TechConf keynote on AI transformation",
            "Your work on ethical AI frameworks resonates with our mission",
        ],
        "common_ground": [
            "Interest in responsible AI development",
            "Shared focus on digital transformation",
        ],
        "topics_to_avoid": [
            "Previous company lawsuit - sensitive topic",
            "Failed product launch in 2022 - may be touchy",
        ],
        "meeting_strategy": "Lead with genuine interest in her AI ethics work.",
        "key_motivations": [
            "Driving AI adoption responsibly",
            "Building industry-leading tech teams",
        ],
        "negotiation_style": "Data-driven, prefers concrete examples over abstract concepts.",
        "recommended_approach": "Prepare specific data points about your shared interests before the meeting.",
    }


@pytest.fixture
def sample_collected_data_dict() -> dict:
    """Sample CollectedData.to_dict() output."""
    return {
        "name": "Jane Doe",
        "linkedin_url": "https://linkedin.com/in/janedoe",
        "linkedin_profile": {
            "name": "Jane Doe",
            "headline": "CTO at Acme Corp",
            "location": "Sydney",
            "summary": "Technology leader",
            "experience": [],
            "education": [],
            "skills": ["AI", "ML"],
            "url": "https://linkedin.com/in/janedoe",
        },
        "web_results": {
            "bio": [
                {
                    "title": "Jane Doe - CTO",
                    "url": "https://example.com/jane",
                    "snippet": "Jane Doe is the CTO of Acme Corp",
                    "date": "2025-01-01",
                }
            ],
            "news": [],
            "statements": [],
            "associates": [],
        },
        "raw_page_text": "Jane Doe CTO at Acme Corp...",
    }


@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear all dossier sessions before each test."""
    _dossier_sessions.clear()
    yield
    _dossier_sessions.clear()


# ============================================================================
# WebSearchResult
# ============================================================================


class TestWebSearchResult:
    def test_basic_construction(self):
        r = WebSearchResult(title="Title", url="https://x.com", snippet="Snippet")
        assert r.title == "Title"
        assert r.url == "https://x.com"
        assert r.snippet == "Snippet"
        assert r.date is None

    def test_with_date(self):
        r = WebSearchResult(title="T", url="U", snippet="S", date="2025-01-01")
        assert r.date == "2025-01-01"

    def test_empty_fields(self):
        r = WebSearchResult(title="", url="", snippet="")
        assert r.title == ""


# ============================================================================
# LinkedInProfile
# ============================================================================


class TestLinkedInProfile:
    def test_default_construction(self):
        p = LinkedInProfile()
        assert p.name == ""
        assert p.headline == ""
        assert p.location == ""
        assert p.skills == []
        assert p.experience == []
        assert p.education == []

    def test_construction_with_values(self):
        p = LinkedInProfile(
            name="Jane", headline="CTO", location="Sydney", skills=["Python"]
        )
        assert p.name == "Jane"
        assert p.skills == ["Python"]

    def test_to_dict(self):
        p = LinkedInProfile(name="Jane", headline="CTO", url="https://li.com/jane")
        d = p.to_dict()
        assert d["name"] == "Jane"
        assert d["headline"] == "CTO"
        assert d["url"] == "https://li.com/jane"
        assert isinstance(d["skills"], list)
        assert isinstance(d["experience"], list)

    def test_to_dict_keys(self):
        d = LinkedInProfile().to_dict()
        expected_keys = {
            "name",
            "headline",
            "location",
            "summary",
            "experience",
            "education",
            "skills",
            "url",
        }
        assert set(d.keys()) == expected_keys


# ============================================================================
# CollectedData
# ============================================================================


class TestCollectedData:
    def test_basic_construction(self):
        c = CollectedData(name="Jane Doe")
        assert c.name == "Jane Doe"
        assert c.linkedin_url == ""
        assert c.linkedin_profile is None
        assert c.web_results == {}
        assert c.raw_page_text == ""

    def test_to_dict_without_profile(self):
        c = CollectedData(name="Jane")
        d = c.to_dict()
        assert d["name"] == "Jane"
        assert d["linkedin_profile"] is None
        assert d["web_results"] == {}

    def test_to_dict_with_profile(self):
        profile = LinkedInProfile(name="Jane", headline="CTO")
        c = CollectedData(name="Jane", linkedin_profile=profile)
        d = c.to_dict()
        assert d["linkedin_profile"]["name"] == "Jane"
        assert d["linkedin_profile"]["headline"] == "CTO"

    def test_to_dict_with_web_results(self):
        results = [WebSearchResult(title="T", url="U", snippet="S")]
        c = CollectedData(name="Jane", web_results={"bio": results})
        d = c.to_dict()
        assert len(d["web_results"]["bio"]) == 1
        assert d["web_results"]["bio"][0]["title"] == "T"

    def test_to_dict_truncates_raw_text(self):
        long_text = "x" * 5000
        c = CollectedData(name="Jane", raw_page_text=long_text)
        d = c.to_dict()
        assert len(d["raw_page_text"]) == 2000


# ============================================================================
# SerperClient
# ============================================================================


class TestSerperClient:
    def test_empty_api_key_returns_empty(self):
        client = SerperClient(api_key="")
        results = asyncio.get_event_loop().run_until_complete(client.search("test"))
        assert results == []

    def test_none_api_key_from_env(self):
        with patch.dict("os.environ", {"SERPER_API_KEY": ""}, clear=False):
            client = SerperClient()
            assert client.api_key == ""

    @pytest.mark.asyncio
    async def test_search_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "organic": [
                {
                    "title": "Result 1",
                    "link": "https://example.com",
                    "snippet": "A snippet",
                    "date": "2025-01-01",
                },
            ],
            "knowledgeGraph": {
                "title": "KG Title",
                "website": "https://kg.com",
                "description": "KG description",
            },
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch(
            "server.tools.dossier_agent.data_collector.httpx.AsyncClient",
            return_value=mock_client,
        ):
            client = SerperClient(api_key="test-key")
            results = await client.search("Jane Doe")

        assert len(results) == 2  # KG + 1 organic
        assert results[0].title == "KG Title"
        assert results[1].title == "Result 1"
        assert results[1].date == "2025-01-01"

    @pytest.mark.asyncio
    async def test_search_no_knowledge_graph(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "organic": [
                {"title": "Result", "link": "https://x.com", "snippet": "Snippet"},
            ],
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch(
            "server.tools.dossier_agent.data_collector.httpx.AsyncClient",
            return_value=mock_client,
        ):
            client = SerperClient(api_key="key")
            results = await client.search("query")

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_http_error(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("HTTP error"))

        with patch(
            "server.tools.dossier_agent.data_collector.httpx.AsyncClient",
            return_value=mock_client,
        ):
            client = SerperClient(api_key="key")
            results = await client.search("query")

        assert results == []

    @pytest.mark.asyncio
    async def test_search_num_results_capped(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"organic": []}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch(
            "server.tools.dossier_agent.data_collector.httpx.AsyncClient",
            return_value=mock_client,
        ):
            client = SerperClient(api_key="key")
            await client.search("query", num_results=50)

        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["num"] == 20  # capped at 20


# ============================================================================
# LinkedInScraper
# ============================================================================


class TestLinkedInScraper:
    def test_init(self):
        scraper = LinkedInScraper()
        assert scraper is not None

    @pytest.mark.asyncio
    async def test_scrape_empty_url(self):
        scraper = LinkedInScraper()
        profile = await scraper.scrape_profile("")
        assert profile.name == ""
        assert profile.url == ""

    @pytest.mark.asyncio
    async def test_scrape_profile_success(self):
        html = """
        <html>
        <head>
            <meta property="og:title" content="Jane Doe - CTO - Acme Corp | LinkedIn" />
            <meta property="og:description" content="Experienced technology leader" />
            <meta name="geo.placename" content="Sydney, Australia" />
        </head>
        <body></body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "server.tools.dossier_agent.data_collector.httpx.AsyncClient",
            return_value=mock_client,
        ):
            scraper = LinkedInScraper()
            profile = await scraper.scrape_profile("https://linkedin.com/in/janedoe")

        assert profile.name == "Jane Doe"
        assert "CTO" in profile.headline
        assert profile.summary == "Experienced technology leader"
        assert profile.location == "Sydney, Australia"

    @pytest.mark.asyncio
    async def test_scrape_profile_non_200(self):
        mock_response = MagicMock()
        mock_response.status_code = 403

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "server.tools.dossier_agent.data_collector.httpx.AsyncClient",
            return_value=mock_client,
        ):
            scraper = LinkedInScraper()
            profile = await scraper.scrape_profile("https://linkedin.com/in/someone")

        assert profile.name == ""

    @pytest.mark.asyncio
    async def test_scrape_profile_with_json_ld(self):
        html = """
        <html>
        <head><title>Jane - LinkedIn</title></head>
        <body>
            <script type="application/ld+json">
            {"@type": "Person", "name": "Jane Doe", "jobTitle": "CTO", "address": {"addressLocality": "Melbourne"}}
            </script>
        </body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "server.tools.dossier_agent.data_collector.httpx.AsyncClient",
            return_value=mock_client,
        ):
            scraper = LinkedInScraper()
            profile = await scraper.scrape_profile("https://linkedin.com/in/janedoe")

        # JSON-LD data should be used as fallback
        assert profile.name in ("Jane", "Jane Doe")

    @pytest.mark.asyncio
    async def test_scrape_profile_error(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("Connection error"))

        with patch(
            "server.tools.dossier_agent.data_collector.httpx.AsyncClient",
            return_value=mock_client,
        ):
            scraper = LinkedInScraper()
            profile = await scraper.scrape_profile("https://linkedin.com/in/someone")

        assert profile.name == ""

    @pytest.mark.asyncio
    async def test_scrape_profile_text_empty_url(self):
        scraper = LinkedInScraper()
        text = await scraper.scrape_profile_text("")
        assert text == ""

    @pytest.mark.asyncio
    async def test_scrape_profile_text_success(self):
        html = """
        <html>
        <head><title>Jane Doe</title></head>
        <body>
            <div>Jane Doe is the CTO of Acme Corp</div>
            <script>var x = 1;</script>
        </body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "server.tools.dossier_agent.data_collector.httpx.AsyncClient",
            return_value=mock_client,
        ):
            scraper = LinkedInScraper()
            text = await scraper.scrape_profile_text("https://linkedin.com/in/janedoe")

        assert "Jane Doe" in text
        assert "var x" not in text  # script should be removed

    @pytest.mark.asyncio
    async def test_scrape_profile_text_non_200(self):
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "server.tools.dossier_agent.data_collector.httpx.AsyncClient",
            return_value=mock_client,
        ):
            scraper = LinkedInScraper()
            text = await scraper.scrape_profile_text("https://linkedin.com/in/someone")

        assert text == ""

    @pytest.mark.asyncio
    async def test_scrape_url_normalization(self):
        """Test that URLs without http prefix get normalized."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><head></head><body></body></html>"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "server.tools.dossier_agent.data_collector.httpx.AsyncClient",
            return_value=mock_client,
        ):
            scraper = LinkedInScraper()
            await scraper.scrape_profile("linkedin.com/in/someone")

        call_args = mock_client.get.call_args
        assert call_args[0][0].startswith("https://")


# ============================================================================
# DataCollector
# ============================================================================


class TestDataCollector:
    @pytest.mark.asyncio
    async def test_collect_basic(self):
        mock_serper = AsyncMock()
        mock_serper.search = AsyncMock(
            return_value=[
                WebSearchResult(title="Bio Result", url="https://x.com", snippet="Bio")
            ]
        )

        mock_linkedin = AsyncMock()
        mock_linkedin.scrape_profile = AsyncMock(
            return_value=LinkedInProfile(name="Jane Doe", headline="CTO")
        )
        mock_linkedin.scrape_profile_text = AsyncMock(return_value="Jane Doe text")

        collector = DataCollector()
        collector.serper = mock_serper
        collector.linkedin = mock_linkedin

        data = await collector.collect(
            name="Jane Doe", linkedin_url="https://li.com/jane"
        )

        assert data.name == "Jane Doe"
        assert data.linkedin_url == "https://li.com/jane"
        assert data.linkedin_profile.name == "Jane Doe"
        assert data.raw_page_text == "Jane Doe text"
        # Should have called search for each category + LinkedIn enhanced queries
        assert mock_serper.search.call_count == 7  # 4 categories + 3 LinkedIn queries

    @pytest.mark.asyncio
    async def test_collect_handles_exceptions(self):
        mock_serper = AsyncMock()
        mock_serper.search = AsyncMock(side_effect=Exception("Search failed"))

        mock_linkedin = AsyncMock()
        mock_linkedin.scrape_profile = AsyncMock(side_effect=Exception("Scrape failed"))
        mock_linkedin.scrape_profile_text = AsyncMock(
            side_effect=Exception("Text failed")
        )

        collector = DataCollector()
        collector.serper = mock_serper
        collector.linkedin = mock_linkedin

        # The LinkedIn fallback also calls serper.search which will raise,
        # but collect() should still not propagate the exception
        data = await collector.collect(name="Jane Doe")

        # Should not raise, just return empty data
        assert data.name == "Jane Doe"
        # LinkedIn profile may be None or empty depending on exception handling
        assert data.raw_page_text == ""

    def test_search_queries_format(self):
        collector = DataCollector()
        assert "bio" in collector.SEARCH_QUERIES
        assert "news" in collector.SEARCH_QUERIES
        assert "statements" in collector.SEARCH_QUERIES
        assert "associates" in collector.SEARCH_QUERIES
        for template in collector.SEARCH_QUERIES.values():
            assert "{name}" in template

    def test_linkedin_search_queries_format(self):
        """Verify enhanced LinkedIn search query templates exist."""
        collector = DataCollector()
        assert "profile" in collector.LINKEDIN_SEARCH_QUERIES
        assert "experience" in collector.LINKEDIN_SEARCH_QUERIES
        assert "education" in collector.LINKEDIN_SEARCH_QUERIES
        for template in collector.LINKEDIN_SEARCH_QUERIES.values():
            assert "{name}" in template

    @pytest.mark.asyncio
    async def test_collect_self_lookup_mode(self):
        """Test collect() with is_self_lookup=True uses Composio client."""
        mock_serper = AsyncMock()
        mock_serper.search = AsyncMock(
            return_value=[
                WebSearchResult(title="Bio", url="https://x.com", snippet="Bio")
            ]
        )

        collector = DataCollector()
        collector.serper = mock_serper

        # Mock the ComposioLinkedInClient to return a profile
        mock_profile = LinkedInProfile(
            name="Muhammad Maulana Firdaussyah",
            headline="Software Engineer",
            location="Indonesia",
            summary="Full-stack developer",
            url="https://www.linkedin.com/in/maulanafirdaus",
        )

        with patch(
            "server.tools.dossier_agent.data_collector.ComposioLinkedInClient"
        ) as MockComposio:
            mock_client_instance = AsyncMock()
            mock_client_instance.get_my_profile = AsyncMock(return_value=mock_profile)
            MockComposio.return_value = mock_client_instance

            data = await collector.collect(
                name="Muhammad Maulana Firdaussyah",
                is_self_lookup=True,
                composio_user_id="user123",
            )

        assert data.name == "Muhammad Maulana Firdaussyah"
        assert data.linkedin_profile is not None
        assert data.linkedin_profile.name == "Muhammad Maulana Firdaussyah"
        assert data.linkedin_profile.headline == "Software Engineer"
        assert data.linkedin_url == "https://www.linkedin.com/in/maulanafirdaus"
        # Self-lookup should only call 4 category searches (no LinkedIn Serper queries)
        assert mock_serper.search.call_count == 4

    @pytest.mark.asyncio
    async def test_collect_self_lookup_composio_failure(self):
        """Test collect() with is_self_lookup=True gracefully handles Composio failure."""
        mock_serper = AsyncMock()
        mock_serper.search = AsyncMock(return_value=[])

        collector = DataCollector()
        collector.serper = mock_serper

        # Mock Composio to return empty profile (simulating failure)
        with patch(
            "server.tools.dossier_agent.data_collector.ComposioLinkedInClient"
        ) as MockComposio:
            mock_client_instance = AsyncMock()
            mock_client_instance.get_my_profile = AsyncMock(
                return_value=LinkedInProfile()
            )
            MockComposio.return_value = mock_client_instance

            data = await collector.collect(
                name="Muhammad Maulana Firdaussyah",
                is_self_lookup=True,
            )

        # Should not crash, just have empty/None profile
        assert data.name == "Muhammad Maulana Firdaussyah"

    @pytest.mark.asyncio
    async def test_collect_other_lookup_enhanced_serper(self):
        """Test collect() with is_self_lookup=False uses enhanced Serper queries."""
        call_count = {"n": 0}

        async def mock_search(query, num_results=10):
            call_count["n"] += 1
            if "linkedin.com/in/" in query:
                return [
                    WebSearchResult(
                        title="Muhammad Maulana Firdaussyah - Software Engineer | LinkedIn",
                        url="https://www.linkedin.com/in/maulanafirdaus",
                        snippet="Full-stack developer with 5+ years experience.",
                    )
                ]
            elif "experience" in query.lower():
                return [
                    WebSearchResult(
                        title="Experience",
                        url="https://www.linkedin.com/in/maulanafirdaus",
                        snippet="Senior Engineer at TechCorp",
                    )
                ]
            elif "education" in query.lower():
                return [
                    WebSearchResult(
                        title="Education",
                        url="https://www.linkedin.com/in/maulanafirdaus",
                        snippet="Bachelor degree from University of Indonesia",
                    )
                ]
            return [
                WebSearchResult(
                    title="Result", url="https://example.com", snippet="Info"
                )
            ]

        mock_serper = AsyncMock()
        mock_serper.search = AsyncMock(side_effect=mock_search)

        mock_linkedin = AsyncMock()
        mock_linkedin.scrape_profile = AsyncMock(
            return_value=LinkedInProfile()  # Empty profile - triggers Serper fallback
        )
        mock_linkedin.scrape_profile_text = AsyncMock(return_value="")

        collector = DataCollector()
        collector.serper = mock_serper
        collector.linkedin = mock_linkedin

        data = await collector.collect(
            name="Muhammad Maulana Firdaussyah",
        )

        assert data.name == "Muhammad Maulana Firdaussyah"
        # Enhanced Serper should have populated the profile
        assert data.linkedin_profile is not None
        assert data.linkedin_profile.name == "Muhammad Maulana Firdaussyah"
        assert data.linkedin_profile.headline == "Software Engineer"
        assert data.linkedin_url == "https://www.linkedin.com/in/maulanafirdaus"
        # 4 category + 3 LinkedIn queries = 7
        assert mock_serper.search.call_count == 7


# ============================================================================
# ComposioLinkedInClient Tests
# ============================================================================


class TestComposioLinkedInClient:
    """Tests for the ComposioLinkedInClient used for self-lookup."""

    def test_init_defaults(self):
        client = ComposioLinkedInClient()
        assert client.user_id == "default"
        assert client._client is None

    def test_init_with_params(self):
        client = ComposioLinkedInClient(composio_api_key="test_key", user_id="user123")
        assert client.api_key == "test_key"
        assert client.user_id == "user123"

    def test_parse_composio_response_full(self):
        """Test parsing a full Composio GET_MY_INFO response."""
        client = ComposioLinkedInClient()
        data = {
            "localizedFirstName": "Muhammad Maulana",
            "localizedLastName": "Firdaussyah",
            "localizedHeadline": "Software Engineer | Full-Stack Developer",
            "location": "Jakarta, Indonesia",
            "summary": "Passionate developer building AI-powered applications",
            "vanityName": "maulanafirdaus",
            "positions": [
                {"title": "Software Engineer", "companyName": "TechCorp"},
                {"title": "Junior Developer", "companyName": "StartupXYZ"},
            ],
            "educations": [
                {
                    "schoolName": "University of Indonesia",
                    "degreeName": "Bachelor of Computer Science",
                    "fieldOfStudy": "Computer Science",
                }
            ],
            "skills": ["Python", "TypeScript", "React", "FastAPI"],
        }

        profile = client._parse_composio_response(data)

        assert profile.name == "Muhammad Maulana Firdaussyah"
        assert profile.headline == "Software Engineer | Full-Stack Developer"
        assert profile.location == "Jakarta, Indonesia"
        assert (
            profile.summary == "Passionate developer building AI-powered applications"
        )
        assert profile.url == "https://www.linkedin.com/in/maulanafirdaus"
        assert len(profile.experience) == 2
        assert profile.experience[0]["title"] == "Software Engineer"
        assert profile.experience[0]["company"] == "TechCorp"
        assert len(profile.education) == 1
        assert profile.education[0]["school"] == "University of Indonesia"
        assert profile.education[0]["degree"] == "Bachelor of Computer Science"
        assert profile.education[0]["field"] == "Computer Science"
        assert profile.skills == ["Python", "TypeScript", "React", "FastAPI"]

    def test_parse_composio_response_minimal(self):
        """Test parsing a minimal response (only name)."""
        client = ComposioLinkedInClient()
        data = {"name": "Muhammad Maulana Firdaussyah"}

        profile = client._parse_composio_response(data)
        assert profile.name == "Muhammad Maulana Firdaussyah"
        assert profile.headline == ""
        assert profile.experience == []
        assert profile.education == []
        assert profile.skills == []

    def test_parse_composio_response_empty(self):
        """Test parsing an empty response."""
        client = ComposioLinkedInClient()
        profile = client._parse_composio_response({})
        assert profile.name == ""
        assert profile.headline == ""

    def test_parse_composio_response_not_dict(self):
        """Test parsing a non-dict response."""
        client = ComposioLinkedInClient()
        profile = client._parse_composio_response("not a dict")
        assert profile.name == ""

    def test_parse_composio_response_location_dict(self):
        """Test parsing when location is a nested dict."""
        client = ComposioLinkedInClient()
        data = {
            "name": "Muhammad Maulana Firdaussyah",
            "location": {"name": "Jakarta, Indonesia"},
        }
        profile = client._parse_composio_response(data)
        assert profile.location == "Jakarta, Indonesia"

    def test_parse_composio_response_skills_mixed(self):
        """Test parsing skills as mix of strings and dicts."""
        client = ComposioLinkedInClient()
        data = {
            "name": "Muhammad Maulana Firdaussyah",
            "skills": [
                "Python",
                {"name": "TypeScript"},
                "React",
            ],
        }
        profile = client._parse_composio_response(data)
        assert len(profile.skills) == 3
        assert profile.skills[0] == "Python"
        assert profile.skills[1] == "TypeScript"
        assert profile.skills[2] == "React"

    def test_parse_composio_response_alt_fields(self):
        """Test parsing with alternative field names (headline, about, profileUrl)."""
        client = ComposioLinkedInClient()
        data = {
            "name": "Muhammad Maulana Firdaussyah",
            "headline": "Engineer",
            "about": "Building things",
            "profileUrl": "https://www.linkedin.com/in/mmf",
            "experience": [{"title": "Dev", "company": "Acme"}],
            "education": [{"school": "MIT", "degree": "BS"}],
        }
        profile = client._parse_composio_response(data)
        assert profile.headline == "Engineer"
        assert profile.summary == "Building things"
        assert profile.url == "https://www.linkedin.com/in/mmf"
        assert len(profile.experience) == 1
        assert profile.experience[0]["company"] == "Acme"
        assert len(profile.education) == 1
        assert profile.education[0]["school"] == "MIT"

    @pytest.mark.asyncio
    async def test_get_my_profile_no_api_key(self):
        """Test get_my_profile with no API key returns empty profile."""
        client = ComposioLinkedInClient(composio_api_key="")
        profile = await client.get_my_profile()
        assert profile.name == ""
        assert profile.headline == ""

    @pytest.mark.asyncio
    async def test_get_my_profile_success(self):
        """Test get_my_profile with mocked Composio client."""
        client = ComposioLinkedInClient(composio_api_key="test_key", user_id="user123")

        mock_composio = MagicMock()
        mock_composio.tools.execute.return_value = {
            "data": {
                "localizedFirstName": "Muhammad Maulana",
                "localizedLastName": "Firdaussyah",
                "localizedHeadline": "Software Engineer",
                "vanityName": "maulanafirdaus",
            }
        }
        client._client = mock_composio

        profile = await client.get_my_profile()
        assert profile.name == "Muhammad Maulana Firdaussyah"
        assert profile.headline == "Software Engineer"
        assert profile.url == "https://www.linkedin.com/in/maulanafirdaus"

    @pytest.mark.asyncio
    async def test_get_my_profile_composio_exception(self):
        """Test get_my_profile handles Composio exceptions gracefully."""
        client = ComposioLinkedInClient(composio_api_key="test_key")

        mock_composio = MagicMock()
        mock_composio.tools.execute.side_effect = Exception("Composio API error")
        client._client = mock_composio

        profile = await client.get_my_profile()
        # Should return empty profile, not raise
        assert profile.name == ""

    @pytest.mark.asyncio
    async def test_get_my_profile_empty_response(self):
        """Test get_my_profile with empty Composio response."""
        client = ComposioLinkedInClient(composio_api_key="test_key")

        mock_composio = MagicMock()
        mock_composio.tools.execute.return_value = {}
        client._client = mock_composio

        profile = await client.get_my_profile()
        assert profile.name == ""


# ============================================================================
# Enhanced Serper LinkedIn Extraction Tests
# ============================================================================


class TestEnhancedSerperExtraction:
    """Tests for _extract_from_serper_linkedin and helper parsers."""

    def test_extract_profile_from_serper(self):
        """Test extracting profile data from Serper LinkedIn search results."""
        collector = DataCollector()
        collected = CollectedData(name="Muhammad Maulana Firdaussyah")

        serper_results = {
            "profile": [
                WebSearchResult(
                    title="Muhammad Maulana Firdaussyah - Software Engineer | LinkedIn",
                    url="https://www.linkedin.com/in/maulanafirdaus",
                    snippet="Full-stack developer building AI applications. Jakarta, Indonesia.",
                )
            ],
            "experience": [],
            "education": [],
        }

        result = collector._extract_from_serper_linkedin(
            "Muhammad Maulana Firdaussyah", "", serper_results, collected
        )

        assert result.linkedin_profile is not None
        assert result.linkedin_profile.name == "Muhammad Maulana Firdaussyah"
        assert result.linkedin_profile.headline == "Software Engineer"
        assert result.linkedin_url == "https://www.linkedin.com/in/maulanafirdaus"
        assert "Full-stack developer" in result.linkedin_profile.summary

    def test_extract_with_experience_snippets(self):
        """Test extracting experience from Serper snippets."""
        collector = DataCollector()
        collected = CollectedData(name="Muhammad Maulana Firdaussyah")

        serper_results = {
            "profile": [
                WebSearchResult(
                    title="Muhammad Maulana Firdaussyah - Engineer | LinkedIn",
                    url="https://www.linkedin.com/in/maulanafirdaus",
                    snippet="Engineer at TechCorp.",
                )
            ],
            "experience": [
                WebSearchResult(
                    title="Experience",
                    url="https://example.com",
                    snippet="Senior Engineer at TechCorp since 2022.",
                )
            ],
            "education": [],
        }

        result = collector._extract_from_serper_linkedin(
            "Muhammad Maulana Firdaussyah", "", serper_results, collected
        )

        assert result.linkedin_profile is not None
        assert result.linkedin_profile.name == "Muhammad Maulana Firdaussyah"

    def test_extract_with_education_snippets(self):
        """Test extracting education from Serper snippets."""
        collector = DataCollector()
        collected = CollectedData(name="Muhammad Maulana Firdaussyah")

        serper_results = {
            "profile": [
                WebSearchResult(
                    title="Muhammad Maulana Firdaussyah - Developer | LinkedIn",
                    url="https://www.linkedin.com/in/maulanafirdaus",
                    snippet="Developer in Jakarta.",
                )
            ],
            "experience": [],
            "education": [
                WebSearchResult(
                    title="Education",
                    url="https://example.com",
                    snippet="Bachelor degree from University of Indonesia in Computer Science.",
                )
            ],
        }

        result = collector._extract_from_serper_linkedin(
            "Muhammad Maulana Firdaussyah", "", serper_results, collected
        )

        assert result.linkedin_profile is not None
        if result.linkedin_profile.education:
            assert "University of Indonesia" in result.linkedin_profile.education[
                0
            ].get("school", "")

    def test_extract_no_linkedin_results(self):
        """Test extraction with no LinkedIn results returns unchanged data."""
        collector = DataCollector()
        collected = CollectedData(name="Muhammad Maulana Firdaussyah")

        serper_results = {
            "profile": [],
            "experience": [],
            "education": [],
        }

        result = collector._extract_from_serper_linkedin(
            "Muhammad Maulana Firdaussyah", "", serper_results, collected
        )

        # Profile should still be set (possibly empty)
        # But linkedin_url should not have been discovered
        assert result.linkedin_url == ""

    def test_extract_summary_fallback(self):
        """Test that summary is built from snippets when profile has no summary."""
        collector = DataCollector()
        collected = CollectedData(name="Test Person")

        serper_results = {
            "profile": [
                WebSearchResult(
                    title="Test Person | LinkedIn",
                    url="https://www.linkedin.com/in/testperson",
                    snippet="",  # empty snippet
                )
            ],
            "experience": [
                WebSearchResult(
                    title="Exp",
                    url="https://www.linkedin.com/in/testperson",
                    snippet="Experienced in AI and ML.",
                )
            ],
            "education": [],
        }

        result = collector._extract_from_serper_linkedin(
            "Test Person", "", serper_results, collected
        )

        # Summary fallback should collect snippets from LinkedIn URLs
        assert result.linkedin_profile is not None
        if result.linkedin_profile.summary:
            assert "Experienced in AI" in result.linkedin_profile.summary

    def test_parse_experience_snippet_at_pattern(self):
        """Test _parse_experience_snippet with 'at' pattern."""
        result = DataCollector._parse_experience_snippet(
            "Muhammad",
            "Muhammad is a Senior Engineer at TechCorp. Based in Jakarta.",
            "",
        )
        assert result is not None
        assert result["company"] == "TechCorp"

    def test_parse_experience_snippet_dot_pattern(self):
        """Test _parse_experience_snippet with middle dot pattern."""
        result = DataCollector._parse_experience_snippet(
            "Test", "TechCorp · Software Engineer. Full-stack.", ""
        )
        assert result is not None
        assert result["title"] == "Software Engineer"
        assert result["company"] == "TechCorp"

    def test_parse_experience_snippet_no_match(self):
        """Test _parse_experience_snippet with no recognizable pattern."""
        result = DataCollector._parse_experience_snippet(
            "Test", "Just some random text without patterns.", ""
        )
        assert result is None

    def test_parse_education_snippet_university(self):
        """Test _parse_education_snippet with university name."""
        result = DataCollector._parse_education_snippet(
            "Test", "Graduated from University of Indonesia with a Bachelor degree.", ""
        )
        assert result is not None
        assert "University of Indonesia" in result["school"]
        assert "Bachelor" in result["degree"]

    def test_parse_education_snippet_no_edu(self):
        """Test _parse_education_snippet with no education keywords."""
        result = DataCollector._parse_education_snippet(
            "Test", "Just some work experience details.", ""
        )
        assert result is None

    def test_parse_education_snippet_mba(self):
        """Test _parse_education_snippet with MBA keyword."""
        result = DataCollector._parse_education_snippet(
            "Test", "Completed MBA from Business School of Jakarta.", ""
        )
        assert result is not None
        assert "MBA" in result["degree"]

    def test_extract_handles_exception_gracefully(self):
        """Test that _extract_from_serper_linkedin doesn't propagate exceptions."""
        collector = DataCollector()
        collected = CollectedData(name="Test")

        # Pass invalid data to trigger internal error
        result = collector._extract_from_serper_linkedin(
            "Test", "", {"profile": "not_a_list"}, collected
        )
        # Should return collected unchanged, not raise
        assert result.name == "Test"

    def test_defaults(self):
        s = SynthesizedResearch()
        assert s.name == ""
        assert s.current_role == ""
        assert s.career_highlights == []
        assert s.recent_statements == []
        assert s.known_associates == []
        assert s.key_topics == []

    def test_to_dict(self):
        s = SynthesizedResearch(name="Jane", current_role="CTO", key_topics=["AI"])
        d = s.to_dict()
        assert d["name"] == "Jane"
        assert d["current_role"] == "CTO"
        assert d["key_topics"] == ["AI"]

    def test_to_dict_all_keys(self):
        d = SynthesizedResearch().to_dict()
        expected_keys = {
            "name",
            "current_role",
            "organization",
            "location",
            "biographical_summary",
            "career_highlights",
            "recent_statements",
            "known_associates",
            "key_topics",
            "education_summary",
            "personality_notes",
            "online_presence",
            "linkedin_url",
        }
        assert set(d.keys()) == expected_keys

    def test_from_dict(self):
        data = {
            "name": "Jane",
            "current_role": "CTO",
            "organization": "Acme",
            "location": "Sydney",
            "biographical_summary": "Bio text",
            "career_highlights": ["Highlight 1"],
            "recent_statements": [{"quote": "Q1"}],
            "known_associates": [{"name": "Bob"}],
            "key_topics": ["AI"],
            "education_summary": "PhD MIT",
            "personality_notes": "Direct",
            "online_presence": "Active LinkedIn",
        }
        s = SynthesizedResearch.from_dict(data)
        assert s.name == "Jane"
        assert s.career_highlights == ["Highlight 1"]
        assert s.key_topics == ["AI"]

    def test_from_dict_missing_keys(self):
        s = SynthesizedResearch.from_dict({})
        assert s.name == ""
        assert s.career_highlights == []

    def test_roundtrip(self):
        original = SynthesizedResearch(
            name="Jane",
            current_role="CTO",
            key_topics=["AI", "ML"],
        )
        d = original.to_dict()
        restored = SynthesizedResearch.from_dict(d)
        assert restored.name == original.name
        assert restored.key_topics == original.key_topics


# ============================================================================
# ResearchSynthesizer
# ============================================================================


class TestResearchSynthesizer:
    @pytest.mark.asyncio
    async def test_synthesize_success(self, sample_collected_data_dict):
        mock_response = MagicMock()
        mock_response.content = json.dumps(
            {
                "name": "Jane Doe",
                "current_role": "CTO",
                "organization": "Acme Corp",
                "location": "Sydney",
                "biographical_summary": "A tech leader",
                "career_highlights": ["Led digital transformation"],
                "recent_statements": [],
                "known_associates": [],
                "key_topics": ["AI"],
                "education_summary": "PhD MIT",
                "personality_notes": "Direct",
                "online_presence": "Active",
            }
        )

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch(
            "server.tools.dossier_agent.research_synthesizer.ChatGoogleGenerativeAI",
            return_value=mock_llm,
        ):
            synthesizer = ResearchSynthesizer(google_api_key="test-key")
            synthesizer.llm = mock_llm
            result = await synthesizer.synthesize(sample_collected_data_dict)

        assert result.name == "Jane Doe"
        assert result.current_role == "CTO"
        assert "AI" in result.key_topics

    @pytest.mark.asyncio
    async def test_synthesize_strips_markdown_fences(self, sample_collected_data_dict):
        json_data = json.dumps(
            {
                "name": "Jane",
                "current_role": "CTO",
                "organization": "X",
                "location": "Y",
                "biographical_summary": "Bio",
                "career_highlights": [],
                "recent_statements": [],
                "known_associates": [],
                "key_topics": [],
                "education_summary": "",
                "personality_notes": "",
                "online_presence": "",
            }
        )
        mock_response = MagicMock()
        mock_response.content = f"```json\n{json_data}\n```"

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch(
            "server.tools.dossier_agent.research_synthesizer.ChatGoogleGenerativeAI",
            return_value=mock_llm,
        ):
            synthesizer = ResearchSynthesizer(google_api_key="test-key")
            synthesizer.llm = mock_llm
            result = await synthesizer.synthesize(sample_collected_data_dict)

        assert result.name == "Jane"

    @pytest.mark.asyncio
    async def test_synthesize_json_parse_error(self, sample_collected_data_dict):
        mock_response = MagicMock()
        mock_response.content = "not valid json at all"

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch(
            "server.tools.dossier_agent.research_synthesizer.ChatGoogleGenerativeAI",
            return_value=mock_llm,
        ):
            synthesizer = ResearchSynthesizer(google_api_key="test-key")
            synthesizer.llm = mock_llm
            result = await synthesizer.synthesize(sample_collected_data_dict)

        assert result.name == "Jane Doe"
        assert "[Synthesis parse error]" in result.biographical_summary

    @pytest.mark.asyncio
    async def test_synthesize_llm_exception(self, sample_collected_data_dict):
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM unavailable"))

        with patch(
            "server.tools.dossier_agent.research_synthesizer.ChatGoogleGenerativeAI",
            return_value=mock_llm,
        ):
            synthesizer = ResearchSynthesizer(google_api_key="test-key")
            synthesizer.llm = mock_llm
            with pytest.raises(DossierSynthesisError):
                await synthesizer.synthesize(sample_collected_data_dict)

    @pytest.mark.asyncio
    async def test_synthesize_with_no_linkedin(self):
        data = {
            "name": "Someone",
            "linkedin_url": "",
            "linkedin_profile": None,
            "web_results": {},
            "raw_page_text": "",
        }

        mock_response = MagicMock()
        mock_response.content = json.dumps(
            {
                "name": "Someone",
                "current_role": "",
                "organization": "",
                "location": "",
                "biographical_summary": "Limited data",
                "career_highlights": [],
                "recent_statements": [],
                "known_associates": [],
                "key_topics": [],
                "education_summary": "",
                "personality_notes": "",
                "online_presence": "",
            }
        )

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch(
            "server.tools.dossier_agent.research_synthesizer.ChatGoogleGenerativeAI",
            return_value=mock_llm,
        ):
            synthesizer = ResearchSynthesizer(google_api_key="test-key")
            synthesizer.llm = mock_llm
            result = await synthesizer.synthesize(data)

        assert result.name == "Someone"


# ============================================================================
# StrategicInsights
# ============================================================================


class TestStrategicInsights:
    def test_defaults(self):
        s = StrategicInsights()
        assert s.relationship_map == []
        assert s.conversation_starters == []
        assert s.common_ground == []
        assert s.topics_to_avoid == []
        assert s.meeting_strategy == ""
        assert s.key_motivations == []
        assert s.negotiation_style == ""
        assert s.recommended_approach == ""

    def test_to_dict(self):
        s = StrategicInsights(
            conversation_starters=["Start 1"],
            meeting_strategy="Be prepared",
        )
        d = s.to_dict()
        assert d["conversation_starters"] == ["Start 1"]
        assert d["meeting_strategy"] == "Be prepared"

    def test_to_dict_all_keys(self):
        d = StrategicInsights().to_dict()
        expected_keys = {
            "relationship_map",
            "conversation_starters",
            "common_ground",
            "topics_to_avoid",
            "meeting_strategy",
            "key_motivations",
            "negotiation_style",
            "recommended_approach",
        }
        assert set(d.keys()) == expected_keys

    def test_from_dict(self):
        data = {
            "relationship_map": [{"person": "Bob"}],
            "conversation_starters": ["Hi"],
            "common_ground": ["AI"],
            "topics_to_avoid": ["Politics"],
            "meeting_strategy": "Be calm",
            "key_motivations": ["Success"],
            "negotiation_style": "Direct",
            "recommended_approach": "Data-driven",
        }
        s = StrategicInsights.from_dict(data)
        assert s.conversation_starters == ["Hi"]
        assert s.meeting_strategy == "Be calm"

    def test_from_dict_missing_keys(self):
        s = StrategicInsights.from_dict({})
        assert s.conversation_starters == []
        assert s.meeting_strategy == ""

    def test_roundtrip(self):
        original = StrategicInsights(
            conversation_starters=["Hi", "Hello"],
            topics_to_avoid=["Bad topic"],
        )
        d = original.to_dict()
        restored = StrategicInsights.from_dict(d)
        assert restored.conversation_starters == original.conversation_starters
        assert restored.topics_to_avoid == original.topics_to_avoid


# ============================================================================
# StrategicAnalyzer
# ============================================================================


class TestStrategicAnalyzer:
    def test_no_api_key_creates_no_llm(self):
        with patch.dict("os.environ", {"GOOGLE_API_KEY": ""}, clear=False):
            analyzer = StrategicAnalyzer(google_api_key=None)
            # When no key is found in env or parameter, llm should be None

    @pytest.mark.asyncio
    async def test_analyze_fallback_when_no_llm(self, sample_synthesized_data):
        with patch(
            "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI"
        ):
            analyzer = StrategicAnalyzer(google_api_key=None)
        analyzer.llm = None

        result = await analyzer.analyze(sample_synthesized_data)

        assert isinstance(result, StrategicInsights)
        assert len(result.conversation_starters) > 0
        assert len(result.relationship_map) > 0

    @pytest.mark.asyncio
    async def test_analyze_success(self, sample_synthesized_data):
        mock_response = MagicMock()
        mock_response.content = json.dumps(
            {
                "relationship_map": [
                    {
                        "person": "John",
                        "relationship": "board",
                        "leverage": "Gov",
                        "notes": "N/A",
                    }
                ],
                "conversation_starters": ["Great keynote!"],
                "common_ground": ["AI interest"],
                "topics_to_avoid": ["Lawsuit"],
                "meeting_strategy": "Lead with AI",
                "key_motivations": ["Innovation"],
                "negotiation_style": "Data-driven",
                "recommended_approach": "Prepare data points",
            }
        )

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch(
            "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI",
            return_value=mock_llm,
        ):
            analyzer = StrategicAnalyzer(google_api_key="test-key")
            analyzer.llm = mock_llm

            result = await analyzer.analyze(
                sample_synthesized_data, meeting_context="Discuss partnership"
            )

        assert result.conversation_starters == ["Great keynote!"]
        assert result.meeting_strategy == "Lead with AI"

    @pytest.mark.asyncio
    async def test_analyze_json_error_falls_back(self, sample_synthesized_data):
        mock_response = MagicMock()
        mock_response.content = "not valid json"

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch(
            "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI",
            return_value=mock_llm,
        ):
            analyzer = StrategicAnalyzer(google_api_key="test-key")
            analyzer.llm = mock_llm

            result = await analyzer.analyze(sample_synthesized_data)

        assert isinstance(result, StrategicInsights)
        # Should have fallback insights
        assert len(result.conversation_starters) > 0

    @pytest.mark.asyncio
    async def test_analyze_exception_falls_back(self, sample_synthesized_data):
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("API error"))

        with patch(
            "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI",
            return_value=mock_llm,
        ):
            analyzer = StrategicAnalyzer(google_api_key="test-key")
            analyzer.llm = mock_llm

            with pytest.raises(DossierAnalysisError):
                await analyzer.analyze(sample_synthesized_data)

    @pytest.mark.asyncio
    async def test_analyze_strips_markdown_fences(self, sample_synthesized_data):
        json_data = json.dumps(
            {
                "relationship_map": [],
                "conversation_starters": ["Hello"],
                "common_ground": [],
                "topics_to_avoid": [],
                "meeting_strategy": "Be nice",
                "key_motivations": [],
                "negotiation_style": "",
                "recommended_approach": "",
            }
        )

        mock_response = MagicMock()
        mock_response.content = f"```json\n{json_data}\n```"

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch(
            "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI",
            return_value=mock_llm,
        ):
            analyzer = StrategicAnalyzer(google_api_key="test-key")
            analyzer.llm = mock_llm

            result = await analyzer.analyze(sample_synthesized_data)
        assert result.conversation_starters == ["Hello"]

    def test_fallback_insights_with_topics(self, sample_synthesized_data):
        with patch(
            "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI"
        ):
            analyzer = StrategicAnalyzer(google_api_key=None)
        analyzer.llm = None
        result = analyzer._fallback_insights(sample_synthesized_data)

        assert len(result.conversation_starters) >= 1
        assert len(result.common_ground) > 0
        assert (
            "artificial intelligence" in result.common_ground[0].lower()
            or "Interest in" in result.common_ground[0]
        )

    def test_fallback_insights_empty_data(self):
        with patch(
            "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI"
        ):
            analyzer = StrategicAnalyzer(google_api_key=None)
        analyzer.llm = None
        result = analyzer._fallback_insights({})

        assert isinstance(result, StrategicInsights)
        assert len(result.conversation_starters) >= 1

    def test_fallback_insights_with_associates(self, sample_synthesized_data):
        with patch(
            "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI"
        ):
            analyzer = StrategicAnalyzer(google_api_key=None)
        analyzer.llm = None
        result = analyzer._fallback_insights(sample_synthesized_data)

        assert len(result.relationship_map) > 0
        assert result.relationship_map[0]["person"] == "John Smith"


# ============================================================================
# DossierGenerator
# ============================================================================


class TestDossierGenerator:
    @pytest.mark.asyncio
    async def test_generate_full_document(
        self, sample_synthesized_data, sample_strategic_insights
    ):
        generator = DossierGenerator()
        doc = await generator.generate(
            sample_synthesized_data, sample_strategic_insights
        )

        assert "# Meeting Prep Dossier: Jane Doe" in doc
        assert "CONFIDENTIAL" in doc
        assert "Chief Technology Officer" in doc
        assert "Acme Corp" in doc
        assert "TechConf 2025" in doc
        assert "John Smith" in doc
        assert "conversation starters" in doc.lower() or "Conversation Starters" in doc
        assert "Topics to Approach with Caution" in doc

    @pytest.mark.asyncio
    async def test_generate_minimal_data(self):
        generator = DossierGenerator()
        doc = await generator.generate(
            {"name": "Unknown Person"},
            {
                "meeting_strategy": "No data",
                "negotiation_style": "Unknown",
                "recommended_approach": "Gather more info",
            },
        )

        assert "# Meeting Prep Dossier: Unknown Person" in doc
        assert "CONFIDENTIAL" in doc

    @pytest.mark.asyncio
    async def test_generate_includes_linkedin_url(
        self, sample_synthesized_data, sample_strategic_insights
    ):
        sample_synthesized_data["linkedin_url"] = "https://linkedin.com/in/janedoe"
        generator = DossierGenerator()
        doc = await generator.generate(
            sample_synthesized_data, sample_strategic_insights
        )

        assert "https://linkedin.com/in/janedoe" in doc

    @pytest.mark.asyncio
    async def test_generate_without_linkedin_url(
        self, sample_synthesized_data, sample_strategic_insights
    ):
        sample_synthesized_data.pop("linkedin_url", None)
        generator = DossierGenerator()
        doc = await generator.generate(
            sample_synthesized_data, sample_strategic_insights
        )

        assert "# Meeting Prep Dossier: Jane Doe" in doc

    @pytest.mark.asyncio
    async def test_generate_footer(
        self, sample_synthesized_data, sample_strategic_insights
    ):
        generator = DossierGenerator()
        doc = await generator.generate(
            sample_synthesized_data, sample_strategic_insights
        )

        assert "Verify critical information before the meeting" in doc


# ============================================================================
# Template Builder Functions
# ============================================================================


class TestDossierTemplateBuilders:
    def test_dossier_title(self):
        title = DOSSIER_TITLE.format(name="Jane Doe")
        assert "Jane Doe" in title

    def test_section_divider(self):
        assert "---" in SECTION_DIVIDER

    def test_confidential_header(self):
        header = CONFIDENTIAL_HEADER.format(date="01 January 2025")
        assert "CONFIDENTIAL" in header
        assert "01 January 2025" in header

    def test_build_biographical_section(self, sample_synthesized_data):
        section = build_biographical_section(sample_synthesized_data)
        assert "Chief Technology Officer" in section
        assert "Acme Corp" in section
        assert "Sydney, Australia" in section

    def test_build_biographical_section_defaults(self):
        section = build_biographical_section({})
        assert "Not available" in section

    def test_build_career_section(self, sample_synthesized_data):
        section = build_career_section(sample_synthesized_data)
        assert "Led digital transformation" in section
        assert "Career Highlights" in section

    def test_build_career_section_empty(self):
        section = build_career_section({"career_highlights": []})
        assert section == ""

    def test_build_career_section_no_key(self):
        section = build_career_section({})
        assert section == ""

    def test_build_education_section(self, sample_synthesized_data):
        section = build_education_section(sample_synthesized_data)
        assert "PhD Computer Science" in section

    def test_build_education_section_empty(self):
        section = build_education_section({})
        assert section == ""

    def test_build_statements_section(self, sample_synthesized_data):
        section = build_statements_section(sample_synthesized_data)
        assert "AI will transform" in section
        assert "TechConf 2025" in section

    def test_build_statements_section_empty(self):
        section = build_statements_section({})
        assert section == ""

    def test_build_statements_section_string_items(self):
        data = {"recent_statements": ["Statement one", "Statement two"]}
        section = build_statements_section(data)
        assert "Statement one" in section

    def test_build_associates_section(self, sample_synthesized_data):
        section = build_associates_section(sample_synthesized_data)
        assert "John Smith" in section
        assert "board member" in section

    def test_build_associates_section_empty(self):
        section = build_associates_section({})
        assert section == ""

    def test_build_associates_section_string_items(self):
        data = {"known_associates": ["Bob Jones", "Alice Lee"]}
        section = build_associates_section(data)
        assert "Bob Jones" in section

    def test_build_relationship_map_section(self, sample_strategic_insights):
        section = build_relationship_map_section(sample_strategic_insights)
        assert "John Smith" in section
        assert "Leverage" in section

    def test_build_relationship_map_section_empty(self):
        section = build_relationship_map_section({})
        assert section == ""

    def test_build_relationship_map_string_items(self):
        data = {"relationship_map": ["Connection 1"]}
        section = build_relationship_map_section(data)
        assert "Connection 1" in section

    def test_build_strategic_section(self, sample_strategic_insights):
        section = build_strategic_section(sample_strategic_insights)
        assert "Lead with genuine interest" in section
        assert "Meeting Strategy" in section
        assert "Negotiation Style" in section

    def test_build_strategic_section_defaults(self):
        section = build_strategic_section({})
        assert "No strategy available" in section

    def test_build_conversation_starters_section(self, sample_strategic_insights):
        section = build_conversation_starters_section(sample_strategic_insights)
        assert "TechConf keynote" in section

    def test_build_conversation_starters_section_empty(self):
        section = build_conversation_starters_section({})
        assert section == ""

    def test_build_common_ground_section(self, sample_strategic_insights):
        section = build_common_ground_section(sample_strategic_insights)
        assert "responsible AI" in section

    def test_build_common_ground_section_empty(self):
        section = build_common_ground_section({})
        assert section == ""

    def test_build_topics_to_avoid_section(self, sample_strategic_insights):
        section = build_topics_to_avoid_section(sample_strategic_insights)
        assert "lawsuit" in section.lower()

    def test_build_topics_to_avoid_section_empty(self):
        section = build_topics_to_avoid_section({})
        assert section == ""

    def test_build_motivations_section(self, sample_strategic_insights):
        section = build_motivations_section(sample_strategic_insights)
        assert "AI adoption" in section

    def test_build_motivations_section_empty(self):
        section = build_motivations_section({})
        assert section == ""

    def test_build_online_presence_section(self, sample_synthesized_data):
        section = build_online_presence_section(sample_synthesized_data)
        assert "LinkedIn" in section

    def test_build_online_presence_section_empty(self):
        section = build_online_presence_section({})
        assert section == ""


# ============================================================================
# Session Store
# ============================================================================


class TestSessionStore:
    def test_create_session(self):
        session = _create_session(
            "test-1", "Jane Doe", "https://li.com/jane", "Meeting about AI"
        )
        assert session["name"] == "Jane Doe"
        assert session["linkedin_url"] == "https://li.com/jane"
        assert session["meeting_context"] == "Meeting about AI"
        assert session["status"] == "collecting"
        assert session["document"] is None
        assert "test-1" in _dossier_sessions

    def test_get_session(self):
        _create_session("test-2", "Bob")
        session = _get_session("test-2")
        assert session is not None
        assert session["name"] == "Bob"

    def test_get_session_nonexistent(self):
        session = _get_session("nonexistent")
        assert session is None

    def test_clear_session(self):
        _create_session("test-3", "Alice")
        _clear_session("test-3")
        assert _get_session("test-3") is None

    def test_clear_nonexistent_session(self):
        # Should not raise
        _clear_session("nonexistent")

    def test_create_session_defaults(self):
        session = _create_session("test-4", "Joe")
        assert session["linkedin_url"] == ""
        assert session["meeting_context"] == ""

    def test_multiple_sessions(self):
        _create_session("s1", "Person A")
        _create_session("s2", "Person B")
        assert _get_session("s1")["name"] == "Person A"
        assert _get_session("s2")["name"] == "Person B"
        assert len(_dossier_sessions) == 2


# ============================================================================
# DossierAgent Orchestrator
# ============================================================================


class TestDossierAgent:
    @pytest.mark.asyncio
    async def test_generate_dossier_full_pipeline(self):
        mock_collected = CollectedData(
            name="Jane Doe",
            linkedin_url="https://li.com/jane",
            linkedin_profile=LinkedInProfile(name="Jane Doe", headline="CTO"),
            web_results={"bio": [WebSearchResult(title="Bio", url="u", snippet="s")]},
            raw_page_text="Some text",
        )

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
        ):
            agent = DossierAgent(google_api_key="test", serper_api_key="test")
            doc = await agent.generate_dossier(
                "test-session", "Jane Doe", "https://li.com/jane"
            )

        assert "# Meeting Prep Dossier: Jane Doe" in doc
        session = _get_session("test-session")
        assert session["status"] == "generated"
        assert session["document"] == doc

    @pytest.mark.asyncio
    async def test_generate_dossier_error_handling(self):
        with (
            patch.object(
                DataCollector,
                "collect",
                new_callable=AsyncMock,
                side_effect=Exception("Network error"),
            ),
            patch(
                "server.tools.dossier_agent.research_synthesizer.ChatGoogleGenerativeAI"
            ),
            patch(
                "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI"
            ),
        ):
            agent = DossierAgent(google_api_key="test", serper_api_key="test")
            doc = await agent.generate_dossier("err-session", "Jane Doe")

        assert "failed" in doc.lower()
        session = _get_session("err-session")
        assert session["status"] == "error"

    @pytest.mark.asyncio
    async def test_get_status_no_session(self):
        with (
            patch(
                "server.tools.dossier_agent.research_synthesizer.ChatGoogleGenerativeAI"
            ),
            patch(
                "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI"
            ),
        ):
            agent = DossierAgent(google_api_key="t", serper_api_key="t")
            status = await agent.get_status("nonexistent")
        assert status["status"] == "none"

    @pytest.mark.asyncio
    async def test_get_status_collecting(self):
        _create_session("s1", "Jane")
        with (
            patch(
                "server.tools.dossier_agent.research_synthesizer.ChatGoogleGenerativeAI"
            ),
            patch(
                "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI"
            ),
        ):
            agent = DossierAgent(google_api_key="t", serper_api_key="t")
            status = await agent.get_status("s1")
        assert status["status"] == "collecting"

    @pytest.mark.asyncio
    async def test_get_status_generated(self):
        session = _create_session("s2", "Jane")
        session["status"] = "generated"
        session["document"] = "# Dossier content here"

        with (
            patch(
                "server.tools.dossier_agent.research_synthesizer.ChatGoogleGenerativeAI"
            ),
            patch(
                "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI"
            ),
        ):
            agent = DossierAgent(google_api_key="t", serper_api_key="t")
            status = await agent.get_status("s2")
        assert status["status"] == "generated"
        assert "document_preview" in status

    @pytest.mark.asyncio
    async def test_update_dossier_no_session(self):
        with (
            patch(
                "server.tools.dossier_agent.research_synthesizer.ChatGoogleGenerativeAI"
            ),
            patch(
                "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI"
            ),
        ):
            agent = DossierAgent(google_api_key="t", serper_api_key="t")
            result = await agent.update_dossier("nonexistent", "New context")
        assert "No dossier found" in result

    @pytest.mark.asyncio
    async def test_update_dossier_no_synthesized_data(self):
        _create_session("s3", "Jane")
        with (
            patch(
                "server.tools.dossier_agent.research_synthesizer.ChatGoogleGenerativeAI"
            ),
            patch(
                "server.tools.dossier_agent.strategic_analyzer.ChatGoogleGenerativeAI"
            ),
        ):
            agent = DossierAgent(google_api_key="t", serper_api_key="t")
            result = await agent.update_dossier("s3", "New context")
        assert "not yet collected" in result.lower()

    @pytest.mark.asyncio
    async def test_update_dossier_success(self):
        session = _create_session("s4", "Jane")
        session["synthesized_data"] = {"name": "Jane", "key_topics": ["AI"]}
        session["status"] = "generated"

        mock_insights = StrategicInsights(
            conversation_starters=["Updated starter"],
            meeting_strategy="Updated strategy",
            negotiation_style="N/A",
            recommended_approach="N/A",
        )

        with (
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
        ):
            agent = DossierAgent(google_api_key="t", serper_api_key="t")
            doc = await agent.update_dossier("s4", "Discussing partnership")

        assert _get_session("s4")["status"] == "generated"
        assert "partnership" in _get_session("s4")["meeting_context"].lower()


# ============================================================================
# Tool Functions
# ============================================================================


class TestDossierTools:
    def test_get_dossier_tools_count(self):
        tools = get_dossier_tools()
        assert len(tools) == 5

    def test_get_dossier_tools_names(self):
        tools = get_dossier_tools()
        names = [t.name for t in tools]
        assert "dossier_check_status" in names
        assert "dossier_generate" in names
        assert "dossier_update" in names
        assert "dossier_get_document" in names

    @pytest.mark.asyncio
    async def test_dossier_check_status_no_session(self):
        result = await dossier_check_status.ainvoke({"dossier_id": "test"})
        assert "No active dossier" in result

    @pytest.mark.asyncio
    async def test_dossier_check_status_generated(self):
        session = _create_session("tool-test", "Jane")
        session["status"] = "generated"
        session["document"] = "# Dossier content"

        result = await dossier_check_status.ainvoke({"dossier_id": "tool-test"})
        assert "GENERATED" in result
        assert "Jane" in result

    @pytest.mark.asyncio
    async def test_dossier_check_status_error(self):
        session = _create_session("err-test", "Jane")
        session["status"] = "error"
        session["document"] = "Something went wrong"

        result = await dossier_check_status.ainvoke({"dossier_id": "err-test"})
        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_dossier_check_status_in_progress(self):
        session = _create_session("prog-test", "Jane")
        session["status"] = "researching"

        result = await dossier_check_status.ainvoke({"dossier_id": "prog-test"})
        assert "RESEARCHING" in result

    @pytest.mark.asyncio
    async def test_dossier_get_document_no_session(self):
        result = await dossier_get_document.ainvoke({"dossier_id": "nonexistent"})
        assert "No dossier found" in result

    @pytest.mark.asyncio
    async def test_dossier_get_document_not_ready(self):
        session = _create_session("doc-test", "Jane")
        session["status"] = "collecting"

        result = await dossier_get_document.ainvoke({"dossier_id": "doc-test"})
        assert "not ready" in result.lower()

    @pytest.mark.asyncio
    async def test_dossier_get_document_success(self):
        session = _create_session("doc-ok", "Jane")
        session["status"] = "generated"
        session["document"] = "# Full dossier document here"

        result = await dossier_get_document.ainvoke({"dossier_id": "doc-ok"})
        assert "# Full dossier document here" == result

    @pytest.mark.asyncio
    async def test_dossier_get_document_empty(self):
        session = _create_session("doc-empty", "Jane")
        session["status"] = "generated"
        session["document"] = ""

        result = await dossier_get_document.ainvoke({"dossier_id": "doc-empty"})
        assert "empty" in result.lower()


# ============================================================================
# Package imports (__init__.py)
# ============================================================================


class TestPackageImports:
    def test_import_main_classes(self):
        from server.tools.dossier_agent import (
            DossierAgent,
            DataCollector,
            ResearchSynthesizer,
            StrategicAnalyzer,
            DossierGenerator,
        )

        assert DossierAgent is not None
        assert DataCollector is not None

    def test_import_data_models(self):
        from server.tools.dossier_agent import (
            CollectedData,
            LinkedInProfile,
            WebSearchResult,
            SynthesizedResearch,
            StrategicInsights,
        )

        assert CollectedData is not None
        assert SynthesizedResearch is not None

    def test_import_tools(self):
        from server.tools.dossier_agent import (
            get_dossier_tools,
            dossier_check_status,
            dossier_generate,
            dossier_update,
            dossier_get_document,
        )

        assert callable(get_dossier_tools)

    def test_import_session_helpers(self):
        from server.tools.dossier_agent import (
            _dossier_sessions,
            _get_session,
            _create_session,
            _clear_session,
        )

        assert isinstance(_dossier_sessions, dict)
        assert callable(_get_session)
