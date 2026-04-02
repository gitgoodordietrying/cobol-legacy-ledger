# Overhaul Handoff — Detailed Findings

**Purpose:** Briefing document for a new Claude instance starting spec-writing for the overhaul roadmap. Read this AFTER `docs/OVERHAUL_ROADMAP.md` and BEFORE writing any `specs/` documents.

**What this contains:** Specific findings from codebase exploration that the roadmap summarizes but doesn't detail. This saves re-exploring dozens of files.

---

## 1. Spaghetti Code: Current Depth & Gaps

### What Exists (Strong)

The 8 payroll programs in `COBOL-BANKING/payroll/src/` total ~3,200 lines with 25+ distinct anti-patterns:

| Program | Lines | Era | Key Anti-Patterns |
|---|---|---|---|
| `PAYROLL.cob` | 472 | 1974 | GO TO network (P-000→P-090), ALTER ×6, PERFORM THRU, cryptic names |
| `TAXCALC.cob` | 288 | 1983 | 6-level nested IF (no END-IF), misleading comments (5% vs 7.25%) |
| `DEDUCTN.cob` | 339 | 1991 | Structured/spaghetti hybrid, mixed COMP types (COMP-3/COMP/DISPLAY) |
| `PAYBATCH.cob` | 368 | 2002 | Y2K dead code, parallel date fields, excessive DISPLAY tracing |
| `MERCHANT.cob` | 449 | 1978 | GO TO DEPENDING ON, shared WS coupling (WK-M1→WK-M7), COPY REPLACING |
| `FEEENGN.cob` | 451 | 1986 | SORT INPUT/OUTPUT PROCEDURE, 3-deep PERFORM VARYING, "temporary" blend override (since 1989) |
| `DISPUTE.cob` | 451 | 1994 | ALTER state machine, dead Report Writer (RD section), STRING/UNSTRING |
| `RISKCHK.cob` | 447 | 2008 | Contradicting velocity checks (KMW vs OFS dual paths), INSPECT TALLYING |

**Developer personalities are well-differentiated:**
- JRK (1974): Cryptic 4-char paragraph names, minimal comments
- TKN (1983): Verbose comments that are factually wrong
- PMR (1991): Careful section headers, incomplete documentation
- RBJ (2002): Y2K patches with TODO comments never resolved
- SLW, ACS, KMW, OFS: Each have distinct styles visible in their sections

**Already-implemented anti-patterns (verified in code):**
- GO TO networks (20+ instances)
- ALTER statements (6 instances)
- GO TO DEPENDING ON (2 instances)
- PERFORM THRU (3 instances)
- 6-level nested IF without END-IF
- SORT INPUT/OUTPUT PROCEDURE (coroutine-style)
- Triple-nested PERFORM VARYING
- Misleading comments (5+ locations)
- Dead code (9+ dead paragraphs)
- Dead Report Writer
- Y2K artifacts with parallel date fields
- Magic numbers throughout
- Mixed COMP types
- COPY REPLACING
- Dead constants (garnishment, zeroed since 1993)
- Contradicting values (5+ locations)
- Dual code paths
- Copy-paste degradation
- Shared WORKING-STORAGE coupling
- STRING/UNSTRING parsing
- INSPECT TALLYING
- Hardcoded values overriding copybooks
- Nested EVALUATE TRUE (3-level)

### What's Missing (Enrichment Opportunities)

These gaps were identified by cross-referencing practitioner insights (`docs/research/COBOL_PRACTITIONER_INSIGHTS.md`) against the actual code:

**Priority 1 — High Impact:**

1. **Missing period bugs**: COBOL periods terminate all open scopes. The Nordea 16-hour outage was caused by a single missing period. The spaghetti code has nested IF without END-IF but NO actual period-related traps. Add 2-3 scenarios where a misplaced or missing period changes behavior subtly — documented as "close enough" by the original developer.

2. **Batch ordering assumptions**: Real legacy systems assume files arrive pre-sorted. Add comments like "MERCHANT-FILE MUST be sorted by MERCH-ID. MR-060 scans sequentially and stops at first match. If unsorted, wrong merchant gets billed. Silently." This is extremely common in real mainframe code.

3. **Numeric overflow edge cases**: `WS-ANNUAL-GROSS = WS-PERIOD-GROSS * 26` can overflow if period gross > ~$38K (exceeds S9(9)). Per-transaction fee addition loses precision for 10000+ transactions. Document these as "known limits" that nobody actually enforces.

**Priority 2 — Medium Impact:**

4. **COMP-3/EBCDIC heritage artifacts**: Comments referencing mainframe heritage — "Field MUST be COMP-3 because downstream SORT expects packed decimal in bytes 47-54." "WS-SPECIAL was USAGE DISPLAY but caused byte-order issues when JCL sort ran."

5. **Field reuse ambiguity**: Same field used for different purposes in different branches. WK-M4 documented as "known MCC flag" but also used as "override count" in a different path. WS-DISPLAY-SCORE used for both "output formatting" and "intermediate calculation."

6. **Abend/recovery notes**: Developer comments about what breaks and how to debug. "SORT will abend with S222 if SORT-RECORD and sort KEY don't align." "If TRANSACTION-FILE is missing, RK-VELOCITY-CHECK silently skips. Cost us $50K in 2010."

7. **Implicit array bounds**: DISPUTE.cob `WS-TBL` OCCURS 500 TIMES — what happens at 501? FEEENGN.cob tier nesting: loop goes to 4 but OCCURS is also 4 — adding tier 5 breaks silently.

8. **Midnight/timezone hazards**: RISKCHK.cob velocity check uses `WS-CURRENT-HOUR` — hourly counter resets if batch spans midnight. FEEENGN.cob "overnight" job processing at 23:50→00:10 splits merchant daily volume across two days.

**Priority 3 — Nice to Have:**

9. **3270 terminal / VSAM era artifacts**: Comments like "MERCHREC layout designed for 3270 screen width (80 chars input). RBJ extended to 120 but JCL DCB still says 80."

10. **Input validation apathy**: MERCHANT.cob MR-000 parses command-line via fixed-position substrings with no length check. DISPUTE.cob UNSTRING catches missing fields but not malformed fields.

11. **Deliberate workarounds**: "SLW divided by 12 not 26 for medical estimation. Off by ~54%." "Y2K team used 30% flat tax instead of calling TAXCALC because 'we're out of time.'"

**Constraint:** All enrichments must be comments, WORKING-STORAGE additions, dead code blocks, or documentation. No changes to executable logic. All 807 tests must still pass.

### Files to Modify
- `COBOL-BANKING/payroll/src/*.cob` — all 8 programs
- `COBOL-BANKING/payroll/copybooks/*.cpy` — add heritage comments to all 7 copybooks
- `COBOL-BANKING/payroll/KNOWN_ISSUES.md` — add new anti-pattern codes (PP-01 period, BO-01 batch order, NO-01 numeric overflow, etc.)
- `COBOL-BANKING/payroll/README.md` — enrich fictional developer history with new incidents

---

## 2. Analysis Tab: Rich Backend, Shallow Frontend

### Backend Endpoints — What Exists

All endpoints are in `python/api/routes_analysis.py`:

| Endpoint | What It Returns | Used in UI? |
|---|---|---|
| `POST /api/analysis/call-graph` | Paragraphs, edges (PERFORM/GOTO/ALTER/FALL_THROUGH), ALTER targets | YES — renders SVG call graph |
| `POST /api/analysis/complexity` | Per-paragraph scores + factors + anti-pattern counts | PARTIALLY — total score shown, factors NOT shown |
| `POST /api/analysis/dead-code` | REACHABLE/DEAD/ALTER_CONDITIONAL per paragraph | PARTIALLY — count shown, categories NOT shown |
| `POST /api/analysis/data-flow` | Field reads/writes per paragraph | NEVER CALLED |
| `POST /api/analysis/cross-file` | Multi-file CALL/COPY dependencies | YES — separate cross-file view |
| `POST /api/analysis/compare` | Complexity + dead code for two files | YES — but only surface data rendered |
| `POST /api/analysis/explain-paragraph` | Complexity + factors + edges + dead status + field accesses | NEVER CALLED |
| `POST /api/analysis/trace` | Ordered execution path following GO TO/ALTER chains | YES — but only in trace panel, NOT in comparison |

### What the Compare Viewer Shows vs What It Could Show

**Currently rendered** (`console/js/compare-viewer.js`, 137 lines):
- Side-by-side source code with heatmap coloring (clean/low/medium/high/dead)
- Header stats: total_score, rating text, dead_count (3 numbers each side)
- Inline score badges on paragraph headers

**Available in the API response but NOT rendered:**
- `paragraphs[name].factors` — strings like "GO TO x4 (+20)", "ALTER x2 (+30)" explaining WHY the score is high
- `paragraphs[name].goto_count`, `alter_count`, `perform_thru_count`, `goto_depending_count`, `max_if_depth` — detailed anti-pattern counts
- `dead_code.dead[]` — which specific paragraphs are unreachable
- `dead_code.alter_conditional[]` — which paragraphs are only reachable via runtime ALTER

**Never fetched in comparison context:**
- `explain-paragraph` — per-paragraph deep dive with edges, field accesses
- `data-flow` — "WS-GROSS modified by 23 paragraphs" vs "modified by 1"
- `trace` for comparison — show spaghetti's chaotic jumps vs clean's linear flow

### Analysis Module Capabilities (Python Backend)

| Module | File | What It Computes |
|---|---|---|
| Call Graph | `python/cobol_analyzer/call_graph.py` | Paragraph dependencies, edge types, ALTER target map, `trace_execution()` follows GO TO chains deterministically |
| Complexity | `python/cobol_analyzer/complexity.py` | Per-paragraph scoring: GO TO (+5), ALTER (+15), PERFORM THRU (+8), nested IF (+3/level), magic number (+2). Ratings: clean (0-19), moderate (20-49), spaghetti (50+) |
| Dead Code | `python/cobol_analyzer/dead_code.py` | Three categories: REACHABLE, DEAD, ALTER_CONDITIONAL |
| Data Flow | `python/cobol_analyzer/data_flow.py` | Field read/write tracking per paragraph |
| Cross-File | `python/cobol_analyzer/cross_file.py` | CALL/COPY dependency graph across files |
| Knowledge Base | `python/cobol_analyzer/knowledge_base.py` | ~20 COBOL pattern encyclopedia entries |

### UI Component Architecture

| Component | File | Lines | Purpose |
|---|---|---|---|
| Analysis controller | `console/js/analysis.js` | 506 | View controller, wires call graph + trace + compare |
| Call graph renderer | `console/js/call-graph.js` | 779 | SVG DAG with color-coded complexity, edge type legend, click interaction |
| Compare viewer | `console/js/compare-viewer.js` | 137 | Side-by-side source with heatmap (SHALLOW — only 137 lines) |

### Key Gap: The Compare Viewer at 137 Lines

The compare viewer is the thinnest component. It does:
1. Split source into lines
2. Map lines to paragraphs via regex
3. Color each line by paragraph complexity
4. Show 3 summary stats per side

It does NOT:
- Explain why lines are colored
- Show factor breakdowns
- Show execution flow differences
- Show data flow differences
- Allow clicking paragraphs for deep dives
- Link to other tabs

This is the root of "lackluster" — the visualization shows symptoms (colors, numbers) without diagnosis (why, how, what to do about it).

---

## 3. Chat System: Capabilities & Isolation

### Tool Inventory (20 Tools)

**Banking (8):** list_accounts, get_account, process_transaction (WRITE), verify_chain, view_chain, transfer (WRITE), verify_all_nodes, run_reconciliation

**Codegen (4):** parse_cobol, generate_cobol (in-memory), edit_cobol (in-memory), validate_cobol

**Analysis (8):** analyze_call_graph, trace_execution, analyze_data_flow, detect_dead_code, analyze_cross_file, explain_paragraph, explain_cobol_pattern, compare_complexity

### Critical Limitation: In-Memory Only Edits

`edit_cobol` and `generate_cobol` return modified source code in the response but **DO NOT write to disk**. The LLM gets the code back; no automatic persistence. A `save_cobol_file` tool would need to be added for the Mainframe dashboard.

### Tool Execution Pipeline (`python/llm/tool_executor.py`)

4 layers: RBAC gate → Input validation → Dispatch → Audit logging. Every call (permitted, denied, error) logged to SQLite.

### Conversation System (`python/llm/conversation.py`)

- Multi-turn tool resolution loop (up to 10 iterations)
- LLM sees tool results and reasons about them
- Sessions are **in-memory only** — lost on server restart
- Two system prompts: DIRECT (90 lines) and TUTOR (Socratic, 30 lines)
- Tutor mode is **global, not per-tab** — no context awareness

### Provider System (`python/llm/providers.py`)

- OllamaProvider (local, default) and AnthropicProvider (cloud, opt-in)
- Both normalized to same response format
- Provider switch clears all sessions

### Chat UI (`console/js/chat.js`, 479 lines)

- Tool results displayed as collapsible JSON cards — no visualization
- 6 hardcoded prompt chips (not context-aware)
- Tutor mode toggle (global checkbox)
- Session management (in-memory, sidebar list)
- Provider switching UI
- **Zero awareness of other tabs**
- **Zero use of existing visualization components** (CallGraphView, CompareViewer, NetworkGraph)

### What the Chat CANNOT Do Today

1. Know which tab is active
2. Know which file the user is looking at
3. Know which paragraph is selected
4. Render tool results as visualizations (call graphs, heatmaps)
5. Trigger actions in other tabs
6. Write COBOL to disk
7. Scope its personality per dashboard

---

## 4. Dashboard Interconnection Audit

### Current State: Complete Isolation

Verified by searching all JS modules for cross-references:

- `dashboard.js` (641 lines): Zero mentions of "Analysis", "Chat", "CallGraph", "CompareViewer", or "tab"
- `analysis.js` (506 lines): Zero mentions of "Dashboard", "Chat", "simulation", or "events"
- `chat.js` (479 lines): Zero mentions of "Dashboard", "Analysis", "simulation", "day", or "feed"
- `app.js` (213 lines): Only manages view switching via CSS class toggle. No state synchronization.

### Shared State: Nearly None

The ONLY cross-tab shared state is the RBAC role selector:
- Synced in `app.js:50-61` (button state gating)
- Synced in `chat.js:89-93` (sidebar display)
- Used by `api-client.js:18` (X-Role header on all API calls)

Everything else is module-private:
- Selected file: `cobol-viewer.js:23` (Dashboard) vs `analysisFileSelect` (Analysis) — NOT synced
- Simulation state: `dayCounter`, `statCompleted`, etc. — Dashboard only
- Chat sessions: `chat.js` internal state — not visible to other tabs
- `localStorage`: Only stores `cll_onboarded` flag

### What Needs to Exist: EventBus

A lightweight pub/sub (~30 lines of vanilla JS) that any module can emit to and listen on:

```
EventBus.emit('file-selected', { file: 'PAYROLL.cob', source: 'analysis' })
EventBus.emit('paragraph-focused', { file: 'PAYROLL.cob', paragraph: 'P-030' })
EventBus.emit('simulation-event', { type: 'batch', program: 'PAYROLL.cob' })
EventBus.emit('challenge-started', { type: 'fix-pregnant-program', code: '...' })
EventBus.emit('tab-switched', { from: 'dashboard', to: 'analysis' })
```

This is the foundation for Workstreams 2, 3, and 4.

---

## 5. COBOL Viewer / Syntax Highlighting: Duplication

Three separate rendering systems exist for COBOL source:

1. **CobolViewer** (`console/js/cobol-viewer.js`, 265 lines): Terminal mode (event log) + Modal mode (full file). Single regex pass for 63 keywords + 9 division names. `highlightLine()` function exists but is NOT exported (only `init`, `highlightForEvent`, `clearLog` are returned).

2. **CompareViewer** (`console/js/compare-viewer.js`, 137 lines): Side-by-side with complexity heatmap backgrounds. Own rendering logic.

3. **CallGraphView** (`console/js/call-graph.js`, 779 lines): SVG node-and-edge rendering. Color by complexity.

**Key action for Workstream 2:** Export `highlightLine` from CobolViewer (add to return statement at line 264). This lets the Mainframe editor and the chat panel reuse the same syntax highlighting.

---

## 6. HTML/CSS Architecture Quick Reference

### SPA Structure (`console/index.html`)

- Nav bar with tab buttons using `data-view` attribute
- View switching via `app.js:switchView()` — toggles `.view--active` class
- Adding a new tab: add `<button data-view="X">` + `<section id="view-X">` — routing is automatic

### Design System (`console/css/variables.css`)

- Glass morphism: `--glass-bg`, `--glass-border`, `--glass-blur`, `--glass-shadow`
- Bank colors: `--bank-a` (#3b82f6 blue) through `--bank-e` (#ec4899 pink), `--clearing` (#a78bfa lavender)
- Status: `--success` (#22c55e), `--warning` (#f59e0b), `--danger` (#ef4444), `--info` (#3b82f6)
- Fonts: `--font-sans` (Inter), `--font-mono` (JetBrains Mono)
- Spacing: `--sp-1` (4px) through `--sp-8` (32px)

### Module Pattern

All JS modules use IIFE pattern: `const ModuleName = (() => { ... return { init }; })();`
Init called from `app.js:init()`. No framework, no build step.

---

## 7. Existing Codegen/Validation Infrastructure

### API Endpoints (reusable for COBOL Mainframe)

| Endpoint | What It Does |
|---|---|
| `POST /api/codegen/parse` | COBOL source → AST summary (program ID, paragraphs, files, fields) |
| `POST /api/codegen/generate` | Template + params → COBOL source (templates: crud, report, batch, copybook) |
| `POST /api/codegen/edit` | Source + operation → modified source (add_field, remove_field, add_paragraph, etc.) |
| `POST /api/codegen/validate` | Source → validation issues (naming, PIC semantics, structure, 88-conditions) |

### Templates (`python/cobol_codegen/templates.py`)

Factory functions producing COBOLProgram AST objects:
- `crud_program()` — ACCOUNTS-style full CRUD with file I/O
- `report_program()` — Read-only reporting (OPEN INPUT only)
- `batch_program()` — Sequential file processor
- `copybook_record()` — Data item definitions for .cpy files

### Validation Rules (`python/cobol_codegen/validator.py`)

- Naming conventions (UPPERCASE-WITH-HYPHENS)
- Field prefix conventions (ACCT-, TRANS-, WS-, RC-, NST-, SIM-)
- PIC clause semantic matching (money=S9(10)V99, date=9(8), ID=X(10))
- STOP RUN presence
- 88-level conditions for flags
- Record byte width checks

### What's Missing for COBOL Mainframe

A `POST /api/mainframe/compile` endpoint that:
1. Accepts raw COBOL source text
2. Writes to a temp file
3. Runs `cobc -x -free` (or `-fixed` depending on format)
4. Returns stdout/stderr + return code
5. Cleans up temp file
6. Falls back to `/api/codegen/validate` if `cobc` not found

---

## 8. Test Infrastructure

- **807 tests** across 28 test files in `python/tests/`
- Run: `python -m pytest python/tests/ -v --ignore=python/tests/test_e2e_playwright.py`
- E2E Playwright tests exist but require running server
- All workstreams must keep tests green
- Spaghetti enrichment (Workstream 1) should not affect any test since it only adds comments/dead code

---

## Reading Order for New Instance

1. `CLAUDE.md` — full project reference (key files, architecture, verification commands)
2. `docs/OVERHAUL_ROADMAP.md` — the vision, architecture, 5 workstreams, decisions, build order
3. This document (`docs/archive/OVERHAUL_HANDOFF.md`) — detailed findings per workstream
4. `docs/research/COBOL_PRACTITIONER_INSIGHTS.md` — source material for spaghetti enrichment
5. `docs/archive/SPECKIT.md` — the speckit workflow (specify → clarify → plan → tasks → build)
6. Begin writing `specs/2-spaghetti-enrichment/spec.md`

---

*AKD Solutions — Data Alchemy & Agentic Development*
