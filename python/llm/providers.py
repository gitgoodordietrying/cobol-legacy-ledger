"""
providers -- LLM provider abstraction: Ollama (local) and Anthropic (cloud).

This module defines the two LLM providers the system can use, swappable at
runtime via POST /api/provider/switch. The key design tradeoff is security
vs. capability:

    Ollama (LOCAL): All inference runs on the user's machine. Zero data
        exfiltration. Limited model quality (Llama 3.1, Mistral, etc.).
        Default for security-conscious deployments and classroom demos.

    Anthropic (CLOUD): State-of-the-art model quality (Claude). Data leaves
        the machine via HTTPS. Requires API key. Opt-in only — never enabled
        by default. Appropriate when the user explicitly chooses capability
        over data locality.

ProviderResponse normalization:
    Both providers return ProviderResponse objects with the same fields:
    content (text), tool_calls (list), model, provider. This lets the
    ConversationManager's tool-use loop work identically regardless of
    which provider is active.

Tool schema format differences:
    Ollama expects tools wrapped as {"type": "function", "function": {...}}.
    Anthropic expects tools as {"name": ..., "input_schema": {...}}.
    Each provider's chat() method handles the transformation internally.

Dependencies:
    httpx (for Ollama HTTP calls), anthropic (optional, for cloud provider)
"""

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


# ── Data Classes ──────────────────────────────────────────────────
# Normalized response types shared by both providers.

@dataclass
class ToolCall:
    """A tool invocation requested by the LLM.

    The `id` field is provider-specific: Anthropic provides unique IDs
    (e.g., "toolu_123"), Ollama duplicates the tool name as the ID.
    """
    id: str                        # Tool call ID (Anthropic: unique, Ollama: tool name)
    name: str                      # Tool name (e.g., "list_accounts")
    arguments: Dict[str, Any]      # Parsed JSON arguments


@dataclass
class ProviderResponse:
    """Normalized response from an LLM provider.

    Every provider.chat() call returns one of these, regardless of whether
    the response contains text, tool calls, or both. The ConversationManager
    checks tool_calls to decide whether to continue the tool-use loop.
    """
    content: str                   # Text content (may be empty if only tool calls)
    tool_calls: List[ToolCall] = field(default_factory=list)  # Tool invocations (may be empty)
    model: str = ""                # Model that generated this response
    provider: str = ""             # Provider name ("ollama" or "anthropic")


# ── Abstract Base ─────────────────────────────────────────────────
# Contract that both providers implement.

class LLMProvider(ABC):
    """Abstract base for LLM providers.

    Subclasses must implement chat() for inference and check_available()
    for health checks. The security_level class attribute indicates whether
    data stays local or goes to the cloud.
    """

    security_level: str = "UNKNOWN"  # "LOCAL" or "CLOUD"

    @abstractmethod
    async def chat(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] = None) -> ProviderResponse:
        """Send messages to the LLM, optionally with tool definitions."""
        ...

    @abstractmethod
    async def check_available(self) -> bool:
        """Check if the provider is reachable and configured."""
        ...


# ── Ollama Provider ───────────────────────────────────────────────
# Local inference via Ollama's HTTP API. Zero data exfiltration.

class OllamaProvider(LLMProvider):
    """Local Ollama provider — zero-trust, no data leaves the machine.

    Uses Ollama's /api/chat endpoint with function calling support.
    Requires Ollama to be running locally (default: http://localhost:11434).
    Models are pulled separately via `ollama pull llama3.1`.
    """

    security_level = "LOCAL"

    def __init__(self, base_url: str = None, model: str = None):
        """Initialize the Ollama provider.

        :param base_url: Ollama API URL (default: OLLAMA_BASE_URL env or localhost:11434)
        :param model: Model name (default: OLLAMA_MODEL env or llama3.1)
        """
        self.base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or os.environ.get("OLLAMA_MODEL", "llama3.1")
        self.last_error: Optional[str] = None

    @staticmethod
    def _normalize_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert Anthropic-format messages to plain strings for Ollama.

        Anthropic uses content as arrays of typed blocks (text, tool_use,
        tool_result). Ollama expects content as a plain string. This method
        normalizes without losing information — tool calls and results are
        serialized into readable bracketed strings.
        """
        normalized = []
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict):
                        btype = block.get("type", "")
                        if btype == "text":
                            parts.append(block.get("text", ""))
                        elif btype == "tool_use":
                            import json
                            args = json.dumps(block.get("input", {}), default=str)
                            parts.append(f"[Tool call: {block.get('name', '?')}({args})]")
                        elif btype == "tool_result":
                            result_content = block.get("content", "")
                            if isinstance(result_content, list):
                                result_content = " ".join(
                                    b.get("text", str(b)) for b in result_content if isinstance(b, dict)
                                )
                            parts.append(f"[Tool result ({block.get('tool_use_id', '?')}): {result_content}]")
                        else:
                            parts.append(str(block))
                    else:
                        parts.append(str(block))
                normalized.append({**msg, "content": "\n".join(parts)})
            elif content is None:
                # Ollama requires content to be a string, never None
                normalized.append({**msg, "content": ""})
            else:
                normalized.append(msg)
        return normalized

    async def chat(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] = None) -> ProviderResponse:
        """Send messages to Ollama's /api/chat endpoint.

        Transforms tool definitions from Anthropic format to Ollama format
        (wrapping each in {"type": "function", "function": {...}}).
        Normalizes message content from Anthropic array format to plain strings.
        """
        import httpx

        # Normalize Anthropic-format messages to plain strings for Ollama
        messages = self._normalize_messages(messages)

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,       # Tool-use needs complete response (no streaming)
        }
        if tools:
            # Transform Anthropic schema → Ollama function-calling format
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["input_schema"],
                    },
                }
                for t in tools
            ]

        async with httpx.AsyncClient(timeout=120.0) as client:  # 120s timeout for large model inference
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            if resp.status_code != 200:
                error_detail = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"
                raise RuntimeError(f"Ollama error ({self.model}): {error_detail}")
            data = resp.json()

        message = data.get("message", {})
        content = message.get("content", "")
        tool_calls = []

        for tc in message.get("tool_calls", []):
            func = tc.get("function", {})
            tool_calls.append(ToolCall(
                id=func.get("name", ""),      # Ollama doesn't provide unique IDs — use tool name
                name=func.get("name", ""),
                arguments=func.get("arguments", {}),
            ))

        return ProviderResponse(
            content=content,
            tool_calls=tool_calls,
            model=self.model,
            provider="ollama",
        )

    async def check_available(self) -> bool:
        """Check if Ollama is running and the configured model is available.

        If the configured model isn't pulled, auto-selects the first available
        model so the chat works out of the box with any Ollama installation.
        """
        try:
            import httpx
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code != 200:
                    return False
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]
                if not models:
                    return False
                # If configured model isn't available, fall back to a
                # tool-capable model.  Small parameter models (≤1B) like
                # gemma3:1b often lack tool-use support; prefer larger ones.
                if self.model not in models:
                    # Prefer models known to support function calling
                    tool_capable = [
                        m for m in models
                        if not m.endswith(":1b") and "1b" not in m.split(":")[0].split("-")
                    ]
                    self.model = tool_capable[0] if tool_capable else models[0]
                return True
        except Exception as exc:
            logger.warning("Ollama check_available failed (%s): %s", self.base_url, exc)
            self.last_error = str(exc)
            return False


# ── Anthropic Provider ────────────────────────────────────────────
# Cloud inference via Anthropic's SDK. Opt-in, requires API key.

class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider — cloud API, opt-in.

    Uses the anthropic SDK with native tool_use support. Data leaves the
    machine via HTTPS — only enabled when the user explicitly provides an
    API key and switches to this provider.
    """

    security_level = "CLOUD"

    DEFAULT_MODEL = "claude-haiku-4-5-20251001"

    def __init__(self, api_key: str = None, model: str = None):
        """Initialize the Anthropic provider.

        :param api_key: Anthropic API key (default: ANTHROPIC_API_KEY env)
        :param model: Model name (default: ANTHROPIC_MODEL env or claude-sonnet-4-20250514)
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model or os.environ.get("ANTHROPIC_MODEL", self.DEFAULT_MODEL)
        self.last_error: Optional[str] = None

    async def chat(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] = None) -> ProviderResponse:
        """Send messages to Anthropic's messages.create endpoint.

        1. Import anthropic SDK (raises RuntimeError if not installed)
        2. Extract system message (Anthropic uses a separate `system` param)
        3. Convert tools to Anthropic format (name, description, input_schema)
        4. Parse response blocks (text blocks → content, tool_use blocks → tool_calls)
        """
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic package not installed. Install with: pip install anthropic")

        client = anthropic.AsyncAnthropic(api_key=self.api_key)

        # Convert tools to Anthropic format (already compatible, just pass through)
        anthropic_tools = None
        if tools:
            anthropic_tools = [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "input_schema": t["input_schema"],
                }
                for t in tools
            ]

        # Separate system message — Anthropic requires it as a top-level param,
        # not as a message with role="system" in the messages array.
        system_msg = ""
        conv_messages = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                conv_messages.append(m)

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": conv_messages,
        }
        if system_msg:
            kwargs["system"] = system_msg
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        response = await client.messages.create(**kwargs)

        # Parse response blocks — may contain text, tool_use, or both
        content = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,                # Anthropic provides unique tool call IDs
                    name=block.name,
                    arguments=block.input,
                ))

        return ProviderResponse(
            content=content,
            tool_calls=tool_calls,
            model=self.model,
            provider="anthropic",
        )

    async def check_available(self) -> bool:
        """Check if Anthropic is configured (API key present)."""
        if not self.api_key:
            self.last_error = "ANTHROPIC_API_KEY not set"
            logger.warning("Anthropic check_available: no API key configured")
            return False
        self.last_error = None
        return True
