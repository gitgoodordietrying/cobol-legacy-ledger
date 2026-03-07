# Dr. Elena Vasquez — Associate Professor of Information Systems, University of Illinois at Chicago

**Teaches IS 447 "Legacy Systems & Modernization" — evaluating this as a semester resource for 30 juniors/seniors**

## Rating: 4.5 / 5 stars (up from 4.1)

---

## First Impressions

I gave this a 4.1 last semester with significant reservations: broken analysis, broken chat, wrong spaghetti scores, no tutor mode, no lab setup script, no accessibility. The author addressed most of my concerns. Let me walk through what changed and what it means for my IS 447 syllabus.

The web console loads with ARIA `role="tab"` on the navigation tabs. The role selector has a proper label: "RBAC role — operator or admin required to run simulations." These are WCAG improvements I specifically requested. The analysis dropdown now shows all 11 files with descriptive labels — I can see at a glance which files are spaghetti and what specific anti-pattern each demonstrates.

---

## What's Fixed Since Last Review

**The analysis scoring is correct.** This was my pedagogical deal breaker — clean TRANSACT.cob was scoring "spaghetti." Now:
- Clean files score appropriately: ACCOUNTS.cob (10/clean), SETTLE.cob (9/clean), TRANSACT.cob (33/moderate)
- Spaghetti files are properly ranked: MERCHANT.cob (232) > DISPUTE.cob (137) > PAYROLL.cob (134) > FEEENGN.cob (68) > RISKCHK.cob (59)
- I can now confidently use these scores in a grading exercise without teaching wrong lessons

**The payroll analysis works.** All 8 spaghetti files load and analyze. The call graph for PAYROLL.cob shows 17 paragraphs with GO TO, ALTER, PERFORM THRU, and FALL_THROUGH edges color-coded. The dead code paragraph (P-085) is marked with a red "DEAD" badge. This is the classroom demo I was missing last semester.

**The chatbot works with tool-use resolution.** I tested it extensively:
- "List all accounts in BANK_A" → LLM called `list_accounts`, returned 8 formatted accounts (~16s)
- "Verify BANK_B chain" → LLM called `verify_chain`, reported 44,627 entries valid (~9s)
- "Compare PAYROLL.cob vs TRANSACT.cob" → LLM called `compare_complexity`, returned structured metrics (~15s)
- "What is ALTER in COBOL?" → LLM called `explain_cobol_pattern`, pulled structured knowledge base entry (~6s)

The tool-use loop works: LLM decides to call a tool → server executes with RBAC check → result fed back → LLM synthesizes explanation. This is genuine AI-augmented learning.

**Tutor mode exists.** The Chat tab has a "Tutor Mode" checkbox. When enabled, the LLM asks guiding questions instead of giving direct answers. I tested "What does ALTER do?" in tutor mode and got: "How do you think COBOL handles changing the execution path between paragraphs? Have you seen any code where a paragraph might be redirected?" — classic Socratic method. This is exactly what I asked for. Not perfect (the LLM sometimes slips into direct explanation), but the intent is right and it works well enough for classroom use.

**Docker and Makefile for lab deployment.** `make lab-setup` exists. Docker Compose for one-click launch. This reduces my lab setup from 5 error-prone steps to 1. My IT department can deploy this.

**Assessment materials exist.** Three lab assignments with rubrics in `docs/ASSESSMENTS.md`. A Teaching Guide with 8 structured lessons. This saves me significant prep time.

**WCAG improvements.** ARIA `role="tab"` on navigation, proper label attributes on form controls, keyboard-accessible role selector. Not a full WCAG audit, but the major interaction points are accessible.

---

## What Works

**Curriculum-ready structure (improved):**
- Learning Path: SMOKETEST → ACCOUNTS → TRANSACT → SETTLE builds complexity gradually
- Teaching Guide: 8 lessons mapping to a 15-week semester
- Assessments: 3 graded labs with rubrics and expected outcomes
- Glossary: Bridges COBOL, banking, and modern dev terminology
- The 8-program spaghetti sidecar now has descriptive labels in the UI (e.g., "PAYROLL.cob (spaghetti)", "DISPUTE.cob (ALTER state machine)")

**Progressive disclosure done right:**
- `SMOKETEST.cob`: Four COBOL divisions, no I/O — Day 1 homework
- `ACCOUNTS.cob`: Introduces file I/O, copybooks, CRUD operations — Week 2-3
- `TRANSACT.cob`: Transaction types, batch processing, error handling — Week 4-5
- `SETTLE.cob`: 3-leg inter-bank settlement — Week 6-7
- Spaghetti sidecar: Anti-pattern identification lab — Week 8-10

**The anti-pattern sidecar as a teaching portfolio:**

| Program | Era | Anti-Pattern | Score | Classroom Use |
|---------|-----|-------------|-------|---------------|
| PAYROLL.cob | 1974 | GO TO + ALTER spaghetti | 134 | Primary spaghetti example |
| MERCHANT.cob | 1978 | GO TO DEPENDING ON | 232 | Worst-case analysis |
| FEEENGN.cob | 1986 | SORT procedures, nested loops | 68 | Moderate complexity example |
| TAXCALC.cob | 1983 | 6-level nested IF | 34 | Nesting depth exercise |
| DEDUCTN.cob | 1991 | Structured/spaghetti hybrid | 25 | Evolution case study |
| DISPUTE.cob | 1994 | ALTER state machine | 137 | State machine analysis |
| PAYBATCH.cob | 2002 | Y2K dead code | 18 | Dead code hunting |
| RISKCHK.cob | 2008 | Contradicting logic | 59 | Logic verification |

Each program maps to a different lesson. The fictional developer history (JRK → PMR → Y2K → KMW) gives students a narrative for understanding code evolution. This is pedagogically sound.

**The compare viewer as a grading exercise:**
Split-pane showing PAYROLL.cob (134/spaghetti) on the left and TRANSACT.cob (33/moderate) on the right. Both with production headers and full source visible. I would assign: "Identify three anti-patterns in the left pane. For each, explain how the right pane handles the same requirement differently. Use the complexity scores to support your argument."

**The chatbot as a classroom tool:**
- Direct mode: Students ask COBOL questions and get immediate answers with tool-backed data
- Tutor mode: LLM asks guiding questions, encouraging Socratic exploration
- The chatbot called `explain_cobol_pattern` to pull structured knowledge base entries (era, purpose, risk, modern equivalent) — this is reference material with AI navigation
- RBAC means I can give students "viewer" access and they can explore without modifying data

**"Analyzed in 13ms — Human estimate: 2 days":**
This badge alone justifies a lecture on static analysis ROI. I'd project this in class and ask: "Why is automated analysis valuable? What can a tool find in 13 milliseconds that a human needs 2 days for?" The answer is in the call graph.

---

## What's Missing / Could Still Improve

**The chatbot's tutor mode is inconsistent:**
When it works, it's excellent — Socratic questions, guided discovery. But roughly 30% of the time, the LLM falls back into direct explanation even in tutor mode. The system prompt guides behavior but can't enforce it with smaller models. For classroom reliability, I'd need tutor mode to consistently ask questions, not just sometimes. This is an LLM limitation more than a code problem, but students will notice the inconsistency.

**The chat prompt chip "Show spaghetti vs clean COBOL" is generic:**
It should say "Compare PAYROLL.cob vs TRANSACT.cob" and directly invoke the comparison tool. The current chip produces a generic text response about spaghetti code rather than pulling live metrics. Other chips ("List all accounts in BANK_A", "Verify all chains") work well.

**No checkpoint data snapshots for mid-lesson recovery:**
If a student corrupts their data during a lab, they need to re-seed from scratch. I'd want `make checkpoint-save lesson3` and `make checkpoint-restore lesson3` for mid-lesson recovery. With 30 students, even one re-seed cascade wastes 10 minutes of class time.

**The Ollama dependency for chat is still a lab concern:**
My IT department can deploy Docker, but Ollama with a 5GB model on 30 lab machines is a stretch. The Anthropic provider option exists but requires an API key. An offline mode where the chatbot degrades gracefully (returns "LLM not available, here's the tool documentation") would be more classroom-friendly than an error.

**The transaction API has a reliability issue:**
Direct API transaction calls return `{"status": "99", "message": "Unknown error"}`. The simulation engine works fine, but if I assign a lab exercise involving the transaction API, students will hit this error. This should either work or return a clear, educational error message.

**Cross-file analysis could be more pedagogically rich:**
The cross-file endpoint works (PAYROLL → TAXCALC → DEDUCTN dependencies), but the output is raw data (edges, shared copybooks). A narrative summary — "PAYROLL.cob calls TAXCALC.cob for tax computation, creating a coupling between the payroll controller and tax calculator" — would help students understand the results without manual interpretation.

---

## WOW Moments

1. **The call graph for PAYROLL.cob projected on screen.** 17 paragraphs. 16 red GO TO arrows. 3 orange ALTER mutations. 5 blue PERFORM THRU arcs. P-085 marked DEAD. I showed this to two colleagues in the CS department — one said "that looks like a circuit board designed by someone who hates the next person." That's the reaction I want from students. The visual communicates "spaghetti" in a way that no lecture can.

2. **The complexity score table across all 8 spaghetti files.** MERCHANT.cob at 232, PAYROLL.cob at 134, DISPUTE.cob at 137, down to PAYBATCH.cob at 18. I can assign: "Rank these programs by maintainability. Explain why MERCHANT.cob scores highest. What specific anti-patterns contribute to its score?" The data is there; students do the analysis.

3. **The tamper → detect demo as a live "aha moment."** "I'm going to change one byte in Bank C's ledger. Now watch." Click corrupt, click verify, see the chain break. 30 seconds. Better than 45 minutes of slides on cryptographic integrity. Every student remembers this demo.

4. **Tutor mode asking "How do you think COBOL handles changing the execution path?"** When it works, it's transformative. Instead of a student copy-pasting the chatbot's answer, they're guided through the reasoning. "What would happen if the GO TO target changes at runtime?" — that's exactly the question I'd ask in office hours.

5. **The compare viewer as a lab exercise.** Spaghetti on the left (score 134), clean on the right (score 33). "Find three differences. Explain why each matters." Students can see both codebases, both scores, and both production headers. The tool sets up the exercise; I just write the rubric.

---

## Deal Breakers

None remaining. The scoring bug (my previous deal breaker) is fixed. The analysis loads. The chatbot works. These were the three things that would have caused me to fail this as a classroom tool.

The tutor mode inconsistency is a concern but not a blocker — I'd set expectations with students that AI tutoring is a supplement, not a replacement for office hours.

---

## Verdict

This has gone from "I'd use it selectively" to "I'm adopting it for my IS 447 syllabus next semester." The fixes addressed every major classroom concern I raised:

| Issue (v5.x) | Status (v6.1) |
|--------------|---------------|
| Spaghetti scoring wrong | Fixed — scores now accurate |
| Payroll analysis 404 | Fixed — all 8 files load |
| Chat broken | Fixed — tool-use loop works |
| No tutor mode | Added — Socratic questioning |
| No lab setup | Added — Docker + Makefile |
| No assessments | Added — 3 labs with rubrics |
| No WCAG | Improved — ARIA tabs, labels |

**How I'd use this in IS 447:**
- Weeks 1-3: SMOKETEST → ACCOUNTS → TRANSACT progression (Learning Path)
- Weeks 4-5: Settlement flow demo, chain verification, distributed systems discussion
- Weeks 6-7: Spaghetti sidecar analysis lab (call graph, complexity scores, compare viewer)
- Week 8: LLM chatbot exploration (direct mode for reference, tutor mode for exercises)
- Weeks 9-10: Cross-file analysis, data flow tracing, dead code identification
- Week 11: Assessment lab (compare two programs, write analysis report)
- Weeks 12-14: Student projects building on the framework

**What would make this a 5-star resource:**
1. Make tutor mode more consistently Socratic (system prompt engineering)
2. Add checkpoint save/restore for mid-lesson data recovery
3. Add offline graceful degradation when Ollama is unavailable
4. Fix the transaction API reliability issue
5. Add narrative summaries to cross-file analysis output

**Would I recommend this to other IS faculty?** Yes. I'm presenting it at the AMCIS conference in August.
