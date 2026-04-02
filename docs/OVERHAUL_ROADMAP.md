# COBOL Legacy Ledger — Overhaul Roadmap

**Author:** AKD Solutions
**Date:** 2026-04-02
**Status:** Approved — spec-writing phase

---

## Vision

Transform the project from "impressive COBOL-themed portfolio demo" into "credible mainframe training simulator with depth." A student can sit down with this system, observe COBOL in action, investigate legacy code like an archaeologist, and practice writing real compiled COBOL — all guided by a Socratic AI tutor that never gives answers, only asks the right questions.

---

## Architectural Model

### Vertical Layers (Trust Gradient)

```
Layer 3: LLM Tutor (optional, local-first, advisory)
  │  Never modifies COBOL. Observes and teaches.
  │  CS50 duck debugger: leads with questions, never answers.
  │  Security-first: mirrors real banking's LLM skepticism.
  │
Layer 2: Python Bridge (bidirectional interface)
  │  Translates COBOL ↔ modern. Parses, monitors, controls.
  │  REST API, SQLite sync, integrity chains, analysis tools.
  │  Makes COBOL accessible without replacing it.
  │
Layer 1: COBOL (the immutable truth)
     Clean banking simulation + mutant payment processor.
     Compiles, runs, processes real financial data.
     A missing period will take down a bank.
```

Layer 1 is untouchable production code. Layer 2 wraps but never modifies it. Layer 3 observes but never controls it. This mirrors real mainframe modernization — augment, don't replace.

### Horizontal User Journey (Passive → Active)

```
Tab 1: OBSERVE            Tab 2: READ & COMPARE       Tab 3: WRITE & PRACTICE
Banking Simulator         Code Analysis                COBOL Mainframe
─────────────────         ─────────────────            ─────────────────
Watch COBOL in action.    Investigate the code.        Write real COBOL.
See transactions flow.    Spaghetti vs clean.          Compile with cobc.
Corrupt the chain.        Why is it bad? Exactly       Fix pregnant programs.
Detect the tamper.        what makes P-030 score       Solve challenges that
See what COBOL does       67 in complexity? Click      flow FROM the other
at a banking level.       it and find out.             tabs.

     ◀─── passive observation              active coding ───▶

┌──────────────────────────────────────────────────────────────┐
│           CHATBOT (slide-out panel, not a tab)               │
│                                                              │
│  Floats alongside ALL three tabs. Context-aware.             │
│  Scopes system prompt, suggested prompts, and tool           │
│  selection to whichever tab is active.                       │
│                                                              │
│  CS50 duck debugger model:                                   │
│  - Never tells the answer                                    │
│  - Leads with Socratic questions and slight hints            │
│  - Local-first (Ollama default, Anthropic opt-in)            │
│  - Optional — system works without LLM                       │
└──────────────────────────────────────────────────────────────┘
```

### The Layers × Journey Matrix

Every cell is an interaction point. Filled = strong today. Empty = hollow or missing.

```
                OBSERVE              READ & COMPARE          WRITE & PRACTICE
           ┌────────────────────┬────────────────────────┬──────────────────────┐
 Layer 1   │ STRONG             │ EXISTS, LACKS DEPTH    │ MISSING              │
 COBOL     │ Sim runs real      │ 8 spaghetti programs   │ No interactive       │
           │ COBOL. Txns flow.  │ but lack archaeological│ COBOL coding yet.    │
           │ Settlement works.  │ depth of real legacy.  │                      │
           ├────────────────────┼────────────────────────┼──────────────────────┤
 Layer 2   │ STRONG             │ RICH BACKEND,          │ ENDPOINTS EXIST,     │
 Python    │ Bridge parses &    │ SHALLOW UI             │ NO UI                │
           │ monitors. Hash     │ explain-paragraph      │ codegen/validate     │
           │ chains record all. │ NEVER CALLED in UI.    │ work but no coding   │
           │                    │                        │ interface calls them. │
           ├────────────────────┼────────────────────────┼──────────────────────┤
 Layer 3   │ ORPHANED           │ ORPHANED               │ ORPHANED             │
 LLM       │ Chat can verify    │ Chat can analyze but   │ Chat can generate &  │
           │ chains but is      │ shows raw JSON, not    │ edit COBOL but is    │
           │ trapped in tab 3.  │ using SVG renderers.   │ locked in tab 3.     │
           └────────────────────┴────────────────────────┴──────────────────────┘
```

### Dashboard Interconnection

**Current state:** All three tabs are completely orphaned. Zero cross-references.

**Target state:** Tabs linked via EventBus. Analysis sends challenges to Mainframe. Banking Sim links to Analysis. Chatbot floats across all three with context awareness.

---

## The 5 Workstreams

### 1. Spaghetti Enrichment
**Priority:** FIRST — content foundation
**Layer:** Layer 1 (COBOL only)
**Speckit:** `specs/2-spaghetti-enrichment/`

Inject practitioner-sourced anti-patterns into the 8 payroll programs. Missing period bugs, COMP-3/EBCDIC artifacts, batch ordering traps, field reuse ambiguity, developer handwriting differentiation, abend recovery notes, deliberate workarounds. No executable logic changes.

### 2. Chat → Slide-Out Panel
**Priority:** SECOND — connective tissue
**Layer:** Layers 2-3
**Speckit:** `specs/3-chat-slide-panel/`

Move chatbot from tab to slide-out panel. Add EventBus for cross-tab communication. Context-aware system prompts per active tab. CS50 duck debugger behavior scoped to banking operations / code archaeology / compiler mentoring.

### 3. Analysis Tab Overhaul
**Priority:** THIRD — surface rich backend
**Layer:** Layers 2-3
**Speckit:** `specs/4-analysis-overhaul/`

Paragraph deep dives via explain-paragraph endpoint. Factor breakdowns in comparison. Animated execution traces. Data flow visualization. Educational annotations. Cross-tab links ("Fix this on the Mainframe").

### 4. COBOL Mainframe Dashboard
**Priority:** FOURTH — showpiece capstone
**Layer:** All 3 layers
**Speckit:** `specs/5-cobol-mainframe/`

Virtual dry-erase board. Real `cobc` compilation via new endpoint (falls back to validate-only). 80-column constraint-aware editor. JCL-style output. Challenge system fed from other tabs. Starter templates.

### 5. Polish & Historical Enrichment
**Priority:** FIFTH — dessert
**Layer:** All layers
**Speckit:** `specs/6-polish-and-history/`

Fun facts toggle, COBOL timeline, war stories, Chain Defense arcade game, onboarding overhaul, cross-tab breadcrumb trail.

---

## Dependencies & Build Order

```
[1] Spaghetti Enrichment ──────────────────────┐
    (content foundation)                        │
                                                ▼
[2] Chat Slide-Out Panel ──── [3] Analysis Overhaul
    (connective tissue)           (surface rich backend)
         │                              │
         └──────────┬───────────────────┘
                    ▼
            [4] COBOL Mainframe
            (capstone)
                    │
                    ▼
            [5] Polish & History
            (dessert)
```

Workstreams 2 and 3 can be built in parallel after 1 completes.

---

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Compilation | Real `cobc` via new API endpoint | Authenticity. Mode A/B fallback. |
| Spec structure | One speckit spec per workstream | Independent review and build. |
| Chat architecture | Slide-out panel, not a tab | Context-aware connective tissue. |
| Chatbot model | CS50 duck debugger (Socratic) | Leads with questions, never answers. |
| Spaghetti approach | Archaeological enrichment | Add depth without changing executable logic. |
| Historical enrichment | Optional toggle, last priority | Aesthetic polish, not structural. |

---

## Optional / Stretch Ideas

These are independent additions that can be pursued after the core 5 workstreams, or woven in opportunistically. Each is self-contained and doesn't block the main roadmap.

### A. COBOL RAG Knowledge Base
Ingest the official COBOL documentation (GnuCOBOL manual, ISO standard reference, IBM Enterprise COBOL docs) into a vector database (e.g., ChromaDB or SQLite with embeddings). Wire RAG retrieval into the chatbot's tool chain so it can ground answers in real documentation instead of hallucinating syntax or compiler behavior. This transforms the tutor from "LLM that knows about COBOL" to "LLM backed by the actual spec." Fits naturally into the Layer 3 architecture — still local-first, still optional, but dramatically more accurate.

### B. Historical Fun-Fact Enrichment Layer
A toggleable overlay that surfaces COBOL history, practitioner war stories, and mainframe culture as contextual tooltips throughout the UI. Examples: "DID YOU KNOW: A missing period took down Nordea bank for 16 hours", "Grace Hopper's team delivered the first COBOL compiler in 1960", "95% of ATM transactions still run on COBOL." Could appear as subtle `(i)` icons next to relevant UI elements, activated by a global "Fun Facts" toggle in the nav. Low effort, high charm. Partially covered by Workstream 5 but could be its own micro-spec.

### C. Hidden Easter Egg: Chain Defense Arcade
A hidden mini-arcade game (Space Invaders re-skinned as protecting transaction chains from corruption attacks) discoverable via a secret key combo (e.g., Konami code) or a hidden link. NOT a full tab — it's an easter egg that rewards exploration. 3-key controls (left, right, fire). The player fires SHA-256 verification pulses to destroy corruption agents before they tamper with blocks in a descending hash chain. Educational overlay explains what each game element represents. Glass morphism visual style. Pure client-side Canvas, no API calls. The kind of thing an interviewer discovers and remembers.

---

## Source Material

- `docs/research/COBOL_PRACTITIONER_INSIGHTS.md` — Practitioner interviews and enhancement proposals
- `docs/TEACHING_GUIDE.md` — 10 structured lessons (current teaching content)
- `docs/LEARNING_PATH.md` — 6-level student self-study guide
- `COBOL-BANKING/payroll/KNOWN_ISSUES.md` — Anti-pattern catalog
- `COBOL-BANKING/payroll/README.md` — Fictional developer history

---

*AKD Solutions — Data Alchemy & Agentic Development*
