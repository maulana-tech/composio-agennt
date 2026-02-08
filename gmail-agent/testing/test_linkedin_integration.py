"""
Tests for LinkedIn Integration.

Covers:
  - LinkedIn Pydantic models (LinkedInPostRequest, LinkedInDeletePostRequest, etc.)
  - LinkedIn action functions (create_linkedin_post, delete_linkedin_post, etc.)
  - LinkedIn auth function (check_linkedin_connected)
  - LinkedIn API endpoints (4 action endpoints + platform checks + toolkits)
  - LinkedIn chatbot tools (4 @tool functions in get_agent_tools)
  - SYSTEM_PROMPT LinkedIn references (tools list, workflow section, intent keywords)
  - Intent detection regex for LinkedIn keywords

Run with:
    .venv/bin/python -m pytest testing/test_linkedin_integration.py -v
"""

import re
import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------
from server.models import (
    LinkedInPostRequest,
    LinkedInDeletePostRequest,
    LinkedInMyInfoRequest,
    LinkedInCompanyInfoRequest,
    ToolExecutionResponse,
)
from server.actions import (
    create_linkedin_post,
    delete_linkedin_post,
    get_linkedin_my_info,
    get_linkedin_company_info,
)
from server.auth import (
    check_linkedin_connected,
    get_connected_accounts,
)


# ============================================================================
# 1. PYDANTIC MODELS
# ============================================================================


class TestLinkedInPostRequest:
    def test_defaults(self):
        req = LinkedInPostRequest(
            author="urn:li:person:123", commentary="Hello LinkedIn"
        )
        assert req.user_id == "default"
        assert req.author == "urn:li:person:123"
        assert req.commentary == "Hello LinkedIn"
        assert req.visibility == "PUBLIC"
        assert req.lifecycle_state == "PUBLISHED"
        assert req.is_reshare_disabled is False

    def test_custom_values(self):
        req = LinkedInPostRequest(
            user_id="user1",
            author="urn:li:organization:456",
            commentary="Company update",
            visibility="CONNECTIONS",
            lifecycle_state="PUBLISHED",
            is_reshare_disabled=True,
        )
        assert req.user_id == "user1"
        assert req.visibility == "CONNECTIONS"
        assert req.is_reshare_disabled is True

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            LinkedInPostRequest(author="urn:li:person:123")  # missing commentary
        with pytest.raises(ValidationError):
            LinkedInPostRequest(commentary="Hello")  # missing author

    def test_serialization(self):
        req = LinkedInPostRequest(author="urn:li:person:123", commentary="Test")
        data = req.model_dump()
        assert data["author"] == "urn:li:person:123"
        assert data["commentary"] == "Test"
        assert data["visibility"] == "PUBLIC"


class TestLinkedInDeletePostRequest:
    def test_defaults(self):
        req = LinkedInDeletePostRequest(share_id="share123")
        assert req.user_id == "default"
        assert req.share_id == "share123"

    def test_missing_share_id(self):
        with pytest.raises(ValidationError):
            LinkedInDeletePostRequest()

    def test_custom_user_id(self):
        req = LinkedInDeletePostRequest(user_id="user2", share_id="abc")
        assert req.user_id == "user2"


class TestLinkedInMyInfoRequest:
    def test_defaults(self):
        req = LinkedInMyInfoRequest()
        assert req.user_id == "default"

    def test_custom_user_id(self):
        req = LinkedInMyInfoRequest(user_id="user3")
        assert req.user_id == "user3"


class TestLinkedInCompanyInfoRequest:
    def test_defaults(self):
        req = LinkedInCompanyInfoRequest()
        assert req.user_id == "default"
        assert req.count is None
        assert req.role is None
        assert req.start is None
        assert req.state is None

    def test_custom_values(self):
        req = LinkedInCompanyInfoRequest(
            user_id="user4", count=10, role="ADMINISTRATOR", start=0, state="ACTIVE"
        )
        assert req.count == 10
        assert req.role == "ADMINISTRATOR"
        assert req.start == 0
        assert req.state == "ACTIVE"


# ============================================================================
# 2. ACTION FUNCTIONS
# ============================================================================


class TestCreateLinkedInPost:
    def test_basic_post(self):
        mock_client = MagicMock()
        mock_client.tools.execute.return_value = {"data": {"id": "share123"}}
        result = create_linkedin_post(
            mock_client, "user1", "urn:li:person:123", "Hello world"
        )
        assert result == {"data": {"id": "share123"}}
        mock_client.tools.execute.assert_called_once_with(
            slug="LINKEDIN_CREATE_LINKED_IN_POST",
            arguments={
                "author": "urn:li:person:123",
                "commentary": "Hello world",
                "visibility": "PUBLIC",
                "lifecycleState": "PUBLISHED",
            },
            user_id="user1",
            dangerously_skip_version_check=True,
        )

    def test_custom_visibility(self):
        mock_client = MagicMock()
        mock_client.tools.execute.return_value = {"data": {"id": "share456"}}
        result = create_linkedin_post(
            mock_client,
            "user1",
            "urn:li:person:123",
            "Hello",
            visibility="CONNECTIONS",
            lifecycle_state="PUBLISHED",
        )
        args = mock_client.tools.execute.call_args
        assert args[1]["arguments"]["visibility"] == "CONNECTIONS"

    def test_exception_propagates(self):
        mock_client = MagicMock()
        mock_client.tools.execute.side_effect = Exception("API error")
        with pytest.raises(Exception, match="API error"):
            create_linkedin_post(mock_client, "user1", "urn:li:person:123", "Hello")


class TestDeleteLinkedInPost:
    def test_delete(self):
        mock_client = MagicMock()
        mock_client.tools.execute.return_value = {"data": {"success": True}}
        result = delete_linkedin_post(mock_client, "user1", "share123")
        assert result == {"data": {"success": True}}
        mock_client.tools.execute.assert_called_once_with(
            slug="LINKEDIN_DELETE_LINKED_IN_POST",
            arguments={"share_id": "share123"},
            user_id="user1",
            dangerously_skip_version_check=True,
        )

    def test_exception_propagates(self):
        mock_client = MagicMock()
        mock_client.tools.execute.side_effect = RuntimeError("Not found")
        with pytest.raises(RuntimeError, match="Not found"):
            delete_linkedin_post(mock_client, "user1", "bad_id")


class TestGetLinkedInMyInfo:
    def test_get_info(self):
        mock_client = MagicMock()
        mock_client.tools.execute.return_value = {
            "data": {"author_id": "urn:li:person:123", "name": "John Doe"}
        }
        result = get_linkedin_my_info(mock_client, "user1")
        assert result["data"]["author_id"] == "urn:li:person:123"
        mock_client.tools.execute.assert_called_once_with(
            slug="LINKEDIN_GET_MY_INFO",
            arguments={},
            user_id="user1",
            dangerously_skip_version_check=True,
        )


class TestGetLinkedInCompanyInfo:
    def test_no_params(self):
        mock_client = MagicMock()
        mock_client.tools.execute.return_value = {"data": []}
        result = get_linkedin_company_info(mock_client, "user1")
        assert result == {"data": []}
        mock_client.tools.execute.assert_called_once_with(
            slug="LINKEDIN_GET_COMPANY_INFO",
            arguments={},
            user_id="user1",
            dangerously_skip_version_check=True,
        )

    def test_with_role(self):
        mock_client = MagicMock()
        mock_client.tools.execute.return_value = {"data": [{"name": "Acme"}]}
        result = get_linkedin_company_info(mock_client, "user1", role="ADMINISTRATOR")
        args = mock_client.tools.execute.call_args
        assert args[1]["arguments"]["role"] == "ADMINISTRATOR"

    def test_with_all_params(self):
        mock_client = MagicMock()
        mock_client.tools.execute.return_value = {"data": []}
        get_linkedin_company_info(
            mock_client, "user1", count=5, role="ADMINISTRATOR", start=0, state="ACTIVE"
        )
        args = mock_client.tools.execute.call_args
        assert args[1]["arguments"] == {
            "count": 5,
            "role": "ADMINISTRATOR",
            "start": 0,
            "state": "ACTIVE",
        }

    def test_optional_params_not_sent_when_none(self):
        mock_client = MagicMock()
        mock_client.tools.execute.return_value = {}
        get_linkedin_company_info(mock_client, "user1", count=None, role=None)
        args = mock_client.tools.execute.call_args
        assert args[1]["arguments"] == {}


# ============================================================================
# 3. AUTH FUNCTIONS
# ============================================================================


class TestCheckLinkedInConnected:
    def test_connected(self):
        mock_client = MagicMock()
        mock_account = MagicMock()
        mock_account.status = "ACTIVE"
        mock_client.connected_accounts.list.return_value = MagicMock(
            items=[mock_account]
        )
        assert check_linkedin_connected(mock_client, "user1") is True
        mock_client.connected_accounts.list.assert_called_once_with(
            user_ids=["user1"],
            toolkit_slugs=["LINKEDIN"],
        )

    def test_not_connected(self):
        mock_client = MagicMock()
        mock_client.connected_accounts.list.return_value = MagicMock(items=[])
        assert check_linkedin_connected(mock_client, "user1") is False

    def test_inactive_account(self):
        mock_client = MagicMock()
        mock_account = MagicMock()
        mock_account.status = "PENDING"
        mock_client.connected_accounts.list.return_value = MagicMock(
            items=[mock_account]
        )
        assert check_linkedin_connected(mock_client, "user1") is False


class TestGetConnectedAccountsIncludesLinkedIn:
    def test_linkedin_in_toolkits(self):
        """Verify LINKEDIN is queried by get_connected_accounts."""
        mock_client = MagicMock()
        mock_client.connected_accounts.list.return_value = MagicMock(items=[])
        result = get_connected_accounts(mock_client, "user1")
        assert "LINKEDIN" in result
        # Verify it was called with LINKEDIN as one of the toolkit slugs
        toolkit_slugs_used = [
            call[1]["toolkit_slugs"][0]
            for call in mock_client.connected_accounts.list.call_args_list
        ]
        assert "LINKEDIN" in toolkit_slugs_used


# ============================================================================
# 4. CHATBOT TOOL FUNCTIONS
# ============================================================================


class TestChatbotLinkedInTools:
    """Test that LinkedIn tools are registered in get_agent_tools()."""

    @patch("server.chatbot.create_serper_tools", return_value=[])
    @patch("server.chatbot.create_grounding_tools", return_value=[])
    @patch("server.chatbot.generate_pdf_report", MagicMock())
    @patch("server.chatbot.generate_quote_image_tool", MagicMock())
    @patch("server.chatbot.generate_and_send_quote_email", MagicMock())
    @patch("server.chatbot.generate_dalle_quote_image_tool", MagicMock())
    @patch("server.chatbot.generate_quote_with_person_photo", MagicMock())
    @patch("server.chatbot.get_gipa_tools", return_value=[])
    @patch("server.chatbot.get_dossier_tools", return_value=[])
    @patch("server.chatbot.Composio")
    def test_linkedin_tools_registered(self, mock_composio_cls, *mocks):
        from server.chatbot import get_agent_tools

        mock_composio_cls.return_value = MagicMock()
        tools = get_agent_tools("test_user")
        tool_names = [t.name for t in tools]

        assert "LINKEDIN_GET_MY_INFO" in tool_names
        assert "LINKEDIN_CREATE_POST" in tool_names
        assert "LINKEDIN_DELETE_POST" in tool_names
        assert "LINKEDIN_GET_COMPANY_INFO" in tool_names

    @patch("server.chatbot.create_serper_tools", return_value=[])
    @patch("server.chatbot.create_grounding_tools", return_value=[])
    @patch("server.chatbot.generate_pdf_report", MagicMock())
    @patch("server.chatbot.generate_quote_image_tool", MagicMock())
    @patch("server.chatbot.generate_and_send_quote_email", MagicMock())
    @patch("server.chatbot.generate_dalle_quote_image_tool", MagicMock())
    @patch("server.chatbot.generate_quote_with_person_photo", MagicMock())
    @patch("server.chatbot.get_gipa_tools", return_value=[])
    @patch("server.chatbot.get_dossier_tools", return_value=[])
    @patch("server.chatbot.Composio")
    def test_linkedin_tool_count(self, mock_composio_cls, *mocks):
        from server.chatbot import get_agent_tools

        mock_composio_cls.return_value = MagicMock()
        tools = get_agent_tools("test_user")
        linkedin_tools = [
            t
            for t in tools
            if isinstance(t.name, str) and t.name.startswith("LINKEDIN_")
        ]
        assert len(linkedin_tools) == 4

    @patch("server.chatbot.create_serper_tools", return_value=[])
    @patch("server.chatbot.create_grounding_tools", return_value=[])
    @patch("server.chatbot.generate_pdf_report", MagicMock())
    @patch("server.chatbot.generate_quote_image_tool", MagicMock())
    @patch("server.chatbot.generate_and_send_quote_email", MagicMock())
    @patch("server.chatbot.generate_dalle_quote_image_tool", MagicMock())
    @patch("server.chatbot.generate_quote_with_person_photo", MagicMock())
    @patch("server.chatbot.get_gipa_tools", return_value=[])
    @patch("server.chatbot.get_dossier_tools", return_value=[])
    @patch("server.chatbot.Composio")
    def test_linkedin_get_my_info_tool_calls_composio(self, mock_composio_cls, *mocks):
        """Test that LINKEDIN_GET_MY_INFO tool function calls Composio correctly."""
        from server.chatbot import get_agent_tools

        mock_client = MagicMock()
        mock_client.tools.execute.return_value = {
            "data": {"author_id": "urn:li:person:123"}
        }
        mock_composio_cls.return_value = mock_client

        tools = get_agent_tools("test_user")
        my_info_tool = next(t for t in tools if t.name == "LINKEDIN_GET_MY_INFO")
        result = my_info_tool.invoke({})
        mock_client.tools.execute.assert_called_with(
            slug="LINKEDIN_GET_MY_INFO",
            arguments={},
            user_id="test_user",
            dangerously_skip_version_check=True,
        )

    @patch("server.chatbot.create_serper_tools", return_value=[])
    @patch("server.chatbot.create_grounding_tools", return_value=[])
    @patch("server.chatbot.generate_pdf_report", MagicMock())
    @patch("server.chatbot.generate_quote_image_tool", MagicMock())
    @patch("server.chatbot.generate_and_send_quote_email", MagicMock())
    @patch("server.chatbot.generate_dalle_quote_image_tool", MagicMock())
    @patch("server.chatbot.generate_quote_with_person_photo", MagicMock())
    @patch("server.chatbot.get_gipa_tools", return_value=[])
    @patch("server.chatbot.get_dossier_tools", return_value=[])
    @patch("server.chatbot.Composio")
    def test_linkedin_create_post_tool_calls_composio(self, mock_composio_cls, *mocks):
        """Test that LINKEDIN_CREATE_POST tool function calls Composio correctly."""
        from server.chatbot import get_agent_tools

        mock_client = MagicMock()
        mock_client.tools.execute.return_value = {"data": {"id": "share123"}}
        mock_composio_cls.return_value = mock_client

        tools = get_agent_tools("test_user")
        post_tool = next(t for t in tools if t.name == "LINKEDIN_CREATE_POST")
        result = post_tool.invoke(
            {
                "author": "urn:li:person:123",
                "commentary": "Hello LinkedIn!",
                "visibility": "PUBLIC",
            }
        )
        mock_client.tools.execute.assert_called_with(
            slug="LINKEDIN_CREATE_LINKED_IN_POST",
            arguments={
                "author": "urn:li:person:123",
                "commentary": "Hello LinkedIn!",
                "visibility": "PUBLIC",
                "lifecycleState": "PUBLISHED",
            },
            user_id="test_user",
            dangerously_skip_version_check=True,
        )

    @patch("server.chatbot.create_serper_tools", return_value=[])
    @patch("server.chatbot.create_grounding_tools", return_value=[])
    @patch("server.chatbot.generate_pdf_report", MagicMock())
    @patch("server.chatbot.generate_quote_image_tool", MagicMock())
    @patch("server.chatbot.generate_and_send_quote_email", MagicMock())
    @patch("server.chatbot.generate_dalle_quote_image_tool", MagicMock())
    @patch("server.chatbot.generate_quote_with_person_photo", MagicMock())
    @patch("server.chatbot.get_gipa_tools", return_value=[])
    @patch("server.chatbot.get_dossier_tools", return_value=[])
    @patch("server.chatbot.Composio")
    def test_linkedin_delete_post_tool_calls_composio(self, mock_composio_cls, *mocks):
        """Test that LINKEDIN_DELETE_POST tool function calls Composio correctly."""
        from server.chatbot import get_agent_tools

        mock_client = MagicMock()
        mock_client.tools.execute.return_value = {"data": {"deleted": True}}
        mock_composio_cls.return_value = mock_client

        tools = get_agent_tools("test_user")
        delete_tool = next(t for t in tools if t.name == "LINKEDIN_DELETE_POST")
        result = delete_tool.invoke({"share_id": "share123"})
        mock_client.tools.execute.assert_called_with(
            slug="LINKEDIN_DELETE_LINKED_IN_POST",
            arguments={"share_id": "share123"},
            user_id="test_user",
            dangerously_skip_version_check=True,
        )

    @patch("server.chatbot.create_serper_tools", return_value=[])
    @patch("server.chatbot.create_grounding_tools", return_value=[])
    @patch("server.chatbot.generate_pdf_report", MagicMock())
    @patch("server.chatbot.generate_quote_image_tool", MagicMock())
    @patch("server.chatbot.generate_and_send_quote_email", MagicMock())
    @patch("server.chatbot.generate_dalle_quote_image_tool", MagicMock())
    @patch("server.chatbot.generate_quote_with_person_photo", MagicMock())
    @patch("server.chatbot.get_gipa_tools", return_value=[])
    @patch("server.chatbot.get_dossier_tools", return_value=[])
    @patch("server.chatbot.Composio")
    def test_linkedin_get_company_info_tool_calls_composio(
        self, mock_composio_cls, *mocks
    ):
        """Test that LINKEDIN_GET_COMPANY_INFO tool function calls Composio correctly."""
        from server.chatbot import get_agent_tools

        mock_client = MagicMock()
        mock_client.tools.execute.return_value = {"data": []}
        mock_composio_cls.return_value = mock_client

        tools = get_agent_tools("test_user")
        company_tool = next(t for t in tools if t.name == "LINKEDIN_GET_COMPANY_INFO")
        result = company_tool.invoke({"role": "ADMINISTRATOR"})
        mock_client.tools.execute.assert_called_with(
            slug="LINKEDIN_GET_COMPANY_INFO",
            arguments={"role": "ADMINISTRATOR"},
            user_id="test_user",
            dangerously_skip_version_check=True,
        )

    @patch("server.chatbot.create_serper_tools", return_value=[])
    @patch("server.chatbot.create_grounding_tools", return_value=[])
    @patch("server.chatbot.generate_pdf_report", MagicMock())
    @patch("server.chatbot.generate_quote_image_tool", MagicMock())
    @patch("server.chatbot.generate_and_send_quote_email", MagicMock())
    @patch("server.chatbot.generate_dalle_quote_image_tool", MagicMock())
    @patch("server.chatbot.generate_quote_with_person_photo", MagicMock())
    @patch("server.chatbot.get_gipa_tools", return_value=[])
    @patch("server.chatbot.get_dossier_tools", return_value=[])
    @patch("server.chatbot.Composio")
    def test_linkedin_tool_error_handling(self, mock_composio_cls, *mocks):
        """Test that LinkedIn tools return error strings on exception."""
        from server.chatbot import get_agent_tools

        mock_client = MagicMock()
        mock_client.tools.execute.side_effect = Exception("Connection refused")
        mock_composio_cls.return_value = mock_client

        tools = get_agent_tools("test_user")

        my_info_tool = next(t for t in tools if t.name == "LINKEDIN_GET_MY_INFO")
        result = my_info_tool.invoke({})
        assert "Error" in result
        assert "Connection refused" in result

        post_tool = next(t for t in tools if t.name == "LINKEDIN_CREATE_POST")
        result = post_tool.invoke(
            {
                "author": "urn:li:person:123",
                "commentary": "test",
            }
        )
        assert "Error" in result

        delete_tool = next(t for t in tools if t.name == "LINKEDIN_DELETE_POST")
        result = delete_tool.invoke({"share_id": "abc"})
        assert "Error" in result

        company_tool = next(t for t in tools if t.name == "LINKEDIN_GET_COMPANY_INFO")
        result = company_tool.invoke({})
        assert "Error" in result


# ============================================================================
# 5. SYSTEM_PROMPT VERIFICATION
# ============================================================================


class TestSystemPromptLinkedIn:
    def test_prompt_lists_linkedin_tools(self):
        from server.chatbot import SYSTEM_PROMPT

        assert "linkedin_get_my_info" in SYSTEM_PROMPT
        assert "linkedin_create_post" in SYSTEM_PROMPT
        assert "linkedin_delete_post" in SYSTEM_PROMPT
        assert "linkedin_get_company_info" in SYSTEM_PROMPT

    def test_prompt_has_linkedin_workflow_section(self):
        from server.chatbot import SYSTEM_PROMPT

        assert "### LinkedIn Integration:" in SYSTEM_PROMPT

    def test_prompt_mentions_author_urn_workflow(self):
        from server.chatbot import SYSTEM_PROMPT

        assert "linkedin_get_my_info" in SYSTEM_PROMPT
        assert (
            "author_id" in SYSTEM_PROMPT
            or "author URN" in SYSTEM_PROMPT
            or "author" in SYSTEM_PROMPT
        )

    def test_prompt_mentions_visibility_options(self):
        from server.chatbot import SYSTEM_PROMPT

        assert "PUBLIC" in SYSTEM_PROMPT
        assert "CONNECTIONS" in SYSTEM_PROMPT

    def test_prompt_mentions_company_posts(self):
        from server.chatbot import SYSTEM_PROMPT

        assert (
            "organization" in SYSTEM_PROMPT.lower()
            or "company" in SYSTEM_PROMPT.lower()
        )

    def test_prompt_critical_workflow_order(self):
        """Verify the prompt instructs to get author info FIRST."""
        from server.chatbot import SYSTEM_PROMPT

        assert "ALWAYS call `linkedin_get_my_info` FIRST" in SYSTEM_PROMPT


# ============================================================================
# 6. INTENT DETECTION
# ============================================================================


class TestIntentDetectionLinkedIn:
    """Test that LinkedIn keywords trigger tool intent detection."""

    def _get_tool_keywords(self):
        """Extract tool_keywords patterns from the chat function source."""
        import inspect
        from server.chatbot import chat

        source = inspect.getsource(chat)
        # Extract patterns between tool_keywords = [ and ]
        match = re.search(r"tool_keywords\s*=\s*\[(.*?)\]", source, re.DOTALL)
        assert match, "Could not find tool_keywords in chat source"
        return match.group(1)

    def test_linkedin_keyword_pattern_exists(self):
        keywords_source = self._get_tool_keywords()
        assert "linkedin" in keywords_source.lower()

    def test_linkedin_keywords_match(self):
        """Test that various LinkedIn-related phrases match the regex."""
        keywords_source = self._get_tool_keywords()

        # Extract all regex patterns
        patterns = re.findall(r'r"([^"]+)"', keywords_source)

        linkedin_phrases = [
            "post on linkedin",
            "linkedin post",
            "linkedin article",
            "linkedin profile",
            "linkedin company",
            "linkedin connection",
            "linked in",
        ]

        for phrase in linkedin_phrases:
            matched = any(
                re.search(pattern, phrase, re.IGNORECASE) for pattern in patterns
            )
            assert matched, f"Phrase '{phrase}' did not match any tool_keyword pattern"


# ============================================================================
# 7. API ENDPOINT INTEGRATION
# ============================================================================


class TestAPILinkedInEndpoints:
    """Test LinkedIn API endpoint registration and behavior via TestClient."""

    @pytest.fixture
    def client(self):
        """Create a FastAPI test client with mocked dependencies."""
        from fastapi.testclient import TestClient

        # Mock ComposioClient dependency
        mock_composio = MagicMock()
        mock_account = MagicMock()
        mock_account.status = "ACTIVE"
        mock_composio.connected_accounts.list.return_value = MagicMock(
            items=[mock_account]
        )
        mock_composio.tools.execute.return_value = {"data": {"success": True}}

        from server.api import create_app

        app = create_app()

        # Override the dependency
        from server.dependencies import provide_composio_client

        app.dependency_overrides[provide_composio_client] = lambda: mock_composio

        return TestClient(app), mock_composio

    def test_linkedin_my_info_endpoint_exists(self, client):
        test_client, mock_composio = client
        response = test_client.get("/actions/linkedin/my_info?user_id=test")
        assert response.status_code == 200
        data = response.json()
        assert "successful" in data

    def test_linkedin_post_endpoint_exists(self, client):
        test_client, mock_composio = client
        response = test_client.post(
            "/actions/linkedin/post",
            json={
                "user_id": "test",
                "author": "urn:li:person:123",
                "commentary": "Hello LinkedIn!",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["successful"] is True

    def test_linkedin_delete_post_endpoint_exists(self, client):
        test_client, mock_composio = client
        response = test_client.post(
            "/actions/linkedin/delete_post",
            json={"user_id": "test", "share_id": "share123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["successful"] is True

    def test_linkedin_company_info_endpoint_exists(self, client):
        test_client, mock_composio = client
        response = test_client.get(
            "/actions/linkedin/company_info?user_id=test&role=ADMINISTRATOR"
        )
        assert response.status_code == 200
        data = response.json()
        assert "successful" in data

    def test_linkedin_post_endpoint_calls_action(self, client):
        test_client, mock_composio = client
        mock_composio.tools.execute.return_value = {"data": {"id": "new_share_id"}}
        response = test_client.post(
            "/actions/linkedin/post",
            json={
                "user_id": "test",
                "author": "urn:li:person:456",
                "commentary": "My post content",
                "visibility": "CONNECTIONS",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["successful"] is True

    def test_linkedin_post_endpoint_error_handling(self, client):
        test_client, mock_composio = client
        mock_composio.tools.execute.side_effect = Exception("LinkedIn API error")
        response = test_client.post(
            "/actions/linkedin/post",
            json={
                "user_id": "test",
                "author": "urn:li:person:123",
                "commentary": "test",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["successful"] is False
        assert "LinkedIn API error" in data["error"]

    def test_linkedin_delete_endpoint_error_handling(self, client):
        test_client, mock_composio = client
        mock_composio.tools.execute.side_effect = Exception("Not found")
        response = test_client.post(
            "/actions/linkedin/delete_post",
            json={"user_id": "test", "share_id": "bad_id"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["successful"] is False
        assert "Not found" in data["error"]


class TestAPIPlatformChecks:
    """Test that LinkedIn is included in platform checks."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        mock_composio = MagicMock()
        mock_account = MagicMock()
        mock_account.status = "ACTIVE"
        mock_account.id = "acc123"
        mock_account.created_at = "2025-01-01"
        mock_composio.connected_accounts.list.return_value = MagicMock(
            items=[mock_account]
        )

        from server.api import create_app

        app = create_app()

        from server.dependencies import provide_composio_client

        app.dependency_overrides[provide_composio_client] = lambda: mock_composio

        return TestClient(app), mock_composio

    def test_linkedin_in_valid_platforms(self, client):
        """Test that LINKEDIN is accepted as a valid platform for connection."""
        test_client, mock_composio = client
        mock_composio.connected_accounts.list.return_value = MagicMock(items=[])

        # This should not return 400 (invalid platform)
        # It may fail for other reasons (auth config), but not platform validation
        response = test_client.post("/connections/test_user/connect/LINKEDIN")
        # Should not be 400 with "Invalid platform" message
        if response.status_code == 400:
            assert "Invalid platform" not in response.json().get("detail", "")

    def test_linkedin_platform_status(self, client):
        """Test that LINKEDIN platform status check works."""
        test_client, mock_composio = client

        # Mock for the check_linkedin_connected call
        mock_account = MagicMock()
        mock_account.status = "ACTIVE"
        mock_composio.connected_accounts.list.return_value = MagicMock(
            items=[mock_account]
        )

        response = test_client.get("/connections/test_user/LINKEDIN/status")
        assert response.status_code == 200
        data = response.json()
        assert data["platform"] == "LINKEDIN"
        assert data["connected"] is True

    def test_linkedin_in_user_connections_summary(self, client):
        """Test that linkedin_connected appears in connection summary."""
        test_client, mock_composio = client
        mock_composio.connected_accounts.list.return_value = MagicMock(items=[])

        response = test_client.get("/connections/test_user")
        assert response.status_code == 200
        data = response.json()
        assert "linkedin_connected" in data["summary"]

    def test_toolkits_status_includes_linkedin(self, client):
        """Test that /toolkits/{user_id}/status queries linkedin."""
        test_client, mock_composio = client

        # Mock the check_toolkits_status function (imported locally in the endpoint)
        with patch("server.auth.check_toolkits_status") as mock_check:
            mock_check.return_value = {
                "twitter": {
                    "name": "Twitter",
                    "connected": True,
                    "connection_id": None,
                },
                "facebook": {
                    "name": "Facebook",
                    "connected": False,
                    "connection_id": None,
                },
                "instagram": {
                    "name": "Instagram",
                    "connected": False,
                    "connection_id": None,
                },
                "linkedin": {
                    "name": "LinkedIn",
                    "connected": True,
                    "connection_id": None,
                },
            }
            response = test_client.get("/toolkits/test_user/status")
            assert response.status_code == 200
            # Verify linkedin was passed in the toolkits list
            call_args = mock_check.call_args
            assert (
                "linkedin" in call_args[0][2]
            )  # third positional arg is toolkits list


# ============================================================================
# 8. MODEL SERIALIZATION ROUNDTRIP
# ============================================================================


class TestLinkedInModelRoundtrip:
    def test_post_request_roundtrip(self):
        original = LinkedInPostRequest(
            user_id="user1",
            author="urn:li:person:123",
            commentary="Test post",
            visibility="CONNECTIONS",
            lifecycle_state="PUBLISHED",
            is_reshare_disabled=True,
        )
        data = original.model_dump()
        restored = LinkedInPostRequest(**data)
        assert restored == original

    def test_delete_request_roundtrip(self):
        original = LinkedInDeletePostRequest(user_id="u1", share_id="s1")
        data = original.model_dump()
        restored = LinkedInDeletePostRequest(**data)
        assert restored == original

    def test_company_info_request_roundtrip(self):
        original = LinkedInCompanyInfoRequest(
            user_id="u1", count=10, role="ADMIN", start=0, state="ACTIVE"
        )
        data = original.model_dump()
        restored = LinkedInCompanyInfoRequest(**data)
        assert restored == original


# ============================================================================
# 9. TOOL EXECUTION RESPONSE
# ============================================================================


class TestToolExecutionResponseLinkedIn:
    def test_successful_response(self):
        resp = ToolExecutionResponse(successful=True, data={"id": "share123"})
        assert resp.successful is True
        assert resp.data == {"id": "share123"}
        assert resp.error is None

    def test_error_response(self):
        resp = ToolExecutionResponse(successful=False, error="LinkedIn API error")
        assert resp.successful is False
        assert resp.data is None
        assert resp.error == "LinkedIn API error"


# ============================================================================
# 10. COMPOSIO SLUG VERIFICATION
# ============================================================================


class TestComposioSlugs:
    """Verify that the correct Composio action slugs are used throughout."""

    def test_action_slugs_in_actions_module(self):
        """Check that actions.py uses the correct slugs."""
        import inspect
        import server.actions as actions_module

        source = inspect.getsource(actions_module)
        assert "LINKEDIN_CREATE_LINKED_IN_POST" in source
        assert "LINKEDIN_DELETE_LINKED_IN_POST" in source
        assert "LINKEDIN_GET_MY_INFO" in source
        assert "LINKEDIN_GET_COMPANY_INFO" in source

    def test_tool_slugs_in_chatbot_module(self):
        """Check that chatbot.py tool functions use the correct Composio slugs."""
        import inspect
        from server.chatbot import get_agent_tools

        source = inspect.getsource(get_agent_tools)
        assert "LINKEDIN_CREATE_LINKED_IN_POST" in source
        assert "LINKEDIN_DELETE_LINKED_IN_POST" in source
        assert "LINKEDIN_GET_MY_INFO" in source
        assert "LINKEDIN_GET_COMPANY_INFO" in source
