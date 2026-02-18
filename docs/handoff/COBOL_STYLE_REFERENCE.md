# Section 0: COBOL Style Reference

**Purpose:** This section gives Claude Code concrete patterns to follow when implementing the four COBOL programs. Every pattern used in ACCOUNTS.cob, TRANSACT.cob, VALIDATE.cob, and REPORTS.cob appears here first in a single annotated reference. Follow these patterns exactly.

---

## 0.1 — Compile Smoke Test (Do This First)

Before writing any real program, verify that GnuCOBOL works, copybooks resolve, and fixed-width file I/O round-trips correctly. This program creates a 70-byte ACCTREC record, writes it to a file, reads it back, and displays it through the pipe-delimited output format the Python bridge expects.

**File:** `cobol/src/SMOKETEST.cob`

```cobol
      *================================================================*
      * SMOKETEST.cob — Compiler and I/O verification
      * Tests: compilation, copybook resolution, file write, file read,
      *        fixed-width record format, pipe-delimited DISPLAY output
      * Compile: cobc -x -free -I ../copybooks SMOKETEST.cob -o ../bin/SMOKETEST
      * Run:     cd banks/BANK_A && ../../cobol/bin/SMOKETEST
      *================================================================*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SMOKETEST.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ACCOUNT-FILE
               ASSIGN TO "TEST-ACCOUNTS.DAT"
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-FILE-STATUS.

       DATA DIVISION.
       FILE SECTION.
       FD  ACCOUNT-FILE.
       COPY "ACCTREC.cpy".

       WORKING-STORAGE SECTION.
       01  WS-FILE-STATUS         PIC XX VALUE SPACES.
           88  WS-FILE-OK         VALUE '00'.
           88  WS-FILE-EOF        VALUE '10'.
       01  WS-RECORD-COUNT        PIC 9(4) VALUE 0.

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           PERFORM WRITE-TEST-RECORD
           PERFORM READ-TEST-RECORD
           PERFORM CLEANUP
           STOP RUN.

       WRITE-TEST-RECORD.
           OPEN OUTPUT ACCOUNT-FILE
           IF NOT WS-FILE-OK
               DISPLAY "ERROR|FILE-OPEN-WRITE|" WS-FILE-STATUS
               STOP RUN
           END-IF

           INITIALIZE ACCOUNT-RECORD
           MOVE "ACT-T-001"      TO ACCT-ID
           MOVE "Smoke Test User" TO ACCT-NAME
           MOVE "C"              TO ACCT-TYPE
           MOVE 12345.67         TO ACCT-BALANCE
           MOVE "A"              TO ACCT-STATUS
           MOVE 20260217         TO ACCT-OPEN-DATE
           MOVE 20260217         TO ACCT-LAST-ACTIVITY

           WRITE ACCOUNT-RECORD
           IF NOT WS-FILE-OK
               DISPLAY "ERROR|FILE-WRITE|" WS-FILE-STATUS
               STOP RUN
           END-IF

           CLOSE ACCOUNT-FILE
           DISPLAY "OK|WRITE|ACT-T-001|Smoke Test User".

       READ-TEST-RECORD.
           OPEN INPUT ACCOUNT-FILE
           IF NOT WS-FILE-OK
               DISPLAY "ERROR|FILE-OPEN-READ|" WS-FILE-STATUS
               STOP RUN
           END-IF

           READ ACCOUNT-FILE
               AT END
                   DISPLAY "ERROR|EMPTY-FILE|No records found"
                   CLOSE ACCOUNT-FILE
                   STOP RUN
           END-READ

           IF NOT WS-FILE-OK AND NOT WS-FILE-EOF
               DISPLAY "ERROR|FILE-READ|" WS-FILE-STATUS
               CLOSE ACCOUNT-FILE
               STOP RUN
           END-IF

           DISPLAY "OK|READ|"
               ACCT-ID "|"
               ACCT-NAME "|"
               ACCT-TYPE "|"
               ACCT-BALANCE "|"
               ACCT-STATUS "|"
               ACCT-OPEN-DATE "|"
               ACCT-LAST-ACTIVITY

           CLOSE ACCOUNT-FILE.

       CLEANUP.
      *    Delete the test file so it doesn't interfere with real data
           DISPLAY "SMOKE-TEST|PASS|All checks succeeded".
```

**Run sequence:**
```bash
# From project root:
./scripts/build.sh                    # compiles all programs including SMOKETEST
cd banks/BANK_A
../../cobol/bin/SMOKETEST

# Expected output:
# OK|WRITE|ACT-T-001|Smoke Test User
# OK|READ|ACT-T-001 |Smoke Test User               |C|00000012345.67|A|20260217|20260217
# SMOKE-TEST|PASS|All checks succeeded
```

**What to verify:**
1. It compiled without warnings (`cobc -x -free -I ../copybooks`)
2. `TEST-ACCOUNTS.DAT` was created in `banks/BANK_A/`
3. The READ output shows the exact same data that was written
4. Balance field shows the COBOL display format (note: COBOL will format `PIC S9(10)V99` as a display string — observe exactly how GnuCOBOL renders it and match that in the bridge parser)
5. Name field is right-padded with spaces to 30 characters

**After verification:** Delete `SMOKETEST.cob` from the build script and `TEST-ACCOUNTS.DAT` from the bank directory. The smoke test is a one-time verification, not a permanent fixture.

---

## 0.2 — Annotated Reference Program

This program demonstrates every COBOL pattern used in the four real programs. It is NOT a program to include in the project — it is a **style guide with runnable code**. When writing ACCOUNTS.cob, TRANSACT.cob, VALIDATE.cob, or REPORTS.cob, copy these patterns.

```cobol
      *================================================================*
      * REFERENCE.cob — Pattern Reference for cobol-legacy-ledger
      * NOT part of the project. Study this, then implement real programs.
      *
      * Patterns demonstrated:
      *   - IDENTIFICATION / ENVIRONMENT / DATA / PROCEDURE divisions
      *   - FILE-CONTROL with FILE STATUS
      *   - FD entries with COPY statements
      *   - WORKING-STORAGE layout with 88-level conditions
      *   - File I/O choreography (OPEN, READ AT END, WRITE, CLOSE)
      *   - PERFORM paragraph structure (no inline PERFORM)
      *   - Loading all records into a table (OCCURS array)
      *   - Sequential search (the only search pattern we use)
      *   - Pipe-delimited DISPLAY for Python bridge parsing
      *   - FILE STATUS error handling at every I/O operation
      *   - ACCEPT for command-line input
      *================================================================*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. REFERENCE.
       AUTHOR. AKD Solutions.
      *    Date-Written and Date-Compiled are period-authentic headers.
      *    Include them in all four programs for the 1985 aesthetic.
       DATE-WRITTEN. 2026-02-17.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
      *    -------------------------------------------------------
      *    PATTERN: SELECT/ASSIGN with FILE STATUS
      *    Every file gets a FILE STATUS variable. Check it after
      *    EVERY I/O operation. Never assume success.
      *    The filename string is relative to CWD — this is how
      *    one COBOL binary serves 6 different bank directories.
      *    ORGANIZATION IS LINE SEQUENTIAL = text file, one record
      *    per line, newline-delimited. This is what Python expects.
      *    Do NOT use ORGANIZATION SEQUENTIAL (binary/fixed-block).
      *    -------------------------------------------------------
           SELECT ACCOUNT-FILE
               ASSIGN TO "ACCOUNTS.DAT"
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-ACCT-FILE-STATUS.

           SELECT TRANSACTION-FILE
               ASSIGN TO "TRANSACT.DAT"
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-TRANS-FILE-STATUS.

       DATA DIVISION.
       FILE SECTION.
      *    -------------------------------------------------------
      *    PATTERN: FD with COPY
      *    The FD entry declares the file's record structure.
      *    COPY pulls in the 01-level record from the copybook.
      *    The copybook defines the EXACT byte layout of each line
      *    in the .DAT file. Every program that touches the file
      *    must COPY the same copybook so layouts match.
      *    -------------------------------------------------------
       FD  ACCOUNT-FILE.
       COPY "ACCTREC.cpy".

       FD  TRANSACTION-FILE.
       COPY "TRANSREC.cpy".

       WORKING-STORAGE SECTION.
      *    -------------------------------------------------------
      *    PATTERN: FILE STATUS variables
      *    PIC XX (not PIC 99). GnuCOBOL returns alphanumeric
      *    status codes. '00' = success, '10' = end of file,
      *    '35' = file not found, '39' = file attribute mismatch.
      *    Always use 88-level conditions for readability.
      *    -------------------------------------------------------
       01  WS-ACCT-FILE-STATUS   PIC XX VALUE SPACES.
           88  WS-ACCT-OK        VALUE '00'.
           88  WS-ACCT-EOF       VALUE '10'.
       01  WS-TRANS-FILE-STATUS  PIC XX VALUE SPACES.
           88  WS-TRANS-OK       VALUE '00'.
           88  WS-TRANS-EOF      VALUE '10'.

      *    -------------------------------------------------------
      *    PATTERN: In-memory account table
      *    COBOL has no dynamic arrays. Declare a fixed-size
      *    OCCURS table in WORKING-STORAGE. 100 is our ceiling
      *    (see KNOWN_ISSUES.md A1). WS-ACCT-COUNT tracks how
      *    many slots are actually populated.
      *    -------------------------------------------------------
       01  WS-ACCOUNT-TABLE.
           05  WS-ACCT-COUNT     PIC 9(4) VALUE 0.
           05  WS-ACCT-ENTRY OCCURS 100 TIMES.
               10  WS-A-ID       PIC X(10).
               10  WS-A-NAME     PIC X(30).
               10  WS-A-TYPE     PIC X(1).
               10  WS-A-BAL      PIC S9(10)V99.
               10  WS-A-STATUS   PIC X(1).
               10  WS-A-OPENED   PIC 9(8).
               10  WS-A-LASTACT  PIC 9(8).

      *    -------------------------------------------------------
      *    PATTERN: Input parameters from command line / stdin
      *    The Python bridge passes operation and arguments via
      *    command-line ACCEPT. Group them under a single 01 level.
      *    -------------------------------------------------------
       01  WS-INPUT-PARAMS.
           05  WS-IN-OPERATION   PIC X(10).
               88  WS-OP-CREATE  VALUE 'CREATE'.
               88  WS-OP-READ    VALUE 'READ'.
               88  WS-OP-LIST    VALUE 'LIST'.
               88  WS-OP-UPDATE  VALUE 'UPDATE'.
               88  WS-OP-CLOSE   VALUE 'CLOSE'.
           05  WS-IN-ACCT-ID     PIC X(10).
           05  WS-IN-NAME        PIC X(30).
           05  WS-IN-TYPE        PIC X(1).
           05  WS-IN-AMOUNT      PIC S9(10)V99.
           05  WS-IN-TARGET-ID   PIC X(10).

      *    -------------------------------------------------------
      *    PATTERN: Work variables and counters
      *    Keep these grouped and named with WS- prefix.
      *    -------------------------------------------------------
       01  WS-WORK-FIELDS.
           05  WS-IDX            PIC 9(4) VALUE 0.
           05  WS-FOUND-FLAG     PIC X(1) VALUE 'N'.
               88  WS-FOUND      VALUE 'Y'.
               88  WS-NOT-FOUND  VALUE 'N'.
           05  WS-FOUND-IDX      PIC 9(4) VALUE 0.

       01  WS-RESULT-CODE        PIC X(2) VALUE '00'.

       PROCEDURE DIVISION.
      *    -------------------------------------------------------
      *    PATTERN: Main program flow
      *    Accept input, dispatch to paragraph, stop run.
      *    Keep MAIN-PROGRAM short — it's a dispatcher.
      *    -------------------------------------------------------
       MAIN-PROGRAM.
           ACCEPT WS-IN-OPERATION FROM COMMAND-LINE
           PERFORM LOAD-ALL-ACCOUNTS

           EVALUATE TRUE
               WHEN WS-OP-CREATE
                   PERFORM CREATE-ACCOUNT
               WHEN WS-OP-READ
                   PERFORM READ-ACCOUNT
               WHEN WS-OP-LIST
                   PERFORM LIST-ACCOUNTS
               WHEN OTHER
                   DISPLAY "ERROR|UNKNOWN-OPERATION|"
                       WS-IN-OPERATION
           END-EVALUATE

           DISPLAY "RESULT|" WS-RESULT-CODE
           STOP RUN.

      *    -------------------------------------------------------
      *    PATTERN: Load entire file into OCCURS array
      *    This is how COBOL "caches" data. Open, read in a loop
      *    until AT END, close. Every record goes into the next
      *    slot of the OCCURS table. Check FILE STATUS after
      *    every operation.
      *    -------------------------------------------------------
       LOAD-ALL-ACCOUNTS.
           MOVE 0 TO WS-ACCT-COUNT

           OPEN INPUT ACCOUNT-FILE
           IF NOT WS-ACCT-OK
               DISPLAY "ERROR|FILE-OPEN|" WS-ACCT-FILE-STATUS
               MOVE '99' TO WS-RESULT-CODE
               STOP RUN
           END-IF

           PERFORM UNTIL WS-ACCT-EOF
               READ ACCOUNT-FILE
                   AT END
                       CONTINUE
                   NOT AT END
                       ADD 1 TO WS-ACCT-COUNT
                       MOVE ACCT-ID       TO
                           WS-A-ID(WS-ACCT-COUNT)
                       MOVE ACCT-NAME     TO
                           WS-A-NAME(WS-ACCT-COUNT)
                       MOVE ACCT-TYPE     TO
                           WS-A-TYPE(WS-ACCT-COUNT)
                       MOVE ACCT-BALANCE  TO
                           WS-A-BAL(WS-ACCT-COUNT)
                       MOVE ACCT-STATUS   TO
                           WS-A-STATUS(WS-ACCT-COUNT)
                       MOVE ACCT-OPEN-DATE TO
                           WS-A-OPENED(WS-ACCT-COUNT)
                       MOVE ACCT-LAST-ACTIVITY TO
                           WS-A-LASTACT(WS-ACCT-COUNT)
               END-READ
           END-PERFORM

           CLOSE ACCOUNT-FILE.

      *    -------------------------------------------------------
      *    PATTERN: Sequential search
      *    No indexes, no SEARCH verb. Just PERFORM VARYING with
      *    a flag. This is O(n) and that's fine for 8 accounts.
      *    See KNOWN_ISSUES.md A2.
      *    -------------------------------------------------------
       FIND-ACCOUNT.
           MOVE 'N' TO WS-FOUND-FLAG
           MOVE 0   TO WS-FOUND-IDX

           PERFORM VARYING WS-IDX FROM 1 BY 1
               UNTIL WS-IDX > WS-ACCT-COUNT
                  OR WS-FOUND
               IF WS-A-ID(WS-IDX) = WS-IN-ACCT-ID
                   SET WS-FOUND TO TRUE
                   MOVE WS-IDX TO WS-FOUND-IDX
               END-IF
           END-PERFORM.

      *    -------------------------------------------------------
      *    PATTERN: DISPLAY for Python bridge
      *    Pipe-delimited. First field is status (OK or ERROR).
      *    Second field is operation name. Remaining fields are
      *    data. The bridge splits on '|' and parses by position.
      *
      *    CRITICAL: Do not put spaces around pipes. Do not add
      *    trailing pipes. The bridge parser is exact-match.
      *    -------------------------------------------------------
       LIST-ACCOUNTS.
           PERFORM VARYING WS-IDX FROM 1 BY 1
               UNTIL WS-IDX > WS-ACCT-COUNT
               DISPLAY "ACCOUNT|"
                   WS-A-ID(WS-IDX) "|"
                   WS-A-NAME(WS-IDX) "|"
                   WS-A-TYPE(WS-IDX) "|"
                   WS-A-BAL(WS-IDX) "|"
                   WS-A-STATUS(WS-IDX) "|"
                   WS-A-OPENED(WS-IDX) "|"
                   WS-A-LASTACT(WS-IDX)
           END-PERFORM
           MOVE '00' TO WS-RESULT-CODE.

       CREATE-ACCOUNT.
      *    Accept additional params from command line
           ACCEPT WS-IN-ACCT-ID FROM COMMAND-LINE
           ACCEPT WS-IN-NAME FROM COMMAND-LINE
           ACCEPT WS-IN-TYPE FROM COMMAND-LINE
           ACCEPT WS-IN-AMOUNT FROM COMMAND-LINE

      *    Check for duplicate
           PERFORM FIND-ACCOUNT
           IF WS-FOUND
               DISPLAY "ERROR|DUPLICATE|" WS-IN-ACCT-ID
               MOVE '03' TO WS-RESULT-CODE
           ELSE
      *        Add to in-memory table
               ADD 1 TO WS-ACCT-COUNT
               MOVE WS-IN-ACCT-ID TO WS-A-ID(WS-ACCT-COUNT)
               MOVE WS-IN-NAME    TO WS-A-NAME(WS-ACCT-COUNT)
               MOVE WS-IN-TYPE    TO WS-A-TYPE(WS-ACCT-COUNT)
               MOVE WS-IN-AMOUNT  TO WS-A-BAL(WS-ACCT-COUNT)
               MOVE 'A'           TO WS-A-STATUS(WS-ACCT-COUNT)
               MOVE 20260217      TO WS-A-OPENED(WS-ACCT-COUNT)
               MOVE 20260217      TO WS-A-LASTACT(WS-ACCT-COUNT)

      *        Rewrite entire file (COBOL doesn't do random insert)
               PERFORM WRITE-ALL-ACCOUNTS

               DISPLAY "OK|CREATED|"
                   WS-IN-ACCT-ID "|"
                   WS-IN-NAME "|"
                   WS-IN-TYPE "|"
                   WS-IN-AMOUNT "|"
                   "A|20260217"
               MOVE '00' TO WS-RESULT-CODE
           END-IF.

       READ-ACCOUNT.
           ACCEPT WS-IN-ACCT-ID FROM COMMAND-LINE
           PERFORM FIND-ACCOUNT
           IF WS-FOUND
               DISPLAY "ACCOUNT|"
                   WS-A-ID(WS-FOUND-IDX) "|"
                   WS-A-NAME(WS-FOUND-IDX) "|"
                   WS-A-TYPE(WS-FOUND-IDX) "|"
                   WS-A-BAL(WS-FOUND-IDX) "|"
                   WS-A-STATUS(WS-FOUND-IDX) "|"
                   WS-A-OPENED(WS-FOUND-IDX) "|"
                   WS-A-LASTACT(WS-FOUND-IDX)
               MOVE '00' TO WS-RESULT-CODE
           ELSE
               DISPLAY "ERROR|ACCOUNT NOT FOUND: "
                   WS-IN-ACCT-ID
               MOVE '03' TO WS-RESULT-CODE
           END-IF.

      *    -------------------------------------------------------
      *    PATTERN: Rewrite entire file from memory
      *    COBOL sequential files don't support random update.
      *    To modify any record, you load everything into the
      *    OCCURS array, modify the array, then rewrite the whole
      *    file. OPEN OUTPUT truncates the file first.
      *    -------------------------------------------------------
       WRITE-ALL-ACCOUNTS.
           OPEN OUTPUT ACCOUNT-FILE
           IF NOT WS-ACCT-OK
               DISPLAY "ERROR|FILE-OPEN-WRITE|"
                   WS-ACCT-FILE-STATUS
               MOVE '99' TO WS-RESULT-CODE
               STOP RUN
           END-IF

           PERFORM VARYING WS-IDX FROM 1 BY 1
               UNTIL WS-IDX > WS-ACCT-COUNT
               MOVE WS-A-ID(WS-IDX)      TO ACCT-ID
               MOVE WS-A-NAME(WS-IDX)    TO ACCT-NAME
               MOVE WS-A-TYPE(WS-IDX)    TO ACCT-TYPE
               MOVE WS-A-BAL(WS-IDX)     TO ACCT-BALANCE
               MOVE WS-A-STATUS(WS-IDX)  TO ACCT-STATUS
               MOVE WS-A-OPENED(WS-IDX)  TO ACCT-OPEN-DATE
               MOVE WS-A-LASTACT(WS-IDX) TO ACCT-LAST-ACTIVITY
               WRITE ACCOUNT-RECORD
               IF NOT WS-ACCT-OK
                   DISPLAY "ERROR|FILE-WRITE|"
                       WS-ACCT-FILE-STATUS
                   MOVE '99' TO WS-RESULT-CODE
                   CLOSE ACCOUNT-FILE
                   STOP RUN
               END-IF
           END-PERFORM

           CLOSE ACCOUNT-FILE.
```

**Key patterns to carry forward into all four programs:**

| Pattern | Where It Appears | Rule |
|---------|-----------------|------|
| `FILE STATUS IS WS-xxx` | Every SELECT statement | Always. No exceptions. |
| `88 WS-xxx-OK VALUE '00'` | After every FILE STATUS declaration | Always pair with `'10'` for EOF |
| `ORGANIZATION IS LINE SEQUENTIAL` | Every SELECT statement | Never omit — default is binary |
| `IF NOT WS-xxx-OK` | After every OPEN, READ, WRITE, CLOSE | Check immediately. Display error with status code. |
| `READ ... AT END / NOT AT END` | Every file read in a loop | AT END sets the EOF flag; NOT AT END processes the record |
| `PERFORM VARYING ... UNTIL` | Every search or iteration | No inline PERFORM. Always a named paragraph. |
| `DISPLAY "PREFIX\|" field "\|" field` | Every output to Python bridge | Pipes, no spaces around pipes, no trailing pipe |
| `MOVE ... TO ...` then `WRITE` | Every file write | Never WRITE directly from input — always stage through the FD record |
| `OPEN OUTPUT` to rewrite | Every file modification | COBOL sequential files: load all → modify array → rewrite all |
| `STOP RUN` on fatal error | After unrecoverable FILE STATUS | Don't continue with bad file state |

---

## 0.3 — GnuCOBOL Cheat Sheet

These are the things that differ from mainframe COBOL (IBM z/OS) or from what AI models typically generate. Every item here has caused a real build or runtime failure in GnuCOBOL projects.

### Compilation

1. **Use `-free` for free-form source.** Without it, GnuCOBOL enforces columns 7–72 (fixed-format). All our programs use free-form. Compile command: `cobc -x -free -I ../copybooks PROGRAM.cob -o ../bin/PROGRAM`

2. **Use `-I ../copybooks` for COPY resolution.** COPY statements (`COPY "ACCTREC.cpy"`) search the include path. Without `-I`, GnuCOBOL only looks in the current directory. Since we compile from `cobol/src/` and copybooks live in `cobol/copybooks/`, the `-I` flag is required.

3. **`-x` produces a standalone executable.** Not a shared object, not a module. The Python bridge runs it as a subprocess. Always use `-x`.

4. **Warnings are informational, not fatal.** GnuCOBOL may warn about unused variables or implicit type conversions. These are acceptable in our project (some come from the known-issues COBOL patterns). Do not add `-Werror`. But if a warning reveals an actual logic bug, note it in `KNOWN_ISSUES.md`.

### File I/O

5. **`ORGANIZATION IS LINE SEQUENTIAL` = text file.** Each WRITE appends a newline. Each READ consumes one line. This is what Python's `open('ACCOUNTS.DAT').readlines()` expects. Without `LINE`, GnuCOBOL uses binary sequential format which produces unreadable files.

6. **`FILE STATUS` must be `PIC XX`, not `PIC 99`.** GnuCOBOL returns alphanumeric status codes ('00', '10', '35', '39'). Using `PIC 99` causes implicit conversion that can mask errors. Always `PIC XX VALUE SPACES` with 88-level conditions.

7. **`OPEN OUTPUT` truncates the file.** If the file already exists, OPEN OUTPUT destroys its contents and starts fresh. Use this for full-file rewrites (the load-modify-rewrite pattern). For appending, use `OPEN EXTEND`.

8. **`OPEN EXTEND` appends to existing file.** Use this for TRANSACT.DAT — transactions are always appended, never rewritten. If the file doesn't exist, GnuCOBOL creates it.

9. **File not found = status '35'.** If `OPEN INPUT` can't find the file, FILE STATUS is '35'. Handle this gracefully — on first run, ACCOUNTS.DAT may not exist yet. Either check for '35' and treat as "empty file," or ensure `seed.sh` creates the file before any COBOL runs.

### Data Types

10. **`PIC S9(10)V99` = signed, 10 integer digits, 2 decimal digits, implied decimal.** Total display width: 12 characters (sign is stored as overpunch or separate depending on USAGE). For LINE SEQUENTIAL files, GnuCOBOL writes display format — the sign may appear as a trailing overpunch character (e.g., `{` for +0, `}` for -0). The bridge parser must handle this. **Test with the smoke test and observe the actual output format before writing the parser.**

11. **`PIC X(n)` is right-padded with spaces.** `MOVE "Hello" TO PIC X(30)` produces `"Hello                         "` (25 trailing spaces). The bridge parser should `.strip()` all string fields after reading.

12. **`INITIALIZE record-name` sets all fields to default.** Alphanumeric fields → spaces, numeric fields → zeros. Use before populating a new record to avoid residual data from previous iterations.

### Program Structure

13. **No inline PERFORM.** Use `PERFORM paragraph-name` exclusively. Every block of logic gets a named paragraph. This is the 1985 style and it makes the code more readable for the Python bridge to trace (TRACE lines reference paragraph names).

14. **EVALUATE TRUE / WHEN condition / END-EVALUATE.** This is COBOL's switch statement. Use it for operation dispatch in the main program and for transaction type dispatch in TRANSACT.cob. Prefer EVALUATE over nested IF for multi-way branching.

15. **ACCEPT ... FROM COMMAND-LINE.** GnuCOBOL supports this extension for reading command-line arguments. Each ACCEPT reads the next argument. The bridge passes operation and arguments as separate command-line words: `./ACCOUNTS CREATE ACT-A-001 "Maria Santos" C 15420.50`. **Important:** If an argument contains spaces (like account names), the bridge must quote it. Test this with the smoke test.

### Common Pitfalls

16. **Never use `CALL SYSTEM` or `CALL "system"`.** This is a C-interop extension, not standard COBOL. Our programs are standalone — they don't shell out to anything.

17. **Don't use `COMP-3` (packed decimal) with LINE SEQUENTIAL files.** Packed decimal is a binary encoding. LINE SEQUENTIAL expects displayable characters. All our PIC clauses use DISPLAY format (the default USAGE), which is correct. If you see `USAGE COMP-3` in any AI-generated code, remove it.

18. **String concatenation doesn't exist in COBOL.** To build a pipe-delimited output line, use multiple items in a single DISPLAY statement: `DISPLAY "OK|" field-1 "|" field-2`. Do NOT try to `STRING ... DELIMITED BY ...` into a buffer and then DISPLAY the buffer — it's fragile and unnecessary.

---

## Verification Checklist

Before proceeding from Section 0 to Section 1 (COBOL program implementation):

- [ ] `cobc --version` runs and shows GnuCOBOL 3.x
- [ ] SMOKETEST.cob compiles with: `cobc -x -free -I ../copybooks SMOKETEST.cob -o ../bin/SMOKETEST`
- [ ] SMOKETEST runs and produces `SMOKE-TEST|PASS|All checks succeeded`
- [ ] TEST-ACCOUNTS.DAT contains exactly 70 bytes per line (plus newline)
- [ ] The balance field in the DISPLAY output has been observed and its exact format noted (sign representation, leading zeros, decimal handling)
- [ ] The bridge parser strategy for balance fields has been decided based on actual GnuCOBOL output (not assumed format)
- [ ] SMOKETEST files have been cleaned up (delete TEST-ACCOUNTS.DAT, optionally remove SMOKETEST.cob from build)

**Only after all checks pass: proceed to implementing ACCOUNTS.cob.**
