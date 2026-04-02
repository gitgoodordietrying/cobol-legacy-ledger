# Spec: Chat Slide-Out Panel — Context-Aware Socratic Tutor

**Status**: Drafting
**Created**: 2026-04-02

## Overview

Transform the chatbot from an isolated Tab 3 into a floating slide-out panel that works across all tabs with context awareness. Introduce an EventBus for cross-tab pub/sub communication, context-scoped system prompts per active tab, CS50 duck debugger Socratic behavior, and visual tool result rendering using existing SVG components. The EventBus is foundational infrastructure that workstreams 4 (Analysis Overhaul) and 5 (COBOL Mainframe Dashboard) depend on.

---

## User Stories

### US-1: EventBus Foundation (Priority: P1)

As a **system**, I want a lightweight pub/sub EventBus so that all UI modules can communicate without direct coupling.

**Acceptance Scenarios**:
1. Given the EventBus module is loaded, When any module calls `EventBus.emit('tab.changed', { tab: 'analysis' })`, Then all subscribers to 'tab.changed' receive the event payload.
2. Given a module has subscribed to an event, When it calls `EventBus.off('event.name', handler)`, Then it no longer receives that event.
3. Given multiple subscribers exist for one event, When the event is emitted, Then all subscribers are called in registration order.
4. Given no subscribers exist for an event, When that event is emitted, Then no error is thrown (silent no-op).

### US-2: Slide-Out Panel Toggle (Priority: P1)

As a **student**, I want to toggle a chat panel from any tab so I can ask questions while exploring the banking simulator or analyzing code without losing my place.

**Acceptance Scenarios**:
1. Given I am on the Dashboard tab, When I click the chat toggle button, Then a slide-out panel appears from the right side, overlaying (not displacing) the Dashboard content.
2. Given the chat panel is open, When I click the toggle button again, Then the panel slides closed with a CSS animation.
3. Given the chat panel is open, When I press Escape, Then the panel closes.
4. Given the chat panel is open on Dashboard, When I switch to Analysis, Then the panel remains open and my conversation is preserved.
5. Given the chat panel is closed, When I switch between tabs, Then no chat UI is visible and no layout shift occurs.

### US-3: Context-Aware System Prompts (Priority: P1)

As a **student**, I want the chatbot's personality to automatically adjust to the tab I am on so that its responses are relevant to what I am doing.

**Acceptance Scenarios**:
1. Given I am on Dashboard with chat open, When I send a message, Then the system prompt scopes the LLM to banking/settlement personality.
2. Given I am on Analysis with chat open, When I send a message, Then the system prompt scopes the LLM to archaeology/anti-pattern personality.
3. Given I switch from Dashboard to Analysis with chat open, When I send my next message, Then the system prompt has changed to match the new tab.
4. Given the future Mainframe tab exists, When I am on it, Then the system prompt scopes to compiler mentoring personality.

### US-4: Context Injection — Active Selection (Priority: P2)

As a **student**, I want the chat to know what file, paragraph, or node I have selected so that my questions get contextually relevant answers.

**Acceptance Scenarios**:
1. Given I have selected PAYROLL.cob in the Analysis file dropdown, When I ask "What does P-030 do?", Then the LLM receives context indicating the active file is PAYROLL.cob.
2. Given I have clicked a node in the call graph (e.g., P-040), When I ask "Why is this paragraph complex?", Then the LLM receives context indicating the selected paragraph is P-040 in PAYROLL.cob.
3. Given I have clicked BANK_C in the network graph, When I ask "Show me the accounts", Then the LLM receives context indicating the selected node is BANK_C.
4. Given no selection is active, When I ask a question, Then the LLM receives only the tab context.

### US-5: CS50 Duck Debugger Behavior (Priority: P1)

As a **student**, I want the tutor to lead with Socratic questions and never give direct answers so that I learn by discovering.

**Acceptance Scenarios**:
1. Given tutor mode is enabled, When I ask "What does ALTER do?", Then the response contains at least one question and does NOT contain a direct definition.
2. Given tutor mode is enabled, When I ask the same question a third time, Then the response provides a partial answer followed by another guiding question.
3. Given tutor mode is disabled, When I ask "What does ALTER do?", Then the response provides a direct, comprehensive answer.
4. Given tutor mode is enabled, When I say "just tell me", Then the response switches to direct mode for that question only.

### US-6: Scoped Suggested Prompts (Priority: P2)

As a **student**, I want the chat panel to show different prompt chips based on the active tab so I get relevant conversation starters.

**Acceptance Scenarios**:
1. Given I am on Dashboard, When I open chat with no active conversation, Then I see prompt chips like "What is a nostro account?", "Verify all chains", "Run a settlement".
2. Given I am on Analysis, When I open chat with no active conversation, Then I see prompt chips like "Analyze PAYROLL.cob", "Compare spaghetti vs clean COBOL", "What is PERFORM THRU?".
3. Given I switch tabs while prompt chips are visible, Then the chips update to match the new tab.

### US-7: Visual Tool Results (Priority: P2)

As a **student**, I want tool results in chat to render as interactive visualizations instead of raw JSON so I can understand the data at a glance.

**Acceptance Scenarios**:
1. Given the LLM calls analyze_call_graph, When the result is displayed in chat, Then a mini CallGraphView SVG renders inline instead of raw JSON.
2. Given the LLM calls compare_complexity, When the result is displayed, Then a compact comparison card renders with score bars.
3. Given a tool returns simple tabular data, When the result is displayed, Then it renders as a formatted HTML table.
4. Given a tool call fails, When the result is displayed, Then it renders as a styled error card.

### US-8: Provider and Session Continuity (Priority: P1)

As a **student**, I want my chat provider settings and session history to persist when the panel opens and closes so I do not lose my conversation.

**Acceptance Scenarios**:
1. Given I have an active conversation, When I close and reopen the panel, Then my conversation history is visible.
2. Given I have switched to Anthropic, When I close and reopen the panel, Then the provider remains Anthropic.
3. Given the chat panel is open with a conversation, When I switch tabs, Then the conversation persists (same session, updated system prompt).

### US-9: Instructor Configuration (Priority: P3)

As an **instructor**, I want to configure the default Socratic behavior so I can tailor the learning experience.

**Acceptance Scenarios**:
1. Given tutor mode is toggled on, Then all subsequent responses use the Socratic system prompt until toggled off.
2. Given the instructor toggles tutor mode off mid-conversation, Then subsequent responses use direct mode without losing conversation history.

---

## Functional Requirements

### EventBus (`console/js/event-bus.js`)

- **FR-001**: Create an EventBus module as a vanilla JS IIFE exposing `on(event, handler)`, `off(event, handler)`, `emit(event, payload)`, and `once(event, handler)`. Maximum 30 lines of implementation code.

- **FR-002**: EventBus must support these initial event types:
  - `tab.changed` — payload: `{ tab: 'dashboard' | 'analysis' | 'chat' | 'mainframe' }`
  - `selection.changed` — payload: `{ type: 'file' | 'paragraph' | 'node' | null, id: string, context: object }`
  - `chat.toggle` — payload: `{ open: boolean }`
  - `chat.context.update` — payload: `{ tab: string, selection: object, prompts: string[] }`

- **FR-003**: `App.switchView()` in `app.js` must emit `tab.changed` on every tab switch. This is the only required modification to `app.js` for the EventBus foundation.

- **FR-004**: `analysis.js` must emit `selection.changed` when the user selects a file in the dropdown or clicks a call graph node.

- **FR-005**: `network-graph.js` must emit `selection.changed` when the user clicks a network node.

### Slide-Out Panel (`console/css/chat.css`, `console/index.html`)

- **FR-006**: Replace the `view-chat` tab section in `index.html` with a fixed-position slide-out panel element outside the `<main>` content flow. Add a toggle button visible in the nav bar.

- **FR-007**: Panel animation must be CSS-only: `transform: translateX(100%)` (closed) to `transform: translateX(0)` (open), with `transition: transform 300ms cubic-bezier(0.4, 0, 0.2, 1)`.

- **FR-008**: Panel width: 420px on screens > 1200px, 360px on 768-1200px, 100% on < 768px (full overlay on mobile).

- **FR-009**: On mobile (< 768px), show a semi-transparent backdrop overlay when the panel is open. Clicking the backdrop closes the panel.

- **FR-010**: Panel z-index must be higher than the nav bar (nav is z-index: 100; panel must be z-index: 200).

- **FR-011**: Remove the Chat tab button from `nav__tabs`. Add a chat toggle button to the right side of the nav bar (icon-based, using a Unicode speech bubble character or CSS shape).

### Chat Module Refactor (`console/js/chat.js`)

- **FR-012**: Refactor `Chat.init()` to subscribe to EventBus events: `tab.changed` (update context), `selection.changed` (update context), `chat.toggle` (open/close panel).

- **FR-013**: Add `Chat.setContext(tabName, selection)` method that updates current context and refreshes prompt chips to match the active tab.

- **FR-014**: Move sidebar elements (provider switcher, model selector, API key, session list) into a collapsible section within the slide-out panel header.

- **FR-015**: The chat toggle button must show an unread indicator (dot or badge) when the LLM responds while the panel is closed.

### Context-Aware System Prompts (`python/llm/conversation.py`)

- **FR-016**: Add a `context` parameter to `ConversationManager.chat()`. Context includes: `{ tab: string, selected_file: string|null, selected_paragraph: string|null, selected_node: string|null }`.

- **FR-017**: Create 3 tab-scoped system prompt variants, each grounded in technical depth from `COBOL_MAINFRAME_QUIRKS.md`:
  - **Banking (Dashboard)**: Settlement, transactions, integrity verification, nostro accounts. Personality: operations analyst. Must understand: EOD batch processing sequence (9-step nightly cycle from transaction posting through GL posting and date roll, gated by job schedulers CA-7/TWS/Control-M), SWIFT MT message formats (MT103 customer transfers, MT202 interbank, MT940 statements, `:32A:` tag format `YYMMDDCCY9999,99`, ISO 20022 transition MT103→pacs.008 and MT940→camt.053), regulatory batch programs (CTR $10K aggregate same-day cash per customer, SAR structuring/velocity/round-amount detection, OFAC SDN list exact+fuzzy matching), banking data patterns (VSAM KSDS for accounts, ESDS for transaction logs, account numbers as PIC X(16) not PIC 9 to preserve leading zeros, journal records with before/after images and SOX 302/404 7-year retention), and banking arithmetic (COMP-3 fixed-point avoiding IEEE 754 errors, `PIC S9(13)V99 COMP-3` for monetary amounts up to ±$999T, day-count conventions 30/360 vs Actual/360 vs Actual/365 vs Actual/Actual, multi-currency ISO 4217 with decimal-places indicator JPY=0 BHD=3, banker's rounding round-half-to-even must be coded explicitly).
  - **Analysis**: Archaeology, anti-patterns, complexity scoring, code comparison. Personality: legacy systems archaeologist. Must understand: implied decimal traps (V occupies zero bytes, truncation default), MOVE truncation rules (alphanumeric left-justified/right-truncated vs numeric right-justified/left-truncated, group MOVE losing decimal alignment, MOVE CORRESPONDING silent field drops), REDEFINES as unsafe union (S0C7 from type confusion, FD implicit REDEFINES, 88-level type guards), three numeric storage formats (DISPLAY with overpunch sign encoding — `-123` displays as `"12L"`, COMP binary size breakpoints, COMP-3 packed BCD two digits/byte), EBCDIC collating reversal (`'a' < 'A' < '1'` in EBCDIC, reversed in ASCII, SEARCH ALL binary search fails on ASCII), ABEND codes (S0C7 data exception, S0C4 protection exception, S322 time exceeded, S806 module not found, CEEDUMP as primary debugging artifact), PERFORM THRU armed mines (GO TO out of range leaves return address on control stack), Y2K windowing expiration (pivot year 40, 2050→1950), CICS WS persistence traps (fresh copy per task, COMMAREA state passing), copybook dependency hell (one change→50-200 recompiles, silent field misalignment), FILE STATUS codes (23 not found, 22 duplicate key, 35 file not found at OPEN), and the "70% of business rules only in code" finding with the car-leasing system story. Should reference the McCracken ALTER quote when discussing ALTER patterns.
  - **Mainframe (future)**: COBOL syntax, compilation, coding challenges. Personality: compiler mentor. Must understand: GnuCOBOL specifics (passes 9,700+/9,748 NIST tests, translates COBOL→C→native via GCC, dialect flags `-std=ibm`/`-std=mf`/`-std=cobol2014`), COMP storage formats (DISPLAY one char/digit with overpunch, COMP binary 2/4/8 bytes, COMP-3 packed BCD, TRUNC(STD) vs TRUNC(BIN)), fixed-format column rules (1-6 sequence, 7 indicator/comment/continuation, 8-11 A-margin for division/section/paragraph headers and 01/77-level items, 12-72 B-margin for statements, 73-80 identification), critical IBM vs GnuCOBOL incompatibilities (EXEC CICS→SCREEN SECTION, EXEC SQL→PostgreSQL/ODBC preprocessors, VSAM→Berkeley DB/VBISAM, COMP-1/COMP-2 hex float vs IEEE 754 — completely incompatible, COMP-3 byte-identical — the critical win), FILE STATUS code interpretation (22/23/35 + what unchecked I/O means), and JCL-to-shell-script equivalences for students coming from mainframe documentation.

  Each variant must include the CS50 duck debugger rules when tutor mode is active.

- **FR-018**: When context includes a selected file or paragraph, append a context injection block to the system prompt: "The student is currently looking at [file] / [paragraph]. Scope your responses accordingly."

### API Changes (`python/api/routes_chat.py`)

- **FR-019**: Extend `ChatRequest` model to accept optional `context` field: `{ tab: str, selected_file: str|None, selected_paragraph: str|None, selected_node: str|None }`.

- **FR-020**: Pass context from the chat request through to `ConversationManager.chat()`.

### Visual Tool Results (`console/js/chat.js`)

- **FR-021**: When a tool call result contains call graph data (detected by `paragraphs` and `edges` keys), render a mini CallGraphView inside the chat message bubble (300px tall, horizontally scrollable).

- **FR-022**: When a tool call result contains comparison data (detected by `a` and `b` keys with `score` fields), render a compact comparison card with score bars.

- **FR-023**: When a tool call result contains tabular data (arrays of objects with consistent keys), render an HTML table with glass styling.

- **FR-024**: Preserve the existing collapsible raw JSON view as a "Show raw" toggle below each visual result.

### Prompt Chips per Tab

- **FR-025**: Define three sets of prompt chips in `chat.js`:
  - Dashboard: banking operations, settlement, chain verification prompts
  - Analysis: COBOL analysis, comparison, pattern explanation prompts
  - Mainframe: compilation, syntax, challenge prompts (placeholder for WS5)

  Update chips when `tab.changed` fires.

---

## Success Criteria

- **SC-001**: The EventBus module loads and is accessible globally. All 4 event types fire correctly.
- **SC-002**: The chat panel opens and closes via the toggle button on all tabs with a smooth CSS animation under 400ms.
- **SC-003**: A student can ask "What does P-030 do?" while viewing PAYROLL.cob in Analysis, and the LLM response references PAYROLL.cob specifically (not a generic answer).
- **SC-004**: Switching from Dashboard to Analysis with the panel open changes prompt chips from banking to analysis prompts within one render cycle.
- **SC-005**: The slide-out panel does not cause layout shift in the underlying tab content. Dashboard network graph, Analysis call graph, and all controls remain fully usable while the panel is open.
- **SC-006**: Tutor mode produces Socratic responses (at least one question per response) when enabled. Direct mode produces comprehensive answers when disabled.
- **SC-007**: At least one tool result type (call graph or comparison) renders as a visual component inside a chat message instead of raw JSON.
- **SC-008**: All 807 existing tests pass unchanged.
- **SC-009**: No Node.js dependencies introduced. EventBus, chat panel, and all new JS are vanilla JavaScript loaded via script tags.
- **SC-010**: The panel functions correctly when no LLM provider is available — toggle works, panel opens, clear "No LLM available" message shown.

---

## Edge Cases & Out-of-Scope

### Edge Cases

- **EC-001**: Panel open + window resize — must respond to responsive breakpoints. If window shrinks below 768px while panel is open, transition to full-width overlay with backdrop.
- **EC-002**: Rapid tab switching with panel open — EventBus must handle rapid `tab.changed` emissions without race conditions in prompt chip rendering.
- **EC-003**: Context injection with no active selection — system prompt must gracefully omit selection context (do not send `selected_file: null` to the LLM).
- **EC-004**: Session continuity across provider switch — switching providers clears conversations (existing behavior). Panel must show "Provider changed — start a new conversation" message.
- **EC-005**: Tool result rendering for unknown types — tools not matching call graph, comparison, or tabular patterns must fall through to existing JSON display.
- **EC-006**: Panel open during simulation — must not interfere with SSE streaming. Event feed and chat panel are independent channels.
- **EC-007**: Keyboard accessibility — toggle button must be focusable and activatable with Enter/Space. Panel must trap focus when in full overlay mode on mobile.

### Out-of-Scope

- No COBOL or data file changes (Layers 2-3 only)
- No new LLM tools (existing 20 tools are sufficient)
- No persistent chat history (sessions remain in-memory)
- No multi-user support
- No voice input or TTS output
- No drag-to-resize panel (fixed widths per breakpoint)
- No chat history export or share
- No WebSocket upgrade (keep HTTP POST for chat, SSE for simulation)
- No Mainframe tab implementation (WS5; only system prompt placeholder created here)
- No changes to Ollama/Anthropic provider architecture
- No RAG or vector database integration

---

## [NEEDS CLARIFICATION]

- **NC-001**: Provider controls placement — the current chat tab has a full sidebar with provider switcher, model selector, API key, and session list. Should all of these move into the slide-out panel header (collapsible), or should provider switching move to a separate settings modal to keep the panel slim? Recommended: collapsible section in panel header to keep it self-contained.
