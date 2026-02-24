      *>================================================================*
      *>  Program:     SIMULATE.cob
      *>  System:      LEGACY LEDGER — Per-Bank Daily Transaction Generator
      *>  Node:        All bank nodes (BANK_A through BANK_E)
      *>  Author:      AKD Solutions
      *>  Written:     2026-02-24
      *>
      *>  Purpose:
      *>    Generates deterministic pseudo-random daily transactions
      *>    for a single bank node. Part of the hub-and-spoke inter-bank
      *>    settlement simulation. Each invocation processes one bank
      *>    for one day.
      *>
      *>  Invocation:
      *>    ./SIMULATE BANK_A 1     (bank code, day number)
      *>
      *>  Transaction mix per day (~5-10 per bank):
      *>    40% Deposits    ($50-$5,000)
      *>    30% Withdrawals ($25-$2,000, NSF-checked)
      *>    20% Internal Transfers (between accounts in same bank)
      *>    10% Outbound Transfers (written to OUTBOUND.DAT)
      *>
      *>  Pseudo-Random Strategy:
      *>    Deterministic seed from day + account index + bank code.
      *>    Reproducible: same inputs always produce same transactions.
      *>
      *>  Files:
      *>    Input/Output: ACCOUNTS.DAT  (LINE SEQUENTIAL, 70-byte)
      *>    Output:       TRANSACT.DAT  (LINE SEQUENTIAL, 103-byte)
      *>    Output:       OUTBOUND.DAT  (LINE SEQUENTIAL, pipe-delimited)
      *>
      *>  Copybooks:
      *>    ACCTREC.cpy  — Account record layout
      *>    TRANSREC.cpy — Transaction record layout
      *>    COMCODE.cpy  — Status codes and bank identifiers
      *>    ACCTIO.cpy   — Account I/O working-storage
      *>    SIMREC.cpy   — Simulation parameters and counters
      *>
      *>  Change Log:
      *>    2026-02-24  AKD  Initial implementation — Simulation
      *>
      *>================================================================*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SIMULATE.

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
           SELECT OUTBOUND-FILE
               ASSIGN TO "OUTBOUND.DAT"
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-OB-STATUS.

       DATA DIVISION.
       FILE SECTION.
       FD  ACCOUNTS-FILE.
       COPY "ACCTREC.cpy".
       FD  TRANSACT-FILE.
       COPY "TRANSREC.cpy".
       FD  OUTBOUND-FILE.
       01  OUTBOUND-LINE             PIC X(120).

       WORKING-STORAGE SECTION.
       01  WS-FILE-STATUS            PIC XX VALUE SPACES.
       01  WS-TX-STATUS              PIC XX VALUE SPACES.
       01  WS-OB-STATUS              PIC XX VALUE SPACES.
       01  WS-CMD-LINE               PIC X(200) VALUE SPACES.
       01  WS-CURRENT-DATE           PIC 9(8) VALUE 0.
       01  WS-CURRENT-TIME           PIC 9(6) VALUE 0.
       COPY "ACCTIO.cpy".
       COPY "COMCODE.cpy".
       COPY "SIMREC.cpy".

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           ACCEPT WS-CURRENT-DATE FROM DATE YYYYMMDD
           ACCEPT WS-CURRENT-TIME FROM TIME
           ACCEPT WS-CMD-LINE FROM COMMAND-LINE

      *>   Parse: "BANK_A 1"
           UNSTRING WS-CMD-LINE DELIMITED BY SPACE
               INTO WS-BANK-CODE WS-DAY-NUM-STR
           END-UNSTRING
           MOVE FUNCTION TRIM(WS-BANK-CODE) TO WS-BANK-CODE
           MOVE FUNCTION TRIM(WS-DAY-NUM-STR) TO WS-DAY-NUM-STR
           MOVE FUNCTION NUMVAL(WS-DAY-NUM-STR) TO WS-DAY-NUM

      *>   Set bank seed from letter (A=1, B=2, ..., E=5)
           MOVE WS-BANK-CODE(6:1) TO WS-NODE-LETTER
           EVALUATE WS-NODE-LETTER
               WHEN 'A' MOVE 1 TO WS-BANK-SEED
               WHEN 'B' MOVE 2 TO WS-BANK-SEED
               WHEN 'C' MOVE 3 TO WS-BANK-SEED
               WHEN 'D' MOVE 4 TO WS-BANK-SEED
               WHEN 'E' MOVE 5 TO WS-BANK-SEED
               WHEN OTHER
                   DISPLAY "ERROR: Invalid bank code " WS-BANK-CODE
                   STOP RUN
           END-EVALUATE

           PERFORM LOAD-ALL-ACCOUNTS

      *>   Open transaction log for append
           OPEN EXTEND TRANSACT-FILE
           IF WS-TX-STATUS NOT = '00'
      *>       File may not exist — create it
               OPEN OUTPUT TRANSACT-FILE
               IF WS-TX-STATUS NOT = '00'
                   DISPLAY "ERROR|TX-FILE|" WS-TX-STATUS
                   STOP RUN
               END-IF
           END-IF

      *>   Open outbound file (overwrite each day)
           OPEN OUTPUT OUTBOUND-FILE
           IF WS-OB-STATUS NOT = '00'
               DISPLAY "ERROR|OB-FILE|" WS-OB-STATUS
               STOP RUN
           END-IF

           DISPLAY "=== SIMULATE " WS-BANK-CODE " DAY "
               WS-DAY-NUM " ==="

           PERFORM GENERATE-DAILY-TRANSACTIONS

           CLOSE TRANSACT-FILE
           CLOSE OUTBOUND-FILE
           PERFORM SAVE-ALL-ACCOUNTS

           DISPLAY "  Deposits:    " WS-SIM-DEPOSITS
           DISPLAY "  Withdrawals: " WS-SIM-WITHDRAWALS
           DISPLAY "  Transfers:   " WS-SIM-TRANSFERS
           DISPLAY "  Outbound:    " WS-SIM-OUTBOUND
           DISPLAY "  Failed:      " WS-SIM-FAILED
           DISPLAY "  Total:       " WS-SIM-TOTAL
           DISPLAY "=== END " WS-BANK-CODE " DAY "
               WS-DAY-NUM " ==="

           STOP RUN.

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

       SAVE-ALL-ACCOUNTS.
           OPEN OUTPUT ACCOUNTS-FILE
           IF WS-FILE-STATUS NOT = '00'
               DISPLAY "ERROR|FILE-OPEN|" WS-FILE-STATUS
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

       GENERATE-DAILY-TRANSACTIONS.
           PERFORM VARYING WS-ACCT-IDX FROM 1 BY 1
               UNTIL WS-ACCT-IDX > WS-ACCOUNT-COUNT
               PERFORM PROCESS-ACCOUNT-DAY
           END-PERFORM.

       PROCESS-ACCOUNT-DAY.
      *>   Skip inactive accounts
           IF WS-A-STATUS(WS-ACCT-IDX) NOT = 'A'
               EXIT PARAGRAPH
           END-IF

      *>   Activity seed: determines if account transacts today
           COMPUTE WS-SEED = WS-DAY-NUM * 7919
               + WS-ACCT-IDX * 104729
               + WS-BANK-SEED * 997
           COMPUTE WS-SEED = FUNCTION MOD(WS-SEED 10000)

      *>   ~60% of accounts transact each day
           IF WS-SEED >= 6000
               EXIT PARAGRAPH
           END-IF

      *>   Type/amount seed: determines what kind of transaction
           COMPUTE WS-SEED2 = WS-DAY-NUM * 6271
               + WS-ACCT-IDX * 8641
               + WS-BANK-SEED * 3571
           COMPUTE WS-SEED2 = FUNCTION MOD(WS-SEED2 10000)

      *>   Transaction type by seed range:
      *>     0-3999 = Deposit (40%)
      *>     4000-6999 = Withdrawal (30%)
      *>     7000-8999 = Internal Transfer (20%)
      *>     9000-9999 = Outbound Transfer (10%)
           EVALUATE TRUE
               WHEN WS-SEED2 < 4000
                   PERFORM DO-DEPOSIT
               WHEN WS-SEED2 < 7000
                   PERFORM DO-WITHDRAWAL
               WHEN WS-SEED2 < 9000
                   PERFORM DO-INTERNAL-TRANSFER
               WHEN OTHER
                   PERFORM DO-OUTBOUND-TRANSFER
           END-EVALUATE.

       DO-DEPOSIT.
           ADD 1 TO WS-TX-SEQ
           ADD 1 TO WS-SIM-TOTAL

      *>   Amount: $50-$5,000
           COMPUTE WS-SIM-AMOUNT =
               50 + FUNCTION MOD((WS-SEED2 * 31) 4950)
           MOVE 'D' TO WS-SIM-TYPE
           MOVE '00' TO WS-SIM-RESULT
           MOVE "Simulated deposit" TO WS-SIM-DESC

           ADD WS-SIM-AMOUNT TO WS-A-BALANCE(WS-ACCT-IDX)
           MOVE WS-CURRENT-DATE TO WS-A-ACTIVITY(WS-ACCT-IDX)
           PERFORM WRITE-SIM-TRANSACTION
           ADD 1 TO WS-SIM-DEPOSITS.

       DO-WITHDRAWAL.
           ADD 1 TO WS-TX-SEQ
           ADD 1 TO WS-SIM-TOTAL

      *>   Amount: $25-$2,000
           COMPUTE WS-SIM-AMOUNT =
               25 + FUNCTION MOD((WS-SEED2 * 17) 1975)
           MOVE 'W' TO WS-SIM-TYPE
           MOVE "Simulated withdrawal" TO WS-SIM-DESC

      *>   NSF check
           IF WS-A-BALANCE(WS-ACCT-IDX) < WS-SIM-AMOUNT
               MOVE '01' TO WS-SIM-RESULT
               MOVE "Simulated withdrawal - NSF" TO WS-SIM-DESC
               PERFORM WRITE-SIM-TRANSACTION
               ADD 1 TO WS-SIM-FAILED
           ELSE
               MOVE '00' TO WS-SIM-RESULT
               SUBTRACT WS-SIM-AMOUNT
                   FROM WS-A-BALANCE(WS-ACCT-IDX)
               MOVE WS-CURRENT-DATE TO WS-A-ACTIVITY(WS-ACCT-IDX)
               PERFORM WRITE-SIM-TRANSACTION
               ADD 1 TO WS-SIM-WITHDRAWALS
           END-IF.

       DO-INTERNAL-TRANSFER.
           ADD 1 TO WS-TX-SEQ
           ADD 1 TO WS-SIM-TOTAL

      *>   Amount: $100-$3,000
           COMPUTE WS-SIM-AMOUNT =
               100 + FUNCTION MOD((WS-SEED2 * 23) 2900)
           MOVE 'T' TO WS-SIM-TYPE

      *>   Pick transfer target (different active account)
           COMPUTE WS-TARGET-IDX = FUNCTION MOD(
               (WS-ACCT-IDX + WS-SEED2) WS-ACCOUNT-COUNT) + 1
           IF WS-TARGET-IDX = WS-ACCT-IDX
               COMPUTE WS-TARGET-IDX = FUNCTION MOD(
                   WS-ACCT-IDX WS-ACCOUNT-COUNT) + 1
           END-IF

           IF WS-A-STATUS(WS-TARGET-IDX) NOT = 'A'
               MOVE '03' TO WS-SIM-RESULT
               MOVE "Transfer - target inactive" TO WS-SIM-DESC
               PERFORM WRITE-SIM-TRANSACTION
               ADD 1 TO WS-SIM-FAILED
           ELSE
               IF WS-A-BALANCE(WS-ACCT-IDX) < WS-SIM-AMOUNT
                   MOVE '01' TO WS-SIM-RESULT
                   MOVE "Internal transfer - NSF" TO WS-SIM-DESC
                   PERFORM WRITE-SIM-TRANSACTION
                   ADD 1 TO WS-SIM-FAILED
               ELSE
                   MOVE '00' TO WS-SIM-RESULT
                   MOVE "Simulated internal transfer"
                       TO WS-SIM-DESC
                   SUBTRACT WS-SIM-AMOUNT
                       FROM WS-A-BALANCE(WS-ACCT-IDX)
                   ADD WS-SIM-AMOUNT
                       TO WS-A-BALANCE(WS-TARGET-IDX)
                   MOVE WS-CURRENT-DATE
                       TO WS-A-ACTIVITY(WS-ACCT-IDX)
                   MOVE WS-CURRENT-DATE
                       TO WS-A-ACTIVITY(WS-TARGET-IDX)
                   PERFORM WRITE-SIM-TRANSACTION
                   ADD 1 TO WS-SIM-TRANSFERS
               END-IF
           END-IF.

       DO-OUTBOUND-TRANSFER.
           ADD 1 TO WS-TX-SEQ
           ADD 1 TO WS-SIM-TOTAL

      *>   Amount: $200-$5,000
           COMPUTE WS-SIM-AMOUNT =
               200 + FUNCTION MOD((WS-SEED2 * 13) 4800)
           MOVE 'T' TO WS-SIM-TYPE

      *>   NSF check
           IF WS-A-BALANCE(WS-ACCT-IDX) < WS-SIM-AMOUNT
               MOVE '01' TO WS-SIM-RESULT
               MOVE "Outbound transfer - NSF" TO WS-SIM-DESC
               PERFORM WRITE-SIM-TRANSACTION
               ADD 1 TO WS-SIM-FAILED
           ELSE
               PERFORM COMPUTE-OUTBOUND-DEST
               MOVE '00' TO WS-SIM-RESULT
               MOVE "Outbound interbank transfer"
                   TO WS-SIM-DESC
               SUBTRACT WS-SIM-AMOUNT
                   FROM WS-A-BALANCE(WS-ACCT-IDX)
               MOVE WS-CURRENT-DATE
                   TO WS-A-ACTIVITY(WS-ACCT-IDX)
               PERFORM WRITE-SIM-TRANSACTION
               PERFORM WRITE-OUTBOUND-RECORD
               ADD 1 TO WS-SIM-OUTBOUND
           END-IF.

       COMPUTE-OUTBOUND-DEST.
      *>   Pick target bank (different from current)
           COMPUTE WS-TARGET-BANK = FUNCTION MOD(
               (WS-BANK-SEED + WS-SEED2) 4)
           ADD 1 TO WS-TARGET-BANK
           IF WS-TARGET-BANK >= WS-BANK-SEED
               ADD 1 TO WS-TARGET-BANK
           END-IF
           EVALUATE WS-TARGET-BANK
               WHEN 1 MOVE 'A' TO WS-TARGET-BANK-LTR
               WHEN 2 MOVE 'B' TO WS-TARGET-BANK-LTR
               WHEN 3 MOVE 'C' TO WS-TARGET-BANK-LTR
               WHEN 4 MOVE 'D' TO WS-TARGET-BANK-LTR
               WHEN 5 MOVE 'E' TO WS-TARGET-BANK-LTR
               WHEN OTHER MOVE 'A' TO WS-TARGET-BANK-LTR
           END-EVALUATE

      *>   Pick target account number (1-6)
           COMPUTE WS-TARGET-ACCT-NUM =
               FUNCTION MOD(WS-SEED2 6) + 1
      *>   Build destination ID: ACT-X-00N
           MOVE SPACES TO WS-OB-DEST-ID
           STRING "ACT-" DELIMITED SIZE
               WS-TARGET-BANK-LTR DELIMITED SIZE
               "-00" DELIMITED SIZE
               WS-TARGET-ACCT-NUM DELIMITED SIZE
               INTO WS-OB-DEST-ID
           END-STRING.

       WRITE-SIM-TRANSACTION.
      *>   Build TX-ID: SIM-X-DDDNNN (12 chars exactly)
           MOVE SPACES TO TRANS-ID
           STRING "SIM-" DELIMITED SIZE
               WS-NODE-LETTER DELIMITED SIZE
               "-" DELIMITED SIZE
               WS-DAY-NUM DELIMITED SIZE
               WS-TX-SEQ DELIMITED SIZE
               INTO TRANS-ID
           END-STRING
           MOVE WS-A-ID(WS-ACCT-IDX) TO TRANS-ACCT-ID
           MOVE WS-SIM-TYPE TO TRANS-TYPE
           MOVE WS-SIM-AMOUNT TO TRANS-AMOUNT
           MOVE WS-CURRENT-DATE TO TRANS-DATE
           MOVE WS-CURRENT-TIME TO TRANS-TIME
           MOVE WS-SIM-DESC TO TRANS-DESC
           MOVE WS-SIM-RESULT TO TRANS-STATUS
           MOVE SPACES TO TRANS-BATCH-ID
           WRITE TRANSACTION-RECORD.

       WRITE-OUTBOUND-RECORD.
      *>   Format amount as integer + decimal for pipe-delimited file
           MOVE WS-SIM-AMOUNT TO WS-AMT-DISPLAY
           MOVE WS-AMT-INT-PART TO WS-AMT-STRING(1:8)
           MOVE '.' TO WS-AMT-STRING(9:1)
           MOVE WS-AMT-DEC-PART TO WS-AMT-STRING(10:2)
      *>   Build pipe-delimited outbound record
           MOVE SPACES TO OUTBOUND-LINE
           STRING
               WS-A-ID(WS-ACCT-IDX) DELIMITED SPACE
               "|" DELIMITED SIZE
               WS-OB-DEST-ID DELIMITED SPACE
               "|" DELIMITED SIZE
               WS-AMT-STRING DELIMITED SPACE
               "|" DELIMITED SIZE
               "Interbank transfer" DELIMITED SIZE
               "|" DELIMITED SIZE
               WS-DAY-NUM DELIMITED SIZE
               INTO OUTBOUND-LINE
           END-STRING
           WRITE OUTBOUND-LINE.
