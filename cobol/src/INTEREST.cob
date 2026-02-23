      *>================================================================*
      *>  Program:     INTEREST.cob
      *>  System:      LEGACY LEDGER — Interest Accrual Batch
      *>  Node:        All (same binary, per-node data directories)
      *>  Author:      AKD Solutions
      *>  Written:     2026-02-23
      *>  Modified:    2026-02-23
      *>
      *>  Purpose:
      *>    Monthly interest accrual for savings accounts. Reads all
      *>    accounts from ACCOUNTS.DAT, calculates tiered interest
      *>    for savings accounts (type 'S'), writes I-type transaction
      *>    records to TRANSACT.DAT, and updates account balances.
      *>
      *>  Operations:
      *>    ACCRUE  — Calculate and post interest for all savings
      *>              accounts in the node
      *>
      *>  Interest Rate Table (annual, tiered):
      *>    Balance < $10,000       → 0.50% APR
      *>    $10,000 - $100,000      → 1.50% APR
      *>    Balance > $100,000      → 2.00% APR
      *>    Monthly rate = APR / 12
      *>
      *>  Files:
      *>    Input/Output: ACCOUNTS.DAT  (70-byte, LINE SEQUENTIAL)
      *>    Output:       TRANSACT.DAT  (103-byte, LINE SEQUENTIAL)
      *>
      *>  Copybooks:
      *>    ACCTREC.cpy   — Account record layout (70 bytes)
      *>    TRANSREC.cpy  — Transaction record layout (103 bytes)
      *>    COMCODE.cpy   — Shared status codes and bank identifiers
      *>    ACCTIO.cpy    — Shared account I/O variables
      *>
      *>  Output Format (to STDOUT, pipe-delimited):
      *>    Per account: INTEREST|ACCT-ID|AMOUNT|NEW-BALANCE
      *>    Summary:     SUMMARY|ACCOUNTS-PROCESSED|TOTAL-INTEREST
      *>    Result:      RESULT|XX
      *>
      *>  Exit Codes:
      *>    RESULT|00 — Interest posted successfully
      *>    RESULT|99 — File I/O error
      *>
      *>  Change Log:
      *>    2026-02-23  AKD  Initial implementation — Phase 2
      *>
      *>================================================================*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. INTEREST.

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
       01  WS-CURRENT-DATE        PIC 9(8) VALUE 0.
       01  WS-CURRENT-TIME        PIC 9(6) VALUE 0.
       01  WS-IN-ACCT-ID          PIC X(10) VALUE SPACES.
       COPY "ACCTIO.cpy".

       01  WS-INTEREST            PIC S9(10)V99 VALUE 0.
       01  WS-ANNUAL-RATE         PIC 9V9(4) VALUE 0.
       01  WS-MONTHLY-RATE        PIC 9V9(6) VALUE 0.
       01  WS-ACCOUNTS-PROCESSED  PIC 9(3) VALUE 0.
       01  WS-TOTAL-INTEREST      PIC S9(10)V99 VALUE 0.
       01  WS-TX-ID               PIC X(12) VALUE SPACES.
       01  WS-TX-ID-NUM           PIC 9(6) VALUE 0.
       01  WS-NODE-CODE           PIC X(1) VALUE 'A'.
       01  WS-INTEREST-DESC       PIC X(40) VALUE SPACES.
       COPY "COMCODE.cpy".

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           ACCEPT WS-CURRENT-DATE FROM DATE YYYYMMDD
           ACCEPT WS-CURRENT-TIME FROM TIME

           DISPLAY "========================================"
           DISPLAY "  INTEREST ACCRUAL — MONTHLY BATCH"
           DISPLAY "  DATE: " WS-CURRENT-DATE
               "  TIME: " WS-CURRENT-TIME
           DISPLAY "========================================"
           DISPLAY ""

           PERFORM LOAD-ALL-ACCOUNTS
           PERFORM COUNT-EXISTING-TRANSACTIONS

      *>   Derive node code from first account ID
           IF WS-ACCOUNT-COUNT > 0
               MOVE WS-A-ID(1)(5:1) TO WS-NODE-CODE
           END-IF

           PERFORM VARYING WS-ACCT-IDX FROM 1 BY 1
               UNTIL WS-ACCT-IDX > WS-ACCOUNT-COUNT

      *>       Only process active savings accounts
               IF WS-A-TYPE(WS-ACCT-IDX) = 'S'
                   AND WS-A-STATUS(WS-ACCT-IDX) = 'A'
                   AND WS-A-BALANCE(WS-ACCT-IDX) > 0

                   PERFORM CALCULATE-INTEREST
                   PERFORM POST-INTEREST

               END-IF

           END-PERFORM

      *>   Rewrite account file with updated balances
           PERFORM WRITE-ALL-ACCOUNTS

           DISPLAY ""
           DISPLAY "========================================"
           DISPLAY "  INTEREST SUMMARY"
           DISPLAY "  Accounts processed:  "
               WS-ACCOUNTS-PROCESSED
           DISPLAY "  Total interest:      "
               WS-TOTAL-INTEREST
           DISPLAY "========================================"
           DISPLAY "SUMMARY|" WS-ACCOUNTS-PROCESSED "|"
               WS-TOTAL-INTEREST
           DISPLAY "RESULT|00"

           STOP RUN.

       CALCULATE-INTEREST.
      *>   Tiered annual rate based on balance
           EVALUATE TRUE
               WHEN WS-A-BALANCE(WS-ACCT-IDX) < 10000.00
                   MOVE 0.0050 TO WS-ANNUAL-RATE
               WHEN WS-A-BALANCE(WS-ACCT-IDX) < 100000.00
                   MOVE 0.0150 TO WS-ANNUAL-RATE
               WHEN OTHER
                   MOVE 0.0200 TO WS-ANNUAL-RATE
           END-EVALUATE

      *>   Monthly interest = balance * annual_rate / 12
           COMPUTE WS-INTEREST ROUNDED =
               WS-A-BALANCE(WS-ACCT-IDX) * WS-ANNUAL-RATE / 12
           END-COMPUTE.

       POST-INTEREST.
      *>   Update balance
           ADD WS-INTEREST TO WS-A-BALANCE(WS-ACCT-IDX)
           MOVE WS-CURRENT-DATE TO WS-A-ACTIVITY(WS-ACCT-IDX)

      *>   Generate transaction ID
           ADD 1 TO WS-TX-ID-NUM
           MOVE SPACES TO WS-TX-ID
           STRING "TRX-" DELIMITED SIZE
               WS-NODE-CODE DELIMITED SIZE
               "-" DELIMITED SIZE
               WS-TX-ID-NUM DELIMITED SIZE
               INTO WS-TX-ID
           END-STRING

      *>   Build description
           MOVE SPACES TO WS-INTEREST-DESC
           STRING "Monthly interest credit — "
               DELIMITED SIZE
               WS-A-ID(WS-ACCT-IDX) DELIMITED SPACES
               INTO WS-INTEREST-DESC
           END-STRING

      *>   Write transaction record
           MOVE WS-TX-ID TO TRANS-ID
           MOVE WS-A-ID(WS-ACCT-IDX) TO TRANS-ACCT-ID
           MOVE 'I' TO TRANS-TYPE
           MOVE WS-INTEREST TO TRANS-AMOUNT
           MOVE WS-CURRENT-DATE TO TRANS-DATE
           MOVE WS-CURRENT-TIME TO TRANS-TIME
           MOVE WS-INTEREST-DESC TO TRANS-DESC
           MOVE '00' TO TRANS-STATUS
           MOVE SPACES TO TRANS-BATCH-ID
           OPEN EXTEND TRANSACT-FILE
           IF WS-TX-STATUS NOT = '00'
               DISPLAY "ERROR|FILE-OPEN|" WS-TX-STATUS
               DISPLAY "RESULT|99"
               STOP RUN
           END-IF
           WRITE TRANSACTION-RECORD
           CLOSE TRANSACT-FILE

      *>   Display and accumulate
           DISPLAY "INTEREST|" WS-A-ID(WS-ACCT-IDX) "|"
               WS-INTEREST "|" WS-A-BALANCE(WS-ACCT-IDX)
           ADD 1 TO WS-ACCOUNTS-PROCESSED
           ADD WS-INTEREST TO WS-TOTAL-INTEREST.

       COUNT-EXISTING-TRANSACTIONS.
           OPEN INPUT TRANSACT-FILE
           IF WS-TX-STATUS NOT = "00"
               MOVE 0 TO WS-TX-ID-NUM
           ELSE
               PERFORM UNTIL 1 = 0
                   READ TRANSACT-FILE
                       AT END
                           CLOSE TRANSACT-FILE
                           EXIT PERFORM
                   END-READ
                   ADD 1 TO WS-TX-ID-NUM
               END-PERFORM
           END-IF.

       LOAD-ALL-ACCOUNTS.
           MOVE 0 TO WS-ACCOUNT-COUNT
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
               ADD 1 TO WS-ACCOUNT-COUNT
               MOVE ACCT-ID TO WS-A-ID(WS-ACCOUNT-COUNT)
               MOVE ACCT-NAME TO WS-A-NAME(WS-ACCOUNT-COUNT)
               MOVE ACCT-TYPE TO WS-A-TYPE(WS-ACCOUNT-COUNT)
               MOVE ACCT-BALANCE TO WS-A-BALANCE(WS-ACCOUNT-COUNT)
               MOVE ACCT-STATUS TO WS-A-STATUS(WS-ACCOUNT-COUNT)
               MOVE ACCT-OPEN-DATE TO WS-A-OPEN(WS-ACCOUNT-COUNT)
               MOVE ACCT-LAST-ACTIVITY
                   TO WS-A-ACTIVITY(WS-ACCOUNT-COUNT)
           END-PERFORM.

       WRITE-ALL-ACCOUNTS.
           OPEN OUTPUT ACCOUNTS-FILE
           IF WS-FILE-STATUS NOT = '00'
               DISPLAY "ERROR|FILE-OPEN|" WS-FILE-STATUS
               DISPLAY "RESULT|99"
               STOP RUN
           END-IF
           PERFORM VARYING WS-ACCT-IDX FROM 1 BY 1
               UNTIL WS-ACCT-IDX > WS-ACCOUNT-COUNT
               MOVE WS-A-ID(WS-ACCT-IDX) TO ACCT-ID
               MOVE WS-A-NAME(WS-ACCT-IDX) TO ACCT-NAME
               MOVE WS-A-TYPE(WS-ACCT-IDX) TO ACCT-TYPE
               MOVE WS-A-BALANCE(WS-ACCT-IDX) TO ACCT-BALANCE
               MOVE WS-A-STATUS(WS-ACCT-IDX) TO ACCT-STATUS
               MOVE WS-A-OPEN(WS-ACCT-IDX) TO ACCT-OPEN-DATE
               MOVE WS-A-ACTIVITY(WS-ACCT-IDX)
                   TO ACCT-LAST-ACTIVITY
               WRITE ACCOUNT-RECORD
           END-PERFORM
           CLOSE ACCOUNTS-FILE.

       FIND-ACCOUNT.
           MOVE 'N' TO WS-FOUND-FLAG
           MOVE 0 TO WS-FOUND-IDX
           PERFORM VARYING WS-ACCT-IDX FROM 1 BY 1
               UNTIL WS-ACCT-IDX > WS-ACCOUNT-COUNT
               IF WS-A-ID(WS-ACCT-IDX) = WS-IN-ACCT-ID
                   MOVE 'Y' TO WS-FOUND-FLAG
                   MOVE WS-ACCT-IDX TO WS-FOUND-IDX
                   EXIT PERFORM
               END-IF
           END-PERFORM.
