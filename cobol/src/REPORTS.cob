      *================================================================*
      * REPORTS.cob — Reporting and Reconciliation
      * System: cobol-legacy-ledger | Purpose: Generate reports
      * Operations: STATEMENT, LEDGER, EOD, AUDIT
      * Output Format: Pipe-delimited to STDOUT
      *================================================================*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. REPORTS.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ACCOUNTS-FILE
               ASSIGN TO "ACCOUNTS.DAT"
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-FILE-STATUS.
           SELECT TRANSACT-FILE
               ASSIGN TO "TRANSACT.DAT"
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-TX-STATUS.

       DATA DIVISION.
       FILE SECTION.
       FD  ACCOUNTS-FILE.
       COPY "ACCTREC.cpy".
       FD  TRANSACT-FILE.
       COPY "TRANSREC.cpy".

       WORKING-STORAGE SECTION.
       01  WS-FILE-STATUS         PIC XX VALUE SPACES.
       01  WS-TX-STATUS           PIC XX VALUE SPACES.
       01  WS-OPERATION           PIC X(10) VALUE SPACES.
       01  WS-TOTAL-BALANCE       PIC S9(15)V99 VALUE 0.
       01  WS-ACCOUNT-COUNT       PIC 9(6) VALUE 0.
       COPY "COMCODE.cpy".

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           ACCEPT WS-OPERATION FROM COMMAND-LINE

           EVALUATE WS-OPERATION
               WHEN "LEDGER"
                   PERFORM PRINT-LEDGER
               WHEN "STATEMENT"
                   PERFORM PRINT-STATEMENT
               WHEN "EOD"
                   PERFORM PRINT-EOD
               WHEN "AUDIT"
                   PERFORM PRINT-AUDIT
               WHEN OTHER
                   DISPLAY "RESULT|99"
           END-EVALUATE

           STOP RUN.

       PRINT-LEDGER.
           OPEN INPUT ACCOUNTS-FILE
           PERFORM UNTIL 1 = 0
               READ ACCOUNTS-FILE
                   AT END
                       CLOSE ACCOUNTS-FILE
                       EXIT PERFORM
               END-READ
               DISPLAY "ACCOUNT|" ACCT-ID "|" ACCT-NAME
                   "|" ACCT-TYPE "|" ACCT-BALANCE
                   "|" ACCT-STATUS
               ADD 1 TO WS-ACCOUNT-COUNT
               ADD ACCT-BALANCE TO WS-TOTAL-BALANCE
           END-PERFORM
           DISPLAY "SUMMARY|TOTAL-BALANCE|" WS-TOTAL-BALANCE
               "|" WS-ACCOUNT-COUNT "|ACCOUNTS"
           DISPLAY "RESULT|00".

       PRINT-STATEMENT.
           DISPLAY "RESULT|00".

       PRINT-EOD.
           DISPLAY "RESULT|00".

       PRINT-AUDIT.
           DISPLAY "RESULT|00".
