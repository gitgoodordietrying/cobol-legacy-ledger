"""
ConversationManager -- Orchestrates the LLM ↔ tool-use resolution loop.

This module is the core of the chat experience. When a user sends a message,
the ConversationManager sends it to the LLM provider, checks if the response
contains tool call requests, executes those tools via the ToolExecutor, feeds
the results back to the LLM, and repeats until the LLM gives a final text
response (or the safety limit is reached).

Tool-use loop logic:
    1. User message → append to session history
    2. Send history + tool definitions to LLM provider
    3. If response has no tool_calls → return text (done)
    4. If response has tool_calls → execute each via ToolExecutor
    5. Append tool results to history, go to step 2
    6. Repeat up to MAX_TOOL_ITERATIONS times (safety limit)

MAX_TOOL_ITERATIONS rationale:
    Set to 10 to prevent infinite loops when the LLM keeps requesting tools
    without converging on a text response. In practice, most conversations
    resolve in 1-3 iterations. The limit is a safety net, not a common case.

Session management:
    Each conversation is a list of message dicts stored in _sessions keyed by
    session_id (UUID). Sessions persist for the lifetime of the ConversationManager
    instance (typically one per user per API process). There is no persistent
    storage — sessions are lost on restart. This is appropriate for a demo system.

Dependencies:
    python.auth, python.llm.providers, python.llm.tools, python.llm.tool_executor
"""

import uuid
from typing import Dict, List, Any, Optional

from python.auth import AuthContext
from python.llm.providers import LLMProvider, ProviderResponse
from python.llm.tools import get_tools_for_role
from python.llm.tool_executor import ToolExecutor


# ── Constants ─────────────────────────────────────────────────────

# System prompt: establishes the LLM's role, capabilities, and rules.
# Designed to be concise but complete — the LLM needs to know about the
# 6-node architecture, status codes, and its position as an observer (not
# controller) of the banking system.
SYSTEM_PROMPT = """You are a banking assistant for the COBOL Legacy Ledger system — a 6-node inter-bank settlement network with COBOL analysis capabilities.

## System Overview
- 6 nodes: BANK_A, BANK_B, BANK_C, BANK_D, BANK_E, CLEARING
- Each node has accounts (ACT-X-NNN format) and an SHA-256 integrity chain
- The clearing house holds nostro accounts (NST-BANK-X) for settlement
- Inter-bank transfers use 3-leg settlement through the clearing house

## Your Capabilities
You can use tools to query accounts, process transactions, verify integrity chains, run cross-node verification, and work with COBOL source code (parse, generate, edit, validate).

You also have COBOL analysis tools for understanding legacy spaghetti code:
- **analyze_call_graph**: Always run this first on unfamiliar COBOL. It maps paragraph dependencies, GO TO targets, ALTER modifications, and fall-through paths.
- **trace_execution**: Use this to follow execution through GO TO chains and ALTER-modified paths. Essential for spaghetti code — do NOT try to trace GO TO chains yourself, use this tool.
- **analyze_data_flow**: Track which fields are read/written in each paragraph, or trace a single field across the entire program.
- **detect_dead_code**: Find unreachable paragraphs (common in legacy COBOL — code is "disabled" by removing PERFORM calls but leaving paragraphs in place).
- **explain_cobol_pattern**: Look up unfamiliar COBOL patterns, idioms, or anti-patterns (ALTER, COMP-3, PERFORM THRU, etc.).

## COBOL Analysis Strategy
When asked to analyze or explain COBOL code:
1. Run analyze_call_graph first to understand the program structure
2. Use trace_execution to follow specific execution paths (especially GO TO chains)
3. Use detect_dead_code to identify paragraphs that never execute
4. Use analyze_data_flow to understand how data moves through the program
5. Use explain_cobol_pattern for unfamiliar constructs
Never try to manually trace GO TO chains or ALTER-modified paths — always use the tools.

## Rules
1. Always confirm destructive operations (withdrawals, transfers) before executing
2. Report tool results clearly — show account IDs, balances, status codes
3. If a tool returns an error, explain what happened and suggest alternatives
4. For chain verification failures, explain which layer detected the issue
5. You are an observer — you call the same APIs the CLI uses, nothing special

## Status Codes
00=success, 01=insufficient funds, 02=limit exceeded, 03=invalid, 04=frozen, 99=error
"""

# Safety limit: maximum tool call iterations per chat() invocation.
# Prevents infinite loops if the LLM keeps requesting tools without
# producing a final text response. 10 is generous — most resolve in 1-3.
MAX_TOOL_ITERATIONS = 10


# ── Session Management ────────────────────────────────────────────
# The ConversationManager holds all session state in memory.

class ConversationManager:
    """Manages conversation sessions between a user and the LLM.

    Each user gets one manager instance (keyed by user_id in the API layer).
    A manager can hold multiple sessions (each with its own message history).
    Sessions start with the SYSTEM_PROMPT and accumulate user/assistant/tool messages.
    """

    def __init__(
        self,
        provider: LLMProvider,
        tool_executor: ToolExecutor,
        auth: AuthContext,
    ):
        """Initialize the conversation manager.

        :param provider: LLM provider (Ollama or Anthropic)
        :param tool_executor: Tool executor with RBAC + audit pipeline
        :param auth: User's auth context (determines which tools are available)
        """
        self.provider = provider
        self.executor = tool_executor
        self.auth = auth
        self._sessions: Dict[str, List[Dict[str, Any]]] = {}  # session_id -> message list

    def _get_or_create_session(self, session_id: Optional[str] = None) -> tuple:
        """Get existing session or create new one.

        Returns (session_id, messages). New sessions start with SYSTEM_PROMPT.
        """
        if session_id and session_id in self._sessions:
            return session_id, self._sessions[session_id]
        new_id = session_id or str(uuid.uuid4())
        self._sessions[new_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
        return new_id, self._sessions[new_id]

    # ── Tool-Use Loop ─────────────────────────────────────────────
    # Core loop: send → check tool calls → execute → repeat.

    async def chat(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Send a user message and get a response, resolving any tool calls.

        1. Get or create session
        2. Append user message to history
        3. Get role-appropriate tool definitions
        4. Enter tool-use loop (up to MAX_TOOL_ITERATIONS)
        5. Send history to LLM provider
        6. If no tool calls → append assistant response, return
        7. If tool calls → execute each via ToolExecutor
        8. Append tool results to history, continue loop
        9. If loop exhausts → return safety limit message

        Returns:
            Dict with keys: response, session_id, tool_calls, provider, model
        """
        session_id, messages = self._get_or_create_session(session_id)
        messages.append({"role": "user", "content": message})

        tools = get_tools_for_role(self.auth.role)  # Only tools this role can use
        tool_call_log = []

        for _ in range(MAX_TOOL_ITERATIONS):
            response = await self.provider.chat(messages, tools=tools)

            # No tool calls — final response
            if not response.tool_calls:
                messages.append({"role": "assistant", "content": response.content})
                return {
                    "response": response.content,
                    "session_id": session_id,
                    "tool_calls": tool_call_log,
                    "provider": response.provider,
                    "model": response.model,
                }

            # Process tool calls — add assistant message with tool_use blocks
            assistant_content = []
            if response.content:
                assistant_content.append({"type": "text", "text": response.content})
            for tc in response.tool_calls:
                assistant_content.append({
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.name,
                    "input": tc.arguments,
                })
            messages.append({"role": "assistant", "content": assistant_content})

            # Execute each tool and collect results
            tool_results = []
            for tc in response.tool_calls:
                result = self.executor.execute(
                    tc.name, tc.arguments, self.auth,
                    provider=response.provider,
                )
                # Determine if the call was permitted (no RBAC denial)
                permitted = result.get("permitted") is not False
                tool_call_log.append({
                    "tool_name": tc.name,
                    "params": tc.arguments,
                    "result": result,
                    "permitted": permitted,
                })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": str(result),
                })
            messages.append({"role": "user", "content": tool_results})

        # Safety limit reached — LLM kept requesting tools without converging
        messages.append({"role": "assistant", "content": "I've reached the maximum number of tool calls for this turn. Please try a simpler request."})
        return {
            "response": "Tool call limit reached. Please try a simpler request.",
            "session_id": session_id,
            "tool_calls": tool_call_log,
            "provider": response.provider,
            "model": response.model,
        }

    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get conversation history for a session. Returns empty list if not found."""
        return self._sessions.get(session_id, [])

    def clear_session(self, session_id: str):
        """Clear a conversation session, freeing its message history."""
        if session_id in self._sessions:
            del self._sessions[session_id]

    def list_sessions(self) -> List[str]:
        """List active session IDs."""
        return list(self._sessions.keys())
