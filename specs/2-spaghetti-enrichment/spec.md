# Spec: Spaghetti Enrichment — Archaeological Depth for Legacy Payroll

**Status**: Drafting
**Created**: 2026-04-02

## Overview

Inject 25+ categories of practitioner-sourced anti-patterns, traps, and archaeological artifacts into the 8 existing payroll spaghetti programs and 7 copybooks. All enrichments are Layer 1 only: comments, WORKING-STORAGE additions (unreferenced by executable code), dead code paragraphs, and documentation updates. The 807 existing tests must pass unchanged — zero executable logic modifications. Source material drawn from two research documents: `COBOL_PRACTITIONER_INSIGHTS.md` (practitioner interviews) and `COBOL_MAINFRAME_QUIRKS.md` (technical reference covering language quirks, dialect incompatibilities, mainframe architecture, banking arithmetic, and hardware).

---

## User Stories

### US-1: Period Bug Discovery (Priority: P1)

As a **student**, I want to find realistic period-related bugs documented in comments so I can understand why a single missing period took down Nordea bank for 16 hours.

**Acceptance Scenarios**:
1. Given PAYROLL.cob, When I read the comments near P-060, Then I find a developer note explaining that a missing period after an IF statement would cause fall-through into the next paragraph, with a reference to the Nordea incident.
2. Given TAXCALC.cob, When I examine the 6-level nested IF in COMPUTE-FEDERAL, Then I find a comment block warning that a period placed inside the nesting terminates ALL open IF scopes simultaneously, with a concrete "what would break" scenario.
3. Given DEDUCTN.cob, When I look at the structured-top/spaghetti-bottom boundary, Then I find a "close enough" placement comment from SLW noting that the GO TO added at 2 AM accidentally avoided a period bug that would have doubled medical deductions.

### US-2: Batch Ordering Trap Awareness (Priority: P1)

As a **student**, I want to encounter batch ordering assumptions in the code comments so I can understand why file pre-sort requirements cause silent failures in legacy systems.

**Acceptance Scenarios**:
1. Given PAYBATCH.cob, When I read the file-open section, Then I find a comment warning that input records MUST be pre-sorted by bank code or output records will be interleaved incorrectly, and that no validation enforces this.
2. Given FEEENGN.cob, When I examine the SORT verb section, Then I find a developer note explaining that the INPUT PROCEDURE assumes ascending MCC codes and that RELEASE in wrong order produces silently incorrect tier assignments.
3. Given RISKCHK.cob, When I look at the SCAN operation, Then I find a comment noting that the merchant file must be pre-sorted by MERCH-ID for sequential lookup to work, with a note that duplicate MERCH-IDs cause the first match to shadow all others.

### US-3: Numeric Overflow Documentation (Priority: P1)

As a **student**, I want to see documented numeric overflow edge cases so I can understand the real-world consequences of fixed-precision arithmetic in COBOL.

**Acceptance Scenarios**:
1. Given PAYROLL.cob, When I examine WS-BATCH-GROSS (PIC S9(9)V99), Then I find a comment calculating that WS-PERIOD-GROSS multiplied by 26 periods can exceed S9(9) if any single period exceeds approximately $38,461.53, causing silent truncation.
2. Given FEEENGN.cob, When I look at the triple-nested PERFORM VARYING fee calculation, Then I find a comment warning that FEE-CALC-TOTAL (PIC S9(7)V99) overflows silently if a single transaction exceeds $99,999.99 and all three surcharges apply.
3. Given RISKCHK.cob, When I examine WS-RISK-SCORE (PIC 9(3)), Then I find a comment noting that double-scored velocity + amount checks can exceed 999, wrapping to 0 and clearing a legitimately flagged transaction.

### US-4: COMP-3/EBCDIC Heritage Artifacts (Priority: P1)

As a **student**, I want to encounter mainframe-specific field layout comments and byte-order notes so I can understand the EBCDIC heritage of production COBOL.

**Acceptance Scenarios**:
1. Given EMPREC.cpy, When I read the header comments, Then I find a COMP-3 byte layout example showing how PIC S9(7)V99 COMP-3 stores 9 digits in 5 bytes with a trailing sign nibble (C=positive, D=negative, F=unsigned).
2. Given PAYCOM.cpy, When I examine PAYCOM-FICA-LIMIT (COMP-3), Then I find a comment explaining that in EBCDIC, packed decimal representation differs from ASCII and that GnuCOBOL handles the conversion silently.
3. Given TAXREC.cpy, When I read the bracket table, Then I find a comment about overpunch sign characters: how PIC S9(n) DISPLAY format stores the sign as an overpunch on the last digit (+0 becomes '{', -1 becomes 'J'), and why Python parsers must handle this.

### US-5: Field Reuse Ambiguity (Priority: P2)

As a **student**, I want to find examples where the same WORKING-STORAGE field is used for different purposes in different code paths so I can understand implicit coupling in legacy COBOL.

**Acceptance Scenarios**:
1. Given MERCHANT.cob, When I trace WK-M4, Then I find a comment block listing all three meanings: (a) reserve percentage in MR-030, (b) risk score accumulator in MR-040, (c) fee tier index in MR-070 — with a warning that modifying the field in one context silently corrupts the other two.
2. Given PAYROLL.cob, When I examine WK-GROSS, Then I find a comment noting reuse across P-040 (salaried) and P-045 (hourly) without zeroing between uses, correct only because the paths are mutually exclusive via ALTER.
3. Given RISKCHK.cob, When I examine WS-RISK-SCORE, Then I find a comment noting that both KMW and offshore paths accumulate into the same field without resetting, which is the root cause of double-scoring.

### US-6: Abend/Recovery Notes (Priority: P2)

As a **student**, I want to find developer comments about what breaks, debugging tips, and historical cost impacts so I can understand the operational culture around legacy COBOL.

**Acceptance Scenarios**:
1. Given DISPUTE.cob, When I read the ALTER state machine section, Then I find an abend note: "If this ABENDs mid-transition, the dispute record is in inconsistent state. Recovery: manually reset DISP-STATE to 'O'. Cost: 4 hours last time (ACS, 1995-11-22)."
2. Given FEEENGN.cob, When I examine the SORT verb, Then I find a recovery note: "SORT failure leaves SORT-WORK file locked. IPL required. On z/OS this meant a 2-hour system restart. Lost the Sunday evening batch window twice in 1988."
3. Given PAYROLL.cob, When I look at the ALTER chain in P-000, Then I find a debugging tip: "To trace ALTER targets, add DISPLAY before each ALTER. Do NOT leave DISPLAYs in production — one site generated 4GB of spool output."

### US-7: Implicit Array Bounds and OCCURS Limits (Priority: P2)

As a **student**, I want to see boundary comments on OCCURS clauses so I can understand what happens when COBOL arrays overflow.

**Acceptance Scenarios**:
1. Given FEEREC.cpy, When I read the OCCURS 4 clause on FEE-INTERCHANGE-ENTRY, Then I find a comment: "What happens at network 5? Subscript out of range. GnuCOBOL may raise EC-RANGE-INDEX; IBM mainframe silently overwrites adjacent memory. This is buffer overflow in COBOL."
2. Given MERCHREC.cpy, When I read the REDEFINES section, Then I find a comment noting that reading MERCH-AGGREGATE-DATA when MERCH-TYPE is 'I' produces garbage from misaligned bytes, with a note that no runtime check enforces the correct view.
3. Given RISKCHK.cob, When I examine the INSPECT TALLYING section, Then I find a comment noting WS-KEYWORD-COUNT (PIC 9(3)) overflows at 1,000 matches, wrapping to 0.

### US-8: Midnight/Timezone Hazards (Priority: P2)

As a **student**, I want to see comments about midnight boundary and timezone edge cases so I can understand why overnight batch processing creates subtle bugs.

**Acceptance Scenarios**:
1. Given RISKCHK.cob, When I examine velocity check paragraphs, Then I find a comment warning that the "per-hour" check resets at midnight: 10 transactions at 23:59 and 10 at 00:01 scores as two separate bursts of 10, not one burst of 20.
2. Given PAYBATCH.cob, When I look at date handling, Then I find a comment noting the batch run date has no timezone context — a batch started at 23:00 EST finishing at 00:15 EST records transactions against two different calendar days.
3. Given PAYROLL.cob, When I examine WS-RUN-DAY, Then I find a comment noting that pay period end date and batch run date are assumed identical, which fails when Friday payroll runs on Saturday morning.

### US-9: 3270 Terminal Artifacts in Batch Code (Priority: P3)

As a **student**, I want to find screen-based input assumptions embedded in batch code so I can understand the 3270 terminal heritage of mainframe COBOL.

**Acceptance Scenarios**:
1. Given MERCHANT.cob, When I examine the ACCEPT statement, Then I find a comment explaining that on a mainframe, ACCEPT retrieves data from a 3270 terminal screen (80x24) and the PIC X(20) field mirrors the BMS map field length from the original CICS transaction.
2. Given PAYROLL.cob, When I examine WS-DISPLAY-LINE (PIC X(80)), Then I find a comment noting this is exactly one 3270 terminal line and that DISPLAY output was designed for a 132-column line printer but truncated to 80 for terminal viewing.

### US-10: Input Validation Apathy (Priority: P3)

As a **student**, I want to see annotated examples of missing input validation so I can understand the trust model of legacy COBOL batch systems.

**Acceptance Scenarios**:
1. Given PAYROLL.cob, When I examine the employee read loop, Then I find a comment noting EMP-SALARY is never validated for negative values — negative salary produces negative gross pay flowing through tax calc to produce a "refund" paystub.
2. Given RISKCHK.cob, When I examine WS-INPUT-AMOUNT, Then I find a comment noting no validation for zero/negative amounts — negative amounts produce negative risk points, reducing the score.
3. Given DISPUTE.cob, When I examine the FILE operation, Then I find a comment noting DISP-AMOUNT is not validated against the original transaction amount — a dispute for $1M on a $50 transaction processes without question.

### US-11: Deliberate Workarounds and Dated Assumptions (Priority: P3)

As a **student**, I want to find "TODO: remove after Y2K" style comments and period-specific hacks so I can understand how temporary code becomes permanent infrastructure.

**Acceptance Scenarios**:
1. Given PAYBATCH.cob, When I look at the Y2K date conversion section, Then I find: "TODO: Remove parallel 2-digit date fields after Y2K validation (target: Q2 2000). It is now 2026."
2. Given FEEENGN.cob, When I examine the blended pricing override, Then I find: "TEMPORARY for Q2 1989. Will remove when interchange+ negotiations complete. Status: 37 years and counting."
3. Given DEDUCTN.cob, When I look at the garnishment section, Then I find: "PMR 1993: Disabled. TODO: delete in next release. Note: 'next release' was 1994. This code has survived 5 platform migrations."

### US-12: Implied Decimal Traps (Priority: P1)

As a **student**, I want to see comments documenting where the implied decimal point (`V`) causes silent truncation or data loss so I can understand why COBOL's most dangerous behaviors are the ones that succeed silently.

**Acceptance Scenarios**:
1. Given TAXCALC.cob, When I examine the tax bracket computation, Then I find a comment explaining that the `V` in `PIC 9(5)V99` occupies zero bytes of storage — the value `80.375` silently becomes `80.37` (truncation, not rounding) unless `ROUNDED` is explicitly coded.
2. Given PAYROLL.cob, When I examine the gross pay multiplication, Then I find a comment warning that multiplying two `PIC 9(4)V99` fields can produce a result requiring `PIC 9(8)V9(4)` — if the receiving field is too small, high-order digits vanish without any error, and this is defined COBOL behavior, not a bug.
3. Given FEEENGN.cob, When I examine the fee calculation result fields, Then I find a comment showing the explicit pattern: `COMPUTE WS-RESULT = WS-A * WS-B ROUNDED ON SIZE ERROR PERFORM ERROR-HANDLER END-COMPUTE` — and noting that the program uses none of these safeguards.

### US-13: MOVE Truncation Hazards (Priority: P1)

As a **student**, I want to see comments documenting where COBOL's MOVE truncation rules silently destroy data so I can understand the difference between alphanumeric and numeric MOVE behavior.

**Acceptance Scenarios**:
1. Given PAYROLL.cob, When I examine a numeric MOVE into a smaller field, Then I find a comment explaining that numeric MOVEs are right-justified and left-truncated: `MOVE 1000005 TO PIC 9(6)` stores `000005` — the leading `1` disappears silently.
2. Given MERCHANT.cob, When I examine a group MOVE, Then I find a comment warning that group MOVEs are treated as alphanumeric regardless of subordinate item types, meaning decimal alignment is lost and numeric fields receive raw character data.
3. Given DEDUCTN.cob, When I examine a MOVE CORRESPONDING operation, Then I find a comment noting that MOVE CORRESPONDING matches fields by name — renaming a field in one group silently drops it from the operation with no compiler warning.

### US-14: REDEFINES Safety Annotations (Priority: P1)

As a **student**, I want to see comments documenting where REDEFINES creates type-unsafe unions so I can understand why accessing the wrong overlay causes S0C7 data exception abends.

**Acceptance Scenarios**:
1. Given MERCHREC.cpy, When I examine the REDEFINES for individual vs aggregate merchant data, Then I find a comment explaining that REDEFINES is COBOL's version of a C union with no discriminator enforcement — reading MERCH-AGGREGATE-DATA when the record is type 'I' (individual) performs arithmetic on character data, triggering S0C7.
2. Given DISPUTE.cob, When I examine the dispute record handling, Then I find a comment noting that all 01-levels under an FD implicitly redefine each other (the file buffer is a single storage area), and VALUE clauses on redefining items produce undefined behavior.
3. Given MERCHANT.cob, When I examine the 88-level type guards, Then I find a comment describing the correct pattern: use `88 IS-HEADER VALUE 'H'` conditions to guard REDEFINES access, and noting that this program omits the guard in at least one code path.

### US-15: EBCDIC Sort Order Dependencies (Priority: P2)

As a **student**, I want to see comments documenting where EBCDIC collating sequence assumptions create migration traps so I can understand why programs that work perfectly on IBM z/OS produce wrong results on ASCII platforms.

**Acceptance Scenarios**:
1. Given MERCHANT.cob, When I examine any SEARCH ALL (binary search) on a table, Then I find a comment warning that tables sorted in EBCDIC order (`'a' < 'A' < '1'`) produce wrong results on ASCII platforms (`'1' < 'A' < 'a'`) because the collating sequence is reversed, and that `PROGRAM COLLATING SEQUENCE` can override this but every missed instance is a subtle bug.
2. Given FEEENGN.cob, When I examine the SORT verb, Then I find a comment noting that key ordering changes between EBCDIC and ASCII platforms, and that AWS migration guidance warns even physical assets like barcode ordering may depend on EBCDIC sequences.
3. Given PAYCOM.cpy, When I examine the SPACES/LOW-VALUES usage, Then I find a comment explaining that SPACES is `X'40'` in EBCDIC but `X'20'` in ASCII, LOW-VALUES is `X'00'` in both, and that a field initialized to LOW-VALUES does NOT equal SPACES — moving LOW-VALUES to a numeric field then performing arithmetic triggers S0C7.

### US-16: Copybook Dependency Chain Awareness (Priority: P2)

As a **student**, I want to see comments documenting how a single copybook change can silently corrupt data across dozens of programs so I can understand why impact analysis is essential in legacy COBOL.

**Acceptance Scenarios**:
1. Given EMPREC.cpy, When I read the header comments, Then I find a note warning that this copybook is included in N programs (listing them), and that changing any field's PIC clause forces recompilation of all dependent programs — miss one and you get silent field misalignment, not obvious errors.
2. Given PAYCOM.cpy, When I read the header, Then I find a comment noting that nested COPY statements create invisible dependency chains, and that research on a worldwide car-leasing COBOL system found over 70% of business rules existed only in the code — not in any documentation.
3. Given any copybook, When I look at the change history comments, Then I find at least one note from a fictional developer about a time when a copybook field change broke a downstream program that was missed during recompilation.

### US-17: Y2K Windowing Expiration (Priority: P2)

As a **student**, I want to see comments documenting how Y2K date windowing code is creating a new time bomb so I can understand that the Y2K problem was not fully solved — it was deferred.

**Acceptance Scenarios**:
1. Given PAYBATCH.cob, When I examine the Y2K date windowing code, Then I find a comment explaining that the pivot year logic (`IF YY >= 60 THEN century = 19 ELSE century = 20`) means a 30-year mortgage calculated in 2020 crosses into 2050 — which the windowing logic interprets as 1950. "Practitioners report batch jobs already encountering ugly run-ins with century-crossed dates."
2. Given PAYROLL.cob, When I examine date fields, Then I find a comment referencing IBM's Millennium Language Extensions `YEARWINDOW` compiler option and warning that these windows are expiring — the COBOL equivalent of the Unix 2038 problem.

### US-18: CICS vs Batch Working-Storage Persistence (Priority: P3)

As a **student**, I want to see comments documenting how Working-Storage behaves differently in CICS versus batch so I can understand the most common source of intermittent bugs in online COBOL programs.

**Acceptance Scenarios**:
1. Given MERCHANT.cob, When I examine the WORKING-STORAGE section, Then I find a comment explaining that in batch COBOL, Working-Storage persists throughout program execution, but in CICS each task gets a fresh copy (compiled RENT) — flags, cursors, and accumulators reset between pseudo-conversational transactions unless state is passed through COMMAREA (max 32,763 bytes).
2. Given DISPUTE.cob, When I examine the state machine fields, Then I find a comment noting that early CICS ran all transactions in the same address space with the same memory protection key — a bug in one program could corrupt any running transaction or even CICS kernel control blocks, causing system-wide crashes.

### US-19: Numeric Storage Format Heritage (Priority: P1)

As a **student**, I want to see detailed comments comparing COBOL's three numeric storage formats (DISPLAY, COMP, COMP-3) with byte-level examples so I can understand why COMP-3 packed decimal is the standard for all financial calculations and why storage format choices have real performance and compatibility consequences.

**Acceptance Scenarios**:
1. Given EMPREC.cpy, When I examine the mixed COMP types, Then I find a comment block comparing all three formats with byte-level examples: DISPLAY stores one character per digit (`+123` in `PIC S9(3)` stores as hex `F1 F2 C3`, and `-123` becomes `F1 F2 D3` which displays as the characters `12L` — bewildering to developers expecting a minus sign); COMP binary packs into 2/4/8 bytes based on PIC digits (`S9(1)`-`S9(4)` → 2 bytes, `S9(5)`-`S9(9)` → 4 bytes, `S9(10)`-`S9(18)` → 8 bytes); COMP-3 packed decimal stores two digits per byte with sign nibble (`PIC S9(5) COMP-3` = 3 bytes as `12 34 5C`).
2. Given PAYCOM.cpy, When I examine the financial amount fields, Then I find a comment explaining why COMP-3 is the standard: IBM z-series hardware has native BCD instructions making packed decimal ~7-10x faster than binary for decimal arithmetic, and COMP-3 avoids all IEEE 754 representation errors (the classic `0.1 + 0.2 = 0.30000000000000004` never happens in COMP-3).
3. Given TAXREC.cpy, When I examine the bracket table fields, Then I find comments noting the banking standard PICs: `PIC S9(13)V99 COMP-3` for monetary amounts (8 bytes, up to ±999 trillion with exact 2-decimal precision), `PIC 9(3)V9(6) COMP-3` for interest rates (six decimal places, e.g., `005.250000` = 5.25%), and `PIC S9(15)V9(6) COMP-3` for intermediate calculations to avoid premature truncation.

### US-20: JCL, Dataset Mapping, and Batch Heritage (Priority: P2)

As a **student**, I want to see comments documenting the JCL and dataset infrastructure that COBOL programs run on so I can understand the layer between programs and data that shapes every mainframe COBOL design.

**Acceptance Scenarios**:
1. Given PAYBATCH.cob, When I examine the SELECT/ASSIGN statements, Then I find a comment explaining that on z/OS, JCL DD statements map these logical names to physical datasets, with the DISP parameter controlling access mode: `OLD` = exclusive lock, `SHR` = shared read, `MOD` = append. The pattern `DISP=(NEW,CATLG,DELETE)` creates a dataset, catalogs it on success, and deletes it on failure.
2. Given PAYBATCH.cob, When I examine the batch output section, Then I find a comment about Generation Data Groups (GDGs): `MY.GDG(0)` is current generation, `(+1)` creates the next, `(-1)` references previous — crucial for daily batch cycles producing new output each run. "Our PAYBATCH.cob would use GDGs on a real mainframe to keep yesterday's run available for comparison."
3. Given PAYROLL.cob, When I examine the file handling, Then I find a comment about the compile-link-go sequence: JCL invokes IGYCRCTL (COBOL compiler) → IEWBLINK (linkage editor) → executes result, with `COND=(8,LT)` skipping steps if any previous return code exceeds 8.

### US-21: FILE STATUS Codes and I/O Error Awareness (Priority: P2)

As a **student**, I want to see FILE STATUS code comments in file-handling programs so I can learn the two codes every banking COBOL programmer memorizes and understand why unchecked I/O is dangerous.

**Acceptance Scenarios**:
1. Given any program with FILE STATUS, When I examine the file operations, Then I find comments listing the critical codes: `23` = record not found (the first code you memorize), `22` = duplicate key on write (the second), `35` = file not found at OPEN (typically a missing DD in JCL), `00` = success, and `10` = end of file. "These five codes account for 95% of production file I/O issues."
2. Given MERCHANT.cob or FEEENGN.cob, When I examine file OPEN/READ/WRITE sequences, Then I find a comment warning that unchecked FILE STATUS after each I/O verb means errors propagate silently — a failed READ returns stale data from the previous successful read, and subsequent logic processes garbage.

### US-22: Banking Arithmetic Patterns (Priority: P1)

As a **student**, I want to see comments documenting how banking COBOL handles money, interest, and multi-currency so I can understand the specific arithmetic patterns that make COBOL indispensable for financial calculations.

**Acceptance Scenarios**:
1. Given TAXCALC.cob, When I examine the interest/tax calculation, Then I find a comment explaining day-count conventions used in banking: **30/360** (corporate bonds, mortgages — assumes 30-day months), **Actual/360** (money markets, SOFR — uses actual days over 360-day year, effectively charging ~5 extra days of interest annually), **Actual/365** (UK conventions), and **Actual/Actual** (US Treasuries — varies denominator by leap year). All arithmetic stays in integer day counts and COMP-3 — no floating point anywhere.
2. Given FEEENGN.cob, When I examine the fee amount fields, Then I find a comment about multi-currency handling: real banking pairs every amount with its ISO 4217 currency code (`PIC X(3)`) and a decimal-places indicator (`PIC 9(1)`) — critical because JPY uses 0 decimal places while BHD (Bahraini dinar) uses 3.
3. Given PAYROLL.cob, When I examine rounding behavior, Then I find a comment explaining that COBOL's `ROUNDED` phrase defaults to round-half-up, but banking requires **banker's rounding** (round-half-to-even) which must be coded explicitly — using ROUNDED alone is not sufficient for financial compliance.
4. Given any program, When I examine account ID fields, Then I find a comment noting that account numbers use `PIC X(16)` not `PIC 9(16)` to preserve leading zeros — a numeric PIC would strip them.

### US-23: DB2 and Embedded SQL Heritage (Priority: P3)

As a **student**, I want to see comments and dead WS fields documenting embedded SQL patterns so I can understand how mainframe COBOL programs interact with DB2 databases.

**Acceptance Scenarios**:
1. Given DISPUTE.cob, When I examine dead WORKING-STORAGE fields, Then I find WS-SQLCODE (PIC S9(9) COMP) and WS-SQLCA group with a comment: "Original DB2 version used EXEC SQL...END-EXEC with host variables (prefixed with : in SQL). SQLCA provides SQLCODE after every operation: 0=success, +100=not found, -803=duplicate key, -811=multiple rows. Replaced with file I/O in the GnuCOBOL port."
2. Given MERCHANT.cob, When I examine dead WS fields, Then I find WS-DCLGEN-TIMESTAMP with a comment: "DCLGEN generates COBOL copybooks from DB2 table definitions. Indicator variables (PIC S9(4) COMP) signal NULLs when set to -1. In CICS, use EXEC CICS SYNCPOINT for commits — never EXEC SQL COMMIT directly."

### US-24: Level Number Semantics (Priority: P3)

As a **student**, I want to see comments about COBOL's level number system — especially level 88's power and levels 77/66's obsolescence — so I can understand the full data description hierarchy.

**Acceptance Scenarios**:
1. Given RISKCHK.cob, When I examine the 88-level conditions, Then I find a comment calling level 88 "COBOL's most underappreciated feature": it allocates no storage, supports multiple values (`VALUE 'A' 'B' 'C'`), ranges (`VALUE 60 THRU 100`), centralizes validation logic, and enables `SET ACTIVE TO TRUE` instead of `MOVE 'A' TO WS-STATUS`.
2. Given PAYROLL.cob, When I examine any level 77 items, Then I find a comment noting that level 77 is functionally identical to a 01 item and has been designated for deletion from the COBOL standard — modern code should use 01 exclusively.
3. Given any program with REDEFINES, When I look for level 66, Then I find a comment mentioning that level 66 RENAMES creates alternative groupings spanning contiguous items but is rarely used in modern code.

### US-25: Dialect and Migration Awareness (Priority: P3)

As a **student**, I want to see comments about what breaks when COBOL programs migrate between compilers so I can understand why GnuCOBOL compatibility is both surprisingly good and critically limited.

**Acceptance Scenarios**:
1. Given any program header, When I read the compilation notes, Then I find a comment noting that GnuCOBOL passes 9,700+ of 9,748 NIST COBOL-85 test suite tests and translates COBOL → C → native binary via GCC.
2. Given MERCHANT.cob (which has EXEC CICS heritage comments), When I examine the CICS-related comments, Then I find a note that EXEC CICS statements are the primary migration blocker — they require replacing the entire CICS middleware layer with SCREEN SECTION I/O and native file operations. Also: EBCDIC→ASCII conversion corrupts signed DISPLAY fields (overpunch encoding differs), hex literals in VALUE clauses change meaning (`X'C1'` = 'A' in EBCDIC but a different character in ASCII), and `INSPECT CONVERTING` with literal character strings produces wrong results.
3. Given PAYBATCH.cob, When I read the JCL heritage comments, Then I find a note that JCL infrastructure must be replaced with shell scripts during migration, and assembler subroutines must be rewritten in C.

### US-26: EOD Batch Processing Heritage (Priority: P2)

As a **student**, I want to see comments documenting the end-of-day batch sequence so I can understand the strict dependency chain that governs how banking systems process a day's work overnight.

**Acceptance Scenarios**:
1. Given PAYBATCH.cob, When I examine the batch processing section, Then I find a comment documenting the real EOD batch sequence: (1) quiesce online systems, (2) post pending transactions, (3) accrue daily interest, (4) assess periodic fees, (5) age loans (current→30→60→90→charge-off), (6) revalue FX positions, (7) generate regulatory reports (CTR/SAR/OFAC), (8) post to General Ledger, (9) roll system date. "Each step's JCL gates on prior return codes. If interest accrual abends, downstream steps must not execute."
2. Given RISKCHK.cob, When I examine the risk scoring section, Then I find a comment referencing regulatory batch programs: CTR (Currency Transaction Reports) trigger for any customer with same-day cash exceeding $10,000; SAR (Suspicious Activity Reports) detect structuring patterns (multiple sub-$10K transactions), velocity anomalies, and round-amount clustering; OFAC screening compares against the SDN list with fuzzy matching.

### US-27: Analyzer Compatibility (Priority: P1)

As an **analyzer**, I want all enrichment additions to be parseable by the existing Python analysis tools so that call graph, dead code detection, and complexity scoring continue to work correctly.

**Acceptance Scenarios**:
1. Given any enriched program, When I run call_graph, Then the paragraph dependency map is identical to pre-enrichment (same nodes, same edges).
2. Given any enriched program with new dead paragraphs, When I run dead_code, Then new paragraphs appear in the dead code list.
3. Given any enriched copybook, When the Python parser processes it, Then no parse errors occur and field extraction produces identical results.

### US-28: Documentation Updates (Priority: P1)

As an **instructor**, I want KNOWN_ISSUES.md and README.md updated to reflect new enrichments so that the documentation remains the authoritative answer key.

**Acceptance Scenarios**:
1. Given KNOWN_ISSUES.md, When I search for each new enrichment category, Then I find new issue entries in the standard format (What, Era, Why It Exists, Risk, Modern Equivalent).
2. Given README.md, When I review the program table, Then the "Key Anti-Patterns" column references the new enrichment categories.
3. Given the Summary table in KNOWN_ISSUES.md, When I check counts, Then they accurately reflect the additional anti-patterns.

---

## Functional Requirements

### Comments and Developer Notes

- **FR-001**: Add 2-3 period bug scenario comments to PAYROLL.cob, TAXCALC.cob, and DEDUCTN.cob. Each must reference a concrete line range and describe the exact failure mode if the period were missing or misplaced. At least one must reference the Nordea 16-hour outage from `COBOL_PRACTITIONER_INSIGHTS.md`.

- **FR-002**: Add batch ordering assumption comments to PAYBATCH.cob, FEEENGN.cob, and RISKCHK.cob. Each must identify a specific pre-sort requirement and describe the silent failure that occurs if the requirement is violated.

- **FR-003**: Add numeric overflow edge case comments to PAYROLL.cob (WS-BATCH-GROSS), FEEENGN.cob (FEE-CALC-TOTAL), and RISKCHK.cob (WS-RISK-SCORE). Each must include the arithmetic showing the overflow threshold.

- **FR-004**: Add COMP-3/EBCDIC heritage comments to EMPREC.cpy, PAYCOM.cpy, and TAXREC.cpy. Include: (a) COMP-3 byte layout showing `PIC S9(5) COMP-3` stored as 3 bytes `12 34 5C` with sign nibble C=positive, D=negative, F=unsigned; (b) overpunch sign encoding table — EBCDIC positive 0-9 maps to `{`, `A`-`I` (zone `C`), negatives to `}`, `J`-`R` (zone `D`); ASCII Micro Focus uses `0x70` zone (`p`-`y` for negatives) — a simple character translation between EBCDIC/ASCII will corrupt signed numeric fields; (c) COMP-3 is byte-identical between IBM and GnuCOBOL (the critical win for financial data interchange), but COMP-1/COMP-2 floating-point is completely incompatible (hex float vs IEEE 754); (d) the TRUNC compiler option: `TRUNC(STD)` truncates COMP fields to PIC-specified digits, `TRUNC(BIN)` uses full binary range — a halfword can hold 65,535 unsigned, not just 9,999.

- **FR-005**: Add field reuse ambiguity comments to MERCHANT.cob (WK-M4 triple-use), PAYROLL.cob (WK-GROSS path dependency), and RISKCHK.cob (WS-RISK-SCORE double-accumulation). Each must list all usage contexts and explain the implicit coupling.

- **FR-006**: Add abend/recovery notes to DISPUTE.cob (ALTER mid-transition), FEEENGN.cob (SORT failure), and PAYROLL.cob (ALTER debugging). Include fictional cost/time-to-recover in developer voice. Reference real mainframe ABEND codes: S0C7 (data exception — invalid packed decimal, the most common COBOL abend), S0C4 (protection exception — bad pointer or subscript overflow), S322 (time exceeded — infinite loop), S806 (module not found). Include the McCracken quote on ALTER in PAYROLL.cob: *"the sight of a GO TO statement in a paragraph by itself...strikes fear in the heart of the bravest programmer"* (Daniel McCracken, 1976).

- **FR-007**: Add implicit array bounds comments to FEEREC.cpy (OCCURS 4), MERCHREC.cpy (REDEFINES boundary), and at least one source program. Each must explain what happens at boundary + 1 on both GnuCOBOL and IBM mainframe.

- **FR-008**: Add midnight/timezone hazard comments to RISKCHK.cob (velocity reset), PAYBATCH.cob (cross-midnight batch), and PAYROLL.cob (pay period vs run date).

- **FR-009**: Add 3270 terminal artifact comments to MERCHANT.cob (ACCEPT/BMS map heritage) and PAYROLL.cob (80-column DISPLAY line).

- **FR-010**: Add input validation apathy comments to PAYROLL.cob (negative salary), RISKCHK.cob (negative/zero amount), and DISPUTE.cob (amount vs original transaction).

- **FR-011**: Add deliberate workaround comments with dated TODOs to PAYBATCH.cob ("remove after Y2K"), FEEENGN.cob ("temporary for Q2 1989"), and DEDUCTN.cob ("delete in next release").

### WORKING-STORAGE Additions (Dead Fields)

- **FR-012**: Add 2-3 unreferenced WORKING-STORAGE fields to each of the 8 source programs. Fields must be contextually appropriate dead variables (e.g., WS-CICS-COMMAREA in MERCHANT, WS-GDG-GENERATION in PAYBATCH, WS-DB2-SQLCODE in DISPUTE). None may be referenced by any executable statement.

- **FR-013**: Add at least one 88-level condition that contradicts an existing 88-level in the same program (e.g., a new "high risk" definition with different thresholds in RISKCHK.cob). Document the contradiction in a comment.

### Dead Code Paragraphs

- **FR-014**: Add 1-2 dead paragraphs (never PERFORMed or GO TO'd) to programs that currently have fewer than 2 dead paragraphs. Each must have a plausible fictional backstory in comments. Follow existing per-program naming conventions (P-### for PAYROLL, MR-### for MERCHANT, etc.).

### Copybook Enrichments

- **FR-015**: Add byte-order and mainframe memory alignment comments to EMPREC.cpy, MERCHREC.cpy, and DISPREC.cpy. Include halfword/fullword/doubleword boundary notes where COMP fields appear.

- **FR-016**: Add at least one contradicting comment per copybook where a comment describes a different value or purpose than the actual field definition. Document the contradiction with developer attribution and date.

### Documentation Updates

- **FR-017**: Update KNOWN_ISSUES.md with new issue entries for each enrichment category. Follow existing format (issue code, What, Era, Why It Exists, Risk, Modern Equivalent). Use existing prefixes with higher numbers (PY-06, TX-07, etc.).

- **FR-018**: Update README.md program table to reference new enrichment categories in the "Key Anti-Patterns" column.

- **FR-019**: Update the Summary anti-pattern frequency table in KNOWN_ISSUES.md with accurate counts reflecting all additions.

### Implied Decimal and MOVE Traps (from `COBOL_MAINFRAME_QUIRKS.md`)

- **FR-020**: Add implied decimal trap comments to TAXCALC.cob (V occupies zero bytes, truncation not rounding), PAYROLL.cob (multiplication overflow from insufficient receiving field), and FEEENGN.cob (missing ROUNDED/ON SIZE ERROR). Each must show the specific PIC clauses involved and the exact data loss scenario.

- **FR-021**: Add MOVE truncation hazard comments to PAYROLL.cob (numeric left-truncation: `MOVE 1000005 TO PIC 9(6)` stores `000005`), MERCHANT.cob (group MOVE loses decimal alignment), and DEDUCTN.cob (MOVE CORRESPONDING silent field drops on rename). Each must contrast alphanumeric (left-justified, right-truncated) vs numeric (right-justified, left-truncated) behavior.

### REDEFINES and Type Safety

- **FR-022**: Add REDEFINES safety comments to MERCHREC.cpy (S0C7 from arithmetic on character data through wrong overlay), DISPUTE.cob (FD implicit REDEFINES — all 01-levels share one buffer), and MERCHANT.cob (missing 88-level type guard in at least one code path). Each must explain that REDEFINES is a union with no discriminator enforcement.

### EBCDIC and Platform Dependencies

- **FR-023**: Add EBCDIC sort order dependency comments to MERCHANT.cob (SEARCH ALL binary search on EBCDIC-sorted table), FEEENGN.cob (SORT key ordering changes across platforms), and RISKCHK.cob (literal comparison assumptions). Include the reversal: EBCDIC `'a' < 'A' < '1'` vs ASCII `'1' < 'A' < 'a'`.

### Copybook Dependency Chains

- **FR-024**: Add dependency chain comments to the header of every copybook (7 total). Each must list which programs include it and warn that field changes require recompilation of all dependents — miss one and you get silent field misalignment, not obvious errors. At least one must reference the statistic: "over 70% of business rules existed only in the code — not in any documentation."

### Y2K Windowing and Date Hazards

- **FR-025**: Add Y2K windowing expiration comments to PAYBATCH.cob (pivot year of 40 means 2050 is interpreted as 1950; 30-year mortgages from 2020 are already crossing this boundary) and PAYROLL.cob (reference IBM's `YEARWINDOW` compiler option). These go beyond the existing Y2K dead code (FR-011) — they document an active, re-emerging bug class.

### CICS vs Batch Persistence

- **FR-026**: Add CICS vs batch Working-Storage persistence comments to MERCHANT.cob (WS fresh copy per CICS task, state must go through COMMAREA max 32,763 bytes, Channels and Containers for CICS TS 3.1+) and DISPUTE.cob (early CICS same-address-space memory corruption risk). These explain why flags and accumulators behave differently in online vs batch execution.

### PERFORM THRU Armed Mines

- **FR-027**: Enrich existing PERFORM THRU comments in TAXCALC.cob and PAYROLL.cob with the "armed mine" pattern: a GO TO that jumps out of a PERFORM THRU range leaves a return address on COBOL's internal control stack. When execution later reaches the exit paragraph through a different path, the mine detonates with an unexpected jump back to the original caller — behavior invisible in the source code.

### Numeric Storage Formats

- **FR-028**: Add a three-format comparison comment block to EMPREC.cpy showing byte-level storage for the same value across DISPLAY, COMP, and COMP-3. Must include: DISPLAY `+123` in `PIC S9(3)` as hex `F1 F2 C3` and `-123` as `F1 F2 D3` displaying as `"12L"`; COMP binary size breakpoints (`S9(1)`-`S9(4)` → 2 bytes, `S9(5)`-`S9(9)` → 4 bytes, `S9(10)`-`S9(18)` → 8 bytes); COMP-3 `PIC S9(5) COMP-3` as 3 bytes `12 34 5C`.

- **FR-029**: Add banking-standard PIC comments to PAYCOM.cpy and TAXREC.cpy: `PIC S9(13)V99 COMP-3` for monetary amounts (8 bytes, up to ±$999 trillion), `PIC 9(3)V9(6) COMP-3` for interest rates (six decimal places), `PIC S9(15)V9(6) COMP-3` for intermediate calculations, and `PIC X(3)` for ISO 4217 currency codes paired with `PIC 9(1)` for decimal-places (JPY=0, BHD=3).

### JCL, Dataset, and Batch Heritage

- **FR-030**: Add JCL heritage comments to PAYBATCH.cob: SELECT/ASSIGN → DD mapping, DISP parameter (`OLD`=exclusive, `SHR`=shared, `MOD`=append), `DISP=(NEW,CATLG,DELETE)` pattern, GDG versioning (`(0)` current, `(+1)` next, `(-1)` previous), and compile-link-go sequence (IGYCRCTL → IEWBLINK → execute with `COND=(8,LT)`).

- **FR-031**: Add EOD batch sequence comments to PAYBATCH.cob documenting the 9-step nightly cycle: quiesce → post → accrue interest → assess fees → age loans → FX reval → regulatory reports → GL posting → date roll. Reference job schedulers (CA-7, TWS/OPC, Control-M) and step-level dependency gating.

### FILE STATUS and I/O Errors

- **FR-032**: Add FILE STATUS code reference comments to at least 3 programs that handle files: codes `00` (success), `10` (end of file), `22` (duplicate key), `23` (record not found — "the first code every banking COBOL programmer memorizes"), `35` (file not found at OPEN — typically missing DD in JCL). Warn that unchecked FILE STATUS after each I/O verb means errors propagate silently.

### Banking Arithmetic

- **FR-033**: Add banking arithmetic comments to TAXCALC.cob (day-count conventions: 30/360, Actual/360, Actual/365, Actual/Actual with `INTEGER-OF-DATE` intrinsic), FEEENGN.cob (multi-currency ISO 4217 + decimal-places indicator), and PAYROLL.cob (banker's rounding round-half-to-even must be coded explicitly since COBOL defaults to round-half-up). Also add to any program handling account IDs: account numbers use `PIC X(16)` not `PIC 9(16)` to preserve leading zeros.

### DB2/SQL Heritage

- **FR-034**: Add dead WS fields and comments for DB2 heritage to DISPUTE.cob (WS-SQLCODE `PIC S9(9) COMP`, WS-SQLCA group) and MERCHANT.cob (WS-DCLGEN-TIMESTAMP). Comments must explain: EXEC SQL...END-EXEC delimiters, DCLGEN copybook generation from DB2 tables, host variables with `:` prefix, indicator variables (`PIC S9(4) COMP`) for NULLs, SQLCA codes (0=success, +100=not found, -803=duplicate, -811=multiple rows), and CICS SYNCPOINT for commits.

### Level Number Semantics

- **FR-035**: Add level number comments to at least 3 programs: (a) Level 88 as "most underappreciated feature" — SET TO TRUE, multiple values (`VALUE 'A' 'B' 'C'`), ranges (`VALUE 60 THRU 100`), centralizes validation in a single declaration (in RISKCHK.cob near existing 88-levels); (b) Level 77 designated for deletion from the standard — modern code should use 01 (in PAYROLL.cob if any level 77 items exist); (c) Level 66 RENAMES creates alternative groupings but is rarely used (as a brief mention).

### Dialect and Migration Awareness

- **FR-036**: Add dialect/migration awareness comments to program headers: (a) GnuCOBOL passes 9,700+ of 9,748 NIST COBOL-85 tests (in PAYROLL.cob or PAYBATCH.cob header); (b) EXEC CICS as primary migration blocker, EBCDIC→ASCII corrupts signed DISPLAY, hex literals change meaning, INSPECT CONVERTING breaks (in MERCHANT.cob); (c) JCL→shell scripts and assembler→C rewrites required (in PAYBATCH.cob).

### Regulatory Compliance Patterns

- **FR-037**: Add regulatory compliance comments to RISKCHK.cob: CTR (Currency Transaction Reports) trigger at $10,000 aggregate same-day cash per customer, SAR (Suspicious Activity Reports) detect structuring (multiple sub-$10K), velocity anomalies, and round-amount clustering, OFAC screening against SDN list with exact and fuzzy matching. Reference SWIFT message formats (MT103 customer transfers, MT202 interbank, MT940 statements) and the ISO 20022 transition (MT103→pacs.008, MT940→camt.053, mandatory for cross-border payments Nov 2025).

---

## Success Criteria

- **SC-001**: All 807 existing tests pass with zero modifications. Verification: `python -m pytest python/tests/ -v --ignore=python/tests/test_e2e_playwright.py` returns 807 passed, 0 failed.
- **SC-002**: Every enrichment category (25 categories: period bugs, batch ordering, numeric overflow, COMP-3/EBCDIC heritage, field reuse, abend/recovery, array bounds, midnight hazards, 3270 artifacts, validation apathy, deliberate workarounds, implied decimal traps, MOVE truncation, REDEFINES safety, EBCDIC sort order, copybook dependencies, Y2K windowing expiration, CICS vs batch WS persistence, numeric storage formats, JCL/dataset/batch heritage, FILE STATUS codes, banking arithmetic, DB2/SQL heritage, level number semantics, dialect/migration awareness) is represented by at least 2 instances across the 8 programs and 7 copybooks.
- **SC-003**: The Python COBOL analyzer produces identical results for all pre-existing paragraphs. New dead paragraphs appear in dead_code output only.
- **SC-004**: Each enriched COBOL source file compiles without warnings using the project's standard compile flags.
- **SC-005**: KNOWN_ISSUES.md issue count increases by at least 35 new entries.
- **SC-006**: No executable COBOL statement is added, modified, or deleted in any existing paragraph.
- **SC-007**: At least 5 enrichments reference real practitioner stories and technical details from both research documents (`COBOL_PRACTITIONER_INSIGHTS.md` and `COBOL_MAINFRAME_QUIRKS.md`) — including the Nordea outage, McCracken ALTER quote, S0C7 data exception, overpunch encoding, TRUNC compiler option, COMP-3 cross-compiler compatibility, TSB Bank migration failure, and Y2K windowing expiration.
- **SC-008**: Each of the 8 source programs receives between 30-60 new comment lines and 4-8 new WORKING-STORAGE fields, keeping enrichment density consistent across programs.

---

## Edge Cases & Out-of-Scope

### Edge Cases

- **EC-001**: New WORKING-STORAGE fields must not collide with existing field names across all 7 copybooks. Verify uniqueness before adding.
- **EC-002**: New dead paragraphs must use names that do not match any existing PERFORM, GO TO, or ALTER target.
- **EC-003**: Inline comments using `*>` must not accidentally terminate a COBOL sentence if misformatted. All enrichment comments should use column-7 `*` or free-format `*>` comment syntax consistently with each file's existing style.
- **EC-004**: WORKING-STORAGE additions must be placed after COPY inclusions to avoid changing copybook byte offsets.

### Out-of-Scope

- No executable logic changes of any kind
- No new COBOL programs (only modify existing 8 + 7 copybooks)
- No modifications to Python analysis tools or test files
- No changes to the web console or API
- No new data files or modifications to EMPLOYEES.DAT
- No changes to build.sh or Makefile compile commands
- No refactoring of existing anti-patterns (they are intentional)
- No addition of COBOL-2002 or COBOL-2014 features (maintain COBOL-74/85 style)

---

## [NEEDS CLARIFICATION]

- **NC-001**: Enrichment density per program — should programs with more existing enrichment (e.g., PAYROLL.cob already has extensive headers) receive fewer additions to maintain balance, or should all 8 programs receive equal enrichment regardless of current density?
