      *> ================================================================
      *> REPORTS.cob — Reporting and Reconciliation
      *> System: cobol-legacy-ledger | Purpose: Generate reports
      *> Operations: STATEMENT, LEDGER, EOD, AUDIT
      *> Output Format: Pipe-delimited to STDOUT
      *> ================================================================
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
       01  WS-IN-ACCT-ID          PIC X(10) VALUE SPACES.
       01  WS-TOTAL-BALANCE       PIC S9(15)V99 VALUE 0.
       01  WS-CHECKING-BALANCE    PIC S9(15)V99 VALUE 0.
       01  WS-SAVINGS-BALANCE     PIC S9(15)V99 VALUE 0.
       01  WS-ACCOUNT-COUNT       PIC 9(6) VALUE 0.
       01  WS-TX-SUCCESS-COUNT    PIC 9(6) VALUE 0.
       01  WS-TX-NSF-COUNT        PIC 9(6) VALUE 0.
       01  WS-TX-LIMIT-COUNT      PIC 9(6) VALUE 0.
       01  WS-TX-BADACCT-COUNT    PIC 9(6) VALUE 0.
       01  WS-TX-FROZEN-COUNT     PIC 9(6) VALUE 0.
       COPY "COMCODE.cpy".

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           ACCEPT WS-OPERATION FROM COMMAND-LINE

           EVALUATE WS-OPERATION
               WHEN "LEDGER"
                   PERFORM PRINT-LEDGER
               WHEN "STATEMENT"
                   ACCEPT WS-IN-ACCT-ID FROM COMMAND-LINE
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
           DISPLAY "LEDGER|ACCOUNT DETAIL"
           OPEN INPUT ACCOUNTS-FILE
           PERFORM UNTIL 1 = 0
               READ ACCOUNTS-FILE
                   AT END
                       CLOSE ACCOUNTS-FILE
                       EXIT PERFORM
               END-READ
               DISPLAY "ACCOUNT|" ACCT-ID "|" ACCT-NAME
                   "|" ACCT-TYPE "|" ACCT-BALANCE
                   "|" ACCT-STATUS "|"
                   ACCT-OPEN-DATE "|"
                   ACCT-LAST-ACTIVITY
               ADD 1 TO WS-ACCOUNT-COUNT
               ADD ACCT-BALANCE TO WS-TOTAL-BALANCE
               IF ACCT-TYPE = 'C'
                   ADD ACCT-BALANCE TO WS-CHECKING-BALANCE
               ELSE
                   ADD ACCT-BALANCE TO WS-SAVINGS-BALANCE
               END-IF
           END-PERFORM
           DISPLAY "SUMMARY|TOTAL-BALANCE|" WS-TOTAL-BALANCE
               "|ACCOUNTS|" WS-ACCOUNT-COUNT
           DISPLAY "SUMMARY|CHECKING-BALANCE|" WS-CHECKING-BALANCE
           DISPLAY "SUMMARY|SAVINGS-BALANCE|" WS-SAVINGS-BALANCE
           DISPLAY "RESULT|00".

       PRINT-STATEMENT.
           DISPLAY "STATEMENT|ACCOUNT|" WS-IN-ACCT-ID
           OPEN INPUT TRANSACT-FILE
           PERFORM UNTIL 1 = 0
               READ TRANSACT-FILE
                   AT END
                       CLOSE TRANSACT-FILE
                       EXIT PERFORM
               END-READ
               IF TRANS-ACCT-ID = WS-IN-ACCT-ID
                   DISPLAY "TRANS|" TRANS-ID "|"
                       TRANS-TYPE "|" TRANS-AMOUNT "|"
                       TRANS-DATE "|" TRANS-TIME "|"
                       TRANS-DESC "|" TRANS-STATUS
               END-IF
           END-PERFORM
           DISPLAY "RESULT|00".

       PRINT-EOD.
           DISPLAY "EOD|END-OF-DAY RECONCILIATION"
           OPEN INPUT ACCOUNTS-FILE
           PERFORM UNTIL 1 = 0
               READ ACCOUNTS-FILE
                   AT END
                       CLOSE ACCOUNTS-FILE
                       EXIT PERFORM
               END-READ
               ADD ACCT-BALANCE TO WS-TOTAL-BALANCE
               IF ACCT-TYPE = 'C'
                   ADD ACCT-BALANCE TO WS-CHECKING-BALANCE
               ELSE
                   ADD ACCT-BALANCE TO WS-SAVINGS-BALANCE
               END-IF
           END-PERFORM
           DISPLAY "SUMMARY|TOTAL-BALANCE|" WS-TOTAL-BALANCE
           DISPLAY "SUMMARY|CHECKING-BALANCE|" WS-CHECKING-BALANCE
           DISPLAY "SUMMARY|SAVINGS-BALANCE|" WS-SAVINGS-BALANCE
           OPEN INPUT TRANSACT-FILE
           PERFORM UNTIL 1 = 0
               READ TRANSACT-FILE
                   AT END
                       CLOSE TRANSACT-FILE
                       EXIT PERFORM
               END-READ
               IF TRANS-STATUS = '00'
                   ADD 1 TO WS-TX-SUCCESS-COUNT
               ELSE IF TRANS-STATUS = '01'
                   ADD 1 TO WS-TX-NSF-COUNT
               ELSE IF TRANS-STATUS = '02'
                   ADD 1 TO WS-TX-LIMIT-COUNT
               ELSE IF TRANS-STATUS = '03'
                   ADD 1 TO WS-TX-BADACCT-COUNT
               ELSE IF TRANS-STATUS = '04'
                   ADD 1 TO WS-TX-FROZEN-COUNT
               END-IF
               END-IF
               END-IF
               END-IF
               END-IF
           END-PERFORM
           DISPLAY "STATS|SUCCESS|" WS-TX-SUCCESS-COUNT
           DISPLAY "STATS|NSF|" WS-TX-NSF-COUNT
           DISPLAY "STATS|LIMIT|" WS-TX-LIMIT-COUNT
           DISPLAY "STATS|BADACCT|" WS-TX-BADACCT-COUNT
           DISPLAY "STATS|FROZEN|" WS-TX-FROZEN-COUNT
           DISPLAY "RESULT|00".

       PRINT-AUDIT.
           DISPLAY "AUDIT|TRANSACTION LEDGER"
           OPEN INPUT TRANSACT-FILE
           PERFORM UNTIL 1 = 0
               READ TRANSACT-FILE
                   AT END
                       CLOSE TRANSACT-FILE
                       EXIT PERFORM
               END-READ
               DISPLAY "TRANS|" TRANS-ID "|"
                   TRANS-ACCT-ID "|" TRANS-TYPE "|"
                   TRANS-AMOUNT "|" TRANS-DATE "|"
                   TRANS-TIME "|" TRANS-DESC "|"
                   TRANS-STATUS "|" TRANS-BATCH-ID
           END-PERFORM
           DISPLAY "RESULT|00".
