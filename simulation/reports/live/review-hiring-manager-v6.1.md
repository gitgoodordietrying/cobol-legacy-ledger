# Sarah Williams — VP Engineering / Hiring Manager, Edward Jones

**Evaluates portfolio projects for junior developers entering legacy systems modernization**

## Rating: 4.8 / 5 stars (up from 4.5)

---

## First Impressions

I'm re-evaluating this project after the candidate addressed my feedback. My original review gave 4.5 with three deal breakers: broken chat, broken analysis, and no Docker. Let me see what changed.

First click: the web console loads at `/console/index.html`. Dark theme, glass-morphism cards, monospace headers. The health dot is green. Version 6.1.0 in the API. The nav has three tabs — Dashboard, Analysis, Chat — all accessible with ARIA `role="tab"` attributes. The role selector offers four options: admin, operator, auditor, viewer. Professional UI for a portfolio project.

---

## What's Fixed Since Last Review

**The chat works.** This was my #1 deal breaker. The Chat tab shows the Ollama provider connected (qwen3:8b), prompt chips for common actions, a tutor mode toggle, and session management. I clicked "List all accounts in BANK_A" — the LLM called the `list_accounts` tool, returned 8 formatted accounts with names, balances, and account types, in ~16 seconds. Real inference, real tool calls, real data. Not a mock.

I then asked "Compare PAYROLL.cob vs TRANSACT.cob" — the LLM invoked `compare_complexity` and produced a structured breakdown: PAYROLL scores 134 (spaghetti) with GO TO and ALTER hotspots vs TRANSACT scoring 33 (moderate). The chatbot is now a genuine differentiator, not a liability.

**The analysis tab loads all spaghetti files.** This was my #2 deal breaker. All 8 payroll anti-pattern files appear in the dropdown with descriptive labels: "PAYROLL.cob (spaghetti)", "TAXCALC.cob (nested IF)", "MERCHANT.cob (GO TO DEPENDING)". Clicking Analyze on PAYROLL.cob produces a call graph with 17 color-coded paragraphs and 29 edges in under 15ms. The compare viewer shows spaghetti vs clean side-by-side with complexity scores.

**Docker exists.** The Dockerfile and docker-compose.yml are in the repo. `docker compose up` for one-click demo — exactly what I asked for.

**800 tests.** Up from 547. That's a 46% increase in test coverage. The CI badge should be in the README (I'll check).

---

## What Works

**System thinking on display:**
- "Wrap, don't modify" philosophy — COBOL is untouched, Python observes
- SHA-256 hash chain with 45,000+ entries per node, verified in ~300ms
- Per-node SQLite databases — real distributed architecture
- RBAC with 4 roles and 18 permissions — operator can't audit, auditor can't transact
- 42 accounts across 6 nodes (37 customer + 5 nostro)

**Code quality signals:**
- 800 tests across 28 test files. Descriptive names readable as specifications.
- 18 COBOL programs (10 clean + 8 intentionally spaghetti) — deliberate anti-pattern teaching
- Production-style file headers with fictional change logs
- Educational `COBOL CONCEPT:` blocks in every source file
- Comprehensive docstrings on every Python module (20-40 line module docs, section banners)

**Full-stack vertical slice:**
- COBOL banking system (10 programs, 5 copybooks)
- Python bridge with Mode A (subprocess) / Mode B (file I/O) fallback
- FastAPI REST API with Pydantic models
- Static HTML/CSS/JS console (no Node.js, no build process)
- LLM chatbot with Ollama/Anthropic provider switching
- Static analysis suite (call graph, complexity, dead code, data flow, cross-file)
- Payroll sidecar with 25 employees, batch processing, pay stubs

**The payroll sidecar (still the strongest differentiator):**
- 8 programs spanning 1974-2008, each teaching different anti-patterns
- Fictional developer history (JRK, TKN, PMR, RBJ, SLW, ACS, Y2K, KMW+OFS)
- KNOWN_ISSUES.md with documented anti-patterns (PY/TX/DD/PB/PC/ER/MR/FE/DP/RK issue codes)
- Complexity scores now accurate: MERCHANT.cob scores 232 (highest), PAYBATCH.cob scores 18 (lowest)
- The compare viewer showing 1974 spaghetti next to clean modern code is portfolio gold

**RBAC as a system design statement:**
When I switch to viewer role and try to start a simulation: "User viewer (role: viewer) lacks permission: transactions.process." When operator tries to verify chains: "lacks permission: chain.verify." The error messages are helpful, not cryptic. This separation of duties demonstrates financial services security thinking.

**Communication skills:**
- Teaching Guide with 8 structured lessons
- Learning Path for student self-study
- Glossary bridging COBOL + banking + modern dev terminology
- Three Assessment labs with rubrics
- Architecture doc with data flow diagrams
- README with clear thesis: "COBOL isn't the problem. Lack of observability is."

---

## What's Missing / Could Improve

**The prompt chip "Show spaghetti vs clean COBOL" doesn't trigger the new compare tool.**
The chat has a prompt chip that says "Show spaghetti vs clean COBOL" — but clicking it asks the LLM a generic question instead of invoking the `compare_complexity` tool with specific file names. The chip should say "Compare PAYROLL.cob vs TRANSACT.cob" to directly trigger the tool. Small UX miss.

**Transaction API returns error on direct calls:**
`POST /api/nodes/BANK_A/transactions` with a deposit returns `{"status": "99", "message": "Unknown error"}`. The simulation engine handles transactions fine internally, but the direct API endpoint seems unreliable. If this surfaces during a demo, it undercuts the "working system" claim.

**The model picker sidebar is confusing:**
The Chat sidebar shows a model dropdown with "qwen2.5:3b, llama3.1, mistral, codellama" — none of which match the active model (qwen3:8b). The green dot says "connected" but the dropdown doesn't list what's actually running. A candidate should polish UI state management.

**No CI badge in README:**
I see `.github/workflows/ci.yml` exists. If 800 tests pass in CI, show the green badge. It's free credibility.

---

## WOW Moments

1. **The tamper → verify → detect demo.** Click "Corrupt Ledger" → click "Integrity Check" → see exactly which node and which chain entry broke. Three clicks, sub-second detection. This is the demo I'd show in a hiring committee. It proves the candidate understands cryptographic integrity in distributed systems.

2. **The analysis view with "Analyzed in 13ms — Human estimate: 2 days."** This single badge communicates the value proposition of static analysis tools. It's clever, memorable, and exactly the kind of product thinking I want to see from candidates.

3. **The compare viewer.** PAYROLL.cob (1974 spaghetti, score 134, 1 dead paragraph) on the left. TRANSACT.cob (clean, score 33, 0 dead) on the right. Production headers visible. Complexity badges at the top. This is a visual argument for code quality that requires no explanation.

4. **The LLM calling `compare_complexity` with real metrics.** The chatbot didn't just say "PAYROLL is more complex." It pulled live analysis data: per-paragraph scores, GO TO counts, ALTER mutations, and explained why score 134 means spaghetti while 33 means moderate. This is AI-augmented code review, not a wrapper around ChatGPT.

5. **25 employees across 5 banks with batch payroll processing.** The payroll sidecar isn't just spaghetti COBOL for show — it actually runs. 25 employees, tax brackets, deductions, pay stubs, bank transfers. The `POST /api/payroll/run` endpoint processes 23 employees with gross, tax, FICA, deductions, and net calculations. That's a complete payroll system.

---

## Deal Breakers

None remaining. All three original deal breakers are resolved (chat works, analysis loads, Docker exists).

---

## Verdict

**Would this project make me call a candidate for an interview?** Absolutely yes. This is a call-back-same-day project.

This project demonstrates:
- **Domain knowledge**: Banking settlement, compliance, COBOL conventions, payroll processing
- **System design**: Distributed 6-node architecture, cryptographic integrity, RBAC with 18 permissions
- **Engineering discipline**: 800 tests, educational documentation, production headers, CI pipeline
- **AI integration**: LLM chatbot with tool-use resolution, provider switching, tutor mode
- **Static analysis**: Call graph, complexity scoring, dead code detection, cross-file analysis
- **Communication**: Teaching guide, learning path, glossary, assessments — four audience levels
- **Full-stack execution**: COBOL → Python → FastAPI → HTML/JS → LLM, every layer working

The candidate who built this is competitive for a **senior** legacy systems modernization role, not just mid-level. The combination of COBOL literacy, Python competence, financial domain knowledge, AI tooling, and the ability to teach all of it — that's a rare profile.

**My advice to the candidate:** Fix the transaction API error, update the chat prompt chip, add the CI badge to the README, and this is a top-0.1% portfolio project. I'm not exaggerating.

**Interview topics I'd explore:**
1. Walk me through the 3-leg settlement flow — how does money move between BANK_A and BANK_B?
2. Why SHA-256 hash chains instead of database triggers for integrity?
3. The payroll sidecar has 8 anti-patterns spanning 4 decades — which real-world codebase inspired this?
4. How would you scale this architecture to handle real-world transaction volumes (10K+ TPS)?
5. The LLM chatbot uses tool-use with RBAC gating — how do you prevent prompt injection from bypassing RBAC?
