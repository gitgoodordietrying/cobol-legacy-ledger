# Marcus Chen — Senior COBOL Systems Programmer, IBM Z

**25 years maintaining CICS/batch COBOL on z/OS at a top-5 US bank**

## Rating: 4.6 / 5 stars (up from 4.2)

---

## First Impressions

I reviewed v5.x six months ago and gave it a 4.2. The author fixed nearly every technical issue I flagged. Let me walk through what changed.

The dashboard loads instantly. Six nodes in a hub-and-spoke SVG — CLEARING in the center (red ring), five banks orbiting (green rings). Each node labeled with its type: Retail, Corporate, Wealth, Institutional, Community. The network graph alone tells the story. My junior devs could look at this for 10 seconds and understand distributed settlement.

The health dot in the nav bar is green. Version 6.1.0. The role selector defaults to admin with four options. The monospace font and dark glass-morphism aesthetic say "mission control," not "toy project."

---

## What's Fixed Since Last Review

**The analysis scoring is correct now.** This was my biggest complaint. TRANSACT.cob previously scored "spaghetti" despite being well-structured code. Now:
- TRANSACT.cob: **33 (moderate)** — correct. It has nested IFs but clean paragraph structure.
- ACCOUNTS.cob: **10 (clean)** — correct. Straightforward CRUD with proper PERFORMs.
- SETTLE.cob: **9 (clean)** — correct. Clean 3-leg settlement flow.
- PAYROLL.cob: **134 (spaghetti)** — correct. GO TO maze, ALTER statements, cryptic names.
- MERCHANT.cob: **232 (spaghetti)** — the worst of the bunch, correctly identified.

This is now a reliable teaching tool. Students will learn the right lesson about code quality.

**Payroll analysis works end-to-end.** All 8 spaghetti files load and analyze without 404 errors. The call graph for PAYROLL.cob shows 17 paragraphs, 29 edges (16 GOTO, 3 ALTER, 5 PERFORM_THRU, 1 PERFORM, 4 FALL_THROUGH). The color-coded legend makes the tangle visible. Red dashed lines for GO TO, orange dotted for ALTER — you can see the spaghetti.

**The compare viewer is excellent.** Split-pane with PAYROLL.cob (1974 spaghetti, score 134) on the left and TRANSACT.cob (clean, score 33) on the right. Production headers visible on both sides. The score badges at the top make the contrast immediate. This is exactly the kind of side-by-side comparison I'd project in a training room.

**The chatbot actually works.** I asked it to list accounts in BANK_A — it called `list_accounts`, got 8 accounts, formatted them with names, balances, and status. Response in ~16 seconds. I asked it to verify BANK_A's chain — it called `verify_chain`, reported 45,924 entries checked, valid, 305ms verification time. The tool-use loop resolves correctly. This was completely broken before.

---

## What Works

**Authentic COBOL patterns (unchanged, still excellent):**
- Production headers on every .cob file with JCL references
- `FILE STATUS IS WS-FILE-STATUS` on every SELECT
- `PIC S9(10)V99` for financials — no floating point
- 70-byte ACCTREC, 103-byte TRANSREC — realistic fixed-width records
- `OPEN EXTEND` for transaction logs, `OPEN OUTPUT` for account rewrites

**The 8-program spaghetti sidecar with complexity scoring:**
- PAYROLL.cob (134): JRK's 1974 GO TO maze with ALTER-modified paragraphs
- MERCHANT.cob (232): GO TO DEPENDING ON, shared working storage, the highest complexity in the project
- DISPUTE.cob (137): ALTER state machine, dead Report Writer code
- FEEENGN.cob (68): SORT INPUT/OUTPUT PROCEDURE, 3-deep PERFORM VARYING
- RISKCHK.cob (59): Contradicting velocity checks, INSPECT TALLYING
- TAXCALC.cob (34): 6-level nested IF, PERFORM THRU
- DEDUCTN.cob (25): Structured/spaghetti hybrid, mixed COMP types
- PAYBATCH.cob (18): Y2K dead code, but relatively clean structure

Each program tells a different anti-pattern story. The complexity scores are now accurate and meaningful.

**The compare_complexity chat tool (NEW):**
When I asked the chatbot "Compare PAYROLL.cob vs TRANSACT.cob," it invoked the `compare_complexity` tool and returned structured data: per-paragraph hotspot scores, GO TO counts, ALTER counts, dead code counts, and a delta summary. The LLM then explained the differences in context — "PAYROLL scores 134 (spaghetti) with 16 GO TOs and 3 ALTERs vs TRANSACT's 33 (moderate) with zero GO TOs." This is genuinely useful for teaching.

**Chain verification at scale:**
45,924 chain entries verified in 305ms for BANK_A alone. SHA-256 hash chain integrity across the full 6-node network. The cross-node verification endpoint reports per-node validity with settlement matching counts. This is production-grade observability.

**RBAC enforcement is real:**
- Operator requesting chain verify: 403 with message "User operator (role: operator) lacks permission: chain.verify"
- Viewer requesting simulation start: 403 with "lacks permission: transactions.process"
- This separation of duties (operators can transact but not audit, auditors can verify but not transact) mirrors real banking access control.

---

## What's Missing / Could Still Improve

**GnuCOBOL vs z/OS gap (unchanged):**
- LINE SEQUENTIAL is still GnuCOBOL-specific. The code mentions it but doesn't emphasize the difference enough for students heading to real mainframes.
- Still no JCL examples beyond the fictional header comments. A sample JCL deck (even non-functional) would bridge the gap.

**Transaction endpoint returns status "99" (Unknown error):**
- When I deposited $100 via the API (`POST /api/nodes/BANK_A/transactions`), it returned `{"status": "99", "tx_id": null, "new_balance": null, "message": "Unknown error"}`. This suggests the COBOL subprocess isn't available (Mode B Python fallback may not be handling API transactions). The simulation works fine, but direct transaction API calls are unreliable. This is a gap for demonstrating individual transaction processing.

**The chat model picker in the sidebar shows stale entries:**
- The model dropdown lists "qwen2.5:3b, llama3.1, mistral, codellama" — but the server auto-detected and is using qwen3:8b (not in the dropdown). The sidebar doesn't reflect the actual active model correctly. Minor UI issue but confusing.

**Dead code detection could be richer:**
- PAYROLL.cob shows 1 dead paragraph (P-085). The call graph marks it with a "DEAD" badge and red-bordered box. But the dead code analysis doesn't explain *why* it's dead — no incoming edges, no PERFORM targeting it. Adding a "reason" field would help teaching.

---

## WOW Moments

1. **The call graph visualization for PAYROLL.cob.** 17 paragraphs connected by a tangle of red dashed (GOTO), orange dotted (ALTER), and blue dashed (PERFORM THRU) lines. P-085 marked dead with a crossed-out badge. The visual immediately communicates "spaghetti" in a way that no code listing can. This is worth the entire project.

2. **"Analyzed in 13ms — Human estimate: 2 days."** This badge in the analysis view is brilliant marketing. It makes the case for static analysis tools in one line. I'd show this to my management to justify tool investment.

3. **The chatbot explaining ALTER with the knowledge base.** I asked "What is ALTER in COBOL?" and the LLM invoked `explain_cobol_pattern`, pulling structured data about ALTER's era (1974), purpose (computed dispatch before EVALUATE), risk level, and modern equivalent. Then it synthesized a coherent explanation. This is a proper AI-augmented documentation tool, not a toy wrapper.

4. **The tamper → detect flow (still the killer demo).** Corrupt BANK_C's ledger with one click, verify all nodes, watch the chain break propagate. The cross-node verification endpoint now reports exactly which node broke and where. Sub-second detection across 6 nodes.

---

## Deal Breakers

None. The scoring bug that was my previous deal breaker is fixed. The transaction API returning status 99 is annoying but not blocking — the simulation and settlement flows work correctly.

---

## Verdict

This has gone from "best COBOL teaching resource I've seen outside IBM" to "I'd use this in production onboarding." The analysis scoring is now trustworthy, the chatbot actually resolves tools, and the 8-program spaghetti sidecar with accurate complexity metrics is a masterclass in teaching anti-patterns.

The compare_complexity tool is exactly what was missing — the LLM can now pull live metrics and explain spaghetti vs clean code with real data, not just generic text. Combined with the split-pane compare viewer showing actual source code, this is a complete teaching pipeline: see the code, see the metrics, hear the explanation.

**Would I recommend this to my team?** Already did. Three junior developers are using the Learning Path.

**What would make it perfect:**
1. Fix the transaction API (status 99 on direct deposits)
2. Add a sample JCL deck for z/OS context
3. Enrich dead code analysis with "reason unreachable" explanations
