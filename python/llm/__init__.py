"""
llm -- LLM-as-client tool-use architecture for cobol-legacy-ledger.

This package enables an LLM (Ollama local or Anthropic cloud) to interact with
the banking system by calling the same bridge/settlement/codegen methods that
the CLI and REST API use. The LLM is a client, not a controller — it has no
special privileges beyond what its user's RBAC role permits.

Why LLM-as-client (not LLM-as-controller):
    The LLM cannot bypass RBAC, skip validation, or access raw databases.
    Every tool call goes through the same 4-layer pipeline: RBAC gate → input
    validation → dispatch → audit. This means a VIEWER-role user chatting with
    the LLM can only read accounts and view chains, never process transactions.
    The LLM sees the same permission boundaries as a human operator.

Tool-use architecture:
    The LLM provider returns ProviderResponse objects that may contain ToolCall
    requests. The ConversationManager detects these, executes them via the
    ToolExecutor, appends the results to the conversation, and loops until the
    LLM gives a final text response (or hits the safety limit).

Module listing:
    tools.py          — 12 tool definitions in Anthropic-compatible JSON Schema
    tool_executor.py  — 4-layer RBAC-gated dispatch to bridge/codegen methods
    providers.py      — Ollama (LOCAL) and Anthropic (CLOUD) provider adapters
    conversation.py   — Session management + tool-use resolution loop
    audit.py          — SQLite audit log for all tool invocations

Dependencies:
    python.auth, python.bridge, python.settlement, python.cross_verify,
    python.cobol_codegen, httpx (for Ollama), anthropic (optional, for cloud)
"""

__all__ = [
    'tools',
    'tool_executor',
    'providers',
    'conversation',
    'audit',
]
