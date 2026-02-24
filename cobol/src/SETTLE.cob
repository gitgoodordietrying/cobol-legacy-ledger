      *>================================================================*
      *>  Program:     SETTLE.cob
      *>  System:      LEGACY LEDGER — Clearing House Settlement Processor
      *>  Node:        CLEARING (central hub)
      *>  Author:      AKD Solutions
      *>  Written:     2026-02-24
      *>
      *>  Purpose:
      *>    Processes outbound inter-bank transfer requests from all
      *>    5 bank nodes through the central clearing house. Implements
      *>    3-leg settlement: debit source nostro, credit destination
      *>    nostro, write settlement record.
      *>
      *>  Invocation:
      *>    ./SETTLE 1     (day number, run from banks/clearing/)
      *>
      *>  Settlement Flow (per outbound record):
      *>    1. Parse outbound record (source acct, dest acct, amount)
      *>    2. Map source bank letter → NST-BANK-X (debit nostro)
      *>    3. Map dest bank letter → NST-BANK-Y (credit nostro)
      *>    4. Write debit + credit transaction records
      *>
      *>  Files:
      *>    Input/Output: ACCOUNTS.DAT  (clearing nostro accounts)
      *>    Output:       TRANSACT.DAT  (settlement transaction log)
      *>    Input:        ../BANK_X/OUTBOUND.DAT (5 bank outbound files)
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
       PROGRAM-ID. SETTLE.

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
               ASSIGN TO WS-OB-FILE-PATH
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
       01  WS-OB-FILE-PATH           PIC X(60) VALUE SPACES.
       01  WS-CMD-LINE               PIC X(200) VALUE SPACES.
       01  WS-CURRENT-DATE           PIC 9(8) VALUE 0.
       01  WS-CURRENT-TIME           PIC 9(6) VALUE 0.
       01  WS-CURRENT-BANK-LTR      PIC X(1) VALUE SPACES.
       01  WS-IN-ACCT-ID            PIC X(10) VALUE SPACES.
       COPY "ACCTIO.cpy".
       COPY "COMCODE.cpy".
       COPY "SIMREC.cpy".

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           ACCEPT WS-CURRENT-DATE FROM DATE YYYYMMDD
           ACCEPT WS-CURRENT-TIME FROM TIME
           ACCEPT WS-CMD-LINE FROM COMMAND-LINE

      *>   Parse: day number
           MOVE FUNCTION TRIM(WS-CMD-LINE) TO WS-DAY-NUM-STR
           MOVE FUNCTION NUMVAL(WS-DAY-NUM-STR) TO WS-DAY-NUM

           PERFORM LOAD-ALL-ACCOUNTS

      *>   Open settlement transaction log for append
           OPEN EXTEND TRANSACT-FILE
           IF WS-TX-STATUS NOT = '00'
               OPEN OUTPUT TRANSACT-FILE
               IF WS-TX-STATUS NOT = '00'
                   DISPLAY "ERROR|TX-FILE|" WS-TX-STATUS
                   STOP RUN
               END-IF
           END-IF

           DISPLAY "=== SETTLE DAY " WS-DAY-NUM " ==="

           PERFORM PROCESS-ALL-OUTBOUND

           CLOSE TRANSACT-FILE
           PERFORM SAVE-ALL-ACCOUNTS

           DISPLAY "  Settlements:  " WS-STL-COUNT
           DISPLAY "  Total volume: " WS-STL-TOTAL-VOL
           DISPLAY "=== END SETTLE DAY " WS-DAY-NUM " ==="
           DISPLAY ""

      *>   Display nostro balances
           DISPLAY "  NOSTRO BALANCES:"
           PERFORM VARYING WS-ACCT-IDX FROM 1 BY 1
               UNTIL WS-ACCT-IDX > WS-ACCOUNT-COUNT
               DISPLAY "    " WS-A-ID(WS-ACCT-IDX)
                   " = " WS-A-BALANCE(WS-ACCT-IDX)
           END-PERFORM

           STOP RUN.

       LOAD-ALL-ACCOUNTS.
           MOVE 0 TO WS-ACCOUNT-COUNT
           OPEN INPUT ACCOUNTS-FILE
           IF WS-FILE-STATUS NOT = '00'
               DISPLAY "ERROR|FILE-OPEN|" WS-FILE-STATUS
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

       FIND-NOSTRO-ACCOUNT.
      *>   Search clearing account table for WS-IN-ACCT-ID
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

       PROCESS-ALL-OUTBOUND.
      *>   Process outbound files from each bank
           MOVE "../BANK_A/OUTBOUND.DAT" TO WS-OB-FILE-PATH
           MOVE 'A' TO WS-CURRENT-BANK-LTR
           PERFORM PROCESS-ONE-BANK-OUTBOUND

           MOVE "../BANK_B/OUTBOUND.DAT" TO WS-OB-FILE-PATH
           MOVE 'B' TO WS-CURRENT-BANK-LTR
           PERFORM PROCESS-ONE-BANK-OUTBOUND

           MOVE "../BANK_C/OUTBOUND.DAT" TO WS-OB-FILE-PATH
           MOVE 'C' TO WS-CURRENT-BANK-LTR
           PERFORM PROCESS-ONE-BANK-OUTBOUND

           MOVE "../BANK_D/OUTBOUND.DAT" TO WS-OB-FILE-PATH
           MOVE 'D' TO WS-CURRENT-BANK-LTR
           PERFORM PROCESS-ONE-BANK-OUTBOUND

           MOVE "../BANK_E/OUTBOUND.DAT" TO WS-OB-FILE-PATH
           MOVE 'E' TO WS-CURRENT-BANK-LTR
           PERFORM PROCESS-ONE-BANK-OUTBOUND.

       PROCESS-ONE-BANK-OUTBOUND.
           OPEN INPUT OUTBOUND-FILE
           IF WS-OB-STATUS NOT = '00'
      *>       No outbound file for this bank — skip
               EXIT PARAGRAPH
           END-IF
           PERFORM UNTIL 1 = 0
               READ OUTBOUND-FILE
                   AT END
                       CLOSE OUTBOUND-FILE
                       EXIT PERFORM
               END-READ
               PERFORM PROCESS-SETTLEMENT
           END-PERFORM.

       PROCESS-SETTLEMENT.
      *>   Parse pipe-delimited outbound record:
      *>   SOURCE-ACCT|DEST-ACCT|AMOUNT|DESC|DAY
           UNSTRING OUTBOUND-LINE DELIMITED BY "|"
               INTO WS-OBP-SOURCE
                   WS-OBP-DEST
                   WS-OBP-AMT-STR
                   WS-OBP-DESC
                   WS-OBP-DAY-STR
           END-UNSTRING

      *>   Parse amount
           MOVE FUNCTION NUMVAL(
               FUNCTION TRIM(WS-OBP-AMT-STR))
               TO WS-STL-AMOUNT

      *>   Extract source bank letter (ACT-A-xxx → 'A', pos 5)
           MOVE WS-OBP-SOURCE(5:1) TO WS-STL-SOURCE-LTR
      *>   Extract dest bank letter (ACT-B-xxx → 'B', pos 5)
           MOVE WS-OBP-DEST(5:1) TO WS-STL-DEST-LTR

      *>   Find source nostro (NST-BANK-X)
           MOVE SPACES TO WS-STL-NOSTRO-ID
           STRING "NST-BANK-" DELIMITED SIZE
               WS-STL-SOURCE-LTR DELIMITED SIZE
               INTO WS-STL-NOSTRO-ID
           END-STRING
           MOVE WS-STL-NOSTRO-ID TO WS-IN-ACCT-ID
           PERFORM FIND-NOSTRO-ACCOUNT
           IF WS-FOUND-FLAG = 'N'
               DISPLAY "WARN: Nostro not found "
                   WS-STL-NOSTRO-ID
               EXIT PARAGRAPH
           END-IF
           MOVE WS-FOUND-IDX TO WS-STL-SRC-IDX

      *>   Find dest nostro (NST-BANK-Y)
           MOVE SPACES TO WS-STL-NOSTRO-ID
           STRING "NST-BANK-" DELIMITED SIZE
               WS-STL-DEST-LTR DELIMITED SIZE
               INTO WS-STL-NOSTRO-ID
           END-STRING
           MOVE WS-STL-NOSTRO-ID TO WS-IN-ACCT-ID
           PERFORM FIND-NOSTRO-ACCOUNT
           IF WS-FOUND-FLAG = 'N'
               DISPLAY "WARN: Nostro not found "
                   WS-STL-NOSTRO-ID
               EXIT PARAGRAPH
           END-IF
           MOVE WS-FOUND-IDX TO WS-STL-DST-IDX

      *>   3-leg settlement:
      *>   Leg 1: Debit source bank's nostro
           SUBTRACT WS-STL-AMOUNT
               FROM WS-A-BALANCE(WS-STL-SRC-IDX)
      *>   Leg 2: Credit dest bank's nostro
           ADD WS-STL-AMOUNT
               TO WS-A-BALANCE(WS-STL-DST-IDX)
      *>   Leg 3: Write settlement records

      *>   Write debit transaction record
           ADD 1 TO WS-STL-SEQ
           MOVE SPACES TO TRANS-ID
           STRING "STL-" DELIMITED SIZE
               WS-DAY-NUM DELIMITED SIZE
               WS-STL-SEQ DELIMITED SIZE
               INTO TRANS-ID
           END-STRING
           MOVE WS-A-ID(WS-STL-SRC-IDX) TO TRANS-ACCT-ID
           MOVE 'W' TO TRANS-TYPE
           MOVE WS-STL-AMOUNT TO TRANS-AMOUNT
           MOVE WS-CURRENT-DATE TO TRANS-DATE
           MOVE WS-CURRENT-TIME TO TRANS-TIME
           STRING "Settlement debit " DELIMITED SIZE
               WS-OBP-SOURCE DELIMITED SPACE
               " -> " DELIMITED SIZE
               WS-OBP-DEST DELIMITED SPACE
               INTO TRANS-DESC
           END-STRING
           MOVE '00' TO TRANS-STATUS
           MOVE SPACES TO TRANS-BATCH-ID
           WRITE TRANSACTION-RECORD

      *>   Write credit transaction record
           ADD 1 TO WS-STL-SEQ
           MOVE SPACES TO TRANS-ID
           STRING "STL-" DELIMITED SIZE
               WS-DAY-NUM DELIMITED SIZE
               WS-STL-SEQ DELIMITED SIZE
               INTO TRANS-ID
           END-STRING
           MOVE WS-A-ID(WS-STL-DST-IDX) TO TRANS-ACCT-ID
           MOVE 'D' TO TRANS-TYPE
           MOVE WS-STL-AMOUNT TO TRANS-AMOUNT
           MOVE WS-CURRENT-DATE TO TRANS-DATE
           MOVE WS-CURRENT-TIME TO TRANS-TIME
           MOVE SPACES TO TRANS-DESC
           STRING "Settlement credit " DELIMITED SIZE
               WS-OBP-SOURCE DELIMITED SPACE
               " -> " DELIMITED SIZE
               WS-OBP-DEST DELIMITED SPACE
               INTO TRANS-DESC
           END-STRING
           MOVE '00' TO TRANS-STATUS
           MOVE SPACES TO TRANS-BATCH-ID
           WRITE TRANSACTION-RECORD

           MOVE WS-CURRENT-DATE TO WS-A-ACTIVITY(WS-STL-SRC-IDX)
           MOVE WS-CURRENT-DATE TO WS-A-ACTIVITY(WS-STL-DST-IDX)

           ADD WS-STL-AMOUNT TO WS-STL-TOTAL-VOL
           ADD 1 TO WS-STL-COUNT.
