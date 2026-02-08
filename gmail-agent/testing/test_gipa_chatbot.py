"""
Integration tests for GIPA agent through the chatbot and REST API endpoints.

Tests two paths:
1. /gipa/* REST endpoints - Direct programmatic access to the GIPA workflow
2. /chat endpoint - GIPA intent detection and ReAct agent tool invocation

All LLM calls are mocked. Tests exercise the full stack:
   HTTP request -> FastAPI -> GIPARequestAgent -> ClarificationEngine -> DocumentGenerator -> PDF
"""

import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

import httpx

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server.tools.gipa_agent.gipa_agent import _gipa_sessions, _clear_session
from server.tools.gipa_agent.clarification_engine import GIPARequestData, TargetPerson


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

COMPLETE_DATA = {
    "agency_name": "Department of Primary Industries",
    "agency_email": "gipa@dpi.nsw.gov.au",
    "applicant_name": "Jane Doe",
    "applicant_organization": "Environmental Defenders Office",
    "applicant_type": "nonprofit",
    "charity_status": "ABN 12 345 678 901",
    "public_interest_justification": "Koala habitat protection is a matter of significant public interest.",
    "start_date": "1 January 2023",
    "end_date": "31 December 2024",
    "targets": [
        {"name": "John Smith", "role": "Director of Forestry", "direction": "sender"}
    ],
    "keywords": ["koala", "habitat"],
    "jurisdiction": "NSW",
}

COMPLETE_GIPA_DATA = GIPARequestData(
    agency_name="Department of Primary Industries",
    agency_email="gipa@dpi.nsw.gov.au",
    applicant_name="Jane Doe",
    applicant_organization="Environmental Defenders Office",
    applicant_type="nonprofit",
    charity_status="ABN 12 345 678 901",
    public_interest_justification="Koala habitat protection is a matter of significant public interest.",
    start_date="1 January 2023",
    end_date="31 December 2024",
    targets=[
        TargetPerson(name="John Smith", role="Director of Forestry", direction="sender")
    ],
    keywords=["koala", "habitat"],
    jurisdiction="NSW",
    fee_reduction_eligible=True,
    summary_sentence="All correspondence about koala habitat held by DPI.",
)


@pytest.fixture(autouse=True)
def clean_sessions():
    """Clear all GIPA sessions before and after each test."""
    _gipa_sessions.clear()
    yield
    _gipa_sessions.clear()


@pytest.fixture
def app():
    """Create a fresh FastAPI app with the Composio dependency overridden."""
    from server.api import create_app
    from server.dependencies import provide_composio_client

    test_app = create_app()
    # Override the Composio dependency so endpoints don't need a real API key
    test_app.dependency_overrides[provide_composio_client] = lambda: MagicMock()
    return test_app


@pytest.fixture
def mock_clarification_engine():
    """Patch ClarificationEngine in gipa_agent module."""
    with patch("server.tools.gipa_agent.gipa_agent.ClarificationEngine") as mock_cls:
        engine = MagicMock()
        mock_cls.return_value = engine
        yield engine


@pytest.fixture
def mock_synonym_expander():
    """Patch SynonymExpander in gipa_agent module."""
    with patch("server.tools.gipa_agent.gipa_agent.SynonymExpander") as mock_cls:
        expander = MagicMock()
        # expand_keywords is async
        expander.expand_keywords = AsyncMock(
            return_value=[
                'Define "koala" to include Phascolarctos cinereus, koala bear, and all related references.',
                'Define "habitat" to include natural environment, ecosystem, and all related references.',
            ]
        )
        mock_cls.return_value = expander
        yield expander


# ============================================================================
# 1. /gipa/start endpoint
# ============================================================================


class TestGIPAStartEndpoint:
    """Tests for POST /gipa/start."""

    @pytest.mark.asyncio
    async def test_start_returns_collecting_status(self, app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/gipa/start", json={"session_id": "test-s1"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["status"] == "collecting"
        assert "GIPA" in data["message"]

    @pytest.mark.asyncio
    async def test_start_default_session_id(self, app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/gipa/start", json={})

        data = resp.json()
        assert data["success"] is True
        assert "default" in _gipa_sessions

    @pytest.mark.asyncio
    async def test_start_creates_session(self, app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/gipa/start", json={"session_id": "test-s2"})

        assert "test-s2" in _gipa_sessions
        assert _gipa_sessions["test-s2"]["status"] == "collecting"

    @pytest.mark.asyncio
    async def test_start_resets_existing_session(self, app):
        # Pre-populate session with old data
        _gipa_sessions["test-s3"] = {
            "data": {"agency_name": "old"},
            "context": "old context",
            "status": "ready",
            "document": "old doc",
        }

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/gipa/start", json={"session_id": "test-s3"})

        assert resp.json()["success"] is True
        assert _gipa_sessions["test-s3"]["status"] == "collecting"
        assert _gipa_sessions["test-s3"]["data"] == {}


# ============================================================================
# 2. /gipa/answer endpoint
# ============================================================================


class TestGIPAAnswerEndpoint:
    """Tests for POST /gipa/answer."""

    @pytest.mark.asyncio
    async def test_answer_still_collecting(
        self, app, mock_clarification_engine, mock_synonym_expander
    ):
        mock_clarification_engine.extract_variables = AsyncMock(
            return_value=(
                {"agency_name": "DPI", "applicant_name": "Jane Doe"},
                ["What type of applicant are you?"],
                False,
            )
        )

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Start first
            await client.post("/gipa/start", json={"session_id": "test-a1"})
            # Then answer
            resp = await client.post(
                "/gipa/answer",
                json={"session_id": "test-a1", "answer": "DPI, I'm Jane Doe"},
            )

        data = resp.json()
        assert data["success"] is True
        assert data["status"] == "collecting"
        assert "applicant" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_answer_completes_to_ready(
        self, app, mock_clarification_engine, mock_synonym_expander
    ):
        mock_clarification_engine.extract_variables = AsyncMock(
            return_value=(COMPLETE_DATA, [], True)
        )

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/gipa/start", json={"session_id": "test-a2"})
            resp = await client.post(
                "/gipa/answer",
                json={"session_id": "test-a2", "answer": "all my info"},
            )

        data = resp.json()
        assert data["success"] is True
        assert data["status"] == "ready"

    @pytest.mark.asyncio
    async def test_answer_without_start_still_works(
        self, app, mock_clarification_engine, mock_synonym_expander
    ):
        """Answering without /gipa/start should auto-create the session."""
        mock_clarification_engine.extract_variables = AsyncMock(
            return_value=(
                {"agency_name": "DPI"},
                ["What is your name?"],
                False,
            )
        )

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/gipa/answer",
                json={"session_id": "test-a3", "answer": "DPI"},
            )

        # The session was auto-created by _get_or_create_session
        data = resp.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_answer_missing_answer_field(self, app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/gipa/answer",
                json={"session_id": "test-a4"},
            )

        # Pydantic validation error
        assert resp.status_code == 422


# ============================================================================
# 3. /gipa/generate endpoint
# ============================================================================


class TestGIPAGenerateEndpoint:
    """Tests for POST /gipa/generate."""

    @pytest.mark.asyncio
    async def test_generate_success(
        self, app, mock_clarification_engine, mock_synonym_expander
    ):
        """Full flow: start -> answer (complete) -> generate."""
        mock_clarification_engine.extract_variables = AsyncMock(
            return_value=(COMPLETE_DATA, [], True)
        )
        mock_clarification_engine.validate_data.return_value = (True, [])
        mock_clarification_engine.build_gipa_request_data.return_value = (
            COMPLETE_GIPA_DATA
        )

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/gipa/start", json={"session_id": "test-g1"})
            await client.post(
                "/gipa/answer",
                json={"session_id": "test-g1", "answer": "all info here"},
            )
            resp = await client.post("/gipa/generate", json={"session_id": "test-g1"})

        data = resp.json()
        assert data["success"] is True
        assert data["status"] == "generated"
        assert data["document"] is not None
        assert "GIPA" in data["document"]
        assert "## Search Terms" in data["document"]
        assert "## Scope and Definitions" in data["document"]

    @pytest.mark.asyncio
    async def test_generate_fails_with_missing_data(
        self, app, mock_clarification_engine, mock_synonym_expander
    ):
        """generate on an incomplete session should fail."""
        mock_clarification_engine.validate_data.return_value = (
            False,
            ["Missing required field: agency_name"],
        )

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/gipa/start", json={"session_id": "test-g2"})
            resp = await client.post("/gipa/generate", json={"session_id": "test-g2"})

        data = resp.json()
        assert data["success"] is False
        assert "Cannot generate" in data["message"]
        assert data["status"] == "collecting"

    @pytest.mark.asyncio
    async def test_generate_document_contains_fee_reduction(
        self, app, mock_clarification_engine, mock_synonym_expander
    ):
        """Nonprofit should produce a Fee Reduction section."""
        mock_clarification_engine.extract_variables = AsyncMock(
            return_value=(COMPLETE_DATA, [], True)
        )
        mock_clarification_engine.validate_data.return_value = (True, [])
        mock_clarification_engine.build_gipa_request_data.return_value = (
            COMPLETE_GIPA_DATA
        )

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/gipa/start", json={"session_id": "test-g3"})
            await client.post(
                "/gipa/answer",
                json={"session_id": "test-g3", "answer": "all info"},
            )
            resp = await client.post("/gipa/generate", json={"session_id": "test-g3"})

        doc = resp.json()["document"]
        assert "## Fee Reduction Request" in doc
        assert "s.127" in doc or "s 127" in doc.lower()


# ============================================================================
# 4. /gipa/expand-keywords endpoint
# ============================================================================


class TestGIPAExpandKeywordsEndpoint:
    """Tests for POST /gipa/expand-keywords."""

    @pytest.mark.asyncio
    async def test_expand_keywords_success(self, app, mock_synonym_expander):
        # The fixture already sets up expand_keywords as AsyncMock
        # But we need to patch at import time in api.py
        with patch("server.tools.gipa_agent.SynonymExpander") as mock_cls:
            mock_cls.return_value = mock_synonym_expander

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/gipa/expand-keywords",
                    json={"keywords": ["koala", "habitat"]},
                )

        data = resp.json()
        assert data["success"] is True
        assert data["status"] == "completed"
        assert "koala" in data["message"].lower()
        assert "habitat" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_expand_keywords_empty_list_rejected(self, app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/gipa/expand-keywords",
                json={"keywords": []},
            )

        # Pydantic validation rejects empty list (min_length=1)
        assert resp.status_code == 422


# ============================================================================
# 5. Full REST API Pipeline: start -> answer -> answer -> generate -> PDF
# ============================================================================


class TestFullRESTPipeline:
    """End-to-end test through the REST API endpoints."""

    @pytest.mark.asyncio
    async def test_multi_turn_conversation_to_pdf(
        self, app, mock_clarification_engine, mock_synonym_expander
    ):
        """Simulate a realistic multi-turn GIPA conversation via REST."""
        session_id = "pipeline-test-1"

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Turn 1: Start
            resp = await client.post("/gipa/start", json={"session_id": session_id})
            assert resp.json()["success"] is True
            assert resp.json()["status"] == "collecting"

            # Turn 2: Partial info
            mock_clarification_engine.extract_variables = AsyncMock(
                return_value=(
                    {"agency_name": "DPI", "applicant_name": "Jane Doe"},
                    [
                        "What type of applicant are you?",
                        "What keywords should be searched?",
                    ],
                    False,
                )
            )
            resp = await client.post(
                "/gipa/answer",
                json={"session_id": session_id, "answer": "DPI, Jane Doe"},
            )
            assert resp.json()["status"] == "collecting"

            # Turn 3: More info (still incomplete)
            mock_clarification_engine.extract_variables = AsyncMock(
                return_value=(
                    {
                        "agency_name": "DPI",
                        "applicant_name": "Jane Doe",
                        "applicant_type": "nonprofit",
                        "keywords": ["koala"],
                    },
                    ["What date range should be searched?"],
                    False,
                )
            )
            resp = await client.post(
                "/gipa/answer",
                json={
                    "session_id": session_id,
                    "answer": "nonprofit, keywords: koala",
                },
            )
            assert resp.json()["status"] == "collecting"

            # Turn 4: Complete
            mock_clarification_engine.extract_variables = AsyncMock(
                return_value=(COMPLETE_DATA, [], True)
            )
            resp = await client.post(
                "/gipa/answer",
                json={
                    "session_id": session_id,
                    "answer": "Jan 2023 to Dec 2024, all other details...",
                },
            )
            assert resp.json()["status"] == "ready"

            # Turn 5: Generate
            mock_clarification_engine.validate_data.return_value = (True, [])
            mock_clarification_engine.build_gipa_request_data.return_value = (
                COMPLETE_GIPA_DATA
            )
            resp = await client.post("/gipa/generate", json={"session_id": session_id})
            data = resp.json()
            assert data["success"] is True
            assert data["status"] == "generated"
            assert data["document"] is not None

            document = data["document"]

        # Verify the document content
        assert "GIPA" in document
        assert "Jane Doe" in document
        assert "Department of Primary Industries" in document
        assert "## Search Terms" in document
        assert "koala" in document.lower()
        assert "habitat" in document.lower()

        # Now pipe through PDF generator
        from server.tools.pdf_generator import generate_pdf_report

        path = generate_pdf_report.invoke(
            {
                "markdown_content": document,
                "filename": "test_rest_pipeline.pdf",
                "sender_email": "jane@edo.org.au",
                "enable_quote_images": False,
            }
        )
        assert not path.startswith("ERROR"), f"PDF generation failed: {path}"
        assert os.path.isfile(path)
        assert os.path.getsize(path) > 1024

    @pytest.mark.asyncio
    async def test_generate_then_re_answer_rejected(
        self, app, mock_clarification_engine, mock_synonym_expander
    ):
        """After generation, further answers should be rejected."""
        session_id = "pipeline-test-2"

        mock_clarification_engine.extract_variables = AsyncMock(
            return_value=(COMPLETE_DATA, [], True)
        )
        mock_clarification_engine.validate_data.return_value = (True, [])
        mock_clarification_engine.build_gipa_request_data.return_value = (
            COMPLETE_GIPA_DATA
        )

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/gipa/start", json={"session_id": session_id})
            await client.post(
                "/gipa/answer",
                json={"session_id": session_id, "answer": "everything"},
            )
            await client.post("/gipa/generate", json={"session_id": session_id})

            # Now try to answer again
            resp = await client.post(
                "/gipa/answer",
                json={"session_id": session_id, "answer": "more info"},
            )

        data = resp.json()
        assert "already been generated" in data["message"]


# ============================================================================
# 6. Chatbot Intent Detection
# ============================================================================


class TestChatbotIntentDetection:
    """Test that GIPA-related messages are detected as tool intents."""

    def test_gipa_keyword_detected(self):
        """Regex should match GIPA-related keywords."""
        import re

        pattern = r"\b(gipa|foi|freedom of information|government information|public access|information request|information access|right to information|rti)\b"

        matches = [
            "I want to make a GIPA request",
            "Help me with an FOI application",
            "I need freedom of information access",
            "government information request for DPI",
            "right to information request NSW",
            "RTI request Queensland",
        ]
        for msg in matches:
            assert re.search(pattern, msg, re.IGNORECASE), f"Should match: {msg}"

        no_matches = [
            "What's the weather today?",
            "Tell me a joke",
            "How do I cook pasta?",
        ]
        for msg in no_matches:
            assert not re.search(pattern, msg, re.IGNORECASE), (
                f"Should NOT match: {msg}"
            )


# ============================================================================
# 7. Chatbot /chat Endpoint with GIPA Tools
# ============================================================================


class TestChatEndpointGIPA:
    """Test the /chat endpoint with GIPA-related messages.

    These tests mock the LLM but let the full agent pipeline run,
    verifying that GIPA tools are available and intent detection works.
    """

    @pytest.mark.asyncio
    async def test_gipa_message_triggers_tool_intent(self, app):
        """A GIPA message should be detected as tool intent (not direct Gemini)."""
        # We mock the entire agent execution to avoid real LLM calls
        with patch("server.chatbot.run_agent_with_fallback") as mock_run:
            mock_state = {
                "messages": [
                    MagicMock(
                        content="I'll help you with your GIPA request. Let me start the process."
                    )
                ]
            }
            mock_run.return_value = (mock_state, "groq")

            # Need GROQ_API_KEY for the chat endpoint
            with patch.dict(os.environ, {"GROQ_API_KEY": "fake-key"}):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://test"
                ) as client:
                    resp = await client.post(
                        "/chat",
                        json={
                            "message": "I want to make a GIPA request for DPI",
                            "user_id": "test-user",
                            "auto_execute": False,
                        },
                    )

            data = resp.json()
            assert data["type"] == "final_result"
            assert "GIPA" in data["message"]
            # Should have used the agent (not direct Gemini)
            assert data["intent"]["action"] == "autonomous_agent"

    @pytest.mark.asyncio
    async def test_non_gipa_message_skips_agent(self, app):
        """A non-tool message should go to direct Gemini, not the agent."""
        with patch("server.chatbot.ChatGoogleGenerativeAI") as mock_gemini_cls:
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = MagicMock(content="Hello! How can I help?")
            mock_gemini_cls.return_value = mock_llm

            with patch.dict(
                os.environ,
                {"GROQ_API_KEY": "fake-key", "GOOGLE_API_KEY": "fake-key"},
            ):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://test"
                ) as client:
                    resp = await client.post(
                        "/chat",
                        json={
                            "message": "Hello there",
                            "user_id": "test-user",
                            "auto_execute": False,
                        },
                    )

            data = resp.json()
            assert data["intent"]["action"] == "direct_gemini"


# ============================================================================
# 8. GIPA Tools in Agent Tool List
# ============================================================================


class TestGIPAToolsInAgent:
    """Verify GIPA tools are included in the agent's tool list."""

    def test_gipa_tools_in_get_agent_tools(self):
        """get_agent_tools should include all 4 GIPA tools."""
        with patch("server.chatbot.Composio"):
            from server.chatbot import get_agent_tools

            tools = get_agent_tools("test-user")
            tool_names = [t.name for t in tools]

            assert "gipa_start_request" in tool_names
            assert "gipa_process_answer" in tool_names
            assert "gipa_generate_document" in tool_names
            assert "gipa_expand_keywords" in tool_names

    def test_gipa_tools_have_descriptions(self):
        """Each GIPA tool should have a meaningful description."""
        from server.tools.gipa_agent import get_gipa_tools

        tools = get_gipa_tools()
        for tool in tools:
            assert len(tool.description) > 20, f"Tool {tool.name} description too short"


# ============================================================================
# 9. Session Isolation Between Endpoints
# ============================================================================


class TestSessionIsolation:
    """Verify that sessions are properly isolated between concurrent requests."""

    @pytest.mark.asyncio
    async def test_two_sessions_dont_interfere(
        self, app, mock_clarification_engine, mock_synonym_expander
    ):
        """Two concurrent sessions should maintain independent state."""
        mock_clarification_engine.extract_variables = AsyncMock(
            side_effect=[
                # Session A: partial
                ({"agency_name": "DPI"}, ["What keywords?"], False),
                # Session B: complete
                (COMPLETE_DATA, [], True),
            ]
        )

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Start both sessions
            await client.post("/gipa/start", json={"session_id": "iso-A"})
            await client.post("/gipa/start", json={"session_id": "iso-B"})

            # Answer in session A (partial)
            resp_a = await client.post(
                "/gipa/answer",
                json={"session_id": "iso-A", "answer": "DPI"},
            )
            # Answer in session B (complete)
            resp_b = await client.post(
                "/gipa/answer",
                json={"session_id": "iso-B", "answer": "all info"},
            )

        assert resp_a.json()["status"] == "collecting"
        assert resp_b.json()["status"] == "ready"
        assert _gipa_sessions["iso-A"]["status"] == "collecting"
        assert _gipa_sessions["iso-B"]["status"] == "ready"


# ============================================================================
# 10. Error Handling
# ============================================================================


class TestErrorHandling:
    """Test error responses from the GIPA endpoints."""

    @pytest.mark.asyncio
    async def test_generate_unknown_session_creates_empty(self, app):
        """Generating for an unknown session should fail (empty data)."""
        with patch(
            "server.tools.gipa_agent.gipa_agent.ClarificationEngine"
        ) as mock_cls:
            engine = MagicMock()
            engine.validate_data.return_value = (
                False,
                ["Missing required field: agency_name"],
            )
            mock_cls.return_value = engine

            with patch("server.tools.gipa_agent.gipa_agent.SynonymExpander"):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://test"
                ) as client:
                    resp = await client.post(
                        "/gipa/generate",
                        json={"session_id": "nonexistent-session"},
                    )

        data = resp.json()
        assert data["success"] is False
        assert "Cannot generate" in data["message"]

    @pytest.mark.asyncio
    async def test_expand_keywords_invalid_body(self, app):
        """Invalid request body should return 422."""
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/gipa/expand-keywords",
                json={"wrong_field": "data"},
            )

        assert resp.status_code == 422


# ============================================================================
# 11. Response Model Validation
# ============================================================================


class TestResponseModel:
    """Verify GIPAResponse fields are properly populated."""

    @pytest.mark.asyncio
    async def test_start_response_shape(self, app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/gipa/start", json={"session_id": "shape-1"})

        data = resp.json()
        assert "success" in data
        assert "message" in data
        assert "status" in data
        assert "document" in data  # should be None
        assert "error" in data  # should be None
        assert data["document"] is None
        assert data["error"] is None

    @pytest.mark.asyncio
    async def test_generate_response_has_document(
        self, app, mock_clarification_engine, mock_synonym_expander
    ):
        mock_clarification_engine.extract_variables = AsyncMock(
            return_value=(COMPLETE_DATA, [], True)
        )
        mock_clarification_engine.validate_data.return_value = (True, [])
        mock_clarification_engine.build_gipa_request_data.return_value = (
            COMPLETE_GIPA_DATA
        )

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/gipa/start", json={"session_id": "shape-2"})
            await client.post(
                "/gipa/answer",
                json={"session_id": "shape-2", "answer": "all info"},
            )
            resp = await client.post("/gipa/generate", json={"session_id": "shape-2"})

        data = resp.json()
        assert data["document"] is not None
        assert isinstance(data["document"], str)
        assert len(data["document"]) > 100


# ============================================================================
# 12. System Prompt Contains GIPA Instructions
# ============================================================================


class TestSystemPrompt:
    """Verify the GIPA section is present in the system prompt."""

    def test_system_prompt_has_gipa_section(self):
        from server.chatbot import SYSTEM_PROMPT

        assert "GIPA" in SYSTEM_PROMPT
        assert "gipa_start_request" in SYSTEM_PROMPT
        assert "gipa_process_answer" in SYSTEM_PROMPT
        assert "gipa_generate_document" in SYSTEM_PROMPT

    def test_system_prompt_has_workflow_steps(self):
        from server.chatbot import SYSTEM_PROMPT

        assert "Start" in SYSTEM_PROMPT
        assert "Collect" in SYSTEM_PROMPT
        assert "Generate" in SYSTEM_PROMPT
