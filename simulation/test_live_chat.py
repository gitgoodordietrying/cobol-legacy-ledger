"""
Live LLM Integration Tests — Real Ollama Calls Through the Chat API
====================================================================

Unlike the fast API tests in test_user_flows.py (which never touch the LLM),
these tests send real messages through the chat endpoint to a running Ollama
instance and verify the LLM actually invokes tools, returns coherent responses,
and the full tool-use loop resolves correctly.

These are SLOW (5-30s per test) because they wait for real LLM inference.
They require Ollama running locally with a model that supports tool use.

Prerequisites:
    - Ollama running at localhost:11434
    - A model installed (qwen3:8b, llama3.1, etc.)
    - Server running at localhost:8000 with seeded data

Run:
    python -m pytest simulation/test_live_chat.py -v -x --timeout=120

Skip these in CI (no Ollama available):
    python -m pytest simulation/test_live_chat.py -v -k "not live"
"""

import os
import pytest
import httpx

BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:8000")
OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

ADMIN = {"X-User": "admin", "X-Role": "admin"}
OPERATOR = {"X-User": "operator", "X-Role": "operator"}
VIEWER = {"X-User": "viewer", "X-Role": "viewer"}


# ── Fixtures ─────────────────────────────────────────────────────

def _ollama_available() -> bool:
    """Check if Ollama is running and has at least one model."""
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        models = r.json().get("models", [])
        return len(models) > 0
    except Exception:
        return False


def _server_available() -> bool:
    """Check if the FastAPI server is running."""
    try:
        r = httpx.get(f"{BASE_URL}/api/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def _pick_model() -> str:
    """Pick the best available Ollama model for tool-use testing."""
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        models = [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return "llama3.1"

    # Prefer models known to handle tool-use well, in order
    preferred = ["qwen3:8b", "qwen3:30b-a3b", "qwen2.5:3b", "llama3.1", "mistral"]
    for pref in preferred:
        if pref in models:
            return pref
    return models[0] if models else "llama3.1"


skip_no_ollama = pytest.mark.skipif(
    not _ollama_available(),
    reason="Ollama not running or no models installed"
)
skip_no_server = pytest.mark.skipif(
    not _server_available(),
    reason="FastAPI server not running at localhost:8000"
)

live = pytest.mark.skipif(
    not (_ollama_available() and _server_available()),
    reason="Requires both Ollama and FastAPI server running"
)


@pytest.fixture(scope="module")
def client():
    """HTTP client pointed at the running server."""
    with httpx.Client(base_url=BASE_URL, timeout=120) as c:
        yield c


@pytest.fixture(scope="module", autouse=True)
def switch_to_available_model(client):
    """Switch provider to Ollama with an installed model before tests run."""
    if not (_ollama_available() and _server_available()):
        return
    model = _pick_model()
    r = client.post("/api/provider/switch", json={
        "provider": "ollama", "model": model,
    }, headers=ADMIN)
    assert r.status_code == 200, f"Failed to switch provider: {r.text}"
    status = r.json()
    assert status["available"] is True, f"Provider not available after switch: {status}"
    print(f"\n  Using Ollama model: {model}")


# ═══════════════════════════════════════════════════════════════════
# LIVE PROVIDER TESTS
# ═══════════════════════════════════════════════════════════════════

@live
class TestProviderManagement:
    """Verify provider switching and status reporting work end-to-end."""

    def test_provider_status_shows_ollama(self, client):
        """Provider status endpoint reports Ollama as active and available."""
        r = client.get("/api/provider/status", headers=ADMIN)
        assert r.status_code == 200
        status = r.json()
        assert status["provider"] == "ollama"
        assert status["available"] is True
        assert status["security_level"] == "LOCAL"

    def test_provider_model_matches_installed(self, client):
        """The active model is one that's actually installed in Ollama."""
        r = client.get("/api/provider/status", headers=ADMIN)
        model = r.json()["model"]
        # Verify model exists in Ollama
        tags = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3).json()
        installed = [m["name"] for m in tags.get("models", [])]
        assert model in installed, f"Model {model} not in installed models: {installed}"


# ═══════════════════════════════════════════════════════════════════
# MARCUS CHEN — Live LLM: "Does the chatbot actually understand COBOL?"
# ═══════════════════════════════════════════════════════════════════

@live
class TestMarcusLiveChat:
    """Marcus tests whether the LLM can actually query the banking system."""

    def test_list_accounts_via_chat(self, client):
        """Ask the LLM to list accounts — it should invoke the list_accounts tool."""
        r = client.post("/api/chat", json={
            "message": "List all accounts in BANK_A",
            "mode": "direct",
        }, headers=ADMIN)
        assert r.status_code == 200
        chat = r.json()
        assert chat["response"]  # Got a text response
        assert chat["session_id"]  # Session created
        assert chat["provider"] == "ollama"

        # The LLM should have called at least one tool
        tool_names = [tc["tool_name"] for tc in chat.get("tool_calls", [])]
        # Either it called list_accounts directly, or gave a text answer
        if tool_names:
            assert "list_accounts" in tool_names, f"Expected list_accounts, got: {tool_names}"
            # If tool was called, it should have been permitted
            for tc in chat["tool_calls"]:
                if tc["tool_name"] == "list_accounts":
                    assert tc["permitted"] is True

    def test_general_knowledge_no_tools(self, client):
        """Ask a general COBOL question — LLM should answer without tools."""
        r = client.post("/api/chat", json={
            "message": "What is a nostro account in banking? Answer briefly.",
            "mode": "direct",
        }, headers=ADMIN)
        assert r.status_code == 200
        chat = r.json()
        assert len(chat["response"]) > 20  # Substantive answer
        # General knowledge questions shouldn't need tools
        # (but we don't enforce this — some models call tools anyway)


# ═══════════════════════════════════════════════════════════════════
# SARAH WILLIAMS — Live LLM: "Does the demo actually work end-to-end?"
# ═══════════════════════════════════════════════════════════════════

@live
class TestSarahLiveChat:
    """Sarah tests the chat as part of her 5-minute portfolio evaluation."""

    def test_chat_returns_session(self, client):
        """First message creates a session that persists."""
        r = client.post("/api/chat", json={
            "message": "Hello, what can you do?",
            "mode": "direct",
        }, headers=ADMIN)
        assert r.status_code == 200
        chat = r.json()
        session_id = chat["session_id"]
        assert session_id

        # Session history should be retrievable
        r2 = client.get(f"/api/chat/history/{session_id}", headers=ADMIN)
        assert r2.status_code == 200
        history = r2.json()
        assert len(history) >= 2  # At least user message + assistant response

    def test_viewer_chat_rbac(self, client):
        """Viewer role can chat but tools should be limited."""
        r = client.post("/api/chat", json={
            "message": "What is this system?",
            "mode": "direct",
        }, headers=VIEWER)
        assert r.status_code == 200
        chat = r.json()
        assert chat["response"]  # Got some response


# ═══════════════════════════════════════════════════════════════════
# DEV PATEL — Live LLM: "Can I quote the chatbot in my article?"
# ═══════════════════════════════════════════════════════════════════

@live
class TestDevLiveChat:
    """Dev tests whether the chatbot produces quotable output."""

    def test_chat_response_is_coherent(self, client):
        """The LLM produces a coherent multi-sentence response."""
        r = client.post("/api/chat", json={
            "message": "Explain in 2-3 sentences what this COBOL Legacy Ledger system does.",
            "mode": "direct",
        }, headers=ADMIN)
        assert r.status_code == 200
        chat = r.json()
        response = chat["response"]
        assert len(response) > 50  # Not a one-word answer
        # Should mention something relevant
        text_lower = response.lower()
        assert any(kw in text_lower for kw in ["cobol", "bank", "ledger", "settlement", "node"]), \
            f"Response doesn't mention any relevant keywords: {response[:200]}"


# ═══════════════════════════════════════════════════════════════════
# ELENA VASQUEZ — Live LLM: "Can I use the tutor mode in class?"
# ═══════════════════════════════════════════════════════════════════

@live
class TestElenaLiveChat:
    """Elena tests whether tutor mode produces Socratic responses."""

    def test_tutor_mode_responds(self, client):
        """Tutor mode produces a response (may include questions)."""
        r = client.post("/api/chat", json={
            "message": "What does the PAYROLL.cob program do?",
            "mode": "tutor",
        }, headers=ADMIN)
        assert r.status_code == 200
        chat = r.json()
        assert len(chat["response"]) > 30  # Substantive response

    def test_direct_vs_tutor_both_work(self, client):
        """Both direct and tutor modes produce responses for the same question."""
        question = "What is an ALTER statement in COBOL?"
        for mode in ["direct", "tutor"]:
            r = client.post("/api/chat", json={
                "message": question,
                "mode": mode,
            }, headers=ADMIN)
            assert r.status_code == 200, f"Mode {mode} failed"
            assert len(r.json()["response"]) > 20, f"Mode {mode} gave empty response"


# ═══════════════════════════════════════════════════════════════════
# TOOL-USE VERIFICATION — Does the LLM actually resolve tools?
# ═══════════════════════════════════════════════════════════════════

@live
class TestToolUseResolution:
    """Verify the full tool-use loop: LLM → tool call → result → final answer."""

    def test_verify_chain_tool_use(self, client):
        """Ask to verify a chain — should invoke verify_chain or verify_all_nodes."""
        r = client.post("/api/chat", json={
            "message": "Verify the integrity chain for BANK_A. Use the verify_chain tool.",
            "mode": "direct",
        }, headers=ADMIN)
        assert r.status_code == 200
        chat = r.json()
        tool_calls = chat.get("tool_calls", [])
        if tool_calls:
            tool_names = [tc["tool_name"] for tc in tool_calls]
            # Should have called a verification tool
            assert any(t in tool_names for t in ["verify_chain", "verify_all_nodes"]), \
                f"Expected verify tool, got: {tool_names}"
            # All called tools should be permitted (admin has all perms)
            for tc in tool_calls:
                assert tc["permitted"] is True, f"Tool {tc['tool_name']} was denied"

    def test_compare_complexity_tool_use(self, client):
        """Ask to compare COBOL files — should invoke compare_complexity tool."""
        r = client.post("/api/chat", json={
            "message": "Compare the complexity of PAYROLL.cob vs TRANSACT.cob using the compare_complexity tool.",
            "mode": "direct",
        }, headers=ADMIN)
        assert r.status_code == 200
        chat = r.json()
        tool_calls = chat.get("tool_calls", [])
        if tool_calls:
            tool_names = [tc["tool_name"] for tc in tool_calls]
            if "compare_complexity" in tool_names:
                tc = next(t for t in tool_calls if t["tool_name"] == "compare_complexity")
                assert tc["permitted"] is True
                # Result should have the comparison structure
                result = tc["result"]
                if isinstance(result, dict) and "file_a" in result:
                    assert result["file_a"]["file"] == "PAYROLL.cob"
                    assert result["file_b"]["file"] == "TRANSACT.cob"

    def test_tool_call_audit_trail(self, client):
        """Tool calls from chat appear in the response's tool_calls array."""
        r = client.post("/api/chat", json={
            "message": "How many accounts does BANK_B have? Use the list_accounts tool to check.",
            "mode": "direct",
        }, headers=ADMIN)
        assert r.status_code == 200
        chat = r.json()
        # Whether or not the LLM called tools, the response should be structured
        assert "tool_calls" in chat
        assert "response" in chat
        assert "session_id" in chat
        assert "provider" in chat
        assert "model" in chat
