# Teaching Guide

An instructor's manual for teaching COBOL to software engineers using this codebase. 8 lessons, beginner to advanced, each building on the previous.

---

## Course Overview

**Audience**: Software engineers with experience in any modern language (Python, Java, C, JavaScript) who want to understand COBOL.

**Duration**: 10 lessons, approximately 1-2 hours each.

**Prerequisites**: Ability to read code in any language. No COBOL experience needed.

**Setup**: Clone this repository. Optionally install GnuCOBOL (`sudo apt install gnucobol` or `brew install gnucobol`). Python 3.8+ required for Lessons 7-8.

---

## Lesson 1: COBOL Program Structure

**Objective**: Understand the four-division structure that every COBOL program follows.

**Files to read**:
- `COBOL-BANKING/src/SMOKETEST.cob` — The simplest program in the system (96 lines)

**Key concepts**:
- The four divisions: IDENTIFICATION, ENVIRONMENT, DATA, PROCEDURE
- Why COBOL separates "what data exists" from "what the program does"
- `PROGRAM-ID` as the entry point declaration
- `STOP RUN` as program termination
- How COBOL's structure differs from C/Python (no main function, no inline declarations)

**Discussion points**:
- Why would the language designers separate data declarations from logic? (Answer: batch processing on punch cards — data layouts were shared across programs via copybooks)
- How does this compare to a Java class with fields and methods? (Similar separation, but COBOL makes it mandatory and structural)

**Exercise**:
1. Read SMOKETEST.cob from top to bottom. Identify each division and what it contains.
2. Find where the program starts executing (PROCEDURE DIVISION / MAIN-PROGRAM).
3. Trace the execution flow: MAIN-PROGRAM → WRITE-TEST-RECORD → READ-TEST-RECORD → CLEANUP.

---

## Lesson 2: Data Definition and PIC Clauses

**Objective**: Understand how COBOL defines data — PIC clauses, level numbers, record layouts, and copybooks.

**Files to read**:
- `COBOL-BANKING/copybooks/ACCTREC.cpy` — Account record (70 bytes, annotated)
- `COBOL-BANKING/copybooks/TRANSREC.cpy` — Transaction record (103 bytes)
- `COBOL-BANKING/copybooks/COMCODE.cpy` — Shared constants

**Key concepts**:
- PIC X(n) — alphanumeric (like `char[n]`)
- PIC 9(n) — unsigned numeric (like `unsigned int`)
- PIC S9(n)V99 — signed numeric with implied decimal (the `V` is not stored)
- Level numbers: 01 (record), 05 (field), 10 (sub-field), 88 (condition name)
- 88-level condition names — named boolean tests on the parent field
- COPY statement — how copybooks are included (like C `#include`)

**Discussion points**:
- Why fixed-width records? (Answer: COBOL predates variable-length formats, CSV, JSON. Fixed-width is fast — you can seek to any record by byte offset.)
- Why implied decimals? (Answer: floating-point didn't exist on early mainframes. COBOL stores $5,000.00 as the integer 500000, with the compiler knowing where the decimal goes. No rounding errors.)
- Why 88-level conditions? (Answer: self-documenting code. `IF ACCT-FROZEN` reads like English, which was COBOL's design goal.)

**Exercise**:
1. Calculate the total byte width of ACCTREC.cpy by adding up all PIC widths. (Answer: 10+30+1+12+1+8+8 = 70)
2. What value does ACCT-BALANCE store for $5,000.00? (Answer: `000000500000` — 10 digits + 2 implied decimal)
3. Write down all 88-level conditions in ACCTREC.cpy and what values trigger them.

---

## Lesson 3: File I/O

**Objective**: Understand how COBOL reads and writes sequential files — the SELECT/ASSIGN/FD pipeline.

**Files to read**:
- `COBOL-BANKING/src/ACCOUNTS.cob` — Full account CRUD with file I/O
- `COBOL-BANKING/copybooks/ACCTIO.cpy` — Shared I/O working-storage

**Key concepts**:
- SELECT ... ASSIGN TO — maps logical file to physical file
- FILE STATUS — error detection on every I/O operation
- FD (File Description) — links file to record layout
- OPEN INPUT / OPEN OUTPUT / OPEN EXTEND — read / write (truncate) / append
- READ ... AT END — sequential read with end-of-file handling
- WRITE — writes current record buffer to file
- LINE SEQUENTIAL — records separated by newlines
- The "load everything into memory, modify, write everything back" pattern

**Discussion points**:
- Why does ACCOUNTS.cob load ALL records into memory just to update one? (Answer: sequential files have no random access. You can't update byte 350 without rewriting the whole file. This is why mainframes use VSAM/ISAM indexed files in production.)
- What happens if the program crashes between OPEN OUTPUT and CLOSE? (Answer: data loss — the file is truncated on OPEN OUTPUT. This is documented in KNOWN_ISSUES.md.)

**Exercise**:
1. Trace the LIST-ACCOUNTS paragraph. What happens on each READ iteration?
2. Trace CREATE-ACCOUNT. Why does it call LOAD-ALL-ACCOUNTS first?
3. Find the OCCURS 100 TIMES in ACCTIO.cpy. What happens if a bank has 101 accounts? (Answer: silent data loss — see KNOWN_ISSUES.md item A1)

---

## Lesson 4: Business Logic and Validation

**Objective**: Understand COBOL's control flow — EVALUATE, nested IF, guard clauses, and the validation pipeline pattern.

**Files to read**:
- `COBOL-BANKING/src/VALIDATE.cob` — Pure validation, no side effects
- `COBOL-BANKING/src/TRANSACT.cob` — Full transaction processing (focus on PROCESS-DEPOSIT and PROCESS-WITHDRAW)

**Key concepts**:
- EVALUATE (switch/case) — `EVALUATE X WHEN 'A' ... WHEN OTHER ...`
- Validation pipeline — sequential checks with EXIT PARAGRAPH (early return)
- ACCEPT FROM COMMAND-LINE — reading CLI arguments
- UNSTRING — parsing command-line arguments (like `split()`)
- FUNCTION NUMVAL — string to number conversion
- Guard clause pattern — reject early, process at the end

**Discussion points**:
- Compare VALIDATE.cob's structure to a modern validation function. How similar is the guard-clause pattern?
- Why does TRANSACT.cob check for frozen accounts BEFORE checking the balance? (Answer: fail fast — a frozen account can't transact regardless of balance)
- Why is VALIDATE.cob a separate program from TRANSACT.cob? (Answer: separation of concerns — the Python bridge can call VALIDATE before TRANSACT to pre-check)

**Exercise**:
1. Read VALIDATE.cob end to end. List the four checks in order.
2. In TRANSACT.cob, trace PROCESS-WITHDRAW. What status code is returned for each failure case?
3. Find the UNSTRING in TRANSACT.cob's MAIN-PROGRAM. What happens if the user passes fewer arguments than expected? (Answer: remaining fields keep their initial VALUE SPACES)

---

## Lesson 5: Transaction Processing and Batch Operations

**Objective**: Understand batch processing — the core pattern of enterprise COBOL.

**Files to read**:
- `COBOL-BANKING/src/TRANSACT.cob` — Focus on PROCESS-BATCH, PARSE-BATCH-LINE, PROCESS-ONE-TRANSACTION

**Key concepts**:
- Pipe-delimited batch input files (`BATCH-INPUT.DAT`)
- Batch processing loop: read → parse → validate → execute → log → repeat
- Transaction ID generation (sequential, per-node)
- STRING verb for output formatting
- Compliance detection (CTR threshold)
- Batch summary reporting (totals, success/fail counts)

**Discussion points**:
- Why pipe-delimited for batch input but fixed-width for ACCOUNTS.DAT? (Answer: batch input is human-created, needs to be readable/editable. Master files are machine-managed, optimized for COBOL I/O.)
- The batch processing pattern is the foundation of mainframe computing. How does it compare to modern ETL pipelines?
- Why does PROCESS-ONE-TRANSACTION validate the target account BEFORE debiting the source in transfers? (Answer: this was a bug fix — see KNOWN_ISSUES.md item T13)

**Exercise**:
1. Create a sample BATCH-INPUT.DAT file with 3 transactions (deposit, withdrawal, transfer).
2. Trace PROCESS-ONE-TRANSACTION for a transfer (type 'T'). Map each step.
3. Find the compliance note at line ~513. What amount triggers it?

---

## Lesson 6: Reports, Reconciliation, and Monthly Processing

**Objective**: Understand how COBOL programs produce reports and handle periodic operations.

**Files to read**:
- `COBOL-BANKING/src/REPORTS.cob` — Four report types
- `COBOL-BANKING/src/RECONCILE.cob` — Balance verification
- `COBOL-BANKING/src/INTEREST.cob` — COMPUTE and ROUNDED
- `COBOL-BANKING/src/FEES.cob` — Balance floor protection

**Key concepts**:
- Read-only file access (OPEN INPUT only) for reporting
- EVALUATE for multi-branch counting
- COMPUTE verb — algebraic expressions in COBOL
- ROUNDED modifier — banker's rounding for financial calculations
- Balance floor protection — skip fee if it would cause negative balance
- Implied opening balance calculation (current - net transactions)

**Discussion points**:
- Why is REPORTS.cob read-only? (Answer: separation of duties — reporting should never modify data. This is an audit principle.)
- Why does INTEREST.cob use COMPUTE instead of MULTIPLY? (Answer: COMPUTE allows complex expressions like `BALANCE * RATE / 12` in one statement. MULTIPLY would need intermediate variables.)
- Why is RECONCILE.cob's implied-opening-balance approach limited? (Answer: it can't detect tampering that occurred before the first transaction — see KNOWN_ISSUES.md item R1)

**Exercise**:
1. Trace PRINT-EOD in REPORTS.cob. What two files does it read?
2. Find the interest calculation in INTEREST.cob. What annual rate is used? How is it converted to monthly?
3. Find the balance floor check in FEES.cob. What happens when a fee would make the balance negative?

---

## Lesson 7: Inter-Program Communication and Simulation

**Objective**: Understand how COBOL programs communicate through files and how the simulation orchestrates multi-bank activity.

**Files to read**:
- `COBOL-BANKING/src/SIMULATE.cob` — Daily transaction generator
- `COBOL-BANKING/src/SETTLE.cob` — Clearing house settlement
- `COBOL-BANKING/copybooks/SIMREC.cpy` — Shared simulation parameters

**Key concepts**:
- OUTBOUND.DAT — inter-bank communication via file exchange
- Deterministic pseudo-random number generation (seed-based)
- REDEFINES — overlaying memory with different field layouts
- FUNCTION MOD — modular arithmetic for randomization
- Dynamic file path assignment (`ASSIGN TO WS-OB-FILE-PATH`)
- 3-leg settlement: debit source nostro → credit dest nostro → write records
- Nostro account concept

**Discussion points**:
- Why do banks communicate through files instead of direct calls? (Answer: this mirrors real mainframe batch processing. Banks exchange files overnight — SWIFT, ACH, and Fedwire all use file-based message formats.)
- Why is the random number generator deterministic? (Answer: reproducibility. Given the same seed and day number, the simulation produces identical transactions every time. This is critical for testing and debugging.)
- What happens if a nostro account has insufficient funds? (Answer: the settlement is rejected — see SETTLE.cob's NSF check)

**Exercise**:
1. Trace SIMULATE.cob's DO-OUTBOUND-TRANSFER. How is the destination bank chosen?
2. In SETTLE.cob, trace PROCESS-SETTLEMENT. Identify the 3 legs of settlement.
3. Why does SETTLE.cob use `ASSIGN TO WS-OB-FILE-PATH` (a variable) instead of a literal filename?

---

## Lesson 8: Modern Integration — Python Bridge and Integrity

**Objective**: Understand how modern languages wrap legacy COBOL without modifying it.

**Files to read**:
- `python/bridge.py` — COBOL subprocess wrapping + DAT file I/O
- `python/integrity.py` — SHA-256 hash chain
- `python/settlement.py` — Multi-node settlement coordinator
- `python/cross_verify.py` — Tamper detection

**Key concepts**:
- Mode A: calling COBOL as a subprocess, parsing pipe-delimited stdout
- Mode B: Python reads/writes the same fixed-width DAT files as COBOL
- SHA-256 hash chains — each entry depends on the previous (tamper = chain break)
- Balance reconciliation — comparing DAT file vs SQLite snapshots
- Cross-node settlement matching — verifying all 3 legs of a settlement exist
- The bridge pattern — observe without modifying

**Discussion points**:
- Why not just rewrite the COBOL in Python? (Answer: $3 trillion/day runs on COBOL. Rewrites are risky, expensive, and often fail. Wrapping preserves the known-working system while adding modern capabilities.)
- What does the integrity layer catch that COBOL alone can't? (Answer: direct file tampering. If someone edits ACCOUNTS.DAT with a hex editor, COBOL has no way to know. The hash chain and balance reconciliation detect this.)
- Why per-node databases instead of one shared database? (Answer: real banks are independent systems. No bank gives another bank direct database access. Settlement is how they reconcile.)

**Exercise**:
1. Run `./scripts/prove.sh` and observe each step.
2. Read `python/integrity.py`. Trace how a new chain entry's hash is computed from the previous entry.
3. Read `python/cross_verify.py`. How does it detect that a DAT file was tampered?
4. (Advanced) Manually tamper a balance in a DAT file using a text editor. Run verification. See it detected.

---

## Lesson 9: Legacy Code Archaeology — The Payroll Sidecar

**Objective**: Recognize and understand real-world COBOL anti-patterns — GO TO networks, ALTER, PERFORM THRU, nested IF without END-IF, dead code, and Y2K artifacts.

**Files to read**:
- `COBOL-BANKING/payroll/src/PAYROLL.cob` — GO TO network, ALTER, magic numbers (1974)
- `COBOL-BANKING/payroll/src/TAXCALC.cob` — 6-level nested IF, misleading comments (1983)
- `COBOL-BANKING/payroll/src/DEDUCTN.cob` — Structured/spaghetti hybrid, mixed COMP types (1991)
- `COBOL-BANKING/payroll/src/PAYBATCH.cob` — Y2K dead code, excessive tracing (2002)
- `COBOL-BANKING/payroll/KNOWN_ISSUES.md` — Anti-pattern catalog (answer key)

**Key concepts**:
- GO TO networks — interconnected paragraph jumps that bypass sequential flow
- ALTER — runtime modification of GO TO targets (the most dangerous COBOL construct)
- PERFORM THRU — paragraph range execution (silently includes new paragraphs)
- Nested IF without END-IF — period terminates ALL open IF scopes
- Dead code — unreachable paragraphs left in source for decades
- Misleading comments — comments that contradict the code (5% vs 7.25%)
- Y2K artifacts — parallel date fields never cleaned up

**Activities**:
1. Read PAYROLL.cob — diagram the P-000 → P-090 flow (follow GO TO, not line order)
2. Read TAXCALC.cob — find the misleading comment (says 5%, code does 7.25%)
3. Read DEDUCTN.cob — identify where structured code transitions to spaghetti (and why)
4. Read PAYBATCH.cob — find all dead Y2K code (Y2K-REVERSE-CONVERT)
5. Cross-reference every finding against KNOWN_ISSUES.md — did you find them all?

**Discussion points**:
- Why does real-world COBOL look like this? (Multiple developers, decades of patches, no refactoring culture)
- Why is dead code never removed? (Risk aversion, change management overhead, "if it ain't broke")
- How does the fictional developer history (JRK 1974, PMR 1983, SLW 1991, Y2K 2002) mirror real mainframe codebases?

**Key teaching point**: **The spaghetti is intentional and contained to the payroll sidecar. All other COBOL in this project follows clean, modern practices. Every anti-pattern is documented in KNOWN_ISSUES.md.**

---

## Lesson 10: Static Analysis — Tools That Understand Spaghetti

**Objective**: Use analysis tools to systematically understand legacy COBOL code that is too tangled to read manually.

**Files to use**:
- `python/cobol_analyzer/` — The 5 analysis modules
- `COBOL-BANKING/payroll/src/PAYROLL.cob` — Primary analysis target
- Web console → Analysis tab — Visual analysis interface

**Key concepts**:
- Call graph analysis — mapping paragraph dependencies by edge type
- Execution tracing — following GO TO/ALTER chains deterministically
- Dead code detection — classifying paragraphs as REACHABLE, DEAD, or ALTER_CONDITIONAL
- Complexity scoring — quantifying anti-pattern density per paragraph
- LLM-assisted analysis — tools provide structure, LLM provides interpretation

**Activities**:
1. Run `analyze_call_graph` on PAYROLL.cob — identify GOTO, ALTER, and FALL_THROUGH edges
2. Run `trace_execution` from P-000 — compare the tool's path to your manual diagram from Lesson 9
3. Run `detect_dead_code` — verify that P-085 is unreachable (cross-reference PY-05)
4. Run `complexity` scoring — identify the highest-scoring (hotspot) paragraphs
5. Run the compare view: PAYROLL.cob (spaghetti) vs TRANSACT.cob (clean) — quantify the difference
6. Open the web console Analysis tab — visualize the call graph as an SVG

**Discussion points**:
- How do these tools change the LLM's ability to explain code? (Structured context vs. raw source)
- What can static analysis detect that a human reviewer might miss? (Fall-through edges, ALTER targets)
- What are the limits of static analysis? (Cannot detect runtime data-dependent paths)

**Key teaching point**: **An LLM cannot reliably trace GO TO chains across 500 lines, but deterministic tools can — then the LLM interprets the structured results. This is the "tool-augmented LLM" pattern.**

---

## Assessment Ideas

### Practical
1. Add a new account type (e.g., 'M' for money market) to ACCTREC.cpy and update COMCODE.cpy
2. Add a new report type to REPORTS.cob (e.g., "HIGH-BALANCE" — accounts over $100K)
3. Write a Python test that verifies Mode B matches COBOL output
4. Analyze an unfamiliar COBOL program using the analysis tools and write a summary of its structure, hotspots, and dead code

### Written
1. Explain why COBOL uses implied decimals instead of floating-point
2. Describe the 3-leg settlement process and why it exists
3. Compare the "load all, modify, write all" file pattern to a modern database UPDATE
4. Explain what tamper detection catches and what it cannot catch
5. Explain why ALTER is more dangerous than GO TO (use the knowledge base entry)

### Discussion
1. "COBOL should be replaced with modern languages." Argue for and against.
2. If you had to add real-time transaction processing to this system, what would change?
3. How would you add encryption at rest without modifying the COBOL programs?
4. Compare the complexity scores of PAYROLL.cob vs TRANSACT.cob — what drives the difference?
