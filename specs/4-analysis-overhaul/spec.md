# Spec: Analysis Tab Overhaul — Surfacing Rich Backend Data

**Status**: Drafting
**Created**: 2026-04-02

## Overview

Surface the rich backend analysis data that already exists in the six `cobol_analyzer` modules but is never rendered in the frontend. The Analysis tab currently shows an SVG call graph and a thin 137-line compare viewer that displays symptoms (colors, scores) without diagnosis (why a score is high, what pattern caused it, how to fix it). Two backend endpoints — `explain-paragraph` and `data-flow` — are fully implemented but never called from the UI. This workstream bridges that gap by adding paragraph deep-dive panels, factor breakdowns, animated execution traces, data flow heatmaps, educational annotations from the knowledge base, and cross-tab navigation links to the Mainframe dashboard.

---

## User Stories

### US-1: Paragraph Deep Dive Panel (Priority: P1)

As a **student**, I want to click any paragraph node in the call graph and see a detailed explanation panel so I can understand what that paragraph does, what it calls, what calls it, and why its complexity score is what it is.

**Acceptance Scenarios**:
1. Given the call graph is rendered with paragraph nodes, When the student clicks a paragraph node, Then a detail panel slides open on the right side showing the paragraph name, complexity score, factors list, calls-to edges, called-by edges, fields read, fields written, and dead code status.
2. Given the detail panel is open for paragraph P-030, When the student clicks a different paragraph P-050, Then the panel updates to show P-050's data without closing and reopening.
3. Given the detail panel is open, When the student clicks the close button or presses Escape, Then the panel closes and the full call graph is visible again.
4. Given the explain-paragraph endpoint returns data, When the panel renders, Then each factor line shows the pattern name, occurrence count, and point contribution (e.g., "GO TO x4 (+20)").

### US-2: Factor Breakdowns in Compare Viewer (Priority: P1)

As an **instructor**, I want the compare viewer to show WHY each paragraph scored the way it did, not just the number, so I can demonstrate anti-patterns to students with specific evidence.

**Acceptance Scenarios**:
1. Given the compare viewer renders a paragraph header line with a score badge, When the student hovers over or clicks the score badge, Then a tooltip or expandable section shows the factor breakdown (e.g., "GO TO x4 (+20), ALTER x2 (+20), PERFORM THRU x1 (+3)").
2. Given the compare viewer shows both panes, When spaghetti code has dead paragraphs, Then dead paragraphs show a "DEAD" label and are categorized as either "DEAD" or "ALTER_CONDITIONAL" with a brief explanation of each category.
3. Given the compare viewer data is loaded, When the student views it, Then anti-pattern counts are summarized in each pane header (e.g., "12 GO TO, 4 ALTER, 3 dead paragraphs").

### US-3: Data Flow Visualization (Priority: P1)

As a **student**, I want to see which paragraphs read and write each working-storage field so I can understand why spaghetti code's shared global state is dangerous.

**Acceptance Scenarios**:
1. Given a file has been analyzed, When the student opens the data flow view, Then the UI calls the `data-flow` endpoint and displays a list of all discovered fields with reader/writer counts.
2. Given a field list is displayed, When the student clicks a specific field (e.g., WS-GROSS-PAY), Then a heatmap or highlight overlay shows which paragraphs read it (blue) and which write it (red), with access counts.
3. Given a field has many writers (e.g., "modified by 23 paragraphs"), When the field card is displayed, Then a warning icon and explanatory text highlight the data coupling risk.
4. Given the data flow endpoint returns paragraph-level read/write sets, When the visualization renders, Then each field shows a mini access timeline ordered by source line number.

### US-4: Animated Execution Traces (Priority: P2)

As a **student**, I want to watch an animated step-by-step execution trace through the call graph so I can visually understand how spaghetti code's GO TO chains create chaotic non-linear flow compared to clean code's linear PERFORM chains.

**Acceptance Scenarios**:
1. Given a trace has been fetched for a paragraph entry point, When the student clicks "Animate Trace", Then the call graph highlights each paragraph node in sequence with a visible delay between steps (configurable speed: slow/medium/fast).
2. Given the animation is running, When a GO TO step occurs, Then the edge is highlighted in red with a pronounced visual effect (pulse or flash), and a GO TO arrow appears more prominently than PERFORM arrows.
3. Given the animation is running, When the student clicks "Pause", Then the animation freezes at the current step, and "Step Forward" / "Step Back" buttons become available.
4. Given a clean file (e.g., TRANSACT.cob) is traced, When the animation plays, Then the linear PERFORM sequence visually contrasts with spaghetti traces by proceeding in a straight top-to-bottom pattern.

### US-5: Educational Annotations (Priority: P2)

As a **student**, I want context-aware explanations of anti-patterns drawn from the knowledge base so I can learn the historical and technical context of patterns I encounter in spaghetti code.

**Acceptance Scenarios**:
1. Given the paragraph detail panel shows factors like "ALTER x2 (+20)", When the student clicks the factor name "ALTER", Then an annotation card appears with the knowledge base entry: era, purpose, mainframe context, modern equivalent, example, and risk.
2. Given the compare viewer shows a paragraph with COMP-3 fields, When the student encounters the pattern, Then a small info icon is available that links to the COMP-3 knowledge base entry.
3. Given the knowledge base has entries for a detected pattern, When the annotation card renders, Then it uses the exact text from `knowledge_base.py` without modification.

### US-6: Cross-Tab Navigation Links (Priority: P2)

As a **student**, I want to click a "Fix this on the Mainframe" link in the Analysis tab so I can jump directly to the Mainframe dashboard with the relevant paragraph pre-loaded as a challenge.

**Acceptance Scenarios**:
1. Given the paragraph detail panel is open for a spaghetti paragraph (score >= 10), When the panel renders, Then a "Fix this pattern" button is visible linking to the Mainframe tab.
2. Given the student clicks "Fix this pattern", When the EventBus dispatches the navigation event, Then the UI switches to the Mainframe tab with the paragraph name and source context pre-populated as a challenge.
3. Given EventBus from Workstream 3 is not yet available, When the link feature attempts to dispatch, Then it falls back to a simple tab switch with a toast notification showing the paragraph name.

### US-7: Banking Arithmetic and Platform Annotations (Priority: P2)

As a **student**, I want the analysis view to surface banking-specific COBOL patterns — day-count conventions, fixed-point arithmetic choices, and platform-specific storage formats — so I can understand why COBOL's `COMP-3` is the standard for financial calculations and how interest is computed in integer arithmetic.

**Acceptance Scenarios**:
1. Given the paragraph detail panel shows a paragraph using COMP-3 fields, When the panel renders, Then an annotation explains that COMP-3 (packed decimal/BCD) is the standard for financial calculations because IBM z-series hardware has native BCD instructions (~7-10x faster than binary for decimal arithmetic) and it avoids all IEEE 754 representation errors (`0.1 + 0.2 = 0.30000000000000004`).
2. Given the data flow view shows a field with PIC clause containing `V` (implied decimal), When the student clicks it, Then an annotation explains that `V` occupies zero bytes of storage and that truncation (not rounding) is the default — with a concrete example of data loss.
3. Given the compare viewer shows spaghetti code with hardcoded numeric literals, When an annotation icon is available, Then it explains the "70% problem" — research found over 70% of business rules in legacy systems existed only in the code, not in any documentation, and that two attempts to replace one such system failed because replacement teams couldn't replicate the undocumented business logic.

### US-8: Enhanced Compare Viewer (Priority: P3)

As an **instructor**, I want the compare viewer to show dead code categories, anti-pattern counts, and mini execution traces within each pane so I can use it as a comprehensive teaching tool beyond the current 137-line implementation.

**Acceptance Scenarios**:
1. Given the compare viewer renders, When dead code is present, Then dead paragraphs are grouped by category (DEAD vs ALTER_CONDITIONAL) with count badges.
2. Given the compare viewer renders, When anti-patterns are detected, Then an anti-pattern summary bar shows counts by type (GO TO, ALTER, PERFORM THRU, nested IF, magic numbers).
3. Given the compare viewer renders for both panes, When the student scrolls one pane, Then the scroll positions are independent (no synchronized scrolling unless toggled on).

---

## Functional Requirements

- **FR-001**: The Analysis tab MUST call `POST /api/analysis/explain-paragraph` when a paragraph node is clicked, passing `source_text` and `paragraph_name`.

- **FR-002**: The paragraph detail panel MUST display: paragraph name, complexity score, complexity factors (from the `factors` array in the explain-paragraph response), calls-to edges (with type), called-by edges (with type), fields read, fields written, dead code status (dead / alter_conditional / reachable).

- **FR-003**: The Analysis tab MUST call `POST /api/analysis/data-flow` when the data flow view is activated, passing the current file's `source_text`.

- **FR-004**: The data flow visualization MUST display each field with the count of reader paragraphs and writer paragraphs, sourced from `field_readers` and `field_writers` in the data-flow response.

- **FR-005**: Factor breakdowns in the compare viewer MUST use the `factors` array from the complexity response (already present at `complexityData.paragraphs[name].factors`), not recalculated client-side.

- **FR-006**: Educational annotations MUST source content from the existing `KnowledgeBase` class, served as a static JSON file at `/console/data/knowledge-base.json`. The JSON is generated once from `knowledge_base.py` during build/setup. The knowledge base MUST be expanded to at least 30 entries, organized by domain:

  **Language Quirks** (~12 entries):
  - Implied decimal (`V` occupies zero bytes, truncation vs rounding default, ROUNDED/ON SIZE ERROR)
  - MOVE truncation (alphanumeric left-justified/right-truncated, numeric right-justified/left-truncated, group MOVE loses decimal alignment, MOVE CORRESPONDING silent drops)
  - REDEFINES (union with no discriminator, S0C7 from type confusion, FD implicit REDEFINES, VALUE on redefining items = undefined)
  - Level 88 ("most underappreciated feature" — SET TO TRUE, multiple values, ranges, centralizes validation)
  - Level 77 (designated for deletion) and Level 66 RENAMES (rarely used)
  - PERFORM THRU ("armed mines" — GO TO out of range leaves return address on control stack)
  - ALTER (McCracken 1976 quote, deprecated COBOL-85, deleted COBOL-2002, still in production)
  - SPACES vs LOW-VALUES vs HIGH-VALUES (hex values, EBCDIC vs ASCII, S0C7 from arithmetic on LOW-VALUES)
  - COMP storage formats (DISPLAY one char/digit with overpunch sign, COMP binary 2/4/8 bytes, COMP-3 packed BCD two digits/byte, TRUNC(STD) vs TRUNC(BIN))
  - Overpunch encoding (EBCDIC: `{`/`A`-`I` positive, `}`/`J`-`R` negative; ASCII Micro Focus: `0x70` zone; `-123` displays as `"12L"`)
  - EBCDIC collating sequence (`'a' < 'A' < '1'` reverses in ASCII; SEARCH ALL binary search produces wrong results on ASCII; PROGRAM COLLATING SEQUENCE override)
  - FILE STATUS codes (00 success, 10 EOF, 22 duplicate key, 23 not found, 35 file not found at OPEN)

  **Mainframe Architecture** (~8 entries):
  - JCL and DD statements (SELECT/ASSIGN mapping, DISP parameter, GDG versioning)
  - VSAM file organizations (KSDS indexed for accounts, ESDS append-only for logs, RRDS slot-based)
  - CICS pseudo-conversational model (QR TCB, BMS SEND MAP, COMMAREA 32,763 bytes, Channels/Containers)
  - Working-Storage persistence (persists in batch, fresh copy per CICS task, state via COMMAREA)
  - ABEND codes (S0C7 data exception, S0C4 protection exception, S322 time exceeded, S806 module not found, CEEDUMP traceback)
  - DB2 embedded SQL (DCLGEN, host variables, indicator variables for NULL, SQLCA codes)
  - Copybook dependency hell (one change → 50-200 recompiles, silent field misalignment, 70% of business rules only in code)
  - Y2K windowing (pivot years expiring, 30-year mortgage crossing 2050, IBM YEARWINDOW compiler option)

  **Banking Patterns** (~6 entries):
  - Fixed-point arithmetic (COMP-3 exact decimal, `PIC S9(13)V99 COMP-3` = 8 bytes up to ±$999T, avoids IEEE 754 `0.1+0.2` error)
  - Interest rate precision (`PIC 9(3)V9(6)`, intermediate `PIC S9(15)V9(6)`, banker's rounding round-half-to-even)
  - Day-count conventions (30/360 bonds, Actual/360 money markets ~5 extra days/year, Actual/365 UK, Actual/Actual Treasuries)
  - Multi-currency (ISO 4217 `PIC X(3)` + decimal-places `PIC 9(1)`, JPY=0, BHD=3)
  - EOD batch processing (9-step nightly: quiesce→post→accrue→fees→aging→FX→regulatory→GL→date roll)
  - Regulatory compliance (CTR $10K threshold, SAR structuring detection, OFAC SDN screening, SWIFT MT103/MT202/MT940, ISO 20022 transition)

  **Dialect Compatibility** (~4 entries):
  - GnuCOBOL (9,700+/9,748 NIST tests, COBOL→C→native via GCC, `-std=ibm`/`-std=mf`/`-std=cobol2014`)
  - IBM vs GnuCOBOL incompatibilities (EXEC CICS not supported, COMP-1/COMP-2 hex vs IEEE, COMP-3 byte-identical, EBCDIC requires translation tables)
  - Migration breakers (EXEC CICS primary blocker, signed DISPLAY overpunch corruption, hex literal meaning change, VSAM key reordering, JCL→shell)
  - Hardware context (z16 Telum 5.2 GHz, on-chip AI 300B inferences/day at 1ms, COMP-3 native BCD 7-10x faster, FIPS 140-2 Level 4 crypto)

- **FR-007**: The paragraph detail panel MUST be a new JS module (`console/js/paragraph-detail.js`) following the existing IIFE module pattern used by `CompareViewer`, `CallGraphView`, and other modules.

- **FR-008**: The data flow heatmap MUST be a new JS module (`console/js/data-flow-view.js`) following the same IIFE pattern. It renders in a separate panel alongside the call graph (not overlaid on the SVG).

- **FR-009**: Animated trace playback MUST reuse existing trace data from `traceCache` in `analysis.js`, not re-fetch traces from the API.

- **FR-010**: Animation speed MUST be configurable with at least three presets: slow (800ms per step), medium (400ms), fast (150ms).

- **FR-011**: Cross-tab navigation MUST use EventBus when available (Workstream 3 dependency) and fall back to direct `App.switchView()` calls with toast notifications when EventBus is absent.

- **FR-012**: The compare viewer enhancement MUST NOT replace the existing `CompareViewer` module but extend it by adding new render methods and expanding `renderPane()`.

- **FR-013**: All new CSS MUST be added to `console/css/analysis.css`, following the existing section-comment pattern (`/* -- Section Name -- */`).

- **FR-014**: No new backend endpoints are required for US-1 through US-4 — all data is available from existing endpoints. US-5 (knowledge base annotations) uses a static JSON export, not a new endpoint.

- **FR-015**: The paragraph detail panel MUST respond to `cg-node-click` custom events already dispatched by `CallGraphView` (see `call-graph.js`).

---

## Success Criteria

- **SC-001**: The `explain-paragraph` endpoint is called from the UI for every paragraph click, confirmed by browser network tab showing `POST /api/analysis/explain-paragraph` requests.
- **SC-002**: The `data-flow` endpoint is called from the UI when the data flow view is activated, confirmed by browser network tab showing `POST /api/analysis/data-flow` requests.
- **SC-003**: A student can click any paragraph in the PAYROLL.cob call graph and see all six data categories (score, factors, calls-to, called-by, fields, dead status) rendered in the detail panel within 500ms.
- **SC-004**: The compare viewer shows factor breakdowns for every paragraph with a score > 0, matching the exact factor format from `complexity.py` (e.g., "GO TO x4 (+20)").
- **SC-005**: The data flow view correctly displays at least 10 fields for PAYROLL.cob with accurate reader/writer counts matching the `data-flow` endpoint output.
- **SC-006**: Animated traces play through at least one complete spaghetti trace (P-010 in PAYROLL.cob) and one clean trace (PROCESS-TRANSACTION in TRANSACT.cob) demonstrating visual contrast.
- **SC-007**: At least 10 knowledge base annotations are accessible from the UI, including entries for: ALTER, GO TO, PERFORM THRU, COMP-3, implied decimal, MOVE truncation, REDEFINES, EBCDIC collating sequence, ABEND codes, and Y2K windowing. Source material from both `knowledge_base.py` and `COBOL_MAINFRAME_QUIRKS.md`.
- **SC-008**: Zero new backend endpoints are created for the core features (US-1 through US-4). One static JSON file is acceptable for knowledge base serving (US-5).
- **SC-009**: All new JavaScript modules follow the IIFE pattern with `init()` method, matching the existing codebase conventions.

---

## Edge Cases & Out-of-Scope

### Edge Cases

- **EC-001**: Paragraph with zero complexity score — detail panel should still show "clean" status with empty factors list, not hide the panel.
- **EC-002**: File with no PROCEDURE DIVISION (e.g., copybooks) — explain-paragraph returns 404, UI should show a user-friendly message ("This is a data copybook, not a program").
- **EC-003**: Very long trace chains (100+ steps) — animation should cap display at max_steps and show a "truncated at 100 steps" indicator.
- **EC-004**: Data flow for files with no WORKING-STORAGE fields — show "No fields discovered" placeholder instead of an empty panel.
- **EC-005**: Knowledge base lookup for a pattern not in the encyclopedia — show "No documentation available for this pattern" instead of failing silently.
- **EC-006**: Multiple rapid paragraph clicks during animation — cancel current animation before starting new one (debounce).

### Out-of-Scope

- Modifying any of the 6 backend analysis modules (`call_graph.py`, `data_flow.py`, `dead_code.py`, `complexity.py`, `cross_file.py`, `knowledge_base.py`)
- Adding new analysis algorithms (e.g., taint analysis, symbolic execution)
- Synchronized scrolling between compare viewer panes (listed as a possible toggle, not a requirement)
- Integration with the Chat slide-out panel (Workstream 3 dependency — that workstream owns the integration)
- Real-time analysis updates during code editing (Workstream 5 owns the editor)

---

## [NEEDS CLARIFICATION]

- **NC-001**: Knowledge base static JSON — should the JSON file be generated as part of `python -m python.cli setup` (build-time) or committed to the repo as a static asset? Recommended: committed as a static asset since the knowledge base is curated content that changes only during development.
