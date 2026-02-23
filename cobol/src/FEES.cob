      *>================================================================*
      *>  Program:     FEES.cob
      *>  System:      LEGACY LEDGER — Fee Assessment Batch
      *>  Node:        All (same binary, per-node data directories)
      *>  Author:      AKD Solutions
      *>  Written:     2026-02-23
      *>  Modified:    2026-02-23
      *>
      *>  Purpose:
      *>    Monthly fee assessment for checking accounts. Reads all
      *>    accounts from ACCOUNTS.DAT, applies maintenance fees and
      *>    low-balance surcharges to checking accounts (type 'C'),
      *>    writes F-type transaction records to TRANSACT.DAT, and
      *>    updates account balances.
      *>
      *>  Operations:
      *>    ASSESS  — Calculate and post fees for all checking
      *>              accounts in the node
      *>
      *>  Fee Schedule:
      *>    Maintenance fee:    $12.00/month (waived if balance > $5,000)
      *>    Low-balance fee:    $8.00/month  (if balance < $500)
      *>    Balance floor:      Fee skipped if it would cause negative
      *>                        balance (fixes KNOWN_ISSUES T11)
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
      *>    Per account: FEE|ACCT-ID|FEE-TYPE|AMOUNT|NEW-BALANCE
      *>    Skipped:     FEE-SKIP|ACCT-ID|REASON
      *>    Summary:     SUMMARY|ACCOUNTS-ASSESSED|TOTAL-FEES
      *>    Result:      RESULT|XX
      *>
      *>  Exit Codes:
      *>    RESULT|00 — Fees assessed successfully
      *>    RESULT|99 — File I/O error
      *>
      *>  Change Log:
      *>    2026-02-23  AKD  Initial implementation — Phase 2
      *>
      *>================================================================*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. FEES.

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

       01  WS-FEE-AMOUNT          PIC S9(10)V99 VALUE 0.
       01  WS-TOTAL-FEE           PIC S9(10)V99 VALUE 0.
       01  WS-ACCOUNTS-ASSESSED   PIC 9(3) VALUE 0.
       01  WS-ACCOUNTS-WAIVED     PIC 9(3) VALUE 0.
       01  WS-ACCOUNTS-SKIPPED    PIC 9(3) VALUE 0.
       01  WS-TOTAL-FEES          PIC S9(10)V99 VALUE 0.
       01  WS-TX-ID               PIC X(12) VALUE SPACES.
       01  WS-TX-ID-NUM           PIC 9(6) VALUE 0.
       01  WS-NODE-CODE           PIC X(1) VALUE 'A'.
       01  WS-FEE-DESC            PIC X(40) VALUE SPACES.

      *>   Fee schedule constants
       01  WS-MAINTENANCE-FEE     PIC 9(4)V99 VALUE 12.00.
       01  WS-LOW-BAL-FEE         PIC 9(4)V99 VALUE 8.00.
       01  WS-WAIVER-THRESHOLD    PIC 9(10)V99 VALUE 5000.00.
       01  WS-LOW-BAL-THRESHOLD   PIC 9(10)V99 VALUE 500.00.
       COPY "COMCODE.cpy".

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           ACCEPT WS-CURRENT-DATE FROM DATE YYYYMMDD
           ACCEPT WS-CURRENT-TIME FROM TIME

           DISPLAY "========================================"
           DISPLAY "  FEE ASSESSMENT — MONTHLY BATCH"
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

      *>       Only process active checking accounts
               IF WS-A-TYPE(WS-ACCT-IDX) = 'C'
                   AND WS-A-STATUS(WS-ACCT-IDX) = 'A'

                   PERFORM ASSESS-FEES

               END-IF

           END-PERFORM

      *>   Rewrite account file with updated balances
           PERFORM WRITE-ALL-ACCOUNTS

           DISPLAY ""
           DISPLAY "========================================"
           DISPLAY "  FEE SUMMARY"
           DISPLAY "  Accounts assessed:   "
               WS-ACCOUNTS-ASSESSED
           DISPLAY "  Accounts waived:     "
               WS-ACCOUNTS-WAIVED
           DISPLAY "  Accounts skipped:    "
               WS-ACCOUNTS-SKIPPED
           DISPLAY "  Total fees collected: "
               WS-TOTAL-FEES
           DISPLAY "========================================"
           DISPLAY "SUMMARY|" WS-ACCOUNTS-ASSESSED "|"
               WS-TOTAL-FEES
           DISPLAY "RESULT|00"

           STOP RUN.

       ASSESS-FEES.
           MOVE 0 TO WS-TOTAL-FEE

      *>   Check maintenance fee waiver
           IF WS-A-BALANCE(WS-ACCT-IDX) > WS-WAIVER-THRESHOLD
               ADD 1 TO WS-ACCOUNTS-WAIVED
               DISPLAY "FEE-SKIP|" WS-A-ID(WS-ACCT-IDX)
                   "|WAIVED-ABOVE-5000"
               EXIT PARAGRAPH
           END-IF

      *>   Calculate total fee
           ADD WS-MAINTENANCE-FEE TO WS-TOTAL-FEE

      *>   Check low-balance surcharge
           IF WS-A-BALANCE(WS-ACCT-IDX) < WS-LOW-BAL-THRESHOLD
               ADD WS-LOW-BAL-FEE TO WS-TOTAL-FEE
           END-IF

      *>   Balance floor protection — skip if fee would go negative
           IF WS-TOTAL-FEE > WS-A-BALANCE(WS-ACCT-IDX)
               ADD 1 TO WS-ACCOUNTS-SKIPPED
               DISPLAY "FEE-SKIP|" WS-A-ID(WS-ACCT-IDX)
                   "|INSUFFICIENT-BALANCE"
               EXIT PARAGRAPH
           END-IF

      *>   Debit the fee
           SUBTRACT WS-TOTAL-FEE FROM WS-A-BALANCE(WS-ACCT-IDX)
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
           MOVE SPACES TO WS-FEE-DESC
           IF WS-TOTAL-FEE > WS-MAINTENANCE-FEE
               STRING "Monthly maint + low-bal fee — "
                   DELIMITED SIZE
                   WS-A-ID(WS-ACCT-IDX) DELIMITED SPACES
                   INTO WS-FEE-DESC
               END-STRING
           ELSE
               STRING "Monthly maintenance fee — "
                   DELIMITED SIZE
                   WS-A-ID(WS-ACCT-IDX) DELIMITED SPACES
                   INTO WS-FEE-DESC
               END-STRING
           END-IF

      *>   Write transaction record
           MOVE WS-TX-ID TO TRANS-ID
           MOVE WS-A-ID(WS-ACCT-IDX) TO TRANS-ACCT-ID
           MOVE 'F' TO TRANS-TYPE
           MOVE WS-TOTAL-FEE TO TRANS-AMOUNT
           MOVE WS-CURRENT-DATE TO TRANS-DATE
           MOVE WS-CURRENT-TIME TO TRANS-TIME
           MOVE WS-FEE-DESC TO TRANS-DESC
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
           DISPLAY "FEE|" WS-A-ID(WS-ACCT-IDX) "|MAINT|"
               WS-TOTAL-FEE "|" WS-A-BALANCE(WS-ACCT-IDX)
           ADD 1 TO WS-ACCOUNTS-ASSESSED
           ADD WS-TOTAL-FEE TO WS-TOTAL-FEES.

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
