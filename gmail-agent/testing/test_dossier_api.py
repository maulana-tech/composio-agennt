"""
Test Dossier API Endpoints — FastAPI TestClient Tests.

Tests all 5 REST endpoints for the Dossier/Meeting Prep agent:
  POST /dossier/status
  POST /dossier/generate
  POST /dossier/update
  GET  /dossier/{dossier_id}
  DELETE /dossier/{dossier_id}

All pipeline stages are mocked so tests run without API keys.
"""

import time
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_sessions():
    """Ensure a clean session store for every test."""
    from server.tools.dossier_agent.dossier_agent import _dossier_sessions

    _dossier_sessions.clear()
    yield
    _dossier_sessions.clear()


@pytest.fixture()
def client():
    """Create a FastAPI TestClient."""
    from server.api import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_session(
    dossier_id: str = "test-123",
    name: str = "Jane Doe",
    status: str = "generated",
    document: str = "# Dossier\nSome content",
):
    """Seed a session directly into the store for read-oriented tests."""
    from server.tools.dossier_agent.dossier_agent import _dossier_sessions

    now = time.time()
    _dossier_sessions[dossier_id] = {
        "name": name,
        "linkedin_url": "https://linkedin.com/in/janedoe",
        "meeting_context": "Board meeting",
        "status": status,
        "collected_data": {"name": name},
        "synthesized_data": {"name": name},
        "strategic_insights": {},
        "document": document,
        "created_at": now,
        "last_accessed": now,
    }


# ===================================================================
# POST /dossier/status
# ===================================================================


class TestDossierStatusEndpoint:
    """Tests for POST /dossier/status."""

    def test_status_no_session(self, client):
        """Status for a non-existent session returns 'none'."""
        resp = client.post(
            "/dossier/status",
            json={"dossier_id": "nonexistent"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["status"] == "none"
        assert "No active" in body["message"]

    def test_status_existing_generated(self, client):
        """Status for a generated session returns document."""
        _seed_session("sess-1", status="generated")
        resp = client.post(
            "/dossier/status",
            json={"dossier_id": "sess-1"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["status"] == "generated"
        assert body["document"] is not None

    def test_status_existing_collecting(self, client):
        """Status for an in-progress session returns its stage."""
        _seed_session("sess-2", status="collecting")
        resp = client.post(
            "/dossier/status",
            json={"dossier_id": "sess-2"},
        )
        body = resp.json()
        assert body["success"] is True
        assert body["status"] == "collecting"

    def test_status_default_id(self, client):
        """Omitting dossier_id uses 'default'."""
        resp = client.post("/dossier/status", json={})
        body = resp.json()
        assert body["success"] is True
        assert body["status"] == "none"

    def test_status_error_session(self, client):
        """Status for an errored session returns error info."""
        _seed_session("sess-err", status="error")
        resp = client.post(
            "/dossier/status",
            json={"dossier_id": "sess-err"},
        )
        body = resp.json()
        assert body["success"] is True
        assert body["status"] == "error"


# ===================================================================
# POST /dossier/generate
# ===================================================================


class TestDossierGenerateEndpoint:
    """Tests for POST /dossier/generate."""

    def test_generate_success(self, client):
        """Successful generation returns document and status 'generated'."""
        fake_doc = "# Meeting Prep: John Smith\nContent..."

        async def _mock_generate(
            self, dossier_id, name, linkedin_url="", meeting_context=""
        ):
            from server.tools.dossier_agent.dossier_agent import _create_session

            session = _create_session(dossier_id, name, linkedin_url, meeting_context)
            session["status"] = "generated"
            session["document"] = fake_doc
            return fake_doc

        with patch(
            "server.tools.dossier_agent.dossier_agent.DossierAgent.generate_dossier",
            _mock_generate,
        ):
            resp = client.post(
                "/dossier/generate",
                json={
                    "name": "John Smith",
                    "linkedin_url": "https://linkedin.com/in/johnsmith",
                    "meeting_context": "Investor call",
                    "dossier_id": "gen-1",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["status"] == "generated"
        assert "John Smith" in body["document"]

    def test_generate_pipeline_error(self, client):
        """Pipeline error returns success=False with error message."""

        async def _mock_fail(
            self, dossier_id, name, linkedin_url="", meeting_context=""
        ):
            from server.tools.dossier_agent.dossier_agent import _create_session

            session = _create_session(dossier_id, name, linkedin_url, meeting_context)
            session["status"] = "error"
            session["document"] = "Dossier generation failed: API key missing"
            return session["document"]

        with patch(
            "server.tools.dossier_agent.dossier_agent.DossierAgent.generate_dossier",
            _mock_fail,
        ):
            resp = client.post(
                "/dossier/generate",
                json={"name": "Fail Person", "dossier_id": "gen-err"},
            )
        body = resp.json()
        assert body["success"] is False
        assert body["status"] == "error"

    def test_generate_missing_name(self, client):
        """Missing required 'name' field returns 422."""
        resp = client.post(
            "/dossier/generate",
            json={"dossier_id": "gen-noname"},
        )
        assert resp.status_code == 422

    def test_generate_default_dossier_id(self, client):
        """Omitting dossier_id defaults to 'default'."""
        fake_doc = "# Default dossier"

        async def _mock_gen(
            self, dossier_id, name, linkedin_url="", meeting_context=""
        ):
            from server.tools.dossier_agent.dossier_agent import _create_session

            session = _create_session(dossier_id, name, linkedin_url, meeting_context)
            session["status"] = "generated"
            session["document"] = fake_doc
            return fake_doc

        with patch(
            "server.tools.dossier_agent.dossier_agent.DossierAgent.generate_dossier",
            _mock_gen,
        ):
            resp = client.post(
                "/dossier/generate",
                json={"name": "Default Person"},
            )
        body = resp.json()
        assert body["success"] is True

    def test_generate_exception_returns_error(self, client):
        """Unhandled exception in the endpoint returns success=False."""

        async def _mock_raise(self, *a, **kw):
            raise RuntimeError("Unexpected crash")

        with patch(
            "server.tools.dossier_agent.dossier_agent.DossierAgent.generate_dossier",
            _mock_raise,
        ):
            resp = client.post(
                "/dossier/generate",
                json={"name": "Crash Person", "dossier_id": "gen-crash"},
            )
        body = resp.json()
        assert body["success"] is False
        assert "Unexpected crash" in (body.get("error") or "")


# ===================================================================
# POST /dossier/update
# ===================================================================


class TestDossierUpdateEndpoint:
    """Tests for POST /dossier/update."""

    def test_update_success(self, client):
        """Update an existing dossier with new context."""
        updated_doc = "# Updated Dossier"

        async def _mock_update(self, dossier_id, additional_context):
            from server.tools.dossier_agent.dossier_agent import _dossier_sessions

            session = _dossier_sessions.get(dossier_id, {})
            session["status"] = "generated"
            session["document"] = updated_doc
            return updated_doc

        _seed_session("upd-1", status="generated")

        with patch(
            "server.tools.dossier_agent.dossier_agent.DossierAgent.update_dossier",
            _mock_update,
        ):
            resp = client.post(
                "/dossier/update",
                json={
                    "dossier_id": "upd-1",
                    "additional_context": "We want to discuss budget",
                },
            )
        body = resp.json()
        assert body["success"] is True
        assert "Updated" in body["document"]

    def test_update_no_session(self, client):
        """Updating a non-existent dossier returns the agent's error message."""

        async def _mock_update_none(self, dossier_id, additional_context):
            return "No dossier found with that ID. Generate one first."

        with patch(
            "server.tools.dossier_agent.dossier_agent.DossierAgent.update_dossier",
            _mock_update_none,
        ):
            resp = client.post(
                "/dossier/update",
                json={
                    "dossier_id": "nonexistent",
                    "additional_context": "anything",
                },
            )
        body = resp.json()
        assert body["success"] is True  # endpoint wraps agent return

    def test_update_missing_context(self, client):
        """Missing required 'additional_context' returns 422."""
        resp = client.post(
            "/dossier/update",
            json={"dossier_id": "upd-1"},
        )
        assert resp.status_code == 422

    def test_update_exception(self, client):
        """Exception in update returns success=False."""

        async def _mock_raise(self, *a, **kw):
            raise RuntimeError("Update crash")

        with patch(
            "server.tools.dossier_agent.dossier_agent.DossierAgent.update_dossier",
            _mock_raise,
        ):
            resp = client.post(
                "/dossier/update",
                json={
                    "dossier_id": "upd-crash",
                    "additional_context": "crash",
                },
            )
        body = resp.json()
        assert body["success"] is False
        assert "Update crash" in (body.get("error") or "")


# ===================================================================
# GET /dossier/{dossier_id}
# ===================================================================


class TestDossierGetDocumentEndpoint:
    """Tests for GET /dossier/{dossier_id}."""

    def test_get_generated_document(self, client):
        """Retrieve a successfully generated dossier."""
        _seed_session("get-1", document="# Full Document")
        resp = client.get("/dossier/get-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["status"] == "generated"
        assert body["document"] == "# Full Document"

    def test_get_nonexistent(self, client):
        """Non-existent dossier returns success=False."""
        resp = client.get("/dossier/does-not-exist")
        body = resp.json()
        assert body["success"] is False
        assert body["status"] == "none"
        assert "No dossier" in body["message"]

    def test_get_not_ready(self, client):
        """Dossier that's still collecting returns 'not ready'."""
        _seed_session("get-collecting", status="collecting")
        resp = client.get("/dossier/get-collecting")
        body = resp.json()
        assert body["success"] is False
        assert "not ready" in body["message"].lower()

    def test_get_analyzing(self, client):
        """Dossier in analyzing state returns not ready."""
        _seed_session("get-analyzing", status="analyzing")
        resp = client.get("/dossier/get-analyzing")
        body = resp.json()
        assert body["success"] is False
        assert body["status"] == "analyzing"

    def test_get_error_session(self, client):
        """Dossier in error state returns not ready."""
        _seed_session("get-error", status="error")
        resp = client.get("/dossier/get-error")
        body = resp.json()
        assert body["success"] is False
        assert body["status"] == "error"


# ===================================================================
# DELETE /dossier/{dossier_id}
# ===================================================================


class TestDossierDeleteEndpoint:
    """Tests for DELETE /dossier/{dossier_id}."""

    def test_delete_existing(self, client):
        """Delete an existing session returns success and confirmation."""
        _seed_session("del-1", name="John Doe")
        resp = client.delete("/dossier/del-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["status"] == "deleted"
        assert "John Doe" in body["message"]

        # Verify session is actually removed
        from server.tools.dossier_agent.dossier_agent import _dossier_sessions

        assert "del-1" not in _dossier_sessions

    def test_delete_nonexistent(self, client):
        """Deleting a non-existent session returns success=False."""
        resp = client.delete("/dossier/nonexistent")
        body = resp.json()
        assert body["success"] is False
        assert body["status"] == "none"
        assert "No dossier" in body["message"]

    def test_delete_then_get(self, client):
        """After deleting, GET returns not found."""
        _seed_session("del-get", name="Delete Me")
        resp = client.delete("/dossier/del-get")
        assert resp.json()["success"] is True

        resp = client.get("/dossier/del-get")
        body = resp.json()
        assert body["success"] is False
        assert body["status"] == "none"

    def test_delete_twice(self, client):
        """Deleting the same session twice: second time returns not found."""
        _seed_session("del-twice")
        resp1 = client.delete("/dossier/del-twice")
        assert resp1.json()["success"] is True

        resp2 = client.delete("/dossier/del-twice")
        assert resp2.json()["success"] is False


# ===================================================================
# Cross-Endpoint Integration Tests
# ===================================================================


class TestDossierEndpointIntegration:
    """Tests that span multiple endpoints."""

    def test_generate_then_status_then_get(self, client):
        """Full flow: generate -> check status -> get document."""
        fake_doc = "# Integration Dossier"

        async def _mock_gen(
            self, dossier_id, name, linkedin_url="", meeting_context=""
        ):
            from server.tools.dossier_agent.dossier_agent import _create_session

            session = _create_session(dossier_id, name, linkedin_url, meeting_context)
            session["status"] = "generated"
            session["document"] = fake_doc
            return fake_doc

        with patch(
            "server.tools.dossier_agent.dossier_agent.DossierAgent.generate_dossier",
            _mock_gen,
        ):
            gen_resp = client.post(
                "/dossier/generate",
                json={"name": "Flow Person", "dossier_id": "flow-1"},
            )
        assert gen_resp.json()["success"] is True

        # Check status
        status_resp = client.post(
            "/dossier/status",
            json={"dossier_id": "flow-1"},
        )
        assert status_resp.json()["status"] == "generated"

        # Get document
        get_resp = client.get("/dossier/flow-1")
        assert get_resp.json()["success"] is True
        assert get_resp.json()["document"] == fake_doc

    def test_generate_then_update_then_get(self, client):
        """Generate -> update with context -> retrieve updated document."""
        original_doc = "# Original"
        updated_doc = "# Updated"

        async def _mock_gen(
            self, dossier_id, name, linkedin_url="", meeting_context=""
        ):
            from server.tools.dossier_agent.dossier_agent import _create_session

            session = _create_session(dossier_id, name, linkedin_url, meeting_context)
            session["status"] = "generated"
            session["document"] = original_doc
            session["synthesized_data"] = {"name": name}
            return original_doc

        async def _mock_upd(self, dossier_id, additional_context):
            from server.tools.dossier_agent.dossier_agent import _dossier_sessions

            session = _dossier_sessions.get(dossier_id, {})
            session["status"] = "generated"
            session["document"] = updated_doc
            return updated_doc

        with patch(
            "server.tools.dossier_agent.dossier_agent.DossierAgent.generate_dossier",
            _mock_gen,
        ):
            client.post(
                "/dossier/generate",
                json={"name": "Update Person", "dossier_id": "upd-flow"},
            )

        with patch(
            "server.tools.dossier_agent.dossier_agent.DossierAgent.update_dossier",
            _mock_upd,
        ):
            upd_resp = client.post(
                "/dossier/update",
                json={
                    "dossier_id": "upd-flow",
                    "additional_context": "New context",
                },
            )
        assert upd_resp.json()["success"] is True

        get_resp = client.get("/dossier/upd-flow")
        assert get_resp.json()["document"] == updated_doc

    def test_generate_then_delete_then_status(self, client):
        """Generate -> delete -> status should return 'none'."""
        fake_doc = "# To Delete"

        async def _mock_gen(
            self, dossier_id, name, linkedin_url="", meeting_context=""
        ):
            from server.tools.dossier_agent.dossier_agent import _create_session

            session = _create_session(dossier_id, name, linkedin_url, meeting_context)
            session["status"] = "generated"
            session["document"] = fake_doc
            return fake_doc

        with patch(
            "server.tools.dossier_agent.dossier_agent.DossierAgent.generate_dossier",
            _mock_gen,
        ):
            client.post(
                "/dossier/generate",
                json={"name": "Del Flow", "dossier_id": "del-flow"},
            )

        client.delete("/dossier/del-flow")

        status_resp = client.post(
            "/dossier/status",
            json={"dossier_id": "del-flow"},
        )
        assert status_resp.json()["status"] == "none"

    def test_multiple_sessions_isolated(self, client):
        """Different dossier_ids maintain separate sessions."""
        _seed_session("sess-a", name="Alice", document="# Alice")
        _seed_session("sess-b", name="Bob", document="# Bob")

        a_resp = client.get("/dossier/sess-a")
        b_resp = client.get("/dossier/sess-b")

        assert "Alice" not in b_resp.json().get("document", "")
        assert "Bob" not in a_resp.json().get("document", "")
        assert a_resp.json()["document"] == "# Alice"
        assert b_resp.json()["document"] == "# Bob"

        # Delete one, other should remain
        client.delete("/dossier/sess-a")
        assert client.get("/dossier/sess-a").json()["success"] is False
        assert client.get("/dossier/sess-b").json()["success"] is True
