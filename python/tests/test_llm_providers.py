"""
Tests for LLM providers -- mocked HTTP for Ollama, mocked SDK for Anthropic.

Test strategy:
    All provider tests use mocked HTTP clients (httpx for Ollama) and mocked
    SDK clients (anthropic for Anthropic). No real API calls are made. This
    ensures tests pass without Ollama running or an Anthropic API key.

Test groups:
    - OllamaProvider: chat (simple + tool calls), availability check, tool format
    - AnthropicProvider: chat (simple + tool use), availability, system message extraction
    - ProviderSwitching: security level constants, default model names

Fixture isolation:
    Each test class has its own provider fixture. Mocking uses patch() context
    managers that are scoped to individual test methods, so no mock state leaks.

Naming convention:
    test_{provider}_{scenario} — e.g., test_chat_simple_response, test_check_available_failure
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from python.llm.providers import (
    OllamaProvider, AnthropicProvider, ProviderResponse, ToolCall,
)


# ── Ollama Provider ───────────────────────────────────────────────
# Tests for local Ollama provider with mocked httpx.AsyncClient.

class TestOllamaProvider:
    """Test Ollama provider with mocked httpx."""

    @pytest.fixture
    def provider(self):
        """Ollama provider pointing at a test URL."""
        return OllamaProvider(base_url="http://test:11434", model="llama3.1")

    @pytest.mark.asyncio
    async def test_chat_simple_response(self, provider):
        """Simple chat returns ProviderResponse with content and no tool calls."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "Hello!"},
        }

        # Mock the httpx.AsyncClient context manager pattern
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)  # async with ... as client
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await provider.chat([{"role": "user", "content": "Hi"}])

        assert isinstance(result, ProviderResponse)
        assert result.content == "Hello!"
        assert result.provider == "ollama"
        assert result.model == "llama3.1"
        assert result.tool_calls == []

    @pytest.mark.asyncio
    async def test_chat_with_tool_calls(self, provider):
        """Chat with tool calls returns parsed ToolCall objects."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "list_accounts",
                            "arguments": {"node": "BANK_A"},
                        }
                    }
                ],
            },
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await provider.chat(
                [{"role": "user", "content": "List accounts"}],
                tools=[{"name": "list_accounts", "description": "...", "input_schema": {"type": "object"}}],
            )

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "list_accounts"
        assert result.tool_calls[0].arguments == {"node": "BANK_A"}

    @pytest.mark.asyncio
    async def test_check_available_success(self, provider):
        """Returns True when Ollama /api/tags responds 200 with models."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "llama3.1"}]}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            assert await provider.check_available() is True

    @pytest.mark.asyncio
    async def test_check_available_failure(self, provider):
        """Returns False when Ollama connection is refused."""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("connection refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            assert await provider.check_available() is False

    @pytest.mark.asyncio
    async def test_tools_sent_in_correct_format(self, provider):
        """Tools are transformed to Ollama function-calling format."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"message": {"content": "ok"}}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await provider.chat(
                [{"role": "user", "content": "test"}],
                tools=[{"name": "test_tool", "description": "A test", "input_schema": {"type": "object", "properties": {}}}],
            )

            call_args = mock_client.post.call_args
            payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
            assert "tools" in payload
            assert payload["tools"][0]["type"] == "function"        # Ollama format
            assert payload["tools"][0]["function"]["name"] == "test_tool"


# ── Anthropic Provider ────────────────────────────────────────────
# Tests for cloud Anthropic provider with mocked SDK.

class TestAnthropicProvider:
    """Test Anthropic provider with mocked SDK."""

    @pytest.fixture
    def provider(self):
        """Anthropic provider with a test API key."""
        return AnthropicProvider(api_key="test-key", model="claude-sonnet-4-20250514")

    @pytest.mark.asyncio
    async def test_check_available_with_key(self, provider):
        """Returns True when API key is present."""
        assert await provider.check_available() is True

    @pytest.mark.asyncio
    async def test_check_available_without_key(self):
        """Returns False when API key is empty."""
        provider = AnthropicProvider(api_key="")
        assert await provider.check_available() is False

    @pytest.mark.asyncio
    async def test_chat_simple_response(self, provider):
        """Simple chat returns text content from Anthropic response blocks."""
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Here are the accounts."

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]

        with patch("anthropic.AsyncAnthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            result = await provider.chat([
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "List accounts"},
            ])

        assert result.content == "Here are the accounts."
        assert result.provider == "anthropic"

    @pytest.mark.asyncio
    async def test_chat_with_tool_use(self, provider):
        """Chat with tool_use blocks returns parsed ToolCall objects."""
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.id = "toolu_123"          # Anthropic provides unique IDs
        mock_tool_block.name = "list_accounts"
        mock_tool_block.input = {"node": "BANK_A"}

        mock_response = MagicMock()
        mock_response.content = [mock_tool_block]

        with patch("anthropic.AsyncAnthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            result = await provider.chat([{"role": "user", "content": "List accounts"}])

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].id == "toolu_123"
        assert result.tool_calls[0].name == "list_accounts"

    @pytest.mark.asyncio
    async def test_system_message_extracted(self, provider):
        """System message is extracted to Anthropic's separate system param."""
        mock_response = MagicMock()
        mock_response.content = []

        with patch("anthropic.AsyncAnthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            await provider.chat([
                {"role": "system", "content": "System prompt"},
                {"role": "user", "content": "Hello"},
            ])

            call_kwargs = mock_client.messages.create.call_args[1]
            assert call_kwargs["system"] == "System prompt"
            # System message should NOT appear in the messages array
            assert all(m["role"] != "system" for m in call_kwargs["messages"])

    @pytest.mark.asyncio
    async def test_no_anthropic_package_raises(self):
        """Raises RuntimeError when anthropic package is not importable."""
        provider = AnthropicProvider(api_key="test")
        with patch.dict("sys.modules", {"anthropic": None}):
            with pytest.raises((RuntimeError, ImportError)):
                await provider.chat([{"role": "user", "content": "test"}])


# ── Provider Switching ────────────────────────────────────────────
# Verify security level constants and default model names.

class TestProviderSwitching:
    """Test runtime provider switching."""

    def test_ollama_security_level(self):
        """Ollama security level is LOCAL."""
        assert OllamaProvider.security_level == "LOCAL"

    def test_anthropic_security_level(self):
        """Anthropic security level is CLOUD."""
        assert AnthropicProvider.security_level == "CLOUD"

    def test_ollama_default_model(self):
        """Ollama default model is llama3.1."""
        p = OllamaProvider()
        assert p.model == "llama3.1"

    def test_anthropic_default_model(self):
        """Anthropic default model is claude-haiku-4-5-20251001."""
        p = AnthropicProvider(api_key="test")
        assert p.model == "claude-haiku-4-5-20251001"


# ── Normalize Messages ────────────────────────────────────────────
# Tests for OllamaProvider._normalize_messages() which converts
# Anthropic-format content blocks to plain strings for Ollama.

class TestNormalizeMessages:
    """Test _normalize_messages static method on OllamaProvider."""

    def test_plain_string_passthrough(self):
        """Messages with plain string content pass through unchanged."""
        msgs = [{"role": "user", "content": "Hello"}]
        result = OllamaProvider._normalize_messages(msgs)
        assert result[0]["content"] == "Hello"

    def test_text_blocks_extracted(self):
        """Content with text blocks is joined into a single string."""
        msgs = [{"role": "assistant", "content": [
            {"type": "text", "text": "Here are"},
            {"type": "text", "text": "the results."},
        ]}]
        result = OllamaProvider._normalize_messages(msgs)
        assert result[0]["content"] == "Here are\nthe results."

    def test_tool_use_blocks_serialized(self):
        """tool_use blocks are serialized to readable bracketed strings."""
        msgs = [{"role": "assistant", "content": [
            {"type": "tool_use", "id": "t1", "name": "list_accounts", "input": {"node": "BANK_A"}},
        ]}]
        result = OllamaProvider._normalize_messages(msgs)
        assert "[Tool call: list_accounts(" in result[0]["content"]
        assert "BANK_A" in result[0]["content"]

    def test_tool_result_blocks_serialized(self):
        """tool_result blocks are serialized with tool_use_id reference."""
        msgs = [{"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "3 accounts found"},
        ]}]
        result = OllamaProvider._normalize_messages(msgs)
        assert "[Tool result (t1):" in result[0]["content"]
        assert "3 accounts found" in result[0]["content"]

    def test_mixed_blocks(self):
        """Messages with text + tool_use blocks in the same content array."""
        msgs = [{"role": "assistant", "content": [
            {"type": "text", "text": "Let me check."},
            {"type": "tool_use", "id": "t2", "name": "get_balance", "input": {"account": "ACT-A-001"}},
        ]}]
        result = OllamaProvider._normalize_messages(msgs)
        content = result[0]["content"]
        assert "Let me check." in content
        assert "[Tool call: get_balance(" in content
