      *>================================================================*
      *>  EDUCATIONAL NOTE: This program contains INTENTIONAL anti-patterns
      *>  for teaching purposes. See KNOWN_ISSUES.md for the full catalog.
      *>  All other COBOL in this project follows clean, modern practices.
      *>================================================================*
      *>  Program:     TAXCALC.cob
      *>  System:      ENTERPRISE PAYROLL — Tax Computation Engine
      *>  Author:      PMR (original 1983), JRK (mods 1992)
      *>  Written:     1983-09-01 (IBM System/370 Model 168)
      *>
      *>  JCL Reference:
      *>    //PAYRL200 JOB (ACCT),'TAX CALC',CLASS=A
      *>    //STEP01   EXEC PGM=TAXCALC
      *>    //EMPFILE  DD DSN=PAYRL.EMPLOYEE.MASTER,DISP=SHR
      *>    //TAXFILE  DD DSN=PAYRL.TAX.BRACKETS,DISP=SHR
      *>    //SYSOUT   DD SYSOUT=*
      *>
      *>  Change Log:
      *>    1983-09-01  PMR  Initial — federal/state/FICA calculation
      *>    1983-11-15  PMR  Added bracket table (TAXREC.cpy)
      *>    1986-03-20  PMR  Tax Reform Act — new brackets
      *>    1992-01-10  JRK  Added top bracket, new state rules
      *>    1992-06-30  JRK  "Temporary" flat tax option (still here)
      *>    1997-08-22  PMR  Updated FICA limit (last update ever)
      *>    2002-01-15  Y2K  Added 4-digit year (left old code)
      *>
      *>  WARNING: This program has 6-level nested IF statements
      *>  without END-IF. Indentation is the ONLY way to follow
      *>  the logic. The 1992 bracket (JRK) has a comment saying
      *>  "5% surcharge" but the code computes 7.25%. Trust the
      *>  code, not the comments.
      *>
      *>================================================================*

       IDENTIFICATION DIVISION.
       PROGRAM-ID. TAXCALC.

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

      *> PMR: Annualized gross for bracket lookup
       01  WS-ANNUAL-GROSS         PIC S9(9)V99 COMP-3.
       01  WS-PERIOD-GROSS         PIC S9(7)V99 COMP-3.

      *> PMR: Tax computation work areas
       01  WS-TAX-WORK.
           05  WS-FED-TAX          PIC S9(7)V99 COMP-3.
           05  WS-STATE-TAX        PIC S9(7)V99 COMP-3.
           05  WS-FICA-TAX         PIC S9(7)V99 COMP-3.
           05  WS-TOTAL-TAX        PIC S9(7)V99 COMP-3.
           05  WS-NET-PAY          PIC S9(7)V99 COMP-3.

      *> JRK 1992: "temporary" flat tax toggle
       01  WS-FLAT-TAX-FLAG        PIC X(1) VALUE 'N'.
           88  WS-USE-FLAT-TAX     VALUE 'Y'.
           88  WS-USE-BRACKETS     VALUE 'N'.

      *> Counters
       01  WS-COUNTERS.
           05  WS-EMP-COUNT        PIC 9(5) VALUE 0.
           05  WS-BRACKET-IDX      PIC 9(2) VALUE 0.

      *> PMR: Hardcoded brackets that OVERRIDE the copybook table
      *> "Just in case the copybook isn't loaded correctly"
       01  WS-HARDCODED-BRACKETS.
           05  WS-BRACKET-1-MAX    PIC S9(7)V99 COMP-3
                                   VALUE 10000.00.
           05  WS-BRACKET-1-RATE   PIC 9V9999 VALUE 0.1000.
           05  WS-BRACKET-2-MAX    PIC S9(7)V99 COMP-3
                                   VALUE 40000.00.
           05  WS-BRACKET-2-RATE   PIC 9V9999 VALUE 0.1200.
           05  WS-BRACKET-3-MAX    PIC S9(7)V99 COMP-3
                                   VALUE 85000.00.
           05  WS-BRACKET-3-RATE   PIC 9V9999 VALUE 0.2200.
           05  WS-BRACKET-4-MAX    PIC S9(7)V99 COMP-3
                                   VALUE 165000.00.
           05  WS-BRACKET-4-RATE   PIC 9V9999 VALUE 0.2400.
           05  WS-BRACKET-5-MAX    PIC S9(7)V99 COMP-3
                                   VALUE 500000.00.
           05  WS-BRACKET-5-RATE   PIC 9V9999 VALUE 0.3200.
      *>   JRK 1992: "Top bracket for high earners"
           05  WS-BRACKET-6-MAX    PIC S9(7)V99 COMP-3
                                   VALUE 9999999.99.
           05  WS-BRACKET-6-RATE   PIC 9V9999 VALUE 0.3700.

      *> State tax rates per state code — JRK 1992
      *> PMR comment: "5% flat state tax"
      *> JRK code: 7.25% — the comment was never updated
       01  WS-STATE-RATES.
           05  WS-DEFAULT-STATE-RATE PIC 9V9999 VALUE 0.0725.

           COPY "TAXREC.cpy".
           COPY "PAYCOM.cpy".

       01  WS-CMD-ARGS.
           05  WS-ARG-PAY-PERIOD   PIC 9(4) VALUE 0.

       PROCEDURE DIVISION.

      *>================================================================*
      *>  MAIN-PARA: Entry point — standalone tax computation
      *>  When called standalone, reads employees and computes taxes.
      *>  When called via PERFORM THRU from PAYROLL.cob, the
      *>  TX-COMPUTE-* paragraphs are used directly.
      *>================================================================*
       MAIN-PARA.
           ACCEPT WS-ARG-PAY-PERIOD FROM COMMAND-LINE
           IF WS-ARG-PAY-PERIOD = 0
               MOVE 1 TO WS-ARG-PAY-PERIOD
           END-IF

           DISPLAY "TAXCALC|START|PERIOD|" WS-ARG-PAY-PERIOD

           OPEN INPUT EMPLOYEE-FILE
           IF WS-FILE-STATUS NOT = '00'
               DISPLAY "TAXCALC|ERROR|FILE|" WS-FILE-STATUS
               STOP RUN
           END-IF

           PERFORM READ-AND-CALC THRU READ-AND-CALC-EXIT
               UNTIL WS-EOF

           CLOSE EMPLOYEE-FILE
           DISPLAY "TAXCALC|COMPLETE|" WS-EMP-COUNT
           STOP RUN.

      *>================================================================*
      *>  READ-AND-CALC: Read one employee, compute taxes
      *>  PMR: Uses PERFORM THRU for the calculation range
      *>================================================================*
       READ-AND-CALC.
           READ EMPLOYEE-FILE
               AT END
                   SET WS-EOF TO TRUE
                   GO TO READ-AND-CALC-EXIT
           END-READ

           ADD 1 TO WS-EMP-COUNT

           IF NOT EMP-ACTIVE
               GO TO READ-AND-CALC-EXIT
           END-IF

      *>   Compute period gross pay
           IF EMP-SALARIED
               COMPUTE WS-PERIOD-GROSS ROUNDED =
                   EMP-SALARY / 26
           ELSE
               COMPUTE WS-PERIOD-GROSS ROUNDED =
                   EMP-HOURLY-RATE * EMP-HOURS-WORKED
           END-IF

      *>   Annualize for bracket lookup
           COMPUTE WS-ANNUAL-GROSS = WS-PERIOD-GROSS * 26

           PERFORM COMPUTE-FEDERAL THRU COMPUTE-FICA-EXIT

      *>   Compute total and net
           COMPUTE WS-TOTAL-TAX =
               WS-FED-TAX + WS-STATE-TAX + WS-FICA-TAX
           COMPUTE WS-NET-PAY =
               WS-PERIOD-GROSS - WS-TOTAL-TAX

           DISPLAY "TAXCALC|RESULT|" EMP-ID "|"
               WS-PERIOD-GROSS "|" WS-TOTAL-TAX "|" WS-NET-PAY.

       READ-AND-CALC-EXIT.
           EXIT.

      *>================================================================*
      *>  COMPUTE-FEDERAL: Federal tax with 6-level nested IF
      *>  PMR original, extended by JRK 1992.
      *>
      *>  WARNING: The nested IF below has NO END-IF terminators.
      *>  This is pre-COBOL-85 style. Each ELSE matches the nearest
      *>  unmatched IF. Indentation is cosmetic only — the compiler
      *>  ignores it. If you add a line in the wrong place, every
      *>  subsequent ELSE will bind to a different IF.
      *>
      *>  To follow the logic, count IF/ELSE pairs from the inside
      *>  out. The period at the end terminates ALL nested IFs.
      *>================================================================*
       COMPUTE-FEDERAL.
      *>   JRK 1992: "temporary" flat tax shortcut
           IF WS-USE-FLAT-TAX
               COMPUTE WS-FED-TAX ROUNDED =
                   WS-PERIOD-GROSS * 0.2000
           ELSE
      *>   PMR: Progressive brackets (nested IF, no END-IF)
      *>   6 levels deep — each ELSE matches its nearest IF
           IF WS-ANNUAL-GROSS > 500000
      *>       PMR: "Top bracket 37%" — JRK addition
               COMPUTE WS-FED-TAX ROUNDED =
                   WS-PERIOD-GROSS * WS-BRACKET-6-RATE
           ELSE
           IF WS-ANNUAL-GROSS > 165000
      *>       PMR: "Bracket 5 — 32%"
               COMPUTE WS-FED-TAX ROUNDED =
                   WS-PERIOD-GROSS * WS-BRACKET-5-RATE
           ELSE
           IF WS-ANNUAL-GROSS > 85000
      *>       PMR: "Bracket 4 — 24%"
               COMPUTE WS-FED-TAX ROUNDED =
                   WS-PERIOD-GROSS * WS-BRACKET-4-RATE
           ELSE
           IF WS-ANNUAL-GROSS > 40000
      *>       PMR: "Bracket 3 — 22%"
               COMPUTE WS-FED-TAX ROUNDED =
                   WS-PERIOD-GROSS * WS-BRACKET-3-RATE
           ELSE
           IF WS-ANNUAL-GROSS > 10000
      *>       PMR: "Bracket 2 — 12%"
               COMPUTE WS-FED-TAX ROUNDED =
                   WS-PERIOD-GROSS * WS-BRACKET-2-RATE
           ELSE
      *>       PMR: "Bracket 1 — 10%"
               COMPUTE WS-FED-TAX ROUNDED =
                   WS-PERIOD-GROSS * WS-BRACKET-1-RATE.
      *>   ^ Period terminates all 6 nested IFs at once.
      *>     This is legal COBOL but incredibly fragile.
      *>     Adding END-IF here would change the binding.

      *>================================================================*
      *>  COMPUTE-STATE: State tax calculation
      *>  PMR comment: "5% flat state tax rate"
      *>  JRK code: Uses WS-DEFAULT-STATE-RATE which is 0.0725 (7.25%)
      *>  KNOWN ISSUE: Comment says 5%, code does 7.25%. Trust the code.
      *>================================================================*
       COMPUTE-STATE.
      *>   PMR: "Apply standard 5% state tax"
      *>   (Actual rate: 7.25% — see WS-DEFAULT-STATE-RATE above)
           COMPUTE WS-STATE-TAX ROUNDED =
               WS-PERIOD-GROSS * WS-DEFAULT-STATE-RATE.

      *>================================================================*
      *>  COMPUTE-FICA: Social Security / Medicare
      *>  PMR: Uses PAYCOM-FICA-RATE from copybook
      *>  FICA limit check uses outdated 1997 cap ($160,200)
      *>================================================================*
       COMPUTE-FICA.
      *>   Check annual FICA wage base limit
           IF WS-ANNUAL-GROSS > PAYCOM-FICA-LIMIT
      *>       Over the limit — no FICA on this period
               MOVE 0 TO WS-FICA-TAX
           ELSE
               COMPUTE WS-FICA-TAX ROUNDED =
                   WS-PERIOD-GROSS * PAYCOM-FICA-RATE
           END-IF.

       COMPUTE-FICA-EXIT.
           EXIT.

      *>================================================================*
      *>  DEAD PARAGRAPHS — 1992 "new algorithm" never completed
      *>  JRK started a marginal rate implementation, then abandoned
      *>  it when told "the current one works fine, don't touch it."
      *>================================================================*
       COMPUTE-MARGINAL.
      *>   JRK 1992: "TODO — implement proper marginal rate calc"
      *>   "For now, the flat-per-bracket approach is close enough"
      *>   This paragraph is never PERFORMed or GO TO'd.
           MOVE 0 TO TAX-WORK-TEMP
           IF WS-ANNUAL-GROSS > WS-BRACKET-1-MAX
               COMPUTE TAX-WORK-TEMP =
                   WS-BRACKET-1-MAX * WS-BRACKET-1-RATE
           END-IF
      *>   JRK: "will finish this later" (1992, never finished)
           DISPLAY "MARGINAL-CALC-INCOMPLETE".

       COMPUTE-MARGINAL-EXIT.
           EXIT.
