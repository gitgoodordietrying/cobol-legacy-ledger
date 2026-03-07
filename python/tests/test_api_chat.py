"""
Tests for chat API endpoints -- mocked LLM providers, session management, provider switching.

Test strategy:
    All LLM provider calls are mocked — no real Ollama or Anthropic API calls.
    The chat module's module-level state (_current_provider, _conversations, etc.)
    is reset between tests via the autouse reset_chat_state fixture. This prevents
    provider and session state from leaking between tests.

Test groups:
    - ProviderStatus: GET /api/provider/status (default provider)
    - ProviderSwitch: POST /api/provider/switch (ollama, anthropic without key)
    - ChatEndpoint: POST /api/chat (unavailable provider, success, validation)
    - ChatHistory: GET /api/chat/history (missing session, after chat)
    - SessionManagement: session reuse, provider switch clears conversations

Fixture isolation:
    The reset_chat_state fixture (autouse) clears all module-level globals in
    routes_chat before and after each test. This is necessary because routes_chat
    uses module-level state for provider, executor, and conversations.

Naming convention:
    test_{endpoint}_{scenario} — e.g., test_chat_success_mocked, test_switch_to_ollama
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from python.api.app import create_app
from python.api import routes_chat
from python.llm.providers import ProviderResponse


@pytest.fixture(autouse=True)
def reset_chat_state():
    """Reset module-level chat state between tests.

    routes_chat stores provider, executor, audit log, and conversations as
    module-level globals. Without this fixture, one test's provider switch
    would affect subsequent tests.
    """
    routes_chat._current_provider = None
    routes_chat._audit_log = None
    routes_chat._executor = None
    routes_chat._conversations.clear()
    yield
    routes_chat._current_provider = None
    routes_chat._conversations.clear()


@pytest.fixture
def client():
    """FastAPI test client for chat endpoints."""
    app = create_app()
    with TestClient(app) as c:
        yield c


# Demo auth headers — admin has all permissions
ADMIN_HEADERS = {"X-User": "admin", "X-Role": "admin"}


# ── Provider Status ───────────────────────────────────────────────
# GET /api/provider/status — reports current provider info.

class TestProviderStatus:
    def test_default_provider_is_ollama(self, client):
        """Default provider is Ollama with LOCAL security level."""
        with patch.object(routes_chat, "_get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.model = "llama3.1"
            mock_provider.security_level = "LOCAL"
            mock_provider.__class__.__name__ = "OllamaProvider"
            mock_provider.check_available = AsyncMock(return_value=False)
            mock_get.return_value = mock_provider

            resp = client.get("/api/provider/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["security_level"] == "LOCAL"


# ── Provider Switch ───────────────────────────────────────────────
# POST /api/provider/switch — change active LLM provider.

class TestProviderSwitch:
    def test_switch_to_anthropic_without_key(self, client):
        """Switching to Anthropic without API key returns 400."""
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("ANTHROPIC_API_KEY", None)
            resp = client.post("/api/provider/switch", json={"provider": "anthropic"})
            assert resp.status_code == 400

    def test_switch_to_ollama(self, client):
        """Switching to Ollama succeeds and reports ollama provider."""
        with patch("python.llm.providers.OllamaProvider.check_available", new_callable=AsyncMock, return_value=False):
            resp = client.post("/api/provider/switch", json={"provider": "ollama", "model": "llama3.1"})
            assert resp.status_code == 200
            assert resp.json()["provider"] == "ollama"

    def test_switch_to_ollama_with_custom_model(self, client):
        """Switching to Ollama with custom model override works."""
        with patch("python.llm.providers.OllamaProvider.check_available", new_callable=AsyncMock, return_value=False):
            resp = client.post("/api/provider/switch", json={"provider": "ollama", "model": "mistral"})
            assert resp.status_code == 200
            assert resp.json()["model"] == "mistral"

    def test_provider_switch_clears_conversations(self, client):
        """Switching providers clears the conversations dict."""
        mock_provider = MagicMock()
        mock_provider.check_available = AsyncMock(return_value=True)
        mock_provider.model = "test"
        mock_provider.security_level = "LOCAL"
        mock_provider.chat = AsyncMock(return_value=ProviderResponse(
            content="Hi", provider="test", model="test"
        ))
        routes_chat._current_provider = mock_provider

        # Create a conversation
        client.post("/api/chat", headers=ADMIN_HEADERS, json={"message": "Hello"})
        assert len(routes_chat._conversations) > 0

        # Switch provider — should clear conversations
        with patch("python.llm.providers.OllamaProvider.check_available", new_callable=AsyncMock, return_value=False):
            client.post("/api/provider/switch", json={"provider": "ollama"})
        assert len(routes_chat._conversations) == 0


# ── Chat Endpoint ─────────────────────────────────────────────────
# POST /api/chat — send message, get response with tool calls.

class TestChatEndpoint:
    def test_chat_provider_unavailable(self, client):
        """Returns 503 when provider is not reachable."""
        mock_provider = MagicMock()
        mock_provider.check_available = AsyncMock(return_value=False)
        mock_provider.__class__.__name__ = "OllamaProvider"
        routes_chat._current_provider = mock_provider

        resp = client.post("/api/chat", headers=ADMIN_HEADERS, json={"message": "Hello"})
        assert resp.status_code == 503

    def test_chat_success_mocked(self, client):
        """Successful chat returns response text and session ID."""
        mock_provider = MagicMock()
        mock_provider.check_available = AsyncMock(return_value=True)
        mock_provider.model = "test"
        mock_provider.security_level = "LOCAL"
        mock_provider.chat = AsyncMock(return_value=ProviderResponse(
            content="Hello! I can help with banking.", provider="test", model="test"
        ))
        routes_chat._current_provider = mock_provider

        resp = client.post("/api/chat", headers=ADMIN_HEADERS, json={"message": "Hello"})
        assert resp.status_code == 200
        data = resp.json()
        assert "Hello" in data["response"]
        assert data["session_id"] is not None

    def test_chat_invalid_request(self, client):
        """Returns 422 when required 'message' field is missing."""
        resp = client.post("/api/chat", headers=ADMIN_HEADERS, json={})
        assert resp.status_code == 422  # Missing required field

    def test_chat_empty_message_rejected(self, client):
        """Returns 422 when message is empty string (min_length=1)."""
        resp = client.post("/api/chat", headers=ADMIN_HEADERS, json={"message": ""})
        assert resp.status_code == 422

    def test_chat_session_reuse(self, client):
        """Same session_id continues an existing conversation."""
        mock_provider = MagicMock()
        mock_provider.check_available = AsyncMock(return_value=True)
        mock_provider.model = "test"
        mock_provider.security_level = "LOCAL"
        mock_provider.chat = AsyncMock(return_value=ProviderResponse(
            content="Response", provider="test", model="test"
        ))
        routes_chat._current_provider = mock_provider

        # First message — creates session
        r1 = client.post("/api/chat", headers=ADMIN_HEADERS, json={"message": "First"})
        session_id = r1.json()["session_id"]

        # Second message — reuses session
        r2 = client.post("/api/chat", headers=ADMIN_HEADERS, json={
            "message": "Second", "session_id": session_id
        })
        assert r2.json()["session_id"] == session_id


# ── Chat History ──────────────────────────────────────────────────
# GET /api/chat/history/{session_id} — retrieve conversation messages.

class TestChatHistory:
    def test_history_not_found(self, client):
        """Returns 404 for nonexistent session ID."""
        resp = client.get("/api/chat/history/nonexistent", headers=ADMIN_HEADERS)
        assert resp.status_code == 404

    def test_history_after_chat(self, client):
        """History endpoint returns messages after a chat."""
        mock_provider = MagicMock()
        mock_provider.check_available = AsyncMock(return_value=True)
        mock_provider.model = "test"
        mock_provider.security_level = "LOCAL"
        mock_provider.chat = AsyncMock(return_value=ProviderResponse(
            content="Hello!", provider="test", model="test"
        ))
        routes_chat._current_provider = mock_provider

        # Chat to create session
        r = client.post("/api/chat", headers=ADMIN_HEADERS, json={"message": "Hi"})
        session_id = r.json()["session_id"]

        # Fetch history
        resp = client.get(f"/api/chat/history/{session_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        messages = resp.json()
        assert len(messages) >= 2  # user + assistant (system filtered out)
        assert all(m["role"] != "system" for m in messages)


# ── Chat Error Paths ─────────────────────────────────────────────
# Tests for 502 conversation errors, provider switch edge cases.

class TestChatErrorPaths:

    def test_chat_conversation_exception_returns_502(self, client):
        """Unexpected exception in conversation.chat() returns 502."""
        mock_provider = MagicMock()
        mock_provider.check_available = AsyncMock(return_value=True)
        mock_provider.model = "test"
        mock_provider.security_level = "LOCAL"
        mock_provider.chat = AsyncMock(side_effect=RuntimeError("LLM exploded"))
        routes_chat._current_provider = mock_provider

        resp = client.post("/api/chat", headers=ADMIN_HEADERS, json={"message": "Boom"})
        assert resp.status_code == 502

    def test_switch_to_anthropic_with_api_key(self, client):
        """Switching to Anthropic with inline API key succeeds."""
        with patch("python.llm.providers.AnthropicProvider.check_available",
                    new_callable=AsyncMock, return_value=True):
            resp = client.post("/api/provider/switch", json={
                "provider": "anthropic",
                "api_key": "sk-test-key-12345",
            })
            assert resp.status_code == 200
            assert resp.json()["provider"] == "anthropic"

    def test_switch_to_invalid_provider(self, client):
        """Switching to invalid provider name returns 422 (regex validation)."""
        resp = client.post("/api/provider/switch", json={
            "provider": "openai",
        })
        assert resp.status_code == 422

    def test_chat_with_empty_session_id(self, client):
        """Empty string session_id creates a new session (not an error)."""
        mock_provider = MagicMock()
        mock_provider.check_available = AsyncMock(return_value=True)
        mock_provider.model = "test"
        mock_provider.security_level = "LOCAL"
        mock_provider.chat = AsyncMock(return_value=ProviderResponse(
            content="New session", provider="test", model="test"
        ))
        routes_chat._current_provider = mock_provider

        resp = client.post("/api/chat", headers=ADMIN_HEADERS, json={
            "message": "Hello", "session_id": "",
        })
        assert resp.status_code == 200
        assert resp.json()["session_id"] != ""
