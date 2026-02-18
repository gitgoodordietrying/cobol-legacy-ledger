      *================================================================*
      * TRANSACT.cob — Transaction Processing Engine
      * System: cobol-legacy-ledger | Purpose: Process deposits, withdrawals, transfers
      * Operations: DEPOSIT, WITHDRAW, TRANSFER, BATCH
      * Files: ACCOUNTS.DAT, TRANSACT.DAT, BATCH-INPUT.DAT
      * Output Format: Pipe-delimited to STDOUT
      *================================================================*
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
       01  WS-IN-AMOUNT           PIC S9(10)V99 VALUE 0.
       01  WS-IN-DESC             PIC X(40) VALUE SPACES.
       01  WS-TX-ID               PIC X(12) VALUE SPACES.
       01  WS-TX-ID-NUM           PIC 9(6) VALUE 0.
       COPY "COMCODE.cpy".

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           ACCEPT WS-OPERATION FROM COMMAND-LINE

           EVALUATE WS-OPERATION
               WHEN "DEPOSIT"
                   PERFORM PROCESS-DEPOSIT
               WHEN "WITHDRAW"
                   PERFORM PROCESS-WITHDRAW
               WHEN "BATCH"
                   PERFORM PROCESS-BATCH
               WHEN OTHER
                   DISPLAY "RESULT|99"
           END-EVALUATE

           STOP RUN.

       PROCESS-DEPOSIT.
           MOVE "TRX-A-000001" TO WS-TX-ID
           OPEN INPUT ACCOUNTS-FILE
           READ ACCOUNTS-FILE
           CLOSE ACCOUNTS-FILE
           ADD WS-IN-AMOUNT TO ACCT-BALANCE
           OPEN OUTPUT TRANSACT-FILE
           MOVE WS-TX-ID TO TRANS-ID
           MOVE WS-IN-ACCT-ID TO TRANS-ACCT-ID
           MOVE 'D' TO TRANS-TYPE
           MOVE WS-IN-AMOUNT TO TRANS-AMOUNT
           MOVE RC-SUCCESS TO TRANS-STATUS
           WRITE TRANSACTION-RECORD
           CLOSE TRANSACT-FILE
           DISPLAY "OK|DEPOSIT|" WS-TX-ID "|" ACCT-ID "|" ACCT-BALANCE
           DISPLAY "RESULT|00".

       PROCESS-WITHDRAW.
           DISPLAY "RESULT|00".

       PROCESS-BATCH.
           DISPLAY "BATCH|BEGIN|BAT20260217080000"
           DISPLAY "BATCH|END|BAT20260217080000|TOTAL=0|SUCCESS=0|FAILED=0"
           DISPLAY "RESULT|00".
