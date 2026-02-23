      *>================================================================*
      *>  Program:     REPORTS.cob
      *>  System:      LEGACY LEDGER — Reporting and Reconciliation
      *>  Node:        All (same binary, per-node data directories)
      *>  Author:      AKD Solutions
      *>  Written:     2026-02-17
      *>  Modified:    2026-02-23
      *>
      *>  Purpose:
      *>    Read-only reporting on account and transaction data.
      *>    Generates ledger summaries, account statements, end-of-day
      *>    reconciliation reports, and full audit trails. No file
      *>    modifications — all output is to STDOUT.
      *>
      *>  Operations (via command-line argument):
      *>    LEDGER    — All accounts with balance totals by type
      *>    STATEMENT — Transaction history for a single account
      *>    EOD       — End-of-day summary with transaction stats
      *>    AUDIT     — Full transaction ledger for audit review
      *>
      *>  Files:
      *>    Input: ACCOUNTS.DAT  (LINE SEQUENTIAL, 70-byte records)
      *>    Input: TRANSACT.DAT  (LINE SEQUENTIAL, 103-byte records)
      *>
      *>  Copybooks:
      *>    ACCTREC.cpy   — Account record layout (70 bytes)
      *>    TRANSREC.cpy  — Transaction record layout (103 bytes)
      *>    COMCODE.cpy   — Shared status codes and bank identifiers
      *>
      *>  Output Format (to STDOUT, pipe-delimited):
      *>    Ledger:    ACCOUNT|id|name|type|balance|status|opened|lastact
      *>    Statement: TRANS|id|type|amount|date|time|desc|status
      *>    EOD:       SUMMARY|label|value  +  STATS|category|count
      *>    Audit:     TRANS|id|acct|type|amount|date|time|desc|status|batch
      *>    Result:    RESULT|XX  (where XX = status code)
      *>
      *>  Exit Codes:
      *>    RESULT|00 — Report generated successfully
      *>    RESULT|99 — Invalid operation or file I/O error
      *>
      *>  Dependencies:
      *>    Requires ACCOUNTS.DAT and/or TRANSACT.DAT in CWD.
      *>    Read-only operations — no file modifications.
      *>
      *>  Change Log:
      *>    2026-02-17  AKD  Initial implementation — Phase 1
      *>    2026-02-23  AKD  Production headers, file status checks,
      *>                     EVALUATE refactoring for status codes
      *>
      *>================================================================*
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
           IF WS-FILE-STATUS NOT = '00'
               DISPLAY "ERROR|FILE-OPEN|" WS-FILE-STATUS
               DISPLAY "RESULT|99"
               STOP RUN
           END-IF
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
               EVALUATE ACCT-TYPE
                   WHEN 'C'
                       ADD ACCT-BALANCE TO WS-CHECKING-BALANCE
                   WHEN 'S'
                       ADD ACCT-BALANCE TO WS-SAVINGS-BALANCE
               END-EVALUATE
           END-PERFORM
           DISPLAY "SUMMARY|TOTAL-BALANCE|" WS-TOTAL-BALANCE
               "|ACCOUNTS|" WS-ACCOUNT-COUNT
           DISPLAY "SUMMARY|CHECKING-BALANCE|" WS-CHECKING-BALANCE
           DISPLAY "SUMMARY|SAVINGS-BALANCE|" WS-SAVINGS-BALANCE
           DISPLAY "RESULT|00".

       PRINT-STATEMENT.
           DISPLAY "STATEMENT|ACCOUNT|" WS-IN-ACCT-ID
           OPEN INPUT TRANSACT-FILE
           IF WS-TX-STATUS NOT = '00'
               DISPLAY "ERROR|FILE-OPEN|" WS-TX-STATUS
               DISPLAY "RESULT|99"
               STOP RUN
           END-IF
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
           IF WS-FILE-STATUS NOT = '00'
               DISPLAY "ERROR|FILE-OPEN|" WS-FILE-STATUS
               DISPLAY "RESULT|99"
               STOP RUN
           END-IF
           PERFORM UNTIL 1 = 0
               READ ACCOUNTS-FILE
                   AT END
                       CLOSE ACCOUNTS-FILE
                       EXIT PERFORM
               END-READ
               ADD ACCT-BALANCE TO WS-TOTAL-BALANCE
               EVALUATE ACCT-TYPE
                   WHEN 'C'
                       ADD ACCT-BALANCE TO WS-CHECKING-BALANCE
                   WHEN 'S'
                       ADD ACCT-BALANCE TO WS-SAVINGS-BALANCE
               END-EVALUATE
           END-PERFORM
           DISPLAY "SUMMARY|TOTAL-BALANCE|" WS-TOTAL-BALANCE
           DISPLAY "SUMMARY|CHECKING-BALANCE|" WS-CHECKING-BALANCE
           DISPLAY "SUMMARY|SAVINGS-BALANCE|" WS-SAVINGS-BALANCE
           OPEN INPUT TRANSACT-FILE
           IF WS-TX-STATUS NOT = '00'
               DISPLAY "ERROR|FILE-OPEN|" WS-TX-STATUS
               DISPLAY "RESULT|99"
               STOP RUN
           END-IF
           PERFORM UNTIL 1 = 0
               READ TRANSACT-FILE
                   AT END
                       CLOSE TRANSACT-FILE
                       EXIT PERFORM
               END-READ
               EVALUATE TRANS-STATUS
                   WHEN '00'
                       ADD 1 TO WS-TX-SUCCESS-COUNT
                   WHEN '01'
                       ADD 1 TO WS-TX-NSF-COUNT
                   WHEN '02'
                       ADD 1 TO WS-TX-LIMIT-COUNT
                   WHEN '03'
                       ADD 1 TO WS-TX-BADACCT-COUNT
                   WHEN '04'
                       ADD 1 TO WS-TX-FROZEN-COUNT
               END-EVALUATE
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
           IF WS-TX-STATUS NOT = '00'
               DISPLAY "ERROR|FILE-OPEN|" WS-TX-STATUS
               DISPLAY "RESULT|99"
               STOP RUN
           END-IF
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
