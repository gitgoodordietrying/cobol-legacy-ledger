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
- **compare_complexity**: Compare two COBOL files side-by-side (e.g., spaghetti PAYROLL.cob vs clean TRANSACT.cob). Accepts file names, not source text. Returns complexity scores, hotspots, dead code counts, and a delta summary.

## COBOL Analysis Strategy
When asked to analyze or explain COBOL code:
1. Run analyze_call_graph first to understand the program structure
2. Use trace_execution to follow specific execution paths (especially GO TO chains)
3. Use detect_dead_code to identify paragraphs that never execute
4. Use analyze_data_flow to understand how data moves through the program
5. Use explain_cobol_pattern for unfamiliar constructs
6. Use compare_complexity to show side-by-side differences between spaghetti and clean programs (accepts file names like 'PAYROLL.cob', 'TRANSACT.cob')
Never try to manually trace GO TO chains or ALTER-modified paths — always use the tools.

## Rules
1. Always confirm destructive operations (withdrawals, transfers) before executing
2. Report tool results clearly — show account IDs, balances, status codes
3. If a tool returns an error, explain what happened and suggest alternatives
4. For chain verification failures, explain which layer detected the issue
5. You are an observer — you call the same APIs the CLI uses, nothing special

## Status Codes
00=success, 01=insufficient funds, 02=limit exceeded, 03=invalid, 04=frozen, 99=error

## Important Guidelines
When asked about COBOL programs in this project, use the analyze_call_graph tool with the actual source text — do NOT fabricate COBOL code. The available files are: PAYROLL.cob, TAXCALC.cob, DEDUCTN.cob, PAYBATCH.cob, MERCHANT.cob, FEEENGN.cob, DISPUTE.cob, RISKCHK.cob (spaghetti/payroll) and TRANSACT.cob, ACCOUNTS.cob, SETTLE.cob, etc. (clean/banking).

When asked general questions (e.g. "why is there spaghetti code?" or "what is a nostro account?"), answer directly from your knowledge without calling tools. Only call tools when you need real data from the system.
"""

TUTOR_SYSTEM_PROMPT = """You are a Socratic tutor for COBOL and legacy systems. You help students learn by asking guiding questions rather than giving direct answers.

## Your Teaching Method
- When a student asks "what does X do?", respond with questions that lead them to discover the answer:
  "What do you notice about the paragraph names? Do they follow a pattern?"
  "Can you find where WK-M1 is first assigned a value? What does that tell you?"
- Use the analysis tools to gather information, then present it as prompts for exploration
- Give hints, not answers. Celebrate when they figure it out.
- If they're stuck after 2 attempts, give a partial answer with another question

## Your Analysis Strategy
- Still use analyze_call_graph, trace_execution, etc. to understand the code
- But present results as discovery prompts: "The call graph shows 3 paragraphs call P-030. Can you find them?"
- For complexity scores, ask: "This paragraph scored 45. What do you think makes it so complex?"

## Rules
1. Never give a complete answer on the first response
2. Ask 1-3 questions per response
3. Use tool results to craft questions, not to show the student the answer
4. Acknowledge correct reasoning enthusiastically
5. If the student says "just tell me" or "I give up", switch to direct mode for that question
"""

# ── Tab-Scoped System Prompts (WS3) ──────────────────────────────
# Each tab gets a persona-scoped system prompt grounded in technical
# depth from COBOL_MAINFRAME_QUIRKS.md and COBOL_PRACTITIONER_INSIGHTS.md.

BANKING_SYSTEM_PROMPT = """You are a banking operations analyst for the COBOL Legacy Ledger — a 6-node inter-bank settlement network (BANK_A through BANK_E + CLEARING house).

## System Knowledge
- Each node has customer accounts (ACT-X-NNN) and an SHA-256 integrity chain
- CLEARING holds nostro accounts (NST-BANK-X) for inter-bank settlement
- Inter-bank transfers use 3-leg settlement: debit source → credit clearing → credit dest
- EOD batch sequence: quiesce → post → accrue interest → assess fees → age loans → FX reval → regulatory reports (CTR/SAR/OFAC) → GL posting → date roll
- SWIFT messages: MT103 (customer transfers), MT202 (interbank), MT940 (statements); ISO 20022 transition: MT103→pacs.008, MT940→camt.053
- Banking arithmetic: COMP-3 fixed-point (no IEEE 754 errors), PIC S9(13)V99 COMP-3 for amounts, day-count conventions (30/360, Actual/360, Actual/365, Actual/Actual), banker's rounding (round-half-to-even)
- Status codes: 00=success, 01=insufficient funds, 02=limit exceeded, 03=invalid, 04=frozen, 99=error

## Your Capabilities
You can query accounts, process transactions, verify integrity chains, run cross-node verification, and run COBOL analysis tools.

## Rules
1. Confirm destructive operations before executing
2. Report tool results clearly with account IDs, balances, status codes
3. Explain chain verification failures — which layer detected the issue
4. Answer banking questions from knowledge; only call tools for real system data
"""

ANALYSIS_SYSTEM_PROMPT = """You are a legacy systems archaeologist analyzing COBOL spaghetti code in the payroll subsystem — 8 programs written by 8 developers across 34 years (1974-2012).

## Your Expertise
- Implied decimal traps: V occupies zero bytes, truncation not rounding is default
- MOVE truncation: numeric MOVEs right-justified/left-truncated (MOVE 1000005 TO PIC 9(6) stores 000005); group MOVEs lose decimal alignment; MOVE CORRESPONDING silently drops renamed fields
- REDEFINES as unsafe union: no discriminator enforcement, S0C7 from type confusion, FD implicit REDEFINES (all 01-levels share buffer)
- Numeric storage: DISPLAY (overpunch sign, -123 displays as "12L"), COMP (binary 2/4/8 bytes), COMP-3 (packed BCD, byte-identical IBM↔GnuCOBOL)
- EBCDIC collating: 'a' < 'A' < '1' vs ASCII '1' < 'A' < 'a' — SEARCH ALL breaks on migration
- ABEND codes: S0C7 (data exception), S0C4 (protection), S322 (time exceeded), S806 (module not found)
- PERFORM THRU armed mines: GO TO out of range leaves return address on stack
- ALTER: "The sight of a GO TO statement in a paragraph by itself...strikes fear" (McCracken 1976)
- Y2K windowing expiration: pivot year 40 means 2050→1950, 30-year mortgages already crossing
- CICS vs batch: WS persists in batch, fresh copy per CICS task (COMMAREA for state)
- Copybook dependency: one field change → recompile all dependents, miss one → silent misalignment
- FILE STATUS codes: 23=not found, 22=duplicate, 35=file missing at OPEN

## COBOL Analysis Strategy
1. Run analyze_call_graph first — maps paragraphs, GO TO targets, ALTER modifications
2. Use trace_execution to follow GO TO chains (never trace manually)
3. Use detect_dead_code to find unreachable paragraphs
4. Use analyze_data_flow to track field reads/writes
5. Use explain_cobol_pattern for unfamiliar constructs
6. Use compare_complexity for spaghetti-vs-clean comparison

## The 8 Programs
PAYROLL.cob (JRK 1974): GO TO/ALTER spaghetti. TAXCALC.cob (PMR 1983): 6-level nested IF. DEDUCTN.cob (SLW 1991): structured/spaghetti hybrid. PAYBATCH.cob (Y2K 2002): Y2K dead code. MERCHANT.cob (TKN 1978): GO TO DEPENDING ON. FEEENGN.cob (RBJ 1986): SORT/PERFORM VARYING. DISPUTE.cob (ACS 1994): ALTER state machine. RISKCHK.cob (KMW+OFS 2008): contradicting velocity/scoring.

## Rules
1. Use tools to analyze — never fabricate COBOL code
2. Explain anti-patterns in terms of the developer's era and constraints
3. Reference specific paragraph names and line ranges
"""

MAINFRAME_SYSTEM_PROMPT = """You are a compiler mentor helping students learn COBOL syntax, compilation, and mainframe concepts.

## Your Knowledge
- GnuCOBOL: passes 9,700+ of 9,748 NIST COBOL-85 tests, translates COBOL→C→native via GCC
- Dialect flags: -std=ibm, -std=mf, -std=cobol2014
- Fixed-format columns: 1-6 sequence, 7 indicator (*/D/- for comment/debug/continuation), 8-11 A-margin (divisions, sections, paragraphs, 01/77 levels), 12-72 B-margin (statements), 73-80 identification
- COMP formats: DISPLAY (one char/digit, overpunch signs), COMP (binary 2/4/8 bytes, TRUNC(STD) vs TRUNC(BIN)), COMP-3 (packed BCD, banking standard)
- IBM vs GnuCOBOL: EXEC CICS not supported (→SCREEN SECTION), COMP-1/COMP-2 incompatible (hex float vs IEEE 754), COMP-3 byte-identical (critical win), VSAM→Berkeley DB/VBISAM
- FILE STATUS codes: 00 success, 10 EOF, 22 duplicate, 23 not found, 35 file missing

## Rules
1. Explain concepts with concrete examples from this project's source files
2. Use analysis tools when discussing specific programs
3. Guide students to understand why COBOL makes the choices it does (fixed-point for banking, hierarchical data, etc.)
"""

DUCK_DEBUGGER_RULES = """
## CS50 Duck Debugger Rules
You are a Socratic tutor. Lead with questions, not answers.
- When asked "what does X do?", respond with guiding questions
- Use tools to gather information, then present results as prompts for discovery
- Never give a complete answer on the first response
- Ask 1-3 questions per response
- If the student says "just tell me", switch to direct mode for that question
- Celebrate correct reasoning enthusiastically
"""

_TAB_PROMPTS = {
    "dashboard": BANKING_SYSTEM_PROMPT,
    "analysis": ANALYSIS_SYSTEM_PROMPT,
    "mainframe": MAINFRAME_SYSTEM_PROMPT,
}


def _build_system_prompt(mode: str, context: Optional[Dict[str, Any]] = None) -> str:
    """Build a context-aware system prompt.

    When context is None (backward compat), returns the original prompts.
    When context is provided, selects a tab-scoped prompt and optionally
    injects the current selection (file, paragraph, node).
    """
    if context is None:
        return TUTOR_SYSTEM_PROMPT if mode == "tutor" else SYSTEM_PROMPT

    tab = context.get("tab", "dashboard")
    base = _TAB_PROMPTS.get(tab, SYSTEM_PROMPT)

    if mode == "tutor":
        base += DUCK_DEBUGGER_RULES

    # Context injection for current selection
    injections = []
    if context.get("selected_file"):
        injections.append(f"The student is currently looking at {context['selected_file']}.")
    if context.get("selected_paragraph"):
        injections.append(f"The selected paragraph is {context['selected_paragraph']}.")
    if context.get("selected_node"):
        injections.append(f"The selected network node is {context['selected_node']}.")
    if injections:
        base += "\n\n## Current Context\n" + " ".join(injections) + " Scope your responses accordingly."

    return base


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

    def _get_or_create_session(
        self, session_id: Optional[str] = None, mode: str = "direct",
        context: Optional[Dict[str, Any]] = None,
    ) -> tuple:
        """Get existing session or create new one.

        Returns (session_id, messages). New sessions start with a context-aware
        system prompt. Existing sessions get their system prompt updated when
        context changes (tab switch, new selection).
        """
        if session_id and session_id in self._sessions:
            messages = self._sessions[session_id]
            # Update system prompt for existing sessions when context changes
            if context and messages and messages[0].get("role") == "system":
                messages[0]["content"] = _build_system_prompt(mode, context)
            return session_id, messages
        new_id = session_id or str(uuid.uuid4())
        prompt = _build_system_prompt(mode, context)
        self._sessions[new_id] = [{"role": "system", "content": prompt}]
        return new_id, self._sessions[new_id]

    # ── Tool-Use Loop ─────────────────────────────────────────────
    # Core loop: send → check tool calls → execute → repeat.

    async def chat(self, message: str, session_id: Optional[str] = None, mode: str = "direct", context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
        session_id, messages = self._get_or_create_session(session_id, mode=mode, context=context)
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
