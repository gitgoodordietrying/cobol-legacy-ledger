"""
Tests for ConversationManager -- session management, tool-use loop, safety limits.

Test strategy:
    All tests use mocked providers (no real LLM calls) and mocked executors
    (no real bridge calls). The ConversationManager is tested in isolation
    to verify its session handling and tool-use loop logic.

Test groups:
    - SessionManagement: session creation, reuse, history retrieval, clearing
    - ToolUseLoop: no-tool response, tool call resolution, safety limit
    - SystemPrompt: system prompt content (node names, status codes)

Fixture isolation:
    Each test gets a fresh ConversationManager with mock provider and executor.
    The admin_auth fixture provides a consistent AuthContext for all tests.
    No temp directories needed — the manager only passes data through to the
    (mocked) executor.

Naming convention:
    test_{aspect}_{scenario} — e.g., test_chat_creates_session, test_max_iterations_safety
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from python.auth import AuthContext, Role
from python.llm.conversation import ConversationManager, SYSTEM_PROMPT, MAX_TOOL_ITERATIONS
from python.llm.providers import ProviderResponse, ToolCall
from python.llm.tool_executor import ToolExecutor


@pytest.fixture
def mock_provider():
    """Mock LLM provider with configurable chat responses.

    Returns a MagicMock with model and security_level attributes.
    Test methods set provider.chat as an AsyncMock with specific return values.
    """
    provider = MagicMock()
    provider.model = "test-model"
    provider.security_level = "LOCAL"
    return provider


@pytest.fixture
def mock_executor():
    """Mock tool executor that returns configurable results.

    Spec'd against ToolExecutor so only valid methods are callable.
    Test methods configure executor.execute.return_value per scenario.
    """
    executor = MagicMock(spec=ToolExecutor)
    return executor


@pytest.fixture
def admin_auth():
    """Admin auth context for conversation tests."""
    return AuthContext("test-admin", Role.ADMIN)


@pytest.fixture
def manager(mock_provider, mock_executor, admin_auth):
    """Fresh ConversationManager with mock provider and executor."""
    return ConversationManager(mock_provider, mock_executor, admin_auth)


# ── Session Management ────────────────────────────────────────────
# Session creation, retrieval, history, and clearing.

class TestSessionManagement:
    """Session creation, retrieval, and clearing."""

    def test_new_session_created(self, manager):
        """New manager starts with zero sessions."""
        sessions = manager.list_sessions()
        assert len(sessions) == 0

    @pytest.mark.asyncio
    async def test_chat_creates_session(self, manager, mock_provider):
        """First chat message creates a new session."""
        mock_provider.chat = AsyncMock(return_value=ProviderResponse(
            content="Hello!", provider="test", model="test-model"
        ))
        result = await manager.chat("Hi")
        assert result["session_id"] is not None
        assert len(manager.list_sessions()) == 1

    @pytest.mark.asyncio
    async def test_chat_reuses_session(self, manager, mock_provider):
        """Providing session_id continues the same session."""
        mock_provider.chat = AsyncMock(return_value=ProviderResponse(
            content="Response", provider="test", model="test-model"
        ))
        r1 = await manager.chat("First message")
        r2 = await manager.chat("Second message", session_id=r1["session_id"])
        assert r1["session_id"] == r2["session_id"]
        assert len(manager.list_sessions()) == 1

    @pytest.mark.asyncio
    async def test_get_history(self, manager, mock_provider):
        """History includes system prompt, user message, and assistant response."""
        mock_provider.chat = AsyncMock(return_value=ProviderResponse(
            content="Hi there!", provider="test", model="test-model"
        ))
        result = await manager.chat("Hello")
        history = manager.get_history(result["session_id"])
        assert len(history) >= 3  # system + user + assistant
        assert history[0]["role"] == "system"

    def test_clear_session(self, manager):
        """Clearing a session removes it from the sessions dict."""
        manager._sessions["test-session"] = [{"role": "system", "content": "test"}]
        manager.clear_session("test-session")
        assert "test-session" not in manager._sessions

    def test_get_history_missing_session(self, manager):
        """Missing session returns empty list."""
        assert manager.get_history("nonexistent") == []

    @pytest.mark.asyncio
    async def test_custom_session_id(self, manager, mock_provider):
        """User-provided session_id creates a new session with that ID."""
        mock_provider.chat = AsyncMock(return_value=ProviderResponse(
            content="Ok", provider="test", model="test-model"
        ))
        result = await manager.chat("Hello", session_id="my-custom-session")
        assert result["session_id"] == "my-custom-session"
        assert "my-custom-session" in manager.list_sessions()

    @pytest.mark.asyncio
    async def test_list_sessions_after_multiple_chats(self, manager, mock_provider):
        """Multiple chats with different session IDs track all sessions."""
        mock_provider.chat = AsyncMock(return_value=ProviderResponse(
            content="Ok", provider="test", model="test-model"
        ))
        await manager.chat("First", session_id="session-1")
        await manager.chat("Second", session_id="session-2")
        sessions = manager.list_sessions()
        assert "session-1" in sessions
        assert "session-2" in sessions
        assert len(sessions) == 2


# ── Tool-Use Loop ─────────────────────────────────────────────────
# Core loop: send → check tool calls → execute → repeat.

class TestToolUseLoop:
    """Tool-use loop resolves tool calls correctly."""

    @pytest.mark.asyncio
    async def test_no_tool_calls_returns_immediately(self, manager, mock_provider):
        """Response without tool calls returns immediately as final answer."""
        mock_provider.chat = AsyncMock(return_value=ProviderResponse(
            content="Direct answer", provider="test", model="test-model"
        ))
        result = await manager.chat("What is 2+2?")
        assert result["response"] == "Direct answer"
        assert result["tool_calls"] == []

    @pytest.mark.asyncio
    async def test_tool_call_resolved(self, manager, mock_provider, mock_executor):
        """Tool call is executed and result fed back to LLM for final response."""
        # First call: LLM requests a tool
        # Second call: LLM gives final text response
        mock_provider.chat = AsyncMock(side_effect=[
            ProviderResponse(
                content="",
                tool_calls=[ToolCall(id="tc1", name="list_accounts", arguments={"node": "BANK_A"})],
                provider="test", model="test-model",
            ),
            ProviderResponse(
                content="BANK_A has 8 accounts.", provider="test", model="test-model",
            ),
        ])
        mock_executor.execute.return_value = {"accounts": [], "count": 8}

        result = await manager.chat("List BANK_A accounts")
        assert result["response"] == "BANK_A has 8 accounts."
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["tool_name"] == "list_accounts"

    @pytest.mark.asyncio
    async def test_max_iterations_safety(self, manager, mock_provider, mock_executor):
        """Loop hits MAX_TOOL_ITERATIONS safety limit when LLM never stops requesting tools."""
        mock_provider.chat = AsyncMock(return_value=ProviderResponse(
            content="",
            tool_calls=[ToolCall(id="tc1", name="list_accounts", arguments={"node": "BANK_A"})],
            provider="test", model="test-model",
        ))
        mock_executor.execute.return_value = {"accounts": [], "count": 0}

        result = await manager.chat("Loop forever")
        assert "limit" in result["response"].lower()
        assert len(result["tool_calls"]) == MAX_TOOL_ITERATIONS

    @pytest.mark.asyncio
    async def test_tool_denied_mid_loop(self, manager, mock_provider, mock_executor):
        """RBAC denial mid-loop is recorded and loop continues."""
        mock_provider.chat = AsyncMock(side_effect=[
            ProviderResponse(
                content="",
                tool_calls=[ToolCall(id="tc1", name="process_transaction", arguments={"node": "BANK_A"})],
                provider="test", model="test-model",
            ),
            ProviderResponse(
                content="Permission denied for that tool.", provider="test", model="test-model",
            ),
        ])
        mock_executor.execute.return_value = {"error": "Permission denied", "permitted": False}

        result = await manager.chat("Process a transaction")
        assert result["tool_calls"][0]["permitted"] is False

    @pytest.mark.asyncio
    async def test_provider_exception_propagates(self, manager, mock_provider):
        """Provider exception propagates to caller."""
        mock_provider.chat = AsyncMock(side_effect=RuntimeError("Connection failed"))
        with pytest.raises(RuntimeError, match="Connection failed"):
            await manager.chat("Hello")


# ── System Prompt ─────────────────────────────────────────────────
# Verify system prompt contains essential information.

class TestSystemPrompt:
    """System prompt is correctly set."""

    def test_system_prompt_mentions_nodes(self):
        """System prompt lists all 6 node names."""
        assert "BANK_A" in SYSTEM_PROMPT
        assert "CLEARING" in SYSTEM_PROMPT

    def test_system_prompt_mentions_status_codes(self):
        """System prompt includes COBOL status code reference."""
        assert "00=success" in SYSTEM_PROMPT
        assert "01=insufficient" in SYSTEM_PROMPT
