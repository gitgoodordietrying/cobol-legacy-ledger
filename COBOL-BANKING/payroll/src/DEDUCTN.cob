      *>================================================================*
      *>  EDUCATIONAL NOTE: This program contains INTENTIONAL anti-patterns
      *>  for teaching purposes. See KNOWN_ISSUES.md for the full catalog.
      *>  All other COBOL in this project follows clean, modern practices.
      *>================================================================*
      *>  Program:     DEDUCTN.cob
      *>  System:      ENTERPRISE PAYROLL — Employee Deductions Processor
      *>  Author:      SLW (original 1991), with JRK/PMR leftovers
      *>  Written:     1991-04-15 (IBM ES/9000 Model 820)
      *>
      *>  JCL Reference:
      *>    //PAYRL300 JOB (ACCT),'DEDUCTIONS',CLASS=A
      *>    //STEP01   EXEC PGM=DEDUCTN
      *>    //EMPFILE  DD DSN=PAYRL.EMPLOYEE.MASTER,DISP=SHR
      *>    //SYSOUT   DD SYSOUT=*
      *>
      *>  Change Log:
      *>    1991-04-15  SLW  Initial — medical, dental, 401(k)
      *>    1991-07-20  SLW  Added union dues (removed 1993, code remains)
      *>    1991-11-30  SLW  Bug fix — GO TO for negative balance
      *>    1993-03-15  PMR  "Disabled" union dues (set flag, left code)
      *>    2002-01-15  Y2K  No changes (but added a comment anyway)
      *>
      *>  STYLE NOTE: SLW started writing structured COBOL (top half)
      *>  but reverted to GO TO when debugging under pressure (bottom
      *>  half). The result is a hybrid: clean PERFORM loops above,
      *>  spaghetti GO TO chains below. This is EXTREMELY common in
      *>  real legacy systems — the structured parts were written
      *>  during normal development, the GO TO parts were added
      *>  during 2 AM production fixes.
      *>
      *>  COMP INCONSISTENCY: Medical costs use COMP-3 (from copybook),
      *>  dental uses COMP (binary — SLW preference), 401(k) uses
      *>  DISPLAY (default — SLW "forgot to specify"). All three work
      *>  but require implicit conversion on every arithmetic operation.
      *>  The compiler handles it silently. Performance suffers.
      *>
      *>================================================================*

       IDENTIFICATION DIVISION.
       PROGRAM-ID. DEDUCTN.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT EMPLOYEE-FILE
               ASSIGN TO "EMPLOYEES.DAT"
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-FILE-STATUS.

       DATA DIVISION.
       FILE SECTION.
       FD  EMPLOYEE-FILE.
           COPY "EMPREC.cpy".

       WORKING-STORAGE SECTION.

       01  WS-FILE-STATUS          PIC X(2).
       01  WS-EOF-FLAG             PIC X(1) VALUE 'N'.
           88  WS-EOF              VALUE 'Y'.

      *> SLW: Deduction accumulators — note the mixed USAGE types
      *>   COMP-3 for medical (matches PAYCOM copybook)
      *>   COMP for dental (SLW: "binary is faster for small numbers")
      *>   DISPLAY for 401k (SLW: "I'll fix it later" — never fixed)
       01  WS-DEDUCTION-FIELDS.
           05  WS-MED-DEDUCTION    PIC S9(5)V99 COMP-3.
           05  WS-DENTAL-DEDUCTION PIC S9(5)V99 COMP.
           05  WS-401K-DEDUCTION   PIC S9(5)V99.
           05  WS-401K-MATCH       PIC S9(5)V99.
           05  WS-UNION-DEDUCTION  PIC S9(5)V99 COMP-3.
           05  WS-TOTAL-DEDUCTIONS PIC S9(7)V99 COMP-3.

      *> SLW: Employee gross pay (passed in or computed)
       01  WS-GROSS-PAY            PIC S9(7)V99 COMP-3.

      *> PMR 1993: Union dues "disabled" via flag
      *> The code still computes union dues but multiplies by 0
      *> if this flag is 'N'. SLW: "just zero it out" PMR: "no,
      *> use a flag in case we re-enable it." Never re-enabled.
       01  WS-UNION-FLAG           PIC X(1) VALUE 'N'.
           88  WS-UNION-ACTIVE     VALUE 'Y'.
           88  WS-UNION-INACTIVE   VALUE 'N'.

      *> Counters
       01  WS-COUNTERS.
           05  WS-EMP-COUNT        PIC 9(5) VALUE 0.
           05  WS-DED-COUNT        PIC 9(5) VALUE 0.
           05  WS-ZERO-COUNT       PIC 9(5) VALUE 0.

      *> SLW: Error handling fields
       01  WS-ERROR-FIELDS.
           05  WS-ERR-CODE         PIC 9(4) VALUE 0.
           05  WS-ERR-MSG          PIC X(40).

      *> Command line
       01  WS-CMD-ARGS.
           05  WS-ARG-PERIOD       PIC 9(4) VALUE 0.

           COPY "PAYCOM.cpy".

       PROCEDURE DIVISION.

      *>================================================================*
      *>  MAIN-PARA: Entry point — structured top
      *>  SLW: "Nice clean PERFORM UNTIL loop"
      *>================================================================*
       MAIN-PARA.
           ACCEPT WS-ARG-PERIOD FROM COMMAND-LINE
           IF WS-ARG-PERIOD = 0
               MOVE 1 TO WS-ARG-PERIOD
           END-IF

           DISPLAY "DEDUCTN|START|PERIOD|" WS-ARG-PERIOD

           OPEN INPUT EMPLOYEE-FILE
           IF WS-FILE-STATUS NOT = '00'
               DISPLAY "DEDUCTN|ERROR|FILE|" WS-FILE-STATUS
               STOP RUN
           END-IF

      *>   SLW: Clean structured loop (the good part)
           PERFORM PROCESS-EMPLOYEE UNTIL WS-EOF

           CLOSE EMPLOYEE-FILE

           DISPLAY "DEDUCTN|SUMMARY"
           DISPLAY "DEDUCTN|EMPLOYEES|" WS-EMP-COUNT
           DISPLAY "DEDUCTN|DEDUCTIONS|" WS-DED-COUNT
           DISPLAY "DEDUCTN|ZERO-DED|" WS-ZERO-COUNT
           DISPLAY "DEDUCTN|COMPLETE"
           STOP RUN.

      *>================================================================*
      *>  PROCESS-EMPLOYEE: Read and compute deductions
      *>  SLW: Started structured, ends with GO TO (2 AM fix)
      *>================================================================*
       PROCESS-EMPLOYEE.
           READ EMPLOYEE-FILE
               AT END
                   SET WS-EOF TO TRUE
           END-READ

           IF WS-EOF
               EXIT PARAGRAPH
           END-IF

           ADD 1 TO WS-EMP-COUNT

           IF NOT EMP-ACTIVE
               EXIT PARAGRAPH
           END-IF

      *>   Initialize deduction accumulators
           MOVE 0 TO WS-MED-DEDUCTION
           MOVE 0 TO WS-DENTAL-DEDUCTION
           MOVE 0 TO WS-401K-DEDUCTION
           MOVE 0 TO WS-401K-MATCH
           MOVE 0 TO WS-UNION-DEDUCTION
           MOVE 0 TO WS-TOTAL-DEDUCTIONS

      *>   Compute gross for this period
           IF EMP-SALARIED
               COMPUTE WS-GROSS-PAY ROUNDED =
                   EMP-SALARY / 26
           ELSE
               COMPUTE WS-GROSS-PAY ROUNDED =
                   EMP-HOURLY-RATE * EMP-HOURS-WORKED
           END-IF

      *>   ── Medical deduction (per pay period) ──────────────
      *>   SLW: "Divide annual by 12 for monthly, then by 2.167
      *>   for biweekly." This is WRONG — should be / 26 directly.
      *>   But it's been "working" for 30 years so nobody touches it.
           PERFORM COMPUTE-MEDICAL

      *>   ── Dental deduction ────────────────────────────────
      *>   SLW: Uses COMP (binary) for dental but COMP-3 for medical.
      *>   Every time these are added together, the compiler inserts
      *>   an implicit COMP-3-to-COMP conversion. Works, but wasteful.
           PERFORM COMPUTE-DENTAL

      *>   ── 401(k) deduction ────────────────────────────────
      *>   SLW: Uses DISPLAY (default) — no USAGE clause at all.
      *>   Compiler uses character-based arithmetic. Slow on mainframes
      *>   but functionally correct.
           PERFORM COMPUTE-401K

      *>   ── Union dues (disabled since 1993) ────────────────
      *>   PMR: "Don't remove the code. Set the flag to N."
      *>   SLW: "Fine, but this is stupid."
           PERFORM COMPUTE-UNION-DUES

      *>   ── Total ───────────────────────────────────────────
      *>   Here's where the spaghetti starts: if total > gross,
      *>   SLW added a GO TO to an error handler instead of using
      *>   structured error handling. This was a 2 AM production fix.
           COMPUTE WS-TOTAL-DEDUCTIONS =
               WS-MED-DEDUCTION + WS-DENTAL-DEDUCTION +
               WS-401K-DEDUCTION + WS-UNION-DEDUCTION

           IF WS-TOTAL-DEDUCTIONS > WS-GROSS-PAY
      *>       SLW 1991-11-30: "Deductions exceed gross — can't
      *>       let net go negative. Jump to error handler."
               MOVE 1001 TO WS-ERR-CODE
               MOVE "DEDUCTIONS EXCEED GROSS PAY" TO WS-ERR-MSG
               GO TO DEDUCTION-OVERFLOW-HANDLER
           END-IF

           IF WS-TOTAL-DEDUCTIONS = 0
               ADD 1 TO WS-ZERO-COUNT
           ELSE
               ADD 1 TO WS-DED-COUNT
           END-IF

           DISPLAY "DEDUCTN|RESULT|" EMP-ID "|"
               WS-TOTAL-DEDUCTIONS "|" WS-MED-DEDUCTION "|"
               WS-DENTAL-DEDUCTION "|" WS-401K-DEDUCTION.

      *>================================================================*
      *>  COMPUTE-MEDICAL: Medical plan deduction
      *>  SLW: Structured paragraph (the good era)
      *>================================================================*
       COMPUTE-MEDICAL.
           EVALUATE TRUE
               WHEN EMP-MED-NONE
                   MOVE 0 TO WS-MED-DEDUCTION
               WHEN EMP-MED-BASIC
      *>           SLW comment: "$250/month per employee"
      *>           PAYCOM says 275.00 — comment is wrong (again)
                   COMPUTE WS-MED-DEDUCTION ROUNDED =
                       PAYCOM-MED-BASIC / 12
               WHEN EMP-MED-PREMIUM
                   COMPUTE WS-MED-DEDUCTION ROUNDED =
                       PAYCOM-MED-PREMIUM / 12
           END-EVALUATE.

      *>================================================================*
      *>  COMPUTE-DENTAL: Dental plan deduction
      *>  SLW: COMP field — binary arithmetic for dental cost
      *>================================================================*
       COMPUTE-DENTAL.
           IF EMP-HAS-DENTAL
      *>       COMP-3 (PAYCOM) → COMP (WS-DENTAL-DEDUCTION):
      *>       Implicit conversion on every assignment.
               COMPUTE WS-DENTAL-DEDUCTION ROUNDED =
                   PAYCOM-DENTAL-COST / 12
           ELSE
               MOVE 0 TO WS-DENTAL-DEDUCTION
           END-IF.

      *>================================================================*
      *>  COMPUTE-401K: Retirement contribution
      *>  SLW: DISPLAY field — character-based arithmetic
      *>  401(k) percentage stored as 9V99 (e.g., 0.06 = 6%)
      *>================================================================*
       COMPUTE-401K.
           IF EMP-401K-PCT > 0
               COMPUTE WS-401K-DEDUCTION ROUNDED =
                   WS-GROSS-PAY * EMP-401K-PCT
      *>       Company match — SLW says "50% match" (PAYCOM-401K-MATCH)
      *>       but also references "4% match cap" in comments.
      *>       Code uses 401K-MATCH (0.50) — matches 50% of employee
      *>       contribution, NOT 4% of salary. Confusing but correct.
               COMPUTE WS-401K-MATCH ROUNDED =
                   WS-401K-DEDUCTION * PAYCOM-401K-MATCH
           ELSE
               MOVE 0 TO WS-401K-DEDUCTION
               MOVE 0 TO WS-401K-MATCH
           END-IF.

      *>================================================================*
      *>  COMPUTE-UNION-DUES: Disabled since 1993
      *>  PMR: "Set flag to N, leave code for audit trail"
      *>  The PERFORM still runs, it just computes 0.
      *>================================================================*
       COMPUTE-UNION-DUES.
           IF WS-UNION-ACTIVE
      *>       Monthly union dues: $45 per pay period
      *>       (Nobody knows where $45 came from — SLW is gone)
               MOVE 45.00 TO WS-UNION-DEDUCTION
           ELSE
               MOVE 0 TO WS-UNION-DEDUCTION
           END-IF.

      *>================================================================*
      *>  DEDUCTION-OVERFLOW-HANDLER: The spaghetti zone
      *>  SLW 1991-11-30: Production fix at 2 AM
      *>  "If deductions > gross, cap deductions at gross - $1"
      *>  This paragraph is reached via GO TO from PROCESS-EMPLOYEE.
      *>  It does NOT return to the caller — it falls through to
      *>  DEDUCTION-CAP-APPLY and then GO TOs back to the read loop.
      *>================================================================*
       DEDUCTION-OVERFLOW-HANDLER.
           DISPLAY "DEDUCTN|OVERFLOW|" EMP-ID "|"
               WS-TOTAL-DEDUCTIONS "|GROSS|" WS-GROSS-PAY

      *>   SLW: "Cap at gross minus one dollar for safety"
      *>   Why $1? "Because zero net pay breaks the check printer"
           IF WS-GROSS-PAY > 1.00
               COMPUTE WS-TOTAL-DEDUCTIONS =
                   WS-GROSS-PAY - 1.00
               GO TO DEDUCTION-CAP-APPLY
           ELSE
      *>       Gross is less than $1 — skip deductions entirely
               MOVE 0 TO WS-TOTAL-DEDUCTIONS
               DISPLAY "DEDUCTN|SKIP-DED|" EMP-ID
               ADD 1 TO WS-ZERO-COUNT
           END-IF.

      *>  SLW: This paragraph is reached by fall-through AND by
      *>  GO TO from the handler above. Classic spaghetti pattern.
       DEDUCTION-CAP-APPLY.
           ADD 1 TO WS-DED-COUNT
           DISPLAY "DEDUCTN|CAPPED|" EMP-ID "|"
               WS-TOTAL-DEDUCTIONS.

      *>================================================================*
      *>  DEAD-GARNISHMENT: Removed feature, code remains
      *>  SLW 1991: Wage garnishment for court orders
      *>  Removed from production in 1993 when new system handled it.
      *>  Nobody deleted the code because "what if we need it again."
      *>================================================================*
       DEAD-GARNISHMENT.
      *>   Court-ordered garnishment calculation
      *>   PAYCOM-GARN-PCT = 0.00 (zeroed out in 1993)
      *>   This code runs but always produces 0.
           IF PAYCOM-GARN-FLAG = 'Y'
               COMPUTE WS-TOTAL-DEDUCTIONS =
                   WS-TOTAL-DEDUCTIONS +
                   (WS-GROSS-PAY * PAYCOM-GARN-PCT)
               IF WS-TOTAL-DEDUCTIONS > PAYCOM-GARN-MAX
                   MOVE PAYCOM-GARN-MAX TO WS-TOTAL-DEDUCTIONS
               END-IF
           END-IF.

       DEAD-GARNISHMENT-EXIT.
           EXIT.
