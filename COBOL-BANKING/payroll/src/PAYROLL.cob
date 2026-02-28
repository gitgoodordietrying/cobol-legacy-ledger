      *>================================================================*
      *>  EDUCATIONAL NOTE: This program contains INTENTIONAL anti-patterns
      *>  for teaching purposes. See KNOWN_ISSUES.md for the full catalog.
      *>  All other COBOL in this project follows clean, modern practices.
      *>================================================================*
      *>  Program:     PAYROLL.cob
      *>  System:      ENTERPRISE PAYROLL PROCESSOR — Main Controller
      *>  Author:      JRK (original 1974), PMR (mods 1983), SLW (1991)
      *>  Written:     1974-03-15 (IBM System/370 Model 158)
      *>
      *>  JCL Reference:
      *>    //PAYRL100 JOB (ACCT),'PAYROLL MASTER',CLASS=A,
      *>    //         MSGCLASS=X,MSGLEVEL=(1,1)
      *>    //STEP01   EXEC PGM=PAYROLL,REGION=512K
      *>    //EMPFILE  DD DSN=PAYRL.EMPLOYEE.MASTER,DISP=SHR
      *>    //PAYFILE  DD DSN=PAYRL.PAYSTUB.YYYYMMDD,DISP=(NEW,CATLG)
      *>    //OUTBNDS  DD DSN=PAYRL.OUTBOUND.YYYYMMDD,DISP=(NEW,CATLG)
      *>    //SYSOUT   DD SYSOUT=*
      *>
      *>  Change Log:
      *>    1974-03-15  JRK  Initial implementation — batch payroll
      *>    1974-06-22  JRK  Added overtime calc (GO TO P-040)
      *>    1975-01-10  JRK  Bug fix — ALTER P-030 TO PROCEED TO P-045
      *>    1983-09-01  PMR  Added PERFORM THRU for tax calc
      *>    1991-04-15  SLW  Added deductions call, broke P-060
      *>    1991-11-30  SLW  "Fixed" P-060 with another GO TO
      *>    2002-01-15  Y2K  Added date handling, left old code
      *>
      *>  WARNING: This program uses GO TO and ALTER statements.
      *>  ALTER modifies GO TO targets AT RUNTIME. If you don't
      *>  understand ALTER, DO NOT MODIFY THIS PROGRAM. You will
      *>  break the paragraph flow and nothing will tell you.
      *>
      *>  Paragraph Flow (nominal path — ALTER can change this):
      *>    P-000 → P-010 → P-020 → P-030 → P-040 → P-050 →
      *>    P-060 → P-070 → P-080 → P-090
      *>
      *>================================================================*

       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYROLL.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT EMPLOYEE-FILE
               ASSIGN TO "EMPLOYEES.DAT"
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-EMP-STATUS.
           SELECT PAYSTUB-FILE
               ASSIGN TO "PAYSTUBS.DAT"
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-PAY-STATUS.
           SELECT OUTBOUND-FILE
               ASSIGN TO "OUTBOUND.DAT"
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-OB-STATUS.

       DATA DIVISION.
       FILE SECTION.
       FD  EMPLOYEE-FILE.
           COPY "EMPREC.cpy".
       FD  PAYSTUB-FILE.
           COPY "PAYREC.cpy".
       FD  OUTBOUND-FILE.
       01  OUTBOUND-RECORD         PIC X(200).

       WORKING-STORAGE SECTION.

      *> File status variables
       01  WS-FILE-STATUSES.
           05  WS-EMP-STATUS       PIC X(2).
           05  WS-PAY-STATUS       PIC X(2).
           05  WS-OB-STATUS        PIC X(2).

      *> JRK: Cryptic working fields — P-010 through P-090 use these
      *> DO NOT RENAME — ALTER targets depend on paragraph names,
      *> and paragraphs reference these by exact name
       01  WS-WORK-FIELDS.
           05  WK-GROSS            PIC S9(7)V99 COMP-3.
           05  WK-NET              PIC S9(7)V99 COMP-3.
           05  WK-TAX-TOT         PIC S9(7)V99 COMP-3.
           05  WK-DED-TOT         PIC S9(7)V99 COMP-3.
           05  WK-OT-HRS          PIC S9(4) COMP.
           05  WK-OT-PAY          PIC S9(7)V99 COMP-3.
           05  WK-REG-PAY         PIC S9(7)V99 COMP-3.
           05  WK-PERIODS         PIC S9(4) COMP VALUE 26.
      *>   JRK: 26 pay periods per year (biweekly)

      *> Counters and flags
       01  WS-COUNTERS.
           05  WS-EMP-COUNT        PIC 9(5) VALUE 0.
           05  WS-PROC-COUNT       PIC 9(5) VALUE 0.
           05  WS-SKIP-COUNT       PIC 9(5) VALUE 0.
           05  WS-ERROR-COUNT      PIC 9(5) VALUE 0.
           05  WS-EOF-FLAG         PIC X(1) VALUE 'N'.
               88  WS-EOF          VALUE 'Y'.
               88  WS-NOT-EOF      VALUE 'N'.

      *> SLW 1991: Added batch total for daily limit check
       01  WS-BATCH-TOTALS.
           05  WS-BATCH-GROSS      PIC S9(9)V99 COMP-3
                                   VALUE 0.
           05  WS-BATCH-NET        PIC S9(9)V99 COMP-3
                                   VALUE 0.

      *> Date fields — mixed old/new formats
       01  WS-DATE-FIELDS.
           05  WS-CURRENT-DATE.
               10  WS-DATE-YYYY    PIC 9(4).
               10  WS-DATE-MM      PIC 9(2).
               10  WS-DATE-DD      PIC 9(2).
           05  WS-PAY-PERIOD       PIC 9(4) VALUE 0.
           05  WS-RUN-DAY          PIC 9(8) VALUE 0.
      *>   Y2K: Old 2-digit year field — kept for "reports"
           05  WS-DATE-YY          PIC 9(2) VALUE 0.

      *> Outbound record for settlement
       01  WS-OUTBOUND-LINE.
           05  WS-OB-ACCT          PIC X(10).
           05  WS-OB-PIPE1         PIC X(1) VALUE '|'.
           05  WS-OB-DEST          PIC X(10).
           05  WS-OB-PIPE2         PIC X(1) VALUE '|'.
           05  WS-OB-AMOUNT        PIC 9(10)V99.
           05  WS-OB-PIPE3         PIC X(1) VALUE '|'.
           05  WS-OB-DESC          PIC X(40).
           05  WS-OB-PIPE4         PIC X(1) VALUE '|'.
           05  WS-OB-DAY           PIC 9(8).

      *> Command line args
       01  WS-CMD-ARGS.
           05  WS-ARG-DAY          PIC 9(8) VALUE 0.

      *> Formatted output line
       01  WS-DISPLAY-LINE         PIC X(80).

      *> JRK: Magic number storage — never documented what these mean
       01  WS-MAGIC.
           05  WK-M1               PIC 9(3) VALUE 40.
           05  WK-M2               PIC 9V99 VALUE 1.50.
           05  WK-M3               PIC 9(3) VALUE 80.

           COPY "PAYCOM.cpy".
           COPY "TAXREC.cpy".

       PROCEDURE DIVISION.

      *>================================================================*
      *>  P-000: MAINLINE — The nominal starting point
      *>  JRK: "This paragraph should only call other paragraphs."
      *>  Reality: It also sets up ALTER chains.
      *>================================================================*
       P-000.
           ACCEPT WS-ARG-DAY FROM COMMAND-LINE
           IF WS-ARG-DAY = 0
               MOVE 20260301 TO WS-ARG-DAY
           END-IF
           MOVE WS-ARG-DAY TO WS-RUN-DAY
           MOVE WS-ARG-DAY(1:4) TO WS-DATE-YYYY
           MOVE WS-ARG-DAY(5:2) TO WS-DATE-MM
           MOVE WS-ARG-DAY(7:2) TO WS-DATE-DD

           DISPLAY "PAYROLL|START|" WS-RUN-DAY

      *>   JRK: ALTER sets up the paragraph chain at runtime.
      *>   After P-020, go to P-030 (type check).
      *>   P-030 then decides: salaried → P-040, hourly → P-045.
      *>   This is how "branching" was done before EVALUATE.
           ALTER P-030 TO PROCEED TO P-040

           OPEN INPUT EMPLOYEE-FILE
           IF WS-EMP-STATUS NOT = '00'
               DISPLAY "PAYROLL|ERROR|EMPFILE|" WS-EMP-STATUS
               GO TO P-090
           END-IF

           OPEN OUTPUT PAYSTUB-FILE
           OPEN OUTPUT OUTBOUND-FILE

           PERFORM P-010

           GO TO P-080.

      *>================================================================*
      *>  P-010: READ LOOP — Reads employees one at a time
      *>  JRK: Uses GO TO for loop instead of PERFORM UNTIL
      *>================================================================*
       P-010.
           READ EMPLOYEE-FILE
               AT END
                   SET WS-EOF TO TRUE
                   GO TO P-080
           END-READ

           ADD 1 TO WS-EMP-COUNT

      *>   Skip non-active employees
           IF NOT EMP-ACTIVE
               ADD 1 TO WS-SKIP-COUNT
               DISPLAY "PAYROLL|SKIP|" EMP-ID "|" EMP-STATUS
               GO TO P-010
           END-IF

           GO TO P-020.

      *>================================================================*
      *>  P-020: COMPUTE GROSS PAY — Dispatches by pay type
      *>  JRK: Falls through to P-030 for type branching
      *>================================================================*
       P-020.
           MOVE 0 TO WK-GROSS
           MOVE 0 TO WK-OT-HRS
           MOVE 0 TO WK-OT-PAY
           MOVE 0 TO WK-REG-PAY
           MOVE 0 TO WK-TAX-TOT
           MOVE 0 TO WK-DED-TOT
           MOVE 0 TO WK-NET

      *>   Determine pay period number (crude — day of year / 14)
           COMPUTE WS-PAY-PERIOD =
               FUNCTION INTEGER-OF-DATE(WS-RUN-DAY) / 14 + 1

           GO TO P-030.

      *>================================================================*
      *>  P-030: TYPE DISPATCH — This GO TO is modified by ALTER
      *>  JRK: ALTER P-030 TO PROCEED TO P-040 (salaried)
      *>       ALTER P-030 TO PROCEED TO P-045 (hourly)
      *>  If you don't understand ALTER, this looks like it always
      *>  goes to P-040. But the target changes at runtime.
      *>================================================================*
       P-030.
      *>   This GO TO's target is set by ALTER in P-000 and P-020
           GO TO P-040.

      *>================================================================*
      *>  P-040: SALARIED PAY CALCULATION
      *>  JRK: Divides annual salary by WK-PERIODS (26)
      *>================================================================*
       P-040.
           IF EMP-SALARIED
      *>       Salaried: annual / 26 pay periods
               COMPUTE WK-REG-PAY ROUNDED =
                   EMP-SALARY / WK-PERIODS
               MOVE WK-REG-PAY TO WK-GROSS
      *>       JRK: Salaried employees get no overtime
      *>       (but we still fall through to P-050, which is fine
      *>       because WK-OT-PAY is already 0)
               GO TO P-050
           END-IF
      *>   If not salaried, must be hourly — fall to P-045
           ALTER P-030 TO PROCEED TO P-045
           GO TO P-045.

      *>================================================================*
      *>  P-045: HOURLY PAY CALCULATION
      *>  JRK 1974-06-22: Added overtime (time and a half after 40)
      *>  WK-M1 = 40 (standard hours), WK-M2 = 1.50 (OT multiplier)
      *>================================================================*
       P-045.
           IF EMP-HOURLY
      *>       Regular hours (up to 40)
               IF EMP-HOURS-WORKED > WK-M1
                   COMPUTE WK-REG-PAY ROUNDED =
                       EMP-HOURLY-RATE * WK-M1
                   COMPUTE WK-OT-HRS =
                       EMP-HOURS-WORKED - WK-M1
                   COMPUTE WK-OT-PAY ROUNDED =
                       EMP-HOURLY-RATE * WK-M2 * WK-OT-HRS
               ELSE
                   COMPUTE WK-REG-PAY ROUNDED =
                       EMP-HOURLY-RATE * EMP-HOURS-WORKED
                   MOVE 0 TO WK-OT-PAY
               END-IF

               COMPUTE WK-GROSS = WK-REG-PAY + WK-OT-PAY
           END-IF

      *>   Reset ALTER for next employee
           ALTER P-030 TO PROCEED TO P-040
           GO TO P-050.

      *>================================================================*
      *>  P-050: TAX CALCULATION — Calls TAXCALC via PERFORM THRU
      *>  PMR 1983: "PERFORM THRU is standard practice"
      *>  (It's actually dangerous — see TAXCALC.cob KNOWN_ISSUES)
      *>================================================================*
       P-050.
      *>   Set up tax work fields
           MOVE WK-GROSS TO TAX-GROSS-PAY
           SET TAX-OK TO TRUE

      *>   PMR: Call tax calculation paragraphs as a range
           PERFORM TX-COMPUTE-FED THRU TX-COMPUTE-EXIT

           IF TAX-ERROR
               ADD 1 TO WS-ERROR-COUNT
               DISPLAY "PAYROLL|TAX-ERR|" EMP-ID
               GO TO P-010
           END-IF

           MOVE TAX-TOTAL-AMOUNT TO WK-TAX-TOT

           GO TO P-060.

      *>================================================================*
      *>  P-060: DEDUCTIONS — Added by SLW in 1991
      *>  SLW: "Just compute deductions inline, no need for a sub"
      *>  SLW (later): "OK fine, I'll add a PERFORM for it"
      *>================================================================*
       P-060.
           MOVE 0 TO WK-DED-TOT

      *>   Medical deduction (per pay period = annual / 12 / 2.167)
      *>   SLW: "close enough" — should be /26 not /12/2.167
           IF EMP-MED-BASIC
               COMPUTE WK-DED-TOT ROUNDED =
                   PAYCOM-MED-BASIC / 12
           END-IF
           IF EMP-MED-PREMIUM
               COMPUTE WK-DED-TOT ROUNDED =
                   PAYCOM-MED-PREMIUM / 12
           END-IF

      *>   Dental
           IF EMP-HAS-DENTAL
               ADD PAYCOM-DENTAL-COST TO WK-DED-TOT
           END-IF

      *>   401(k) employee contribution
           IF EMP-401K-PCT > 0
               COMPUTE WK-DED-TOT ROUNDED =
                   WK-DED-TOT + (WK-GROSS * EMP-401K-PCT)
           END-IF

           GO TO P-070.

      *>================================================================*
      *>  P-070: NET PAY — Gross minus taxes minus deductions
      *>  JRK original, modified by everyone
      *>================================================================*
       P-070.
           COMPUTE WK-NET ROUNDED =
               WK-GROSS - WK-TAX-TOT - WK-DED-TOT

      *>   Sanity check — net pay should not be negative
           IF WK-NET < 0
               DISPLAY "PAYROLL|NEG-NET|" EMP-ID "|" WK-NET
               MOVE 0 TO WK-NET
               ADD 1 TO WS-ERROR-COUNT
           END-IF

      *>   Accumulate batch totals
           ADD WK-GROSS TO WS-BATCH-GROSS
           ADD WK-NET TO WS-BATCH-NET
           ADD 1 TO WS-PROC-COUNT

      *>   Write pay stub
           MOVE EMP-ID TO PAY-EMP-ID
           MOVE EMP-NAME TO PAY-EMP-NAME
           MOVE WS-PAY-PERIOD TO PAY-PERIOD-NUM
           MOVE WK-GROSS TO PAY-GROSS
           MOVE TAX-FED-AMOUNT TO PAY-FED-TAX
           MOVE TAX-STATE-AMOUNT TO PAY-STATE-TAX
           MOVE TAX-FICA-AMOUNT TO PAY-FICA
           MOVE WK-DED-TOT TO PAY-MEDICAL
           MOVE 0 TO PAY-DENTAL
           MOVE 0 TO PAY-401K
           MOVE WK-NET TO PAY-NET
           MOVE EMP-BANK-CODE TO PAY-DEST-BANK
           MOVE EMP-ACCT-ID TO PAY-DEST-ACCT
           MOVE WS-RUN-DAY TO PAY-DATE-FULL
      *>   Y2K: Still writing 2-digit year for "backwards compat"
           MOVE WS-DATE-YY TO PAY-DATE-YY

           WRITE PAY-STUB-RECORD

      *>   Write outbound settlement record
           MOVE EMP-ACCT-ID TO WS-OB-ACCT
           MOVE EMP-ACCT-ID TO WS-OB-DEST
           MOVE WK-NET TO WS-OB-AMOUNT
           STRING
               "Payroll deposit — " DELIMITED SIZE
               EMP-NAME DELIMITED SPACES
               INTO WS-OB-DESC
           END-STRING
           MOVE WS-RUN-DAY TO WS-OB-DAY

           WRITE OUTBOUND-RECORD FROM WS-OUTBOUND-LINE

           DISPLAY "PAYROLL|PAID|" EMP-ID "|" WK-NET

      *>   Loop back for next employee
           GO TO P-010.

      *>================================================================*
      *>  P-080: WRAP-UP — Close files and display totals
      *>================================================================*
       P-080.
           CLOSE EMPLOYEE-FILE
           CLOSE PAYSTUB-FILE
           CLOSE OUTBOUND-FILE

           DISPLAY "PAYROLL|SUMMARY"
           DISPLAY "PAYROLL|TOTAL-EMP|" WS-EMP-COUNT
           DISPLAY "PAYROLL|PROCESSED|" WS-PROC-COUNT
           DISPLAY "PAYROLL|SKIPPED|" WS-SKIP-COUNT
           DISPLAY "PAYROLL|ERRORS|" WS-ERROR-COUNT
           DISPLAY "PAYROLL|BATCH-GROSS|" WS-BATCH-GROSS
           DISPLAY "PAYROLL|BATCH-NET|" WS-BATCH-NET
           DISPLAY "PAYROLL|COMPLETE|" WS-RUN-DAY

           GO TO P-090.

      *>================================================================*
      *>  P-085: DEAD PARAGRAPH — Was overtime cap check (JRK 1975)
      *>  Removed when SLW restructured P-045. Never deleted.
      *>  Nothing PERFORMs or GO TOs here. Pure dead code.
      *>================================================================*
       P-085.
           IF WK-OT-HRS > WK-M3
               MOVE WK-M3 TO WK-OT-HRS
               DISPLAY "PAYROLL|OT-CAP|" EMP-ID
           END-IF
           GO TO P-050.

      *>================================================================*
      *>  P-090: EXIT POINT
      *>================================================================*
       P-090.
           STOP RUN.

      *>================================================================*
      *>  TX-COMPUTE-FED: Federal tax computation
      *>  PMR 1983: Simplified bracket lookup
      *>  PERFORM THRU range: TX-COMPUTE-FED THRU TX-COMPUTE-EXIT
      *>================================================================*
       TX-COMPUTE-FED.
      *>   PMR: "Use simple bracket. Close enough for demo."
           IF TAX-GROSS-PAY > 100000
               COMPUTE TAX-FED-AMOUNT ROUNDED =
                   TAX-GROSS-PAY * 0.32
           ELSE IF TAX-GROSS-PAY > 50000
               COMPUTE TAX-FED-AMOUNT ROUNDED =
                   TAX-GROSS-PAY * 0.22
           ELSE IF TAX-GROSS-PAY > 20000
               COMPUTE TAX-FED-AMOUNT ROUNDED =
                   TAX-GROSS-PAY * 0.12
           ELSE
               COMPUTE TAX-FED-AMOUNT ROUNDED =
                   TAX-GROSS-PAY * 0.10
           END-IF.

      *>   State tax — PMR says "5%" but uses 7.25%
       TX-COMPUTE-STATE.
           COMPUTE TAX-STATE-AMOUNT ROUNDED =
               TAX-GROSS-PAY * 0.0725.

      *>   FICA
       TX-COMPUTE-FICA.
           COMPUTE TAX-FICA-AMOUNT ROUNDED =
               TAX-GROSS-PAY * PAYCOM-FICA-RATE.

      *>   Total
       TX-COMPUTE-TOTAL.
           COMPUTE TAX-TOTAL-AMOUNT =
               TAX-FED-AMOUNT + TAX-STATE-AMOUNT +
               TAX-FICA-AMOUNT.

       TX-COMPUTE-EXIT.
           EXIT.
