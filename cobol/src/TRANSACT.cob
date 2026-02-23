      *>================================================================*
      *>  Program:     TRANSACT.cob
      *>  System:      LEGACY LEDGER — Transaction Processing Engine
      *>  Node:        All (same binary, per-node data directories)
      *>  Author:      AKD Solutions
      *>  Written:     2026-02-17
      *>  Modified:    2026-02-23
      *>
      *>  Purpose:
      *>    Core transaction engine for deposits, withdrawals,
      *>    transfers, and batch processing. Validates business rules,
      *>    updates account balances, and writes transaction records
      *>    to the TRANSACT.DAT sequential log file.
      *>
      *>  Operations (via command-line argument):
      *>    DEPOSIT   — Credit funds to an account
      *>    WITHDRAW  — Debit funds with NSF + limit checks
      *>    TRANSFER  — Move funds between two accounts
      *>    BATCH     — Process pipe-delimited batch input file
      *>
      *>  Files:
      *>    Input/Output: ACCOUNTS.DAT  (LINE SEQUENTIAL, 70-byte)
      *>    Output:       TRANSACT.DAT  (LINE SEQUENTIAL, 103-byte)
      *>    Input:        BATCH-INPUT.DAT (pipe-delimited batch)
      *>
      *>  Copybooks:
      *>    ACCTREC.cpy   — Account record layout (70 bytes)
      *>    TRANSREC.cpy  — Transaction record layout (103 bytes)
      *>    COMCODE.cpy   — Shared status codes and bank identifiers
      *>    ACCTIO.cpy    — Shared account I/O paragraphs
      *>
      *>  Output Format (to STDOUT, pipe-delimited):
      *>    Success: OK|TYPE|TX-ID|ACCT-ID|NEW-BALANCE
      *>    Batch:   Columnar trace (see Supplement A)
      *>    Result:  RESULT|XX  (where XX = status code)
      *>
      *>  Exit Codes:
      *>    RESULT|00 — Success
      *>    RESULT|01 — Insufficient funds (NSF)
      *>    RESULT|02 — Daily limit exceeded
      *>    RESULT|03 — Invalid account
      *>    RESULT|04 — Account frozen
      *>    RESULT|99 — File I/O or system error
      *>
      *>  Dependencies:
      *>    Requires ACCOUNTS.DAT in CWD. TRANSACT.DAT created/appended
      *>    automatically. BATCH-INPUT.DAT required for BATCH operation.
      *>
      *>  Change Log:
      *>    2026-02-17  AKD  Initial implementation — Phase 1
      *>    2026-02-23  AKD  Production headers, dynamic dates,
      *>                     file status checks, dead code removal,
      *>                     copybook extraction, parameterized node
      *>
      *>================================================================*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TRANSACT.

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
           SELECT BATCH-FILE
               ASSIGN TO "BATCH-INPUT.DAT"
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-BATCH-STATUS.

       DATA DIVISION.
       FILE SECTION.
       FD  ACCOUNTS-FILE.
       COPY "ACCTREC.cpy".
       FD  TRANSACT-FILE.
       COPY "TRANSREC.cpy".
       FD  BATCH-FILE.
       01  BATCH-RECORD           PIC X(100).

       WORKING-STORAGE SECTION.
       01  WS-FILE-STATUS         PIC XX VALUE SPACES.
       01  WS-TX-STATUS           PIC XX VALUE SPACES.
       01  WS-BATCH-STATUS        PIC XX VALUE SPACES.
       01  WS-OPERATION           PIC X(10) VALUE SPACES.
       01  WS-IN-ACCT-ID          PIC X(10) VALUE SPACES.
       01  WS-IN-TARGET-ID        PIC X(10) VALUE SPACES.
       01  WS-IN-TYPE             PIC X(1) VALUE SPACES.
       01  WS-IN-AMOUNT           PIC S9(10)V99 VALUE 0.
       01  WS-IN-AMOUNT-STR       PIC X(20) VALUE SPACES.
       01  WS-IN-DESC             PIC X(40) VALUE SPACES.
       01  WS-TX-ID               PIC X(12) VALUE SPACES.
       01  WS-TX-ID-NUM           PIC 9(6) VALUE 0.
       01  WS-NODE-CODE           PIC X(1) VALUE 'A'.
       01  WS-RESULT-CODE         PIC X(2) VALUE '00'.
       COPY "ACCTIO.cpy".
       01  WS-BATCH-SEQ           PIC 9(3) VALUE 0.
       01  WS-BATCH-SUCCESS       PIC 9(5) VALUE 0.
       01  WS-BATCH-FAILED        PIC 9(5) VALUE 0.
       01  WS-TOTAL-DEPOSITS      PIC S9(10)V99 VALUE 0.
       01  WS-TOTAL-WITHDRAWALS   PIC S9(10)V99 VALUE 0.
       01  WS-TOTAL-TRANSFERS     PIC S9(10)V99 VALUE 0.
       01  WS-BATCH-ID            PIC X(12) VALUE SPACES.
       01  WS-BATCH-LINE          PIC X(200) VALUE SPACES.
       01  WS-DISPLAY-FIELDS.
           05  WS-SEQ-DISPLAY     PIC ZZ9.
           05  WS-STATUS-DISPLAY  PIC X(6).
           05  WS-TYPE-DISPLAY    PIC X(4).
           05  WS-AMOUNT-DISPLAY  PIC $$$,$$$,$$9.99.
           05  WS-BALANCE-DISPLAY PIC $$$,$$$,$$9.99.
       01  WS-BATCH-PARSE-FIELDS.
           05  WS-BP-ACCT         PIC X(10).
           05  WS-BP-TYPE         PIC X(1).
           05  WS-BP-AMOUNT       PIC 9(10)V99.
           05  WS-BP-DESC         PIC X(40).
           05  WS-BP-TARGET       PIC X(10).
       01  WS-CURRENT-DATE        PIC 9(8) VALUE 0.
       01  WS-CURRENT-TIME        PIC 9(6) VALUE 0.
       01  WS-DAILY-LIMIT         PIC 9(10)V99 VALUE 50000.00.
       COPY "COMCODE.cpy".

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           ACCEPT WS-CURRENT-DATE FROM DATE YYYYMMDD
           ACCEPT WS-CURRENT-TIME FROM TIME
           ACCEPT WS-BATCH-LINE FROM COMMAND-LINE

           *> Extract operation keyword and all fields (first word)
           UNSTRING WS-BATCH-LINE DELIMITED BY SPACE
               INTO WS-OPERATION
                    WS-IN-ACCT-ID
                    WS-IN-AMOUNT-STR
                    WS-IN-TARGET-ID
                    WS-IN-DESC
           END-UNSTRING

           *> Trim all fields after parsing
           MOVE FUNCTION TRIM(WS-OPERATION) TO WS-OPERATION
           MOVE FUNCTION TRIM(WS-IN-ACCT-ID) TO WS-IN-ACCT-ID
           MOVE FUNCTION TRIM(WS-IN-AMOUNT-STR) TO WS-IN-AMOUNT-STR
           MOVE FUNCTION TRIM(WS-IN-TARGET-ID) TO WS-IN-TARGET-ID
           MOVE FUNCTION TRIM(WS-IN-DESC) TO WS-IN-DESC

           *> Convert amount from string to numeric
           IF WS-IN-AMOUNT-STR NOT = SPACES
               MOVE FUNCTION NUMVAL(WS-IN-AMOUNT-STR)
                   TO WS-IN-AMOUNT
           END-IF

           EVALUATE WS-OPERATION
               WHEN "DEPOSIT"
                   PERFORM PROCESS-DEPOSIT
               WHEN "WITHDRAW"
                   PERFORM PROCESS-WITHDRAW
               WHEN "TRANSFER"
                   PERFORM PROCESS-TRANSFER
               WHEN "BATCH"
                   PERFORM PROCESS-BATCH
               WHEN OTHER
                   DISPLAY "RESULT|99"
           END-EVALUATE

           STOP RUN.

       GENERATE-TX-ID.
      *>   Count existing TRANSACT.DAT records to continue sequence
           IF WS-TX-ID-NUM = 0
               PERFORM COUNT-EXISTING-TRANSACTIONS
           END-IF
      *>   Derive node code from first loaded account ID (4th char)
      *>   ACT-A-001 → 'A', ACT-B-001 → 'B', NST-BANK-A → 'B'
           IF WS-ACCOUNT-COUNT > 0
               MOVE WS-A-ID(1)(5:1) TO WS-NODE-CODE
           END-IF
           ADD 1 TO WS-TX-ID-NUM
           MOVE SPACES TO WS-TX-ID
           STRING "TRX-" DELIMITED SIZE
               WS-NODE-CODE DELIMITED SIZE
               "-" DELIMITED SIZE
               WS-TX-ID-NUM DELIMITED SIZE
               INTO WS-TX-ID
           END-STRING.

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
               MOVE ACCT-LAST-ACTIVITY TO WS-A-ACTIVITY(WS-ACCOUNT-COUNT)
           END-PERFORM.

       SAVE-ALL-ACCOUNTS.
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
               MOVE WS-A-ACTIVITY(WS-ACCT-IDX) TO ACCT-LAST-ACTIVITY
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

       WRITE-TRANSACTION-RECORD.
           MOVE WS-TX-ID TO TRANS-ID
           MOVE WS-IN-ACCT-ID TO TRANS-ACCT-ID
           MOVE WS-IN-TYPE TO TRANS-TYPE
           MOVE WS-IN-AMOUNT TO TRANS-AMOUNT
           MOVE WS-CURRENT-DATE TO TRANS-DATE
           MOVE WS-CURRENT-TIME TO TRANS-TIME
           MOVE WS-IN-DESC TO TRANS-DESC
           MOVE WS-RESULT-CODE TO TRANS-STATUS
           MOVE SPACES TO TRANS-BATCH-ID
           OPEN EXTEND TRANSACT-FILE
           IF WS-TX-STATUS NOT = '00'
               DISPLAY "ERROR|FILE-OPEN|" WS-TX-STATUS
               DISPLAY "RESULT|99"
               STOP RUN
           END-IF
           WRITE TRANSACTION-RECORD
           CLOSE TRANSACT-FILE.

       PROCESS-DEPOSIT.
           PERFORM LOAD-ALL-ACCOUNTS
           PERFORM FIND-ACCOUNT
           IF WS-FOUND-FLAG = 'N'
               MOVE RC-INVALID-ACCT TO WS-RESULT-CODE
               PERFORM WRITE-TRANSACTION-RECORD
               DISPLAY "RESULT|03"
               EXIT PARAGRAPH
           END-IF
           IF WS-A-STATUS(WS-FOUND-IDX) = 'F'
               MOVE RC-ACCOUNT-FROZEN TO WS-RESULT-CODE
               PERFORM WRITE-TRANSACTION-RECORD
               DISPLAY "RESULT|04"
               EXIT PARAGRAPH
           END-IF
           PERFORM GENERATE-TX-ID
           ADD WS-IN-AMOUNT TO WS-A-BALANCE(WS-FOUND-IDX)
           PERFORM SAVE-ALL-ACCOUNTS
           MOVE RC-SUCCESS TO WS-RESULT-CODE
           PERFORM WRITE-TRANSACTION-RECORD
           DISPLAY "OK|DEPOSIT|" WS-TX-ID "|" WS-IN-ACCT-ID "|"
               WS-A-BALANCE(WS-FOUND-IDX)
           DISPLAY "RESULT|00".

       PROCESS-WITHDRAW.
           PERFORM LOAD-ALL-ACCOUNTS
           PERFORM FIND-ACCOUNT
           IF WS-FOUND-FLAG = 'N'
               MOVE RC-INVALID-ACCT TO WS-RESULT-CODE
               PERFORM WRITE-TRANSACTION-RECORD
               DISPLAY "RESULT|03"
               EXIT PARAGRAPH
           END-IF
           IF WS-A-STATUS(WS-FOUND-IDX) = 'F'
               MOVE RC-ACCOUNT-FROZEN TO WS-RESULT-CODE
               PERFORM WRITE-TRANSACTION-RECORD
               DISPLAY "RESULT|04"
               EXIT PARAGRAPH
           END-IF
           IF WS-A-BALANCE(WS-FOUND-IDX) < WS-IN-AMOUNT
               MOVE RC-NSF TO WS-RESULT-CODE
               PERFORM WRITE-TRANSACTION-RECORD
               DISPLAY "RESULT|01"
               EXIT PARAGRAPH
           END-IF
           IF WS-IN-AMOUNT > WS-DAILY-LIMIT
               MOVE RC-LIMIT-EXCEEDED TO WS-RESULT-CODE
               PERFORM WRITE-TRANSACTION-RECORD
               DISPLAY "RESULT|02"
               EXIT PARAGRAPH
           END-IF
           PERFORM GENERATE-TX-ID
           SUBTRACT WS-IN-AMOUNT FROM WS-A-BALANCE(WS-FOUND-IDX)
           PERFORM SAVE-ALL-ACCOUNTS
           MOVE RC-SUCCESS TO WS-RESULT-CODE
           PERFORM WRITE-TRANSACTION-RECORD
           DISPLAY "OK|WITHDRAW|" WS-TX-ID "|" WS-IN-ACCT-ID "|"
               WS-A-BALANCE(WS-FOUND-IDX)
           DISPLAY "RESULT|00".

       PROCESS-TRANSFER.
           PERFORM LOAD-ALL-ACCOUNTS
           PERFORM FIND-ACCOUNT
           IF WS-FOUND-FLAG = 'N'
               MOVE RC-INVALID-ACCT TO WS-RESULT-CODE
               PERFORM WRITE-TRANSACTION-RECORD
               DISPLAY "RESULT|03"
               EXIT PARAGRAPH
           END-IF
           IF WS-A-STATUS(WS-FOUND-IDX) = 'F'
               MOVE RC-ACCOUNT-FROZEN TO WS-RESULT-CODE
               PERFORM WRITE-TRANSACTION-RECORD
               DISPLAY "RESULT|04"
               EXIT PARAGRAPH
           END-IF
           IF WS-A-BALANCE(WS-FOUND-IDX) < WS-IN-AMOUNT
               MOVE RC-NSF TO WS-RESULT-CODE
               PERFORM WRITE-TRANSACTION-RECORD
               DISPLAY "RESULT|01"
               EXIT PARAGRAPH
           END-IF
           MOVE WS-FOUND-IDX TO WS-ACCT-IDX
           MOVE WS-IN-TARGET-ID TO WS-IN-ACCT-ID
           PERFORM FIND-ACCOUNT
           IF WS-FOUND-FLAG = 'N'
               MOVE RC-INVALID-ACCT TO WS-RESULT-CODE
               DISPLAY "RESULT|03"
               EXIT PARAGRAPH
           END-IF
           PERFORM GENERATE-TX-ID
           MOVE 'T' TO WS-IN-TYPE
           SUBTRACT WS-IN-AMOUNT FROM WS-A-BALANCE(WS-ACCT-IDX)
           ADD WS-IN-AMOUNT TO WS-A-BALANCE(WS-FOUND-IDX)
           PERFORM SAVE-ALL-ACCOUNTS
           MOVE RC-SUCCESS TO WS-RESULT-CODE
           PERFORM WRITE-TRANSACTION-RECORD
           DISPLAY "OK|TRANSFER|" WS-TX-ID "|" WS-IN-ACCT-ID
           DISPLAY "RESULT|00".

       PROCESS-BATCH.
           PERFORM LOAD-ALL-ACCOUNTS
           IF WS-ACCOUNT-COUNT > 0
               MOVE WS-A-ID(1)(5:1) TO WS-NODE-CODE
           END-IF
           DISPLAY "========================================"
           DISPLAY "  LEGACY LEDGER — BATCH PROCESSING LOG"
           DISPLAY "  NODE: BANK_" WS-NODE-CODE
           DISPLAY "  DATE: " WS-CURRENT-DATE
               "  TIME: " WS-CURRENT-TIME
           DISPLAY "  INPUT: BATCH-INPUT.DAT"
           DISPLAY "========================================"
           DISPLAY ""
           DISPLAY "--- BEGIN BATCH RUN ---"
           DISPLAY ""
           DISPLAY "SEQ  STATUS  TYPE  AMOUNT        ACCOUNT     "
               "BALANCE-AFTER  DESCRIPTION"
           DISPLAY "---  ------  ----  -----------   ----------  "
               "-------------  --------------------------------"

           OPEN INPUT BATCH-FILE
           IF WS-BATCH-STATUS NOT = '00'
               DISPLAY "ERROR|FILE-OPEN|" WS-BATCH-STATUS
               DISPLAY "RESULT|99"
               STOP RUN
           END-IF
           PERFORM UNTIL 1 = 0
               READ BATCH-FILE
                   AT END
                       CLOSE BATCH-FILE
                       EXIT PERFORM
               END-READ

               PERFORM PARSE-BATCH-LINE
               PERFORM PROCESS-ONE-TRANSACTION
           END-PERFORM

           DISPLAY ""
           DISPLAY "--- END BATCH RUN ---"
           DISPLAY ""
           DISPLAY "========================================"
           DISPLAY "  BATCH SUMMARY"
           DISPLAY "  ------"
           DISPLAY "  Total transactions read:    " WS-BATCH-SEQ
           DISPLAY "  Successful:                 " WS-BATCH-SUCCESS
           DISPLAY "  Failed:                     " WS-BATCH-FAILED
           DISPLAY "  ------"
           DISPLAY "  Total deposits:             " WS-TOTAL-DEPOSITS
           DISPLAY "  Total withdrawals:          " WS-TOTAL-WITHDRAWALS
           DISPLAY "  Total transfers:            " WS-TOTAL-TRANSFERS
           DISPLAY "========================================"

           PERFORM SAVE-ALL-ACCOUNTS
           DISPLAY "RESULT|00".

       PARSE-BATCH-LINE.
           UNSTRING BATCH-RECORD DELIMITED BY "|"
               INTO WS-BP-ACCT
                   WS-BP-TYPE
                   WS-BP-AMOUNT
                   WS-BP-DESC
                   WS-BP-TARGET
           END-UNSTRING
           MOVE WS-BP-ACCT TO WS-IN-ACCT-ID
           MOVE WS-BP-TYPE TO WS-IN-TYPE
           MOVE WS-BP-AMOUNT TO WS-IN-AMOUNT
           MOVE WS-BP-DESC TO WS-IN-DESC
           MOVE WS-BP-TARGET TO WS-IN-TARGET-ID.

       PROCESS-ONE-TRANSACTION.
           ADD 1 TO WS-BATCH-SEQ
           MOVE WS-BATCH-SEQ TO WS-SEQ-DISPLAY
           MOVE RC-SUCCESS TO WS-RESULT-CODE

           PERFORM FIND-ACCOUNT
           IF WS-FOUND-FLAG = 'N'
               MOVE RC-INVALID-ACCT TO WS-RESULT-CODE
           END-IF

           IF WS-RESULT-CODE = '00'
               IF WS-A-STATUS(WS-FOUND-IDX) = 'F'
                   MOVE RC-ACCOUNT-FROZEN TO WS-RESULT-CODE
               END-IF
           END-IF

           IF WS-RESULT-CODE = '00'
               EVALUATE WS-IN-TYPE
                   WHEN 'D'
                       ADD WS-IN-AMOUNT TO WS-A-BALANCE(WS-FOUND-IDX)
                       ADD WS-IN-AMOUNT TO WS-TOTAL-DEPOSITS
                       MOVE "DEP" TO WS-TYPE-DISPLAY
                   WHEN 'W'
                       IF WS-A-BALANCE(WS-FOUND-IDX) < WS-IN-AMOUNT
                           MOVE RC-NSF TO WS-RESULT-CODE
                       ELSE
                           SUBTRACT WS-IN-AMOUNT
                               FROM WS-A-BALANCE(WS-FOUND-IDX)
                           ADD WS-IN-AMOUNT TO WS-TOTAL-WITHDRAWALS
                       END-IF
                       MOVE "WDR" TO WS-TYPE-DISPLAY
                   WHEN 'T'
                       IF WS-A-BALANCE(WS-FOUND-IDX) < WS-IN-AMOUNT
                           MOVE RC-NSF TO WS-RESULT-CODE
                       ELSE
                           SUBTRACT WS-IN-AMOUNT
                               FROM WS-A-BALANCE(WS-FOUND-IDX)
                           ADD WS-IN-AMOUNT TO WS-TOTAL-TRANSFERS
                           MOVE WS-IN-TARGET-ID TO WS-IN-ACCT-ID
                           PERFORM FIND-ACCOUNT
                           IF WS-FOUND-FLAG = 'Y'
                               ADD WS-IN-AMOUNT TO
                                   WS-A-BALANCE(WS-FOUND-IDX)
                           END-IF
                       END-IF
                       MOVE "XFR" TO WS-TYPE-DISPLAY
                   WHEN 'I'
                       ADD WS-IN-AMOUNT TO WS-A-BALANCE(WS-FOUND-IDX)
                       MOVE "INT" TO WS-TYPE-DISPLAY
                   WHEN 'F'
                       SUBTRACT WS-IN-AMOUNT
                           FROM WS-A-BALANCE(WS-FOUND-IDX)
                       MOVE "FEE" TO WS-TYPE-DISPLAY
               END-EVALUATE
           END-IF

           PERFORM FORMAT-DISPLAY-LINE
           PERFORM GENERATE-TX-ID

           IF WS-IN-TYPE = 'D' AND WS-IN-AMOUNT > 9500.00
               IF WS-RESULT-CODE = '00'
                   DISPLAY " ** COMPLIANCE NOTE: Deposit "
                       WS-AMOUNT-DISPLAY
                       " within $500 of $10,000 CTR threshold"
               END-IF
           END-IF

           IF WS-RESULT-CODE = '00'
               ADD 1 TO WS-BATCH-SUCCESS
           ELSE
               ADD 1 TO WS-BATCH-FAILED
           END-IF.

       FORMAT-DISPLAY-LINE.
           MOVE WS-IN-AMOUNT TO WS-AMOUNT-DISPLAY
           MOVE WS-A-BALANCE(WS-FOUND-IDX) TO WS-BALANCE-DISPLAY

           EVALUATE WS-RESULT-CODE
               WHEN '00'
                   MOVE "OK    " TO WS-STATUS-DISPLAY
               WHEN '01'
                   MOVE "FAIL01" TO WS-STATUS-DISPLAY
               WHEN '02'
                   MOVE "FAIL02" TO WS-STATUS-DISPLAY
               WHEN '03'
                   MOVE "FAIL03" TO WS-STATUS-DISPLAY
               WHEN '04'
                   MOVE "FAIL04" TO WS-STATUS-DISPLAY
               WHEN OTHER
                   STRING "FAIL" WS-RESULT-CODE
                       DELIMITED SIZE INTO WS-STATUS-DISPLAY
                   END-STRING
           END-EVALUATE

           DISPLAY WS-SEQ-DISPLAY "  "
               WS-STATUS-DISPLAY "  "
               WS-TYPE-DISPLAY "  "
               WS-AMOUNT-DISPLAY "   "
               WS-IN-ACCT-ID "  "
               WS-BALANCE-DISPLAY "  "
               WS-IN-DESC.
