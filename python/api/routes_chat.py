"""
routes_chat -- LLM conversation endpoints with tool-use resolution.

This module provides the chat interface where users send messages to an LLM
(Ollama or Anthropic) and the LLM can invoke banking/codegen tools via the
tool-use protocol. It also provides provider management endpoints for switching
between local (Ollama) and cloud (Anthropic) providers at runtime.

Module-level state rationale:
    The provider, executor, audit log, and conversations dict are stored as
    module-level globals (not FastAPI app.state) because the chat router may
    not be mounted (if LLM deps are missing). Module-level state avoids
    coupling to FastAPI's lifecycle. Each user gets their own ConversationManager
    keyed by user_id, providing per-user session isolation.

Async rationale:
    Chat and provider endpoints are async because they call external HTTP APIs
    (Ollama's /api/chat, Anthropic's messages.create). FastAPI runs async route
    handlers on the event loop without blocking the thread pool.

Provider availability check:
    Before processing a chat message, we check if the provider is reachable.
    This prevents confusing error messages when Ollama isn't running — the user
    gets a clear 503 instead of a connection timeout buried in a stack trace.

Endpoint surface:
    POST /api/chat                  — Send message, get response + tool calls
    GET  /api/chat/history/{id}     — Get conversation history for a session
    POST /api/provider/switch       — Switch LLM provider (ollama/anthropic)
    GET  /api/provider/status       — Current provider info + availability

Dependencies:
    fastapi, python.auth, python.api.dependencies, python.api.models,
    python.llm.providers, python.llm.tool_executor, python.llm.conversation,
    python.llm.audit
"""

import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException

from python.auth import AuthContext
from python.api.dependencies import get_auth, DATA_DIR
from python.api.models import (
    ChatRequest, ChatResponse, ToolCallInfo,
    ProviderStatus, ProviderSwitchRequest,
)
from python.llm.providers import OllamaProvider, AnthropicProvider, LLMProvider
from python.llm.tool_executor import ToolExecutor
from python.llm.conversation import ConversationManager
from python.llm.audit import AuditLog


router = APIRouter(prefix="/api", tags=["chat"])

# ── Module State ──────────────────────────────────────────────────
# Lazily initialized singletons. Test fixtures reset these between tests.
_current_provider: Optional[LLMProvider] = None
_audit_log: Optional[AuditLog] = None
_executor: Optional[ToolExecutor] = None
_conversations: dict = {}  # user_id -> ConversationManager


# ── Private Helpers ───────────────────────────────────────────────
# Lazy singleton factories for the LLM subsystem components.

def _get_audit_log() -> AuditLog:
    """Get or create the singleton audit log for tool invocation tracking."""
    global _audit_log
    if _audit_log is None:
        _audit_log = AuditLog()
    return _audit_log


def _get_executor() -> ToolExecutor:
    """Get or create the singleton tool executor with RBAC + audit pipeline."""
    global _executor
    if _executor is None:
        _executor = ToolExecutor(data_dir=DATA_DIR, audit_log=_get_audit_log())
    return _executor


def _get_provider() -> LLMProvider:
    """Get or create the current LLM provider.

    Defaults to Ollama (local, zero-trust) — no data leaves the machine.
    Users can switch to Anthropic via POST /api/provider/switch.
    """
    global _current_provider
    if _current_provider is None:
        _current_provider = OllamaProvider()  # Zero-trust default
    return _current_provider


def _get_conversation(auth: AuthContext) -> ConversationManager:
    """Get or create a ConversationManager for the given user.

    Each user_id gets its own manager with isolated session history.
    The manager is created with the current provider and executor, so
    switching providers invalidates all existing conversations.
    """
    key = auth.user_id
    if key not in _conversations:
        _conversations[key] = ConversationManager(
            provider=_get_provider(),
            tool_executor=_get_executor(),
            auth=auth,
        )
    return _conversations[key]


# ── Chat Routes ───────────────────────────────────────────────────
# LLM conversation with tool-use resolution.

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, auth: AuthContext = Depends(get_auth)):
    """Send a message and get a response with resolved tool calls.

    1. Check provider availability (503 if unreachable)
    2. Get or create ConversationManager for this user
    3. Call conversation.chat() which runs the tool-use loop
    4. Map resolved tool calls to ToolCallInfo models
    5. Return response text + session ID + tool call log
    """
    provider = _get_provider()
    available = await provider.check_available()
    if not available:
        raise HTTPException(
            status_code=503,
            detail=f"LLM provider ({provider.__class__.__name__}) is not available. "
                   f"Start Ollama locally or configure ANTHROPIC_API_KEY.",
        )

    conversation = _get_conversation(auth)
    result = await conversation.chat(req.message, session_id=req.session_id)

    return ChatResponse(
        response=result["response"],
        session_id=result["session_id"],
        tool_calls=[
            ToolCallInfo(
                tool_name=tc["tool_name"],
                params=tc["params"],
                result=tc["result"],
                permitted=tc["permitted"],
            )
            for tc in result["tool_calls"]
        ],
        provider=result["provider"],
        model=result["model"],
    )


@router.get("/chat/history/{session_id}")
async def get_history(session_id: str, auth: AuthContext = Depends(get_auth)):
    """Get conversation history for a session.

    Returns all messages except system-role messages (which contain the
    system prompt and are not useful for display).
    """
    conversation = _get_conversation(auth)
    history = conversation.get_history(session_id)
    if not history:
        raise HTTPException(status_code=404, detail="Session not found")
    return [m for m in history if m.get("role") != "system"]  # Filter system prompt


# ── Provider Routes ───────────────────────────────────────────────
# Runtime provider switching and status reporting.

@router.post("/provider/switch", response_model=ProviderStatus)
async def switch_provider(req: ProviderSwitchRequest):
    """Switch the active LLM provider.

    Switching providers clears all existing conversations because the new
    provider may have different capabilities, context windows, and tool
    formats. Users must start fresh conversations after switching.
    """
    global _current_provider, _conversations

    if req.provider == "ollama":
        _current_provider = OllamaProvider(model=req.model)
    elif req.provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise HTTPException(status_code=400, detail="ANTHROPIC_API_KEY not configured")
        _current_provider = AnthropicProvider(api_key=api_key, model=req.model or "claude-sonnet-4-20250514")

    _conversations.clear()  # Invalidate all sessions — new provider, fresh start

    available = await _current_provider.check_available()
    return ProviderStatus(
        provider=req.provider,
        model=_current_provider.model,
        security_level=_current_provider.security_level,
        available=available,
    )


@router.get("/provider/status", response_model=ProviderStatus)
async def provider_status():
    """Get current LLM provider status and availability."""
    provider = _get_provider()
    available = await provider.check_available()
    return ProviderStatus(
        provider=provider.__class__.__name__.replace("Provider", "").lower(),
        model=provider.model,
        security_level=provider.security_level,
        available=available,
    )
