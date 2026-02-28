# Payroll System Known Issues — Anti-Pattern Catalog

**System**: Enterprise Payroll Processor (Legacy Sidecar)
**Purpose**: Educational reference — every anti-pattern is intentional and documented
**Last Updated**: 2026-02-28

> **For instructors and students**: This document is the **answer key** for Lesson 9 of the Teaching Guide. The anti-patterns cataloged here are real-world patterns drawn from decades of mainframe COBOL development. They are **intentional and contained** to the payroll sidecar — all other COBOL in this project follows clean, modern practices. Each issue is cross-referenced to the specific source file and line where it occurs. Use this catalog alongside the analysis tools (Lesson 10) to verify your findings programmatically.

This document is the **educational crown jewel** of the payroll sidecar. Each issue catalogs a real-world COBOL anti-pattern, explains why it exists, and describes what a modern developer would do instead.

---

## PAYROLL.cob Issues

### PY-01: GO TO Network (Paragraph Spaghetti)

**What**: P-000 through P-090 form an interconnected GO TO network. Flow control jumps between paragraphs non-sequentially (P-070 → P-010, P-040 → P-050, etc.).

**Era**: 1974 (JRK). COBOL-68 had no EVALUATE, no inline PERFORM, limited END-IF.

**Why It Exists**: GO TO was the only way to implement loops and conditional branches. The PERFORM statement existed but was limited to calling single paragraphs without parameters.

**Risk**: Adding a new paragraph between existing ones can break the flow chain. There is no compiler warning when a GO TO target is deleted.

**Modern Equivalent**: PERFORM UNTIL loops, EVALUATE/WHEN, structured IF/END-IF.

---

### PY-02: ALTER Statement (Runtime GO TO Modification)

**What**: `ALTER P-030 TO PROCEED TO P-040` changes where `GO TO` in P-030 will jump — at runtime. The same GO TO statement can go to different paragraphs depending on previous execution.

**Era**: 1974 (JRK). ALTER was an "advanced technique" in IBM training courses.

**Why It Exists**: Before EVALUATE (added in COBOL-85), ALTER was the standard way to implement computed dispatch — "go to this paragraph if salaried, that paragraph if hourly."

**Risk**: Extremely difficult to trace execution flow. Static analysis tools cannot determine GO TO targets without simulating ALTER chains. The COBOL-85 standard deprecated ALTER, and COBOL-2002 removed it entirely.

**Modern Equivalent**: EVALUATE TRUE / WHEN condition / PERFORM paragraph.

---

### PY-03: Cryptic Paragraph and Variable Names

**What**: Paragraphs named P-010, P-020, etc. Variables named WK-A1, WK-B2, WK-M1, WK-M3.

**Era**: 1974 (JRK). Common IBM mainframe convention.

**Why It Exists**: Early COBOL had a 30-character name limit. Paragraph numbering (P-010, P-020 by tens) left room to insert new paragraphs (P-015) without renaming. Variable prefixes (WK = working) saved characters.

**Risk**: New developers cannot understand the code without extensive tribal knowledge or documentation (which rarely exists).

**Modern Equivalent**: Descriptive names — PROCESS-SALARIED-PAY, COMPUTE-OVERTIME, EMPLOYEE-HOURLY-RATE.

---

### PY-04: Magic Numbers

**What**: WK-M1 = 40 (standard work hours), WK-M2 = 1.50 (overtime multiplier), WK-M3 = 80 (overtime cap). No comments, no named constants.

**Era**: 1974 (JRK). Named constants via 01-level VALUE clauses were available but not universally adopted.

**Why It Exists**: JRK used numeric literals for "obvious" values. Overtime rules were mandated by law and "everyone knows 40 hours and time-and-a-half."

**Risk**: When overtime rules change, you must find every magic number in every program. Searching for "40" returns hundreds of false positives.

**Modern Equivalent**: Named constants in a shared copybook (like PAYCOM.cpy, which PMR added later).

---

### PY-05: Dead Paragraph (P-085)

**What**: P-085 (overtime cap check) is never PERFORMed or GO TO'd. It was replaced when SLW restructured P-045 in 1991 but never deleted.

**Era**: 1991 (SLW removed the call, left the paragraph).

**Why It Exists**: Removing code from a production COBOL program requires a formal change request, regression testing, and sign-off. It is universally considered "safer" to leave dead code in place than to risk breaking something by removing it.

**Risk**: Dead code misleads readers into thinking it is executed. It also accumulates, making the program harder to understand over time.

**Modern Equivalent**: Version control. Delete the code; git preserves the history.

---

## TAXCALC.cob Issues

### TX-01: 6-Level Nested IF Without END-IF

**What**: COMPUTE-FEDERAL contains 6 nested IF statements with no END-IF terminators. A single period (`.`) at the end terminates all 6 levels simultaneously.

**Era**: 1983 (PMR). COBOL-68 had no END-IF; COBOL-85 added it, but PMR used the old style.

**Why It Exists**: PMR learned COBOL-68 and carried the habits to COBOL-85. The nested IF worked correctly and was never refactored. "If it ain't broke, don't fix it."

**Risk**: Adding a statement inside the nesting changes which IF each ELSE matches. A misplaced period terminates ALL open scopes. These bugs are nearly invisible in code review.

**Modern Equivalent**: EVALUATE TRUE / WHEN condition / statement / END-EVALUATE.

---

### TX-02: PERFORM THRU (Paragraph Range Execution)

**What**: `PERFORM COMPUTE-FEDERAL THRU COMPUTE-FICA-EXIT` executes all paragraphs from COMPUTE-FEDERAL through COMPUTE-FICA-EXIT in sequence, including any paragraphs between them.

**Era**: 1983 (PMR). PERFORM THRU was considered "standard practice."

**Why It Exists**: Before inline PERFORM (COBOL-85), THRU was the way to group related operations. The problem is that inserting a new paragraph between the start and end of the range silently adds it to the execution.

**Risk**: If someone adds a paragraph between COMPUTE-FEDERAL and COMPUTE-FICA-EXIT, it will execute as part of the tax calculation without any explicit call. Compiler gives no warning.

**Modern Equivalent**: PERFORM individual paragraphs or use inline PERFORM blocks.

---

### TX-03: Misleading Comments (5% vs 7.25%)

**What**: Comments throughout say "5% state tax rate." The actual code uses `WS-DEFAULT-STATE-RATE` which is `0.0725` (7.25%). PAYCOM.cpy also has `PAYCOM-STATE-RATE VALUE 0.0500` (5%) — but TAXCALC ignores it.

**Era**: 1983 (PMR wrote "5%"), 1992 (JRK changed rate to 7.25% without updating comments).

**Why It Exists**: Comments are not verified by the compiler. When the rate changed, JRK updated the code but not the comments. This is the single most common documentation bug in legacy COBOL.

**Risk**: New developers trust comments over code. A developer "fixing" the rate to match the comments would introduce a 2.25% tax calculation error.

**Modern Equivalent**: Use named constants whose names describe the value. `STATE-TAX-RATE-7-25-PCT` is self-documenting.

---

### TX-04: Hardcoded Brackets Override Copybook

**What**: WS-HARDCODED-BRACKETS duplicates the tax bracket table from TAXREC.cpy with different values. The program uses the hardcoded version, never the copybook.

**Era**: 1983 (PMR). "Just in case the copybook isn't loaded correctly."

**Why It Exists**: PMR didn't trust the COPY mechanism. The hardcoded values were "verified" and the copybook values were "from someone else."

**Risk**: Updating TAXREC.cpy has no effect on tax calculations. Two sources of truth = zero sources of truth.

**Modern Equivalent**: Single source of truth. Use the copybook or don't — never both.

---

### TX-05: Dead Marginal Rate Code

**What**: COMPUTE-MARGINAL paragraph implements a partial marginal tax rate algorithm that is never called.

**Era**: 1992 (JRK). "TODO — finish later." Never finished.

**Why It Exists**: JRK planned to replace the flat-per-bracket approach with proper marginal rates. Management said "the current one works fine." The half-implemented code was left in place.

**Risk**: A future developer might call this paragraph thinking it works. It doesn't.

---

### TX-06: Outdated FICA Wage Base

**What**: PAYCOM-FICA-LIMIT is $160,200 (the 1997 Social Security wage base). The 2026 limit is much higher.

**Era**: 1997 (PMR's last update).

**Why It Exists**: PMR updated the limit in 1997 and retired in 1998. Nobody knew the limit needed annual updating.

---

## DEDUCTN.cob Issues

### DD-01: Structured Top / Spaghetti Bottom

**What**: The top half of the program uses clean PERFORM loops (MAIN-PARA → PROCESS-EMPLOYEE → COMPUTE-*). The bottom half (DEDUCTION-OVERFLOW-HANDLER) uses GO TO to jump back into the processing loop.

**Era**: 1991 (SLW). The structured part was written during normal development. The GO TO part was a 2 AM production fix.

**Why It Exists**: When production breaks at 2 AM, you fix the immediate problem as fast as possible. Structured refactoring happens "later" (it never does). This hybrid pattern is the most common real-world COBOL style.

**Risk**: The GO TO bypasses the normal return path of PROCESS-EMPLOYEE. If any logic is added after the PERFORM COMPUTE-* calls, it won't execute for overflow cases.

---

### DD-02: Mixed COMP Types

**What**: Medical uses COMP-3, dental uses COMP, 401(k) uses DISPLAY. All three are added together, requiring implicit type conversion.

**Era**: 1991 (SLW). Three different "preferences" for three different fields.

**Why It Exists**: COBOL allows mixing COMP types in arithmetic. The compiler inserts conversion instructions silently. SLW used whatever felt natural for each field.

**Risk**: Performance degradation from implicit conversions. On mainframes with millions of records, this matters. For 25 employees, nobody notices.

**Modern Equivalent**: Consistent USAGE clause across all numeric fields in a group.

---

### DD-03: Contradicting Comments from 3 Developers

**What**: The 401(k) section has comments from SLW ("50% match"), PMR ("4% match cap"), and JRK (nothing — left the field undocumented). The code uses 50% of employee contribution (SLW's version).

**Era**: 1991-1993. Three developers, three interpretations, one codebase.

**Why It Exists**: Each developer documented their understanding without checking existing comments. Nobody reconciled the contradictions.

---

### DD-04: Dead Garnishment Code

**What**: DEAD-GARNISHMENT paragraph computes wage garnishments using PAYCOM-GARN-PCT (set to 0.00 since 1993).

**Era**: 1991 (SLW added), 1993 (PMR "disabled").

**Why It Exists**: The garnishment feature was moved to a new system. Instead of deleting the code, PMR zeroed out the constants and set the flag to 'N'. The code still executes but produces 0.

---

### DD-05: Wrong Medical Division Factor

**What**: Medical deduction divides annual cost by 12 (monthly) instead of 26 (biweekly pay periods).

**Era**: 1991 (SLW). "Divide annual by 12 for monthly, close enough."

**Why It Exists**: SLW confused "monthly cost" with "per-pay-period cost." The result is that employees are under-deducted by about 54% for medical premiums.

**Risk**: Actual financial discrepancy — the company absorbs the difference.

---

## PAYBATCH.cob Issues

### PB-01: Y2K Dead Date Conversion Code

**What**: Y2K-REVERSE-CONVERT paragraph converts 2-digit years to 4-digit using a windowing technique. It is never called.

**Era**: 2002 (Y2K team). Added "just in case" there were 2-digit dates in input. There aren't.

**Why It Exists**: The Y2K team added defensive code for every possible date format they could imagine. This one handles a case that doesn't exist in the input data.

**Risk**: The Y2K pivot year (50) means this code will break again in 2050 if anyone ever calls it.

---

### PB-02: Excessive DISPLAY Tracing

**What**: WS-TRACE-FLAG defaults to 'Y', producing DISPLAY output for every employee read, skip, and write. In a 25-employee run, this generates 100+ trace lines that nobody reads.

**Era**: 2002 (Y2K team). "For validation during Y2K testing."

**Why It Exists**: The Y2K team needed to verify date conversions were correct. They added tracing and forgot to remove it (or set the default to 'N').

**Risk**: Performance impact on large batches. Log files fill up. Signal-to-noise ratio approaches zero.

**Modern Equivalent**: Configurable log levels (DEBUG, INFO, WARN, ERROR).

---

### PB-03: Half-Finished Format Refactor

**What**: Outbound file is pipe-delimited (new format). Report output is still fixed-width (old format). Two formatting systems in one program.

**Era**: 2002 (Y2K team). Started converting all output to pipe-delimited, gave up halfway.

**Why It Exists**: The downstream settlement system accepted pipe-delimited. The downstream report parser expected fixed-width. Converting the report parser was out of scope for Y2K. "We'll do it in Phase 2." Phase 2 never happened.

---

### PB-04: Temporary Flat Tax Rate

**What**: PAYBATCH uses a hardcoded 30% flat tax rate instead of calling TAXCALC. Comments say "temporary."

**Era**: 2002 (Y2K team). "We don't have time to integrate TAXCALC here."

**Why It Exists**: Tight Y2K deadline. Integrating TAXCALC properly required testing the PERFORM THRU interface. The Y2K team chose a flat estimate and moved on.

**Risk**: Batch output amounts don't match actual payroll amounts. The outbound settlement records have incorrect net pay values.

---

## PAYCOM.cpy Issues

### PC-01: Conflicting Daily Limits

**What**: WK-B2 = 500,000 and PAYCOM-DAILY-LIMIT = 750,000. Both claim to be "max daily payroll batch." PAYROLL.cob uses WK-B2. DEDUCTN.cob uses PAYCOM-DAILY-LIMIT.

**Era**: 1974 (JRK: WK-B2) and 1991 (SLW: PAYCOM-DAILY-LIMIT).

**Why It Exists**: SLW added PAYCOM-DAILY-LIMIT without checking for WK-B2. JRK's cryptic naming made it invisible.

---

### PC-02: Comment/Value Mismatch (Medical Premium)

**What**: Comment says "$250/month per employee." VALUE is 275.00.

**Era**: 1991 (SLW). Rate was $250 when written, updated to $275 later without fixing the comment.

---

### PC-03: Dead Garnishment Constants

**What**: PAYCOM-DEAD-SECTION contains three garnishment-related constants, all zeroed out since 1993.

**Era**: 1988 (added), 1993 (zeroed).

---

## EMPREC.cpy Issues

### ER-01: Mixed COMP Types in One Record

**What**: Salary uses COMP-3, hours use COMP, text fields use DISPLAY. Three different storage formats in one 120-byte record.

**Era**: 1974 (COMP-3), 1983 (COMP), 1991 (DISPLAY added for new fields).

**Why It Exists**: Each developer used the storage format they were comfortable with. The compiler handles all conversions but inserts hidden overhead.

---

### ER-02: Undocumented Byte Offsets

**What**: JCL job PAYRL210 (SORT) depends on exact byte offsets. Changing field order or sizes breaks the sort job without any compile error.

**Era**: 1974 (JRK). JCL SORT fields reference byte positions, not field names.

**Why It Exists**: JCL and COBOL are separate systems. JCL doesn't read copybooks — it uses raw byte offsets. This creates an invisible coupling.

---

## Summary: Anti-Pattern Frequency

| Anti-Pattern | Occurrences | Programs |
|-------------|-------------|----------|
| GO TO | 15+ | PAYROLL, DEDUCTN |
| ALTER | 3 | PAYROLL |
| PERFORM THRU | 3 | PAYROLL, TAXCALC |
| Nested IF (no END-IF) | 1 (6-level) | TAXCALC |
| Dead paragraphs | 5 | All 4 programs |
| Misleading comments | 4 | TAXCALC, DEDUCTN, PAYCOM |
| Magic numbers | 6 | PAYROLL |
| Mixed COMP types | 3+ records | DEDUCTN, EMPREC |
| Y2K artifacts | 3 | PAYBATCH |
| Dead constants | 4 | PAYCOM |
| Comment/value mismatch | 3 | PAYCOM, TAXCALC, DEDUCTN |
| Conflicting values | 2 | PAYCOM |
