      *>================================================================*
      *>  Program:     RECONCILE.cob
      *>  System:      LEGACY LEDGER — EOD Balance Reconciliation
      *>  Node:        All (same binary, per-node data directories)
      *>  Author:      AKD Solutions
      *>  Written:     2026-02-23
      *>  Modified:    2026-02-23
      *>
      *>  Purpose:
      *>    End-of-day reconciliation. For each account, sums all
      *>    transactions in TRANSACT.DAT by type and compares the
      *>    computed balance against the actual balance in ACCOUNTS.DAT.
      *>    Reports MATCH or MISMATCH per account.
      *>
      *>  Algorithm:
      *>    For each account:
      *>      net = sum(credits: D+I) - sum(debits: W+F+T) from
      *>            successful transactions (status '00')
      *>      implied_opening = current_balance - net
      *>      If no transactions → MATCH (balance unchanged)
      *>      If implied_opening >= 0 → MATCH (txns consistent)
      *>      If implied_opening < 0  → MISMATCH (txns don't
      *>        add up — missing deposits, double debits, or
      *>        corrupted balance field)
      *>
      *>  Files:
      *>    Input: ACCOUNTS.DAT  (70-byte, LINE SEQUENTIAL)
      *>    Input: TRANSACT.DAT  (103-byte, LINE SEQUENTIAL)
      *>
      *>  Copybooks:
      *>    ACCTREC.cpy   — Account record layout (70 bytes)
      *>    TRANSREC.cpy  — Transaction record layout (103 bytes)
      *>    COMCODE.cpy   — Shared status codes and bank identifiers
      *>    ACCTIO.cpy    — Shared account I/O variables
      *>
      *>  Output Format (to STDOUT, pipe-delimited):
      *>    Per account: RECON|ACCT-ID|STATUS|BALANCE|TX-COUNT
      *>    Summary:     RECON-SUMMARY|MATCHED|MISMATCHED|TOTAL
      *>    Result:      RESULT|XX
      *>
      *>  Exit Codes:
      *>    RESULT|00 — Reconciliation complete (all matched)
      *>    RESULT|01 — Reconciliation complete (mismatches found)
      *>    RESULT|99 — File I/O error
      *>
      *>  Change Log:
      *>    2026-02-23  AKD  Initial implementation — Phase 2
      *>
      *>================================================================*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. RECONCILE.

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

      *>   Per-account transaction accumulators
       01  WS-TX-TABLE.
           05  WS-TX-ENTRY OCCURS 100 TIMES.
               10  WS-TX-ACCT-ID  PIC X(10).
               10  WS-TX-CREDITS  PIC S9(10)V99 VALUE 0.
               10  WS-TX-DEBITS   PIC S9(10)V99 VALUE 0.
               10  WS-TX-COUNT    PIC 9(6) VALUE 0.

       01  WS-TX-IDX              PIC 9(3) VALUE 0.
       01  WS-MATCHED             PIC 9(3) VALUE 0.
       01  WS-MISMATCHED          PIC 9(3) VALUE 0.
       01  WS-TX-NET              PIC S9(10)V99 VALUE 0.
       01  WS-EXPECTED-BAL        PIC S9(10)V99 VALUE 0.
       01  WS-SEARCH-IDX          PIC 9(3) VALUE 0.
       01  WS-TX-FOUND            PIC X VALUE 'N'.
       01  WS-NODE-CODE           PIC X(1) VALUE 'A'.
       COPY "COMCODE.cpy".

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           ACCEPT WS-CURRENT-DATE FROM DATE YYYYMMDD
           ACCEPT WS-CURRENT-TIME FROM TIME

           DISPLAY "========================================"
           DISPLAY "  BALANCE RECONCILIATION — EOD"
           DISPLAY "  DATE: " WS-CURRENT-DATE
               "  TIME: " WS-CURRENT-TIME
           DISPLAY "========================================"
           DISPLAY ""

      *>   Load all accounts
           PERFORM LOAD-ALL-ACCOUNTS

      *>   Derive node code
           IF WS-ACCOUNT-COUNT > 0
               MOVE WS-A-ID(1)(5:1) TO WS-NODE-CODE
           END-IF

      *>   Initialize TX accumulators for each account
           PERFORM VARYING WS-ACCT-IDX FROM 1 BY 1
               UNTIL WS-ACCT-IDX > WS-ACCOUNT-COUNT
               MOVE WS-A-ID(WS-ACCT-IDX)
                   TO WS-TX-ACCT-ID(WS-ACCT-IDX)
               MOVE 0 TO WS-TX-CREDITS(WS-ACCT-IDX)
               MOVE 0 TO WS-TX-DEBITS(WS-ACCT-IDX)
               MOVE 0 TO WS-TX-COUNT(WS-ACCT-IDX)
           END-PERFORM

      *>   Read all transactions and accumulate by account
           OPEN INPUT TRANSACT-FILE
           IF WS-TX-STATUS NOT = '00'
      *>       No transactions file — all accounts match by default
               DISPLAY "NOTE|No TRANSACT.DAT — skipping TX scan"
           ELSE
               PERFORM UNTIL 1 = 0
                   READ TRANSACT-FILE
                       AT END
                           CLOSE TRANSACT-FILE
                           EXIT PERFORM
                   END-READ

      *>           Only count successful transactions
                   IF TRANS-STATUS = '00'
                       PERFORM ACCUMULATE-TRANSACTION
                   END-IF
               END-PERFORM
           END-IF

      *>   Compare accumulated totals vs actual balances
           DISPLAY ""
           DISPLAY "ACCT-ID     STATUS   BALANCE        TX-COUNT"
           DISPLAY "----------  ------   -------------  --------"

           PERFORM VARYING WS-ACCT-IDX FROM 1 BY 1
               UNTIL WS-ACCT-IDX > WS-ACCOUNT-COUNT
               PERFORM CHECK-ACCOUNT-BALANCE
           END-PERFORM

      *>   Summary
           DISPLAY ""
           DISPLAY "========================================"
           DISPLAY "  RECONCILIATION SUMMARY"
           DISPLAY "  Matched:     " WS-MATCHED
           DISPLAY "  Mismatched:  " WS-MISMATCHED
           DISPLAY "  Total:       " WS-ACCOUNT-COUNT
           DISPLAY "========================================"
           DISPLAY "RECON-SUMMARY|" WS-MATCHED "|"
               WS-MISMATCHED "|" WS-ACCOUNT-COUNT

           IF WS-MISMATCHED = 0
               DISPLAY "RESULT|00"
           ELSE
               DISPLAY "RESULT|01"
           END-IF

           STOP RUN.

       ACCUMULATE-TRANSACTION.
      *>   Find the account index for this transaction
           MOVE 'N' TO WS-TX-FOUND
           PERFORM VARYING WS-SEARCH-IDX FROM 1 BY 1
               UNTIL WS-SEARCH-IDX > WS-ACCOUNT-COUNT
               IF WS-TX-ACCT-ID(WS-SEARCH-IDX) = TRANS-ACCT-ID
                   MOVE 'Y' TO WS-TX-FOUND
                   EXIT PERFORM
               END-IF
           END-PERFORM

           IF WS-TX-FOUND = 'N'
               EXIT PARAGRAPH
           END-IF

           ADD 1 TO WS-TX-COUNT(WS-SEARCH-IDX)

      *>   Accumulate credits and debits by type
           EVALUATE TRANS-TYPE
               WHEN 'D'
                   ADD TRANS-AMOUNT TO WS-TX-CREDITS(WS-SEARCH-IDX)
               WHEN 'I'
                   ADD TRANS-AMOUNT TO WS-TX-CREDITS(WS-SEARCH-IDX)
               WHEN 'W'
                   ADD TRANS-AMOUNT TO WS-TX-DEBITS(WS-SEARCH-IDX)
               WHEN 'F'
                   ADD TRANS-AMOUNT TO WS-TX-DEBITS(WS-SEARCH-IDX)
               WHEN 'T'
      *>           Transfers: source account is debited
                   ADD TRANS-AMOUNT TO WS-TX-DEBITS(WS-SEARCH-IDX)
           END-EVALUATE.

       CHECK-ACCOUNT-BALANCE.
      *>   Net = credits - debits for this account
           COMPUTE WS-TX-NET =
               WS-TX-CREDITS(WS-ACCT-IDX)
               - WS-TX-DEBITS(WS-ACCT-IDX)
           END-COMPUTE

      *>   No transactions → automatic MATCH (balance unchanged)
           IF WS-TX-COUNT(WS-ACCT-IDX) = 0
               ADD 1 TO WS-MATCHED
               DISPLAY WS-A-ID(WS-ACCT-IDX) "  MATCH    "
                   WS-A-BALANCE(WS-ACCT-IDX) "  "
                   WS-TX-COUNT(WS-ACCT-IDX)
               DISPLAY "RECON|" WS-A-ID(WS-ACCT-IDX)
                   "|MATCH|" WS-A-BALANCE(WS-ACCT-IDX)
                   "|" WS-TX-COUNT(WS-ACCT-IDX)
           ELSE
      *>       Implied opening = current balance - net transactions
      *>       If negative, transactions exceed what balance allows
               COMPUTE WS-EXPECTED-BAL =
                   WS-A-BALANCE(WS-ACCT-IDX) - WS-TX-NET
               END-COMPUTE
               IF WS-EXPECTED-BAL >= 0
                   ADD 1 TO WS-MATCHED
                   DISPLAY WS-A-ID(WS-ACCT-IDX) "  MATCH    "
                       WS-A-BALANCE(WS-ACCT-IDX) "  "
                       WS-TX-COUNT(WS-ACCT-IDX)
                   DISPLAY "RECON|" WS-A-ID(WS-ACCT-IDX)
                       "|MATCH|" WS-A-BALANCE(WS-ACCT-IDX)
                       "|" WS-TX-COUNT(WS-ACCT-IDX)
               ELSE
                   ADD 1 TO WS-MISMATCHED
                   DISPLAY WS-A-ID(WS-ACCT-IDX) "  MISMATCH "
                       WS-A-BALANCE(WS-ACCT-IDX) "  "
                       WS-TX-COUNT(WS-ACCT-IDX)
                   DISPLAY "RECON|" WS-A-ID(WS-ACCT-IDX)
                       "|MISMATCH|" WS-A-BALANCE(WS-ACCT-IDX)
                       "|" WS-TX-COUNT(WS-ACCT-IDX)
               END-IF
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
