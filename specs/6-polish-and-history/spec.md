# Spec: Polish & Historical Enrichment — Charm, Context, and an Easter Egg

**Status**: Drafting
**Created**: 2026-04-02

## Overview

Add educational charm, historical depth, and navigational quality-of-life improvements to the COBOL Legacy Ledger console. Surface practitioner war stories, COBOL timeline milestones, and contextual "did you know" facts as a toggleable overlay layer, overhaul the onboarding experience with a guided walkthrough, add cross-tab breadcrumb navigation, and hide a Chain Defense arcade easter egg discoverable via the Konami code. All additions are non-blocking — the core application functions identically with every feature in this workstream disabled or undiscovered.

---

## User Stories

### US-1: Fun Facts Toggle (Priority: P1)

As a **student**, I want to see interesting historical facts and practitioner anecdotes woven into the UI so I can appreciate the real-world context behind the COBOL patterns I am learning.

**Acceptance Scenarios**:
1. Given I am on any tab with the fun facts toggle OFF (default), When I look at the UI, Then I see zero fun-fact overlays and the interface is unchanged from the pre-workstream baseline.
2. Given I click the fun facts toggle in the nav bar, When the toggle activates, Then small `(i)` indicator icons appear next to relevant UI elements across all tabs, and a toast confirms "Fun Facts: ON."
3. Given fun facts are ON and I click an `(i)` icon next to "Corrupt Ledger", When the popover appears, Then it displays a fact about real-world data integrity incidents (e.g., the Nordea missing-period outage) with source attribution.
4. Given fun facts are ON and I switch tabs, When the new tab renders, Then the `(i)` icons appropriate to that tab are visible without requiring a re-toggle.
5. Given I toggle fun facts OFF, When the toggle deactivates, Then all `(i)` icons and any open popovers disappear immediately and a toast confirms "Fun Facts: OFF."
6. Given I close and reopen the browser, When the page loads, Then the fun facts toggle state persists (via localStorage).

### US-2: COBOL Historical Timeline (Priority: P1)

As a **history buff**, I want to see a visual timeline of COBOL and mainframe computing milestones so I can understand the 65-year arc that produced the code I am studying.

**Acceptance Scenarios**:
1. Given I am on any tab with fun facts ON, When I click the timeline icon or a "COBOL Timeline" link, Then a modal displays a vertical timeline of key milestones.
2. Given the timeline is visible, When I scan from top to bottom, Then I see at minimum: 1959 COBOL-60 specification, 1960 first compiler, 1968 ANSI standard, 1974 COBOL-74, 1985 COBOL-85 (structured programming), 2002 OO COBOL, 2014 COBOL 2014 (current ISO standard), plus project-specific milestones (the fictional payroll program dates: 1974 JRK, 1983 PMR, 1991 SLW, 2002 Y2K team).
3. Given a timeline milestone has a practitioner anecdote, When I hover or click on it, Then I see the expanded story (e.g., "1985: Structured COBOL eliminated GO TO for new code — but ALTER persisted in legacy programs until shops could afford the rewrite. Many never could.").
4. Given I press Escape or click outside the timeline, When the modal closes, Then I return to the previous view state.

### US-3: War Stories Integration (Priority: P2)

As a **student**, I want practitioner war stories to appear in context — next to the UI elements they relate to — so the anecdotes reinforce what I am actively looking at.

**Acceptance Scenarios**:
1. Given fun facts are ON and I am viewing the Analysis tab with PAYROLL.cob selected, When I click the `(i)` icon near the complexity score, Then I see a war story about real-world spaghetti code (e.g., "A major EU bank has 6 million lines of COBOL. Rewrite estimates range from 5 to 20+ years.").
2. Given fun facts are ON and I am viewing the Dashboard with a batch simulation running, When I see the batch processing indicator, Then an available `(i)` icon links to a story about Sunday deployment culture and nightly batch runs.
3. Given fun facts are ON and I click the `(i)` near the settlement network visualization, When the popover appears, Then it explains nostro accounts with a real practitioner perspective (e.g., "Real banks have 50+ account types for personal, 50+ for business. Our 8 per node is a simplification.").

### US-4: Onboarding Overhaul (Priority: P1)

As a **first-time student**, I want a guided introduction that tells me where to start and what learning path to follow so I do not feel lost when I first open the console.

**Acceptance Scenarios**:
1. Given I am a first-time visitor (no localStorage flag), When the page loads, Then I see a multi-step welcome modal that walks through: (a) what the project teaches, (b) the tabs and what each does, (c) a suggested first action per tab, and (d) a link to the Learning Path document.
2. Given I am on step 2 of the onboarding walkthrough, When I click "Next", Then I see step 3 with a smooth transition, and a progress indicator shows 2/N completed.
3. Given I dismiss the onboarding at step 2 by clicking "Skip" or pressing Escape, When the modal closes, Then the localStorage flag is set and I am not shown onboarding again unless I click the "?" help button.
4. Given I am a returning visitor who has completed onboarding, When I click the "?" help button in the nav, Then I see the full onboarding walkthrough again (not just the current abbreviated popup).
5. Given I have completed onboarding and switch to the Analysis tab for the first time, When the tab loads, Then a subtle "Start here" tooltip appears near the Analyze button (one-time per tab, tracked in localStorage).

### US-5: Cross-Tab Breadcrumb Trail (Priority: P2)

As a **returning student**, I want to see where I have been across tabs so I can retrace my steps and understand the connections between different views.

**Acceptance Scenarios**:
1. Given the EventBus (from Workstream 3) is available, When I navigate from Dashboard to Analysis and select PAYROLL.cob, Then a breadcrumb bar below the nav shows "Dashboard > Analysis > PAYROLL.cob".
2. Given the breadcrumb bar is visible with 3+ entries, When I click on "Dashboard" in the breadcrumb, Then I switch to the Dashboard tab.
3. Given I have navigated across 10+ locations, When I view the breadcrumb bar, Then it shows the most recent 5 entries with a "..." indicator for earlier history, keeping the bar a single line.
4. Given the EventBus is NOT available (Workstream 3 incomplete), When the page loads, Then the breadcrumb bar is hidden entirely and no errors appear in the console.
5. Given I reload the page, When the page loads, Then the breadcrumb trail is reset (session-only, not persisted).

### US-6: Chain Defense Arcade Game (Priority: P3)

As a **student** (or interviewer), I want to discover a hidden arcade game that teaches hash chain integrity concepts through gameplay so I can learn while having fun and remember the project.

**Acceptance Scenarios**:
1. Given I am on any page and type the Konami code (Up Up Down Down Left Right Left Right B A), When the sequence completes, Then a full-screen canvas overlay appears with the Chain Defense game, a brief "How to play" overlay, and a toast announcing "EASTER EGG UNLOCKED: Chain Defense."
2. Given the Chain Defense game is active, When I look at the game, Then I see descending "corruption agents" approaching a horizontal row of "hash chain blocks" at the bottom, and I control a "verifier" ship that fires "SHA-256 verification pulses" upward.
3. Given I am playing Chain Defense, When a corruption agent reaches a hash chain block, Then that block visually cracks and a brief educational tooltip says "Block corrupted! In a real hash chain, this would invalidate all subsequent blocks."
4. Given I am playing Chain Defense, When I destroy all corruption agents in a wave, Then the wave counter increments (5 waves total, one per bank), the chain blocks glow green to indicate integrity verified, and the next wave begins with faster/more agents.
5. Given I complete all 5 waves, When the victory screen appears, Then it shows "All chains verified. Integrity preserved across all 5 banks." with total score.
6. Given I press Escape during Chain Defense, When the overlay closes, Then I return to the normal console view with no side effects.
7. Given I type a partial Konami code then a wrong key, When the sequence breaks, Then nothing happens and the detector resets silently.

---

## Functional Requirements

### Fun Facts System (`console/js/fun-facts.js`)

- **FR-001**: A `FunFacts` JS module MUST manage the toggle state, icon placement, and popover content following the IIFE pattern.

- **FR-002**: Fun fact data MUST be stored as a structured JS object (array of objects) within the module, each entry containing: `id`, `category` (history/practitioner/technical), `anchor` (CSS selector or element ID where the icon appears), `tab` (dashboard/analysis/mainframe/all), `title`, `body`, and optional `source`.

- **FR-003**: The fun facts toggle MUST be a switch element in the nav bar, positioned between the help button and the role selector.

- **FR-004**: Fun fact `(i)` icons MUST reuse the existing `.help-tip` CSS pattern from `components.css` with a distinct modifier class (`.help-tip--fun-fact`) to differentiate from help tips.

- **FR-005**: The toggle state MUST persist across page reloads via `localStorage` key `cll_fun_facts`.

- **FR-006**: Fun fact popovers MUST be dismissible by clicking outside, clicking the `(i)` icon again, or pressing Escape.

- **FR-007**: The fun facts dataset MUST include at minimum 25 facts distributed across all tabs, sourced from both `docs/research/COBOL_PRACTITIONER_INSIGHTS.md` and `docs/research/COBOL_MAINFRAME_QUIRKS.md`. Required facts include:
  - **Hardware**: IBM z16 processes 25 billion encrypted transactions/day at 5.2 GHz; on-chip AI scores 100% of credit card transactions in real-time (1ms latency, 300B inferences/day); z17 announced with Telum II at 5.5 GHz and 64 TB DDR5.
  - **Economics**: Large banks deploy 300,000-400,000+ MIPS at ~$1,200/MIPS; 68% of mainframe costs are software licensing; five z16 systems replace 192 x86 servers (10,364 cores) with 75% less energy.
  - **Migration failures**: TSB Bank (2018) locked out 1.9M of 5.2M customers during migration, £330M losses + £48.65M regulatory fines. Queensland Health payroll replacement cost $1.2B AUD to remediate.
  - **Silent killers**: `MOVE 1000005 TO PIC 9(6)` silently stores `000005` — the leading `1` disappears. `0.1 + 0.2 = 0.30000000000000004` in IEEE 754, but COMP-3 packed decimal is exact by construction.
  - **Scale**: COBOL processes 85-90% of world's credit card transactions. CICS benchmarks: 174,000 transactions/second per single LPAR.
  - **Human cost**: 2-3 year ramp-up for new COBOL hires; over 70% of business rules exist only in code, not documentation; two replacement attempts failed because teams couldn't replicate undocumented logic; first two years after redevelopment spent putting "lost" business rules back in.
  - **Language quirks**: `-123` in `PIC S9(3)` DISPLAY format displays as `"12L"` (overpunch sign encoding). EBCDIC sorts `'a' < 'A' < '1'` — ASCII reverses this entirely. COMP-3 is byte-identical between IBM and GnuCOBOL, but COMP-1/COMP-2 floating-point is completely incompatible.
  - **Banking precision**: Banks use `PIC S9(13)V99 COMP-3` (8 bytes, ±$999 trillion exact). Interest rates: `PIC 9(3)V9(6)` (six decimal places). Account numbers are `PIC X(16)` not `PIC 9` — to preserve leading zeros.
  - **Architecture**: z16 Telum has no physical L3/L4 cache — idle cores' L2 dynamically shared as virtual L3 (256 MB/chip) and virtual L4 (2 GB/drawer). Data access: 3.6 nanoseconds. Crypto Express8S HSMs: FIPS 140-2 Level 4 (highest commercially available) with quantum-safe cryptography.
  - **Availability**: Parallel Sysplex clusters 32 z/OS systems via Coupling Facility (sub-8μs latency). DB2 Data Sharing Groups: actual concurrent read/write across systems (not replication). GDPS Metro Mirror: RPO=0, RTO in seconds. DS8900F storage: seven nines (99.99999%) availability.
  - **I/O**: FICON channels at 16/32 Gbps with dedicated channel subsystem offloading I/O from CPUs. zHyperLink: 18-30 μs latency (10x lower than FICON). PAV/HyperPAV: parallel I/O to same volume.
  - **Y2K not over**: Windowing code with pivot year 40 means 2050 is interpreted as 1950. 30-year mortgages from 2020 are already crossing this boundary. "The COBOL equivalent of the Unix 2038 problem."

### COBOL Timeline

- **FR-008**: The COBOL timeline MUST be rendered as an HTML/CSS component inside a modal overlay, reusing the `.popup-overlay` and `.glass` patterns from `components.css`.

- **FR-009**: The timeline MUST contain at minimum 18 milestones spanning 1959-2026, organized in two tracks (COBOL language + IBM hardware):
  - **Language**: 1959 COBOL-60 specification, 1960 first compiler, 1968 ANSI standard, 1974 COBOL-74, 1976 McCracken ALTER warning, 1985 COBOL-85 (structured programming, ALTER deprecated), 2000 Y2K (windowing "fix"), 2002 COBOL-2002 (ALTER deleted from standard), 2014 COBOL 2014 (current ISO standard).
  - **Hardware**: 2017 z14 (pervasive encryption — 100% data encrypted without app changes, 3.5x crypto performance), 2019 z15 (Data Privacy Passports, Instant Recovery, on-chip deflate compression 17x throughput, 190 cores, 40 TB), 2022 z16 (Telum 7nm 5.2 GHz, on-chip AI accelerator — industry first — 300B inferences/day at 1ms, 200 cores, 40 TB, quantum-safe crypto), 2025 z17 (Telum II 5.5 GHz, 32 cores per chip, 64 TB DDR5).
  - **Project-specific**: 1974 JRK (PAYROLL.cob), 1983 PMR (TAXCALC.cob), 1991 SLW (DEDUCTN.cob), 2002 Y2K team (PAYBATCH.cob).

- **FR-010**: Each milestone MUST display: year, title (max 60 characters), and a 1-2 sentence description. Milestones with practitioner stories MUST have an expandable detail section.

- **FR-011**: The timeline MUST be accessible via a dedicated link/button in the fun facts popover area AND via a fun fact `(i)` icon on the Dashboard.

### War Stories

- **FR-012**: War stories MUST be a subset of fun facts (category: `practitioner`) that are placed contextually near the UI elements they describe.

- **FR-013**: At minimum, war stories MUST cover: the Nordea missing-period outage (near PAYROLL.cob references), the 2-3 year ramp-up (near onboarding/learning path), the 50+ account types (near settlement network), Sunday deployment culture (near batch simulation), the failed rewrite narrative (near the "why not rewrite" theme), the TSB Bank £330M migration disaster (near settlement/banking context), the Queensland Health $1.2B payroll remediation (near payroll tab), the "70% of business rules only in code" finding (near analysis/complexity views), the Y2K windowing expiration (near date-related UI elements), and the McCracken ALTER quote (near ALTER references in analysis).

### Onboarding (`console/js/onboarding.js`)

- **FR-014**: The onboarding modal MUST be a multi-step walkthrough with: (a) welcome/overview (1 step), (b) tab-by-tab guidance (3 steps), (c) suggested first action (1 step), (d) learning path link (1 step) — 6 steps total.

- **FR-015**: The onboarding MUST include step navigation: "Next", "Back", "Skip" buttons, and a step indicator (dots or "3 of 6").

- **FR-016**: The onboarding MUST replace the existing single-page popup (`#onboarding` in `index.html`) — the existing onboarding HTML and JS logic in `app.js` MUST be replaced, not supplemented.

- **FR-017**: Per-tab "start here" tooltips MUST appear once per tab on first visit (tracked via localStorage keys `cll_tab_hint_dashboard`, `cll_tab_hint_analysis`, `cll_tab_hint_mainframe`).

- **FR-018**: The "?" help button in the nav MUST reopen the full multi-step walkthrough, not just the old popup.

### Breadcrumbs (`console/js/breadcrumbs.js`)

- **FR-019**: The breadcrumb module MUST listen for navigation events on the EventBus (from Workstream 3) and build a trail of `{tab, label, timestamp}` entries. Trail includes both tab switches and intra-tab selections (file, paragraph, node) when the EventBus provides them.

- **FR-020**: The breadcrumb bar MUST render below the nav bar and above the main content, as a single horizontal line with `>` separators.

- **FR-021**: The breadcrumb bar MUST display at most 5 entries. Older entries MUST be collapsed behind a `...` indicator that expands on click.

- **FR-022**: Clicking a breadcrumb entry MUST navigate to that tab (and restore context if possible, e.g., re-selecting the COBOL file in Analysis).

- **FR-023**: If the EventBus global is undefined (Workstream 3 not yet implemented), the breadcrumb module MUST silently skip initialization — no errors, no UI elements rendered.

- **FR-024**: The breadcrumb trail MUST be session-only (not persisted to localStorage). Page reload clears it.

### Chain Defense Arcade (`console/js/chain-defense.js`)

- **FR-025**: The Konami code detector MUST listen on `document` for `keydown` events and track the sequence: ArrowUp, ArrowUp, ArrowDown, ArrowDown, ArrowLeft, ArrowRight, ArrowLeft, ArrowRight, KeyB, KeyA.

- **FR-026**: Any incorrect key in the sequence MUST reset the detector to position 0 silently.

- **FR-027**: The game MUST render on a full-screen `<canvas>` element with a semi-transparent backdrop, using the glass morphism color palette from `variables.css`.

- **FR-028**: Game entities MUST include: (a) a player "verifier" ship (movable left/right with arrow keys, fires with spacebar), (b) descending "corruption agents" in wave formation, (c) a row of "hash chain blocks" at the bottom that the player defends.

- **FR-029**: When a corruption agent reaches a hash chain block, the block MUST visually crack and display a brief educational tooltip explaining hash chain corruption.

- **FR-030**: The game MUST have 5 waves (one per bank: BANK_A through BANK_E). Each wave is faster/more agents than the last. Completing all 5 shows a victory screen with total score and chain integrity message.

- **FR-031**: The game MUST display a score, wave number, and chain integrity percentage (blocks remaining / total blocks).

- **FR-032**: The game MUST be entirely client-side (Canvas API). No API calls, no external dependencies.

- **FR-033**: Pressing Escape during gameplay MUST close the game and return to normal console state. Game state is not preserved between sessions.

- **FR-034**: The game MUST include a brief "How to Play" overlay on first launch (dismissible with any key or click) explaining the controls and the educational metaphor.

- **FR-035**: The Konami code detector MUST NOT activate the game while another overlay is visible (onboarding, timeline modal, COBOL source viewer).

### Cross-Cutting

- **FR-036**: All new JS modules MUST follow the existing IIFE revealing module pattern (`const ModuleName = (() => { ... return { init }; })();`).

- **FR-037**: All new CSS MUST use existing design tokens from `variables.css` — no hardcoded colors, font sizes, or spacing values.

- **FR-038**: No feature in this workstream MUST be required for core functionality. If any new JS file fails to load, the Dashboard, Analysis, and Mainframe tabs MUST continue to work.

---

## Success Criteria

- **SC-001**: Fun facts toggle adds at least 35 contextual `(i)` icons across all tabs when activated, and removes all of them when deactivated. Facts span 8 categories: hardware, economics, migration failures, silent killers, scale, human cost, language quirks, banking precision, architecture, availability, I/O, and Y2K expiration.
- **SC-002**: The COBOL timeline renders at least 22 milestones across three tracks (COBOL language evolution, IBM hardware generations, and project-specific fictional eras) with correct dates and descriptions, each with expandable detail.
- **SC-003**: The onboarding walkthrough has 6 steps with working Next/Back/Skip navigation, and the "?" button re-triggers it.
- **SC-004**: The breadcrumb bar correctly reflects the last 5 navigation events when the EventBus is available, and is entirely absent when it is not.
- **SC-005**: The Konami code correctly activates Chain Defense and an incorrect sequence produces no visible effect.
- **SC-006**: Chain Defense runs at a stable frame rate (>30 FPS) on a mid-range laptop, with no memory leaks (`requestAnimationFrame` properly cancelled on exit).
- **SC-007**: All features degrade gracefully: disabling any single new JS file does not break existing Dashboard, Analysis, or Mainframe functionality.
- **SC-008**: The fun facts toggle state persists across page reloads.
- **SC-009**: All new UI elements are keyboard-accessible (focusable, activatable with Enter/Space, dismissible with Escape).
- **SC-010**: Zero new console warnings or errors introduced in normal operation (fun facts off, no easter egg activated).

---

## Edge Cases & Out-of-Scope

### Edge Cases

- **EC-001**: Fun facts toggle activated with no API connection — facts are static data embedded in the JS module, so they render regardless of API health.
- **EC-002**: User rapidly toggles fun facts on/off — the toggle MUST debounce icon injection/removal (100ms minimum between state changes).
- **EC-003**: Konami code typed while a modal is open (onboarding, node popup, COBOL source viewer) — the detector MUST NOT activate the game while another overlay is visible. Queue or ignore.
- **EC-004**: Browser window resized during Chain Defense gameplay — the canvas MUST handle resize events and adjust dimensions without crashing.
- **EC-005**: Breadcrumb bar with very long labels (e.g., "PROCESS-TRANSFER-BATCH-VALIDATION") — labels MUST truncate at 25 characters with ellipsis.
- **EC-006**: Multiple rapid tab switches generating breadcrumb entries — consecutive duplicate tab entries SHOULD be collapsed (e.g., "Dashboard > Dashboard" becomes one entry).
- **EC-007**: Onboarding modal shown while simulation is running — the simulation MUST continue in the background.

### Out-of-Scope

- Instructor configuration panel for enabling/disabling specific fun facts (master toggle only)
- Persistent game high scores or leaderboards for Chain Defense
- Mobile-optimized Chain Defense gameplay (desktop keyboards only)
- Animated COBOL timeline with scrolling or parallax effects (static modal with expandable items)
- Internationalization (i18n) of fun facts or onboarding text (English-only)
- Integration with the LLM chat for fun fact Q&A
- Sound effects for Chain Defense (visual-only)
- Breadcrumb persistence across sessions (resets on reload by design)
- Any backend (Python/API) changes — this workstream is entirely frontend + static content

---

## [NEEDS CLARIFICATION]

- **NC-001**: Fun facts initial state — should fun facts default to ON for first-time visitors (to surface the content proactively) or OFF (to keep the UI clean until the student opts in)? Recommended: OFF, consistent with the roadmap's "toggleable, not forced" constraint.
