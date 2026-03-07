# Dev Patel — Staff Writer, TechCrunch

**Covers developer tools, open-source highlights, and "GitHub repos you should know"**

## Rating: 4.3 / 5 stars (up from 3.8)

---

## First Impressions

I flagged this repo six months ago with a "not yet, but close" verdict. The substance was there but the packaging wasn't — broken features, no screenshots, no companion content. Let me see if the gap closed.

Opening the web console: dark glass-morphism UI with frosted cards, monospace headers, a hub-and-spoke network graph showing 6 banking nodes. The CLEARING node is red (hub), the 5 banks are green (spokes), each labeled — Retail, Corporate, Wealth, Institutional, Community. The contrast between "1959 programming language" and "2026 dark-mode mission control" is still the angle. That hasn't changed.

What has changed: the Chat tab works, the Analysis tab loads spaghetti files, and there's a Docker setup. My three blockers are gone.

---

## What's Fixed Since Last Review

**The chat feature works end-to-end.** I clicked "List all accounts in BANK_A" and the LLM (qwen3:8b via Ollama) called the `list_accounts` tool, returned 8 formatted accounts with real data, in about 16 seconds. This is a real AI chatbot querying a real COBOL banking system. That sentence alone is an article hook.

**The analysis tab loads all spaghetti files.** 11 options in the dropdown: 8 spaghetti + 3 clean. Each labeled with its anti-pattern: "PAYROLL.cob (spaghetti)", "MERCHANT.cob (GO TO DEPENDING)", "DISPUTE.cob (ALTER state machine)". Clicking Analyze produces a call graph visualization in under 15ms. The compare button opens a split-pane viewer showing spaghetti vs clean side-by-side with complexity scores.

**Docker exists.** `docker compose up` for a one-click demo. This removes the "but I have to install GnuCOBOL?" objection.

---

## What Works

**The narrative is stronger than ever:**
- 18 COBOL programs (up from 14) — 10 clean + 8 intentionally spaghetti
- 800 tests (up from 547) — nearly 50% growth in test coverage
- 42 accounts across 6 nodes — the same compelling real number
- 20 LLM tools (up from 0 working) — banking, codegen, and analysis tools
- The thesis "COBOL isn't the problem" now has an AI dimension: "and an LLM can prove it by querying the system live"

**The demo is now screenshot-ready:**
- Dashboard: Network topology with 6 color-coded nodes, simulation controls, transaction log, live COBOL viewer
- Analysis: Call graph with GO TO/ALTER/PERFORM edges color-coded, complexity heatmap, "Analyzed in 13ms — Human estimate: 2 days" badge
- Compare: Split-pane with PAYROLL.cob (134/spaghetti) vs TRANSACT.cob (33/moderate), production headers visible
- Chat: Provider sidebar, prompt chips, session management, tutor mode toggle

I could screenshot all four views right now and have enough visuals for an article.

**The numbers are even more compelling:**
- 18 COBOL programs, 12 copybooks, 800 tests
- 42 accounts, 6 nodes, 45,000+ chain entries per node
- 20 LLM tools with RBAC gating (4 roles, 18 permissions)
- 25 payroll employees with batch processing
- Complexity scores: MERCHANT.cob at 232 (worst), ACCOUNTS.cob at 10 (best)
- Chain verification: 45,924 entries in 305ms

**The spaghetti narrative has deepened:**
- 4 new programs since last review (MERCHANT, FEEENGN, DISPUTE, RISKCHK)
- Each tells a different legacy story: GO TO DEPENDING ON (1978), SORT procedures (1986), ALTER state machines (1994), contradicting velocity checks (2008)
- KNOWN_ISSUES.md now has 10 issue code categories — it's a proper anti-pattern catalog
- The fictional developer timeline (JRK 1974 through KMW+OFS 2008) spans 34 years of maintenance decisions

**The LLM comparison tool is quotable:**
When I asked the chatbot "Compare PAYROLL.cob vs TRANSACT.cob," it pulled real metrics: "PAYROLL scores 134 (spaghetti) with 16 GO TOs, 3 ALTERs, and paragraph P-000 as the worst hotspot at 23 points. TRANSACT scores 33 (moderate) with zero GO TOs and structured PERFORM logic." That's a concrete, data-driven answer. I can quote that in an article.

---

## What's Missing / Could Improve

**Still no embedded screenshots in the README.**
I can see `docs/screenshots/` and `simulation/screenshots/` exist. But the README itself — what appears on the GitHub page — doesn't embed any images. For a "repos you should know" article, I need to see the project without cloning it. Three embedded screenshots (dashboard, analysis call graph, compare viewer) would transform the README from "text wall" to "visual pitch."

**Still no live demo.**
No GitHub Pages, no hosted instance, no video. A 30-second GIF of: dashboard → run simulation → tamper → detect → analysis → compare → chat would be perfect for Twitter/X and would 10x the reach. The project is now visual enough to support this.

**The chat model picker UI needs polish.**
The sidebar shows a dropdown with models that don't match what's running. The green dot says "connected" to qwen3:8b but the dropdown lists qwen2.5:3b, llama3.1, mistral, codellama. This is a minor cosmetic issue but it's the kind of thing that breaks the "polished" impression.

**Social proof is still absent.**
No stars, no forks, no blog post, no dev.to article, no Hacker News submission. The project is mature enough to share now — it would generate discussion on r/programming or HN.

**One prompt chip is generic:**
The chat has "Show spaghetti vs clean COBOL" as a prompt chip, but this triggers a generic text response. It should say "Compare PAYROLL.cob vs TRANSACT.cob" to invoke the actual comparison tool with metrics. The other chips ("List all accounts in BANK_A", "Verify all chains") work well.

---

## WOW Moments

1. **The spaghetti call graph.** PAYROLL.cob's 17 paragraphs connected by 16 red GO TO lines, 3 orange ALTER lines, and 5 blue PERFORM THRU arcs. P-085 marked DEAD in red. The visual is immediately striking — it looks like tangled yarn. This is the hero image for any article about legacy code.

2. **"Analyzed in 13ms — Human estimate: 2 days."** This badge is marketing genius. It belongs in a slide deck, on a landing page, in a tweet. It makes the case for static analysis without a single word of explanation.

3. **The compare viewer.** PAYROLL.cob (1974, score 134, "spaghetti") on the left. TRANSACT.cob (clean, score 33, "moderate") on the right. Production headers, JCL references, educational comments visible. The score badges at the top make the contrast instant. This is the "before and after" shot that writes itself.

4. **An LLM that queries a COBOL banking system live.** I asked it a question, it called a tool, it got real data, it explained the results. This isn't a wrapper around GPT — it's an AI that understands COBOL through actual analysis tools. The tool-use audit trail (tool name, arguments, result, permitted/denied) is visible in the response. That's transparency.

5. **The payroll batch run.** 25 employees processed with gross pay, federal tax, state tax, FICA, deductions, and net pay calculated per employee. 23 processed, 2 skipped (terminated). Total batch gross: $56,738.76, total batch net: $31,053.80. This is a real payroll system running through intentionally spaghetti COBOL. The numbers are realistic.

---

## Deal Breakers (for article inclusion)

**No embedded screenshots in README** — still the gap. I need visuals on the GitHub page itself.

Everything else is fixed. The chat works, the analysis works, Docker exists.

---

## Verdict

**Would I write a "GitHub Repos You Should Know" article featuring this?** Yes, with one condition: embed 3-4 screenshots in the README.

**The angle I'd use:** "While banks spend billions replacing COBOL, one developer built a 6-node banking system with an AI chatbot that can analyze and explain 34 years of spaghetti code — proving the real problem isn't the language, it's the observability."

**Headline draft:** "This COBOL Banking System Has an AI That Can Explain 50-Year-Old Spaghetti Code"

**What would make it viral:**
1. Embed screenshots in README (dashboard, call graph, compare viewer, chat with tool calls)
2. Create a 30-second GIF or video walkthrough
3. Write a companion post: "I Built a COBOL Banking System to Prove Legacy Code Isn't the Problem"
4. Submit to Hacker News with the thesis framing
5. Share the PAYROLL.cob call graph image on Twitter/X — that tangle of GO TO arrows will generate engagement

The project has both the substance and the visual quality now. It just needs the distribution strategy.
