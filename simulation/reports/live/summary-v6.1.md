# v6.1.0 Persona Review Summary — Triangulated Findings

**Date**: 2026-03-06
**Version**: 6.1.0
**Method**: 4 persona simulations, each exploring the full system (API, web console, LLM chatbot, analysis suite)

---

## Ratings

| Persona | Role | v5.x Rating | v6.1 Rating | Change |
|---------|------|-------------|-------------|--------|
| Marcus Chen | COBOL Maintainer | 4.2 | **4.6** | +0.4 |
| Sarah Williams | Hiring Manager | 4.5 | **4.8** | +0.3 |
| Dev Patel | Tech Journalist | 3.8 | **4.3** | +0.5 |
| Dr. Elena Vasquez | University Teacher | 4.1 | **4.5** | +0.4 |
| **Average** | | **4.15** | **4.55** | **+0.4** |

---

## What Was Broken (v5.x) → Status (v6.1)

| Issue | v5.x Status | v6.1 Status | Who Flagged |
|-------|-------------|-------------|-------------|
| Chat/LLM broken (JSON error) | BROKEN | **FIXED** — tool-use loop resolves | Sarah, Dev, Elena |
| Payroll analysis 404 | BROKEN | **FIXED** — all 8 files load | Sarah, Dev, Elena, Marcus |
| TRANSACT.cob scored "spaghetti" | WRONG | **FIXED** — scores 33/moderate | Marcus, Elena |
| No Docker | MISSING | **ADDED** — docker-compose.yml | Sarah |
| No tutor mode | MISSING | **ADDED** — Socratic questioning | Elena |
| No lab setup | MISSING | **ADDED** — Makefile, Docker | Elena |
| No assessments | MISSING | **ADDED** — 3 labs with rubrics | Elena |
| No WCAG accessibility | MISSING | **IMPROVED** — ARIA tabs, labels | Elena |
| Only 547 tests | LOW | **800 tests** — 46% increase | Sarah |
| Only 14 COBOL programs | LOW | **18 programs** — 4 new spaghetti | Dev, Marcus |

---

## Consensus WOW Moments (cited by 3+ personas)

1. **The spaghetti call graph visualization** (4/4) — PAYROLL.cob with 17 paragraphs, 29 edges, color-coded by type. Instantly communicates "spaghetti." Hero image for articles, classroom demos, and portfolio.

2. **The tamper → detect demo** (4/4) — Corrupt one byte, verify all nodes, see the chain break. 3 clicks, sub-second detection. Every persona cites this as the killer demo.

3. **The compare viewer** (4/4) — Split-pane with spaghetti (134) vs clean (33), production headers visible, complexity badges. Works for teaching, articles, and interviews.

4. **"Analyzed in 13ms — Human estimate: 2 days"** (3/4) — Static analysis ROI in one badge. Marketing genius per Dev, teaching tool per Elena, impressive engineering per Marcus.

5. **The LLM compare_complexity tool** (3/4) — Chatbot pulls live metrics, explains spaghetti vs clean with real data. Cited as differentiator by Marcus, Sarah, Dev.

---

## Consensus Issues (cited by 2+ personas)

### Must Fix

| Issue | Severity | Who Flagged | Impact |
|-------|----------|-------------|--------|
| Transaction API returns status 99 | HIGH | Marcus, Elena, Sarah | Demo breaks on direct API transaction calls |
| Chat prompt chip "Show spaghetti vs clean COBOL" is generic | MEDIUM | Sarah, Dev, Elena | Doesn't trigger compare_complexity tool |
| Chat model picker shows stale/wrong models | MEDIUM | Marcus, Sarah, Dev | UI inconsistency, confusing |

### Should Fix

| Issue | Severity | Who Flagged | Impact |
|-------|----------|-------------|--------|
| No README screenshots embedded | HIGH (Dev) | Dev | Blocks article inclusion |
| No CI badge in README | LOW | Sarah, Dev | Free credibility signal |
| Tutor mode inconsistency (~30% fallback) | MEDIUM | Elena | Students notice, undermines Socratic intent |
| No checkpoint save/restore | MEDIUM | Elena | Lab recovery when students corrupt data |

### Nice to Have

| Issue | Who Flagged | Notes |
|-------|-------------|-------|
| JCL sample deck | Marcus | z/OS context for mainframe students |
| Dead code "reason unreachable" | Marcus | Enhanced analysis output |
| Cross-file narrative summary | Elena | Pedagogical enrichment |
| Offline graceful degradation for LLM | Elena | Lab machines without Ollama |
| Live demo / GIF / video | Dev | Distribution strategy |
| Companion blog post | Dev | Shareability |

---

## Feature Assessment Matrix

| Feature | Working? | Visual Quality | UX | Teaching Value | Demo Value |
|---------|----------|---------------|-----|---------------|------------|
| Network topology graph | YES | Excellent | Excellent | High | High |
| Simulation engine | YES | Good | Good | High | High |
| Tamper → detect flow | YES | Excellent | Excellent | Very High | Very High |
| Chain verification | YES | Good | Good | High | High |
| Settlement transfer | YES | Good | Good | High | Medium |
| RBAC enforcement | YES | Good | Good | High | Medium |
| Analysis: Call graph | YES | Excellent | Excellent | Very High | Very High |
| Analysis: Complexity | YES | Good | Good | Very High | High |
| Analysis: Compare viewer | YES | Excellent | Excellent | Very High | Very High |
| Analysis: Dead code | YES | Good | Good | High | Medium |
| Analysis: Cross-file | YES | Good | Good | High | Medium |
| LLM Chat: Direct mode | YES | Good | Good | High | High |
| LLM Chat: Tutor mode | PARTIAL | Good | Inconsistent | Medium-High | Medium |
| LLM Chat: Tool-use | YES | Good | Good | High | Very High |
| Payroll sidecar | YES | Good | Good | Very High | High |
| Transaction API | PARTIAL | N/A | Error-prone | Low | Low |
| Codegen: Parse | YES | Good | Good | Medium | Low |
| COBOL source viewer | YES | Good | Good | High | Medium |

---

## Priority Action Items

### P0 — Fix Before Showing to Anyone
1. **Fix transaction API status 99** — Direct deposits/withdrawals return unknown error. Critical for hands-on demos.
2. **Update chat prompt chip** — Change "Show spaghetti vs clean COBOL" to "Compare PAYROLL.cob vs TRANSACT.cob" to trigger the new tool.

### P1 — Fix Before Publishing
3. **Embed 3-4 screenshots in README** — Dashboard, call graph, compare viewer, chat with tool calls.
4. **Fix chat model picker** — Show actual installed/active models, not stale list.
5. **Add CI badge to README.**

### P2 — Fix Before Classroom Adoption
6. **Improve tutor mode consistency** — System prompt engineering to reduce direct-answer fallback.
7. **Add checkpoint save/restore** — `make checkpoint-save/restore` for lab recovery.
8. **Add offline LLM graceful degradation** — Helpful error message when Ollama unavailable.

### P3 — Polish
9. Dead code "reason unreachable" in analysis output
10. Cross-file narrative summary
11. Sample JCL deck
12. Companion blog post / video / GIF
