      *>================================================================*
      *>  EDUCATIONAL NOTE: This program contains INTENTIONAL anti-patterns
      *>  for teaching purposes. See KNOWN_ISSUES.md for the full catalog.
      *>  All other COBOL in this project follows clean, modern practices.
      *>================================================================*
      *>  Program:     PAYBATCH.cob
      *>  System:      ENTERPRISE PAYROLL — Batch Output Formatter
      *>  Author:      Y2K Remediation Team (2002), SLW (1991 original)
      *>  Written:     2002-01-15 (IBM zSeries 900)
      *>
      *>  JCL Reference:
      *>    //PAYRL400 JOB (ACCT),'PAYBATCH',CLASS=A
      *>    //STEP01   EXEC PGM=PAYBATCH
      *>    //EMPFILE  DD DSN=PAYRL.EMPLOYEE.MASTER,DISP=SHR
      *>    //OUTFILE  DD DSN=PAYRL.OUTBOUND.YYYYMMDD,DISP=(NEW,CATLG)
      *>    //SYSOUT   DD SYSOUT=*
      *>
      *>  Change Log:
      *>    1991-04-15  SLW  Initial — simple batch formatter
      *>    1999-06-01  Y2K  Assessment — flagged date fields
      *>    2002-01-15  Y2K  Remediation — added 4-digit year support
      *>    2002-03-20  Y2K  "Cleanup" — started refactoring, gave up
      *>
      *>  Y2K REMEDIATION NOTES:
      *>    This program was "fixed" for Y2K by adding parallel 4-digit
      *>    year fields alongside the original 2-digit fields. The Y2K
      *>    team planned to remove the old fields after validation but
      *>    never did. Result: every date operation is done twice (once
      *>    for the old 2-digit field, once for the new 4-digit field).
      *>
      *>  HALF-FINISHED REFACTOR:
      *>    The Y2K team started converting the output format from
      *>    fixed-width to pipe-delimited. They finished the outbound
      *>    file format but never updated the report format. So the
      *>    outbound file is pipe-delimited (new) and the report is
      *>    still fixed-width (old). Two formats, one program.
      *>
      *>  OUTPUT FORMAT (pipe-delimited, settlement-compatible):
      *>    SOURCE_ACCT|DEST_ACCT|AMOUNT|DESCRIPTION|DAY
      *>
      *>================================================================*

       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYBATCH.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT EMPLOYEE-FILE
               ASSIGN TO "EMPLOYEES.DAT"
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-EMP-STATUS.
           SELECT OUTBOUND-FILE
               ASSIGN TO "OUTBOUND.DAT"
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-OUT-STATUS.

       DATA DIVISION.
       FILE SECTION.
       FD  EMPLOYEE-FILE.
           COPY "EMPREC.cpy".
       FD  OUTBOUND-FILE.
       01  OUTBOUND-RECORD         PIC X(200).

       WORKING-STORAGE SECTION.

      *> File statuses
       01  WS-FILE-STATUSES.
           05  WS-EMP-STATUS       PIC X(2).
           05  WS-OUT-STATUS       PIC X(2).

       01  WS-EOF-FLAG             PIC X(1) VALUE 'N'.
           88  WS-EOF              VALUE 'Y'.

      *> Command line args
       01  WS-CMD-ARGS.
           05  WS-ARG-DAY          PIC 9(8) VALUE 0.

      *> ── Y2K: Parallel date fields (old + new) ─────────────────
      *> The Y2K team added WS-DATE-FULL alongside WS-DATE-SHORT.
      *> Both are populated. Both are written to output. Neither is
      *> ever removed. Classic Y2K remediation artifact.
       01  WS-DATE-FIELDS.
           05  WS-DATE-FULL        PIC 9(8) VALUE 0.
           05  WS-DATE-SHORT       PIC 9(6) VALUE 0.
      *>   Y2K: "temporary" conversion workspace
           05  WS-DATE-WORK.
               10  WS-DW-CC        PIC 9(2).
               10  WS-DW-YY        PIC 9(2).
               10  WS-DW-MM        PIC 9(2).
               10  WS-DW-DD        PIC 9(2).
      *>   Y2K: "window" for 2-digit year conversion
      *>   If YY >= 50, assume 19XX. If YY < 50, assume 20XX.
      *>   In 2026, this is fine. In 2050, this breaks again.
           05  WS-Y2K-PIVOT        PIC 9(2) VALUE 50.
      *>   Y2K: Conversion counter (how many dates were converted)
           05  WS-Y2K-CONV-COUNT   PIC 9(5) VALUE 0.

      *> ── Payroll computation fields ────────────────────────────
       01  WS-PAY-FIELDS.
           05  WS-GROSS-PAY        PIC S9(7)V99 COMP-3.
           05  WS-NET-PAY          PIC S9(7)V99 COMP-3.
           05  WS-TAX-AMOUNT       PIC S9(7)V99 COMP-3.
           05  WS-DED-AMOUNT       PIC S9(7)V99 COMP-3.

      *> ── Output record construction ────────────────────────────
      *> Y2K: Pipe-delimited format for outbound settlement file.
      *> Matches the existing OUTBOUND.DAT format used by SETTLE.cob.
       01  WS-OUT-LINE.
           05  WS-OL-SRC-ACCT      PIC X(10).
           05  WS-OL-PIPE1         PIC X(1) VALUE '|'.
           05  WS-OL-DST-ACCT      PIC X(10).
           05  WS-OL-PIPE2         PIC X(1) VALUE '|'.
           05  WS-OL-AMOUNT        PIC 9(10)V99.
           05  WS-OL-PIPE3         PIC X(1) VALUE '|'.
           05  WS-OL-DESC          PIC X(40).
           05  WS-OL-PIPE4         PIC X(1) VALUE '|'.
           05  WS-OL-DAY           PIC 9(8).

      *> ── Counters ──────────────────────────────────────────────
       01  WS-COUNTERS.
           05  WS-EMP-COUNT        PIC 9(5) VALUE 0.
           05  WS-OUT-COUNT        PIC 9(5) VALUE 0.
           05  WS-SKIP-COUNT       PIC 9(5) VALUE 0.
           05  WS-ERROR-COUNT      PIC 9(5) VALUE 0.
           05  WS-BATCH-TOTAL      PIC S9(9)V99 COMP-3 VALUE 0.

      *> ── Y2K: Tracing (excessive DISPLAYs) ────────────────────
      *> The Y2K team added DISPLAY statements at every decision
      *> point "for validation." They were supposed to be removed
      *> after Y2K testing. They never were. Each run produces
      *> hundreds of trace lines that nobody reads.
       01  WS-TRACE-FLAG           PIC X(1) VALUE 'Y'.
           88  WS-TRACE-ON         VALUE 'Y'.
           88  WS-TRACE-OFF        VALUE 'N'.

      *> ── Old fixed-width report format (SLW 1991) ─────────────
      *> Never updated to pipe-delimited. Still uses 2-digit years.
       01  WS-REPORT-LINE.
           05  WS-RPT-EMP-ID       PIC X(7).
           05  WS-RPT-FILLER1      PIC X(1) VALUE ' '.
           05  WS-RPT-NAME         PIC X(25).
           05  WS-RPT-FILLER2      PIC X(1) VALUE ' '.
           05  WS-RPT-GROSS        PIC Z(7)9.99.
           05  WS-RPT-FILLER3      PIC X(1) VALUE ' '.
           05  WS-RPT-NET          PIC Z(7)9.99.
           05  WS-RPT-FILLER4      PIC X(1) VALUE ' '.
           05  WS-RPT-DATE-YY      PIC 9(2).

           COPY "PAYCOM.cpy".

       PROCEDURE DIVISION.

      *>================================================================*
      *>  MAIN-PARA: Entry point
      *>  Y2K: Added "extensive" tracing
      *>================================================================*
       MAIN-PARA.
           ACCEPT WS-ARG-DAY FROM COMMAND-LINE
           IF WS-ARG-DAY = 0
               MOVE 20260301 TO WS-ARG-DAY
           END-IF

           MOVE WS-ARG-DAY TO WS-DATE-FULL

      *>   Y2K: Convert full date to components
           PERFORM Y2K-CONVERT-DATE

           IF WS-TRACE-ON
               DISPLAY "PAYBATCH|TRACE|START"
               DISPLAY "PAYBATCH|TRACE|DAY=" WS-DATE-FULL
               DISPLAY "PAYBATCH|TRACE|SHORT=" WS-DATE-SHORT
               DISPLAY "PAYBATCH|TRACE|CC=" WS-DW-CC
               DISPLAY "PAYBATCH|TRACE|YY=" WS-DW-YY
               DISPLAY "PAYBATCH|TRACE|MM=" WS-DW-MM
               DISPLAY "PAYBATCH|TRACE|DD=" WS-DW-DD
           END-IF

           DISPLAY "PAYBATCH|START|" WS-DATE-FULL

           OPEN INPUT EMPLOYEE-FILE
           IF WS-EMP-STATUS NOT = '00'
               DISPLAY "PAYBATCH|ERROR|EMPFILE|" WS-EMP-STATUS
               STOP RUN
           END-IF

           OPEN OUTPUT OUTBOUND-FILE

           PERFORM PROCESS-EMPLOYEE UNTIL WS-EOF

           CLOSE EMPLOYEE-FILE
           CLOSE OUTBOUND-FILE

           DISPLAY "PAYBATCH|SUMMARY"
           DISPLAY "PAYBATCH|EMPLOYEES|" WS-EMP-COUNT
           DISPLAY "PAYBATCH|RECORDS|" WS-OUT-COUNT
           DISPLAY "PAYBATCH|SKIPPED|" WS-SKIP-COUNT
           DISPLAY "PAYBATCH|ERRORS|" WS-ERROR-COUNT
           DISPLAY "PAYBATCH|BATCH-TOTAL|" WS-BATCH-TOTAL
           IF WS-TRACE-ON
               DISPLAY "PAYBATCH|TRACE|Y2K-CONVERSIONS="
                   WS-Y2K-CONV-COUNT
           END-IF
           DISPLAY "PAYBATCH|COMPLETE|" WS-DATE-FULL

           STOP RUN.

      *>================================================================*
      *>  PROCESS-EMPLOYEE: Read and format output
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

           IF WS-TRACE-ON
               DISPLAY "PAYBATCH|TRACE|READ|" EMP-ID "|"
                   EMP-STATUS
           END-IF

           IF NOT EMP-ACTIVE
               ADD 1 TO WS-SKIP-COUNT
               IF WS-TRACE-ON
                   DISPLAY "PAYBATCH|TRACE|SKIP|" EMP-ID
               END-IF
               EXIT PARAGRAPH
           END-IF

      *>   Simple payroll computation (tax at flat 30% for batch)
      *>   Y2K team: "We don't have time to integrate TAXCALC here.
      *>   Use 30% flat rate. It's just a batch estimate anyway."
      *>   This has been "temporary" since 2002.
           IF EMP-SALARIED
               COMPUTE WS-GROSS-PAY ROUNDED =
                   EMP-SALARY / 26
           ELSE
               COMPUTE WS-GROSS-PAY ROUNDED =
                   EMP-HOURLY-RATE * EMP-HOURS-WORKED
           END-IF

      *>   "Temporary" flat tax estimate
           COMPUTE WS-TAX-AMOUNT ROUNDED =
               WS-GROSS-PAY * 0.30

      *>   Minimal deduction estimate
           MOVE 0 TO WS-DED-AMOUNT
           IF EMP-MED-PREMIUM
               COMPUTE WS-DED-AMOUNT ROUNDED =
                   PAYCOM-MED-PREMIUM / 12
           ELSE IF EMP-MED-BASIC
               COMPUTE WS-DED-AMOUNT ROUNDED =
                   PAYCOM-MED-BASIC / 12
           END-IF

           COMPUTE WS-NET-PAY =
               WS-GROSS-PAY - WS-TAX-AMOUNT - WS-DED-AMOUNT

           IF WS-NET-PAY < 0
               MOVE 0 TO WS-NET-PAY
               ADD 1 TO WS-ERROR-COUNT
           END-IF

      *>   Write pipe-delimited outbound record
           MOVE EMP-ACCT-ID TO WS-OL-SRC-ACCT
           MOVE EMP-ACCT-ID TO WS-OL-DST-ACCT
           MOVE WS-NET-PAY TO WS-OL-AMOUNT
           INITIALIZE WS-OL-DESC
           STRING
               "Payroll deposit — " DELIMITED SIZE
               EMP-NAME DELIMITED SPACES
               INTO WS-OL-DESC
           END-STRING
           MOVE WS-DATE-FULL TO WS-OL-DAY

           WRITE OUTBOUND-RECORD FROM WS-OUT-LINE

           ADD 1 TO WS-OUT-COUNT
           ADD WS-NET-PAY TO WS-BATCH-TOTAL

           IF WS-TRACE-ON
               DISPLAY "PAYBATCH|TRACE|WROTE|" EMP-ID "|"
                   WS-NET-PAY
           END-IF

           DISPLAY "PAYBATCH|RECORD|" EMP-ID "|" WS-NET-PAY.

      *>================================================================*
      *>  Y2K-CONVERT-DATE: The Y2K conversion routine
      *>  Converts 8-digit date to components and back.
      *>  Populates BOTH old (6-digit) and new (8-digit) fields.
      *>  This runs for every date operation even though the input
      *>  is already in 8-digit format. Pure overhead.
      *>================================================================*
       Y2K-CONVERT-DATE.
           ADD 1 TO WS-Y2K-CONV-COUNT

      *>   Parse 8-digit date into components
           MOVE WS-DATE-FULL(1:2) TO WS-DW-CC
           MOVE WS-DATE-FULL(3:2) TO WS-DW-YY
           MOVE WS-DATE-FULL(5:2) TO WS-DW-MM
           MOVE WS-DATE-FULL(7:2) TO WS-DW-DD

      *>   Build 6-digit short date (YYMMDD)
           STRING WS-DW-YY WS-DW-MM WS-DW-DD
               DELIMITED SIZE
               INTO WS-DATE-SHORT
           END-STRING

      *>   Y2K: Validate century
           IF WS-DW-CC NOT = 19 AND WS-DW-CC NOT = 20
               DISPLAY "PAYBATCH|Y2K-WARN|INVALID-CC|" WS-DW-CC
           END-IF

           IF WS-TRACE-ON
               DISPLAY "PAYBATCH|TRACE|Y2K-CONV|"
                   WS-DATE-FULL "|" WS-DATE-SHORT
           END-IF.

      *>================================================================*
      *>  Y2K-REVERSE-CONVERT: Convert 2-digit year to 4-digit
      *>  Uses the windowing technique: YY >= 50 → 19XX, else 20XX
      *>  DEAD CODE: This is never called. The Y2K team added it
      *>  "just in case" there were any 2-digit dates in input.
      *>  There aren't. But removing it requires a change request.
      *>================================================================*
       Y2K-REVERSE-CONVERT.
           ADD 1 TO WS-Y2K-CONV-COUNT

           IF WS-DW-YY >= WS-Y2K-PIVOT
               MOVE 19 TO WS-DW-CC
           ELSE
               MOVE 20 TO WS-DW-CC
           END-IF

           STRING WS-DW-CC WS-DW-YY WS-DW-MM WS-DW-DD
               DELIMITED SIZE
               INTO WS-DATE-FULL
           END-STRING

           IF WS-TRACE-ON
               DISPLAY "PAYBATCH|TRACE|Y2K-REV|"
                   WS-DATE-SHORT "|" WS-DATE-FULL
           END-IF.

      *>================================================================*
      *>  DEAD-REPORT-FORMAT: Old fixed-width report output
      *>  SLW 1991: Original report format with 2-digit years.
      *>  Y2K team started converting this to 4-digit years,
      *>  realized it would break the downstream report parser,
      *>  and gave up. The pipe-delimited format above is the
      *>  "new" format; this is the "old" format that no system
      *>  reads anymore but "we can't delete it."
      *>================================================================*
       DEAD-REPORT-FORMAT.
           MOVE EMP-ID TO WS-RPT-EMP-ID
           MOVE EMP-NAME TO WS-RPT-NAME
           MOVE WS-GROSS-PAY TO WS-RPT-GROSS
           MOVE WS-NET-PAY TO WS-RPT-NET
           MOVE WS-DW-YY TO WS-RPT-DATE-YY
           DISPLAY WS-REPORT-LINE.
