# Spec: COBOL Mainframe Dashboard — Virtual Dry-Erase Board

**Status**: Drafting
**Created**: 2026-04-02

## Overview

Build a virtual dry-erase board where students write, compile, and run real COBOL using `cobc` (GnuCOBOL). This is the capstone of the passive-to-active learning journey: Tab 1 (Dashboard) lets students observe COBOL in action, Tab 2 (Analysis) lets students investigate code, and this new Tab 3 (Mainframe) lets students write and practice COBOL. The dashboard includes an 80-column constraint-aware editor, a real compilation endpoint with Mode A/B fallback, JCL-style output rendering, a challenge system fed from other tabs via EventBus, starter templates from the existing codegen pipeline, and syntax highlighting reused from the existing `CobolViewer` module.

---

## User Stories

### US-1: Compile Endpoint (Priority: P1)

As a **student**, I want to submit COBOL source code and get real compiler feedback so I can learn from actual `cobc` errors instead of theoretical explanations.

**Acceptance Scenarios**:
1. Given `cobc` is installed on the server, When the student submits valid COBOL source via `POST /api/mainframe/compile`, Then the endpoint returns `{"success": true, "return_code": 0, "stdout": "", "stderr": "", "mode": "compile"}` within 5 seconds.
2. Given `cobc` is installed, When the student submits COBOL with a syntax error (e.g., missing period), Then the endpoint returns `{"success": false, "return_code": 1, "stdout": "", "stderr": "STUDENT.cob:42: error: ...", "mode": "compile"}`.
3. Given `cobc` is NOT installed on the server, When the student submits COBOL source, Then the endpoint falls back to validation-only mode and returns `{"success": true/false, "return_code": 0, "stdout": "", "stderr": "", "mode": "validate", "validation": {"valid": true/false, "issues": [...]}}`.
4. Given the student submits a source file larger than 100KB, When the endpoint processes it, Then it rejects with a 413 status code and error message "Source too large (max 100KB)".
5. Given the compile endpoint is called, When it writes to a temp file, Then the temp file is deleted after compilation completes (success or failure), and the temp directory is cleaned up.

### US-2: 80-Column Constraint-Aware Editor (Priority: P1)

As a **student**, I want an editor that enforces COBOL's 80-column fixed-format rules so I can learn the physical constraints that real COBOL programmers face.

**Acceptance Scenarios**:
1. Given the editor is in fixed-format mode, When the student types beyond column 72, Then the editor visually indicates the line exceeds the code area (columns 73-80 are reserved for identification).
2. Given the editor is displayed, When the student views a line, Then column indicators are visible at columns 7 (A-margin), 12 (B-margin), and 72 (end of code area).
3. Given the editor is in fixed-format mode, When the student types in columns 1-6, Then those columns are visually distinguished as the sequence number area.
4. Given the editor supports both modes, When the student toggles between fixed-format and free-format, Then column constraints update accordingly (free-format has no column restrictions).
5. Given the editor is loaded, When the student types COBOL keywords, Then syntax highlighting matches the existing `highlightLine()` output from `CobolViewer`.

### US-3: JCL-Style Output Panel (Priority: P1)

As a **student**, I want compiler output displayed in a JCL-style mainframe terminal aesthetic so the experience feels authentic and educational.

**Acceptance Scenarios**:
1. Given a compilation returns successfully, When the output panel renders, Then it displays an authentic JCL-style job card and step sequence (e.g., `//STUDENT JOB (ACCT),'STUDENT'`, `//STEP01 EXEC PGM=IGYCRCTL` for compile, `//STEP02 EXEC PGM=IEWBLINK` for link, `//STEP03 EXEC PGM=STUDENT` for go) followed by the compilation result in monospace font on a dark background. Return codes displayed as `MAXCC=0000` for success, `MAXCC=0008` for warnings, `MAXCC=0012` for errors — matching real z/OS compile-link-go JCL output.
2. Given a compilation returns errors, When the output panel renders, Then error lines are highlighted in red with the source line number extracted and clickable (scrolls to that line in the editor).
3. Given the compile mode is "validate" (Mode B fallback), When the output panel renders, Then it shows a clear indicator that validation-only mode is active ("cobc not available — showing validation results") with the list of issues.
4. Given multiple compilations have occurred in the session, When the student scrolls the output panel, Then previous compilation results are preserved in a scrollable log with timestamps.

### US-4: Starter Templates (Priority: P1)

As a **student**, I want to load pre-built COBOL program templates so I can start from working code and modify it rather than writing from scratch.

**Acceptance Scenarios**:
1. Given the template selector is displayed, When the student selects "CRUD Program", Then the editor loads a generated CRUD template from the existing `crud_program()` factory with default parameters.
2. Given the template selector lists options, When the student views it, Then at least 7 templates are available: CRUD, Report, Batch, Copybook (from existing codegen), plus Interest Accrual (day-count convention skeleton with `INTEGER-OF-DATE`, COMP-3 intermediate fields, banker's rounding), Transaction Validator (FILE STATUS checking, record-not-found handling, before/after journal images), and VSAM Master File (indexed file with `ORGANIZATION IS INDEXED`, `ACCESS MODE IS DYNAMIC`, `ALTERNATE RECORD KEY WITH DUPLICATES`, proper FILE STATUS checking after every I/O verb).
3. Given the editor has unsaved content, When the student selects a template, Then a confirmation dialog warns "This will replace your current code. Continue?" before overwriting.
4. Given a template is loaded, When the student views the editor, Then the generated code includes educational comments explaining each section (these come from the codegen pipeline).

### US-5: Syntax Highlighting via CobolViewer (Priority: P1)

As a **student**, I want the editor to have the same syntax highlighting as the existing COBOL source viewer so the visual experience is consistent across the application.

**Acceptance Scenarios**:
1. Given the `CobolViewer` module has a private `highlightLine()` function, When the Mainframe dashboard needs highlighting, Then `highlightLine()` is exported from `CobolViewer` as a public method.
2. Given `highlightLine()` is exported, When the editor renders COBOL source, Then keywords are highlighted in the same colors (divisions, verbs, strings, numbers, comments) as the source modal viewer.
3. Given the editor content changes, When the student finishes typing a line (on Enter or after a debounce timeout), Then that line is re-highlighted using the shared `highlightLine()` function.

### US-6: Dialect Comparison Mode (Priority: P2)

As a **student**, I want to compile my code in different COBOL dialect modes so I can see which IBM-specific features break on other compilers and understand why migration is so difficult.

**Acceptance Scenarios**:
1. Given the compile panel has a dialect selector, When the student selects "IBM" mode, Then the compile endpoint passes `-std=ibm` to cobc and IBM-specific extensions are accepted.
2. Given the student writes code using IBM-specific features, When they switch to "COBOL 2014" mode, Then the compiler flags deprecated constructs (ALTER, GO TO DEPENDING ON) and the output panel annotates each warning with educational context.
3. Given a compilation succeeds in one dialect but fails in another, When the output panel renders, Then it highlights the dialect-specific differences and links to the knowledge base entry for that incompatibility.

### US-7: Challenge System (Priority: P2)

As a **student**, I want to receive coding challenges from the Analysis tab so I can practice fixing the specific anti-patterns I just learned about.

**Acceptance Scenarios**:
1. Given the Analysis tab dispatches a "fix this paragraph" event via EventBus, When the Mainframe tab receives it, Then the editor loads the relevant paragraph source code and the output panel shows the challenge description (e.g., "Refactor P-030: remove ALTER statements, replace GO TO chains with PERFORM").
2. Given a challenge is loaded, When the student compiles their solution, Then the output panel shows both the compilation result AND a re-analysis of the modified code showing the new complexity score compared to the original.
3. Given no EventBus is available (Workstream 3 not complete), When the Mainframe tab loads, Then the challenge system is simply inactive — no errors, no hidden features, just the editor and templates.
4. Given the Banking dashboard dispatches a "write a settlement batch" event, When the Mainframe tab receives it, Then the editor loads a batch template pre-configured for settlement processing.

### US-7: Save Capability (Priority: P2)

As an **LLM** (via tool invocation), I want to save generated COBOL code to disk so that the code generation workflow is complete (generate, edit, save, compile).

**Acceptance Scenarios**:
1. Given the LLM calls the new `save_cobol_file` tool, When the tool executes, Then the COBOL source is written to a specified path within allowed COBOL directories only.
2. Given the save path is outside allowed directories (e.g., `../../etc/passwd`), When the tool attempts to save, Then it returns a permission error and does not write any file.
3. Given the save is successful, When the tool returns, Then the response includes the file path, byte count, and a confirmation message.

---

## Functional Requirements

### Compile Endpoint (`python/api/routes_mainframe.py`)

- **FR-001**: A new `POST /api/mainframe/compile` endpoint MUST be created in a new file `python/api/routes_mainframe.py`, following the existing router pattern (APIRouter with prefix and tags).

- **FR-002**: The compile endpoint MUST accept a JSON body with `source_text` (required, string), `format` (optional, enum: "fixed" or "free", default "free"), `program_name` (optional, string, default "STUDENT"), and `dialect` (optional, enum: "default" or "ibm" or "mf" or "cobol2014", default "default"). When `dialect` is set, pass `-std={dialect}` to cobc for dialect-specific compatibility checking (e.g., `-std=ibm` enables IBM Enterprise COBOL compatibility mode).

- **FR-003**: In Mode A (cobc available), the endpoint MUST: write source to a temporary file, invoke `cobc -x -free` (or `cobc -x -fixed` based on format parameter), capture stdout/stderr/return_code, delete the temp file, and return the result.

- **FR-004**: In Mode B (cobc not available), the endpoint MUST: parse the source using `COBOLParser`, validate using `COBOLValidator`, and return validation issues as a structured response with `mode: "validate"`.

- **FR-005**: The compile endpoint MUST detect cobc availability at startup (not per-request) using `shutil.which("cobc")` and cache the result.

- **FR-006**: The compile endpoint MUST enforce a maximum source size of 100KB (102400 bytes) and return HTTP 413 if exceeded.

- **FR-007**: The compile endpoint MUST enforce a compilation timeout of 10 seconds and return HTTP 504 if exceeded. Use `subprocess.run(timeout=10)` with process cleanup.

- **FR-008**: Temp files created during compilation MUST use Python's `tempfile.NamedTemporaryFile` with `suffix='.cob'` and `delete=False`, with explicit cleanup in a `finally` block.

### Frontend (`console/js/mainframe.js`, `console/index.html`)

- **FR-009**: A new frontend module `console/js/mainframe.js` MUST be created following the IIFE module pattern with an `init()` method, matching `Analysis`, `Dashboard`, `Chat` conventions.

- **FR-010**: The Mainframe tab MUST be registered in `console/index.html` as a new `<section class="view" id="view-mainframe">` with a corresponding nav tab `<button class="nav__tab" data-view="mainframe">Mainframe</button>`. Tab position: Dashboard / Analysis / Mainframe.

- **FR-011**: The editor component MUST render line numbers and column position indicators (at minimum columns 7, 12, 72) using CSS grid or flexbox, not a third-party editor library.

- **FR-012**: The editor MUST use a `<textarea>` element with a syntax-highlighted overlay (the overlay renders `highlightLine()` output; the textarea captures keystrokes). The textarea is transparent; the overlay shows highlighted code.

- **FR-013**: Template loading MUST call `POST /api/codegen/generate` with the selected template name and default parameters, reusing the existing codegen endpoint. New banking-specific templates (Interest Accrual, Transaction Validator, VSAM Master File) MUST be added to the codegen pipeline. The Interest Accrual template MUST demonstrate: `FUNCTION INTEGER-OF-DATE` for day counting, COMP-3 intermediate precision fields (`PIC S9(15)V9(6)`), and the explicit banker's rounding pattern (COBOL `ROUNDED` defaults to round-half-up, not round-half-to-even). The VSAM Master File template MUST demonstrate: INDEXED organization with DYNAMIC access, FILE STATUS checking after every I/O verb (with comments referencing codes 22, 23, 35), and ALTERNATE RECORD KEY WITH DUPLICATES.

- **FR-014**: The compile button MUST call `POST /api/mainframe/compile` via `ApiClient.post()`, using the existing auth headers.

- **FR-015**: The output panel MUST render compilation results in monospace font with green text for success and red text for errors, matching the existing COBOL terminal aesthetic in `dashboard.css`. Error messages should include educational annotations when they match known ABEND patterns — e.g., a "data exception" error gets a tooltip explaining "This is the equivalent of an S0C7 abend on IBM z/OS — the most common COBOL production error, caused by invalid packed decimal data in a COMP-3 field."

### CobolViewer Export

- **FR-016**: The `CobolViewer` module MUST export `highlightLine()` by adding it to the return object: `return { init, highlightForEvent, clearLog, highlightLine }`.

### Routing & CSS

- **FR-017**: The `routes_mainframe.py` router MUST be registered in `app.py` using the same try/except pattern as other optional routers.

- **FR-018**: A new CSS file `console/css/mainframe.css` MUST be created and linked in `index.html`, following the existing stylesheet organization.

### Quick Reference Sidebar

- **FR-019a**: The Mainframe tab MUST include a collapsible quick reference sidebar with three sections: (a) **FILE STATUS Codes** — a compact table of codes 00, 10, 22, 23, 35, 39, 41, 42, 46, 47, 48 with one-line descriptions; (b) **ABEND Code Reference** — S0C7 (data exception), S0C4 (protection exception), S322 (time exceeded), S806 (module not found), with educational tooltips explaining common causes; (c) **Dialect Compatibility** — a compact table showing IBM vs GnuCOBOL differences (EXEC CICS, COMP-1/COMP-2, VSAM, SCREEN SECTION). Reference data sourced from `COBOL_MAINFRAME_QUIRKS.md` sections 3 and 4.

### Challenge System

- **FR-019b**: The challenge system MUST listen for EventBus events with type `challenge.load` containing `{ paragraph_name, source_text, description }` payload.

### Save Tool

- **FR-020**: The `save_cobol_file` tool MUST be added to `python/llm/tools.py` with `required_permission: "cobol.write"` and path validation using the existing `_ALLOWED_COBOL_DIRS` pattern from `routes_codegen.py`.

---

## Success Criteria

- **SC-001**: A student can type valid COBOL in the editor, click Compile, and see "Compilation successful" with return code 0 when cobc is installed.
- **SC-002**: A student can type COBOL with a deliberate syntax error (missing period), click Compile, and see the specific error message with line number from cobc.
- **SC-003**: When cobc is not installed, the compile button still works and returns validation-only results with clear mode indication.
- **SC-004**: The editor visually distinguishes column areas (1-6 sequence, 7 indicator, 8-11 A-margin, 12-72 B-margin, 73-80 identification) in fixed-format mode.
- **SC-005**: All 4 starter templates (CRUD, Report, Batch, Copybook) load successfully from the existing codegen API and render in the editor with syntax highlighting.
- **SC-006**: The Mainframe tab appears as the third nav tab and switches cleanly with existing Dashboard and Analysis views.
- **SC-007**: The `highlightLine()` function is accessible from outside `CobolViewer` (confirmed by `typeof CobolViewer.highlightLine === 'function'` in browser console).
- **SC-008**: The compile endpoint handles concurrent requests safely (no shared temp file state between requests).
- **SC-009**: The JCL-style output panel preserves a history of at least 10 previous compilation results within the current browser session.

---

## Edge Cases & Out-of-Scope

### Edge Cases

- **EC-001**: Student submits empty source text — compile endpoint should return a 400 error with message "No source code provided", not attempt compilation.
- **EC-002**: Student submits COBOL with `STOP RUN` in an infinite loop construct — the 10-second timeout (FR-007) must terminate the compilation subprocess cleanly.
- **EC-003**: cobc produces warnings but compilation succeeds (return code 0) — output panel should show warnings in yellow/amber, not red, with the "success" indicator still green.
- **EC-004**: The editor content contains mixed line endings (CRLF/LF) — the compile endpoint should normalize to LF before writing the temp file.
- **EC-005**: Student loads a template while a compilation is in progress — the UI should not overwrite the editor content until the compilation completes or is cancelled.
- **EC-006**: Very large COBOL programs with 80+ paragraphs — the editor should remain performant (no full re-highlight on every keystroke; use line-by-line highlighting with debounce).
- **EC-007**: The `save_cobol_file` tool receives a path with directory traversal — must be rejected by path validation before any filesystem access.

### Out-of-Scope

- **Execution** of compiled COBOL programs (compile only, not run). Running student code would require sandboxing beyond this workstream.
- **Multi-file compilation** (linking multiple .cob files). Single-file compilation only.
- **Collaborative editing** (multiple students editing the same file simultaneously).
- **Version control integration** (git commit/push from the editor).
- **Auto-completion or intellisense** for COBOL keywords (syntax highlighting only).
- **Code formatting / auto-indent** (students should learn COBOL column rules manually).
- **File browser / directory tree** for navigating existing COBOL source files (the Analysis tab handles source browsing).
- **Debugging / stepping through COBOL execution** (the Analysis tab's trace animator handles execution visualization).

---

## [NEEDS CLARIFICATION]

- **NC-001**: Compilation security sandboxing — should the compile endpoint run cobc in a restricted subprocess environment (e.g., `ulimit` resource limits, restricted PATH), or rely on the 10-second timeout as sufficient protection? Recommended: basic `ulimit` restrictions (max memory, max file size) in addition to the timeout, since students may submit pathological code.
