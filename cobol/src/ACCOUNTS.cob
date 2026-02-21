      *> ================================================================
      *> ACCOUNTS.cob — Account Lifecycle Management
      *> System: cobol-legacy-ledger | Node: BANK_{node} | Purpose: Account CRUD operations
      *> Operations: CREATE, READ, UPDATE, CLOSE, LIST
      *> Files: ACCOUNTS.DAT (input/output)
      *> Output Format: Pipe-delimited to STDOUT
      *> ================================================================
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ACCOUNTS.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ACCOUNTS-FILE
               ASSIGN TO "ACCOUNTS.DAT"
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-FILE-STATUS.

       DATA DIVISION.
       FILE SECTION.
       FD  ACCOUNTS-FILE.
       COPY "ACCTREC.cpy".

       WORKING-STORAGE SECTION.
       01  WS-FILE-STATUS         PIC XX VALUE SPACES.
       01  WS-OPERATION           PIC X(10) VALUE SPACES.
       01  WS-IN-ACCT-ID          PIC X(10) VALUE SPACES.
       01  WS-IN-NAME             PIC X(30) VALUE SPACES.
       01  WS-IN-TYPE             PIC X(1) VALUE 'C'.
       01  WS-IN-STATUS           PIC X(1) VALUE 'A'.
       01  WS-FOUND-FLAG          PIC X VALUE 'N'.
       01  WS-FOUND-IDX           PIC 9(3) VALUE 0.
       01  WS-ACCOUNT-COUNT       PIC 9(3) VALUE 0.
       01  WS-ACCT-IDX            PIC 9(3) VALUE 0.
       01  WS-ACCOUNT-TABLE.
           05  WS-ACCT-ENTRY OCCURS 100 TIMES.
               10  WS-A-ID        PIC X(10).
               10  WS-A-NAME      PIC X(30).
               10  WS-A-TYPE      PIC X(1).
               10  WS-A-BALANCE   PIC S9(10)V99.
               10  WS-A-STATUS    PIC X(1).
               10  WS-A-OPEN      PIC 9(8).
               10  WS-A-ACTIVITY  PIC 9(8).
       COPY "COMCODE.cpy".

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           ACCEPT WS-OPERATION FROM COMMAND-LINE

           EVALUATE WS-OPERATION
               WHEN "LIST"
                   PERFORM LIST-ACCOUNTS
               WHEN "CREATE"
                   ACCEPT WS-IN-ACCT-ID FROM COMMAND-LINE
                   ACCEPT WS-IN-NAME FROM COMMAND-LINE
                   ACCEPT WS-IN-TYPE FROM COMMAND-LINE
                   PERFORM CREATE-ACCOUNT
               WHEN "READ"
                   ACCEPT WS-IN-ACCT-ID FROM COMMAND-LINE
                   PERFORM READ-ACCOUNT
               WHEN "UPDATE"
                   ACCEPT WS-IN-ACCT-ID FROM COMMAND-LINE
                   ACCEPT WS-IN-STATUS FROM COMMAND-LINE
                   PERFORM UPDATE-ACCOUNT
               WHEN "CLOSE"
                   ACCEPT WS-IN-ACCT-ID FROM COMMAND-LINE
                   PERFORM CLOSE-ACCOUNT
               WHEN OTHER
                   DISPLAY "RESULT|99"
           END-EVALUATE

           STOP RUN.

       LIST-ACCOUNTS.
           OPEN INPUT ACCOUNTS-FILE
           PERFORM UNTIL 1 = 0
               READ ACCOUNTS-FILE
                   AT END
                       CLOSE ACCOUNTS-FILE
                       EXIT PERFORM
               END-READ
               DISPLAY "ACCOUNT|"
                   ACCT-ID "|"
                   ACCT-NAME "|"
                   ACCT-TYPE "|"
                   ACCT-BALANCE "|"
                   ACCT-STATUS "|"
                   ACCT-OPEN-DATE "|"
                   ACCT-LAST-ACTIVITY
           END-PERFORM
           DISPLAY "RESULT|00".

       LOAD-ALL-ACCOUNTS.
           MOVE 0 TO WS-ACCOUNT-COUNT
           OPEN INPUT ACCOUNTS-FILE
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

       WRITE-ALL-ACCOUNTS.
           OPEN OUTPUT ACCOUNTS-FILE
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

       CREATE-ACCOUNT.
           PERFORM LOAD-ALL-ACCOUNTS
           PERFORM FIND-ACCOUNT
           IF WS-FOUND-FLAG = 'Y'
               DISPLAY "RESULT|99"
               EXIT PARAGRAPH
           END-IF
           ADD 1 TO WS-ACCOUNT-COUNT
           MOVE WS-IN-ACCT-ID TO WS-A-ID(WS-ACCOUNT-COUNT)
           MOVE WS-IN-NAME TO WS-A-NAME(WS-ACCOUNT-COUNT)
           MOVE WS-IN-TYPE TO WS-A-TYPE(WS-ACCOUNT-COUNT)
           MOVE 0 TO WS-A-BALANCE(WS-ACCOUNT-COUNT)
           MOVE 'A' TO WS-A-STATUS(WS-ACCOUNT-COUNT)
           MOVE 20260217 TO WS-A-OPEN(WS-ACCOUNT-COUNT)
           MOVE 20260217 TO WS-A-ACTIVITY(WS-ACCOUNT-COUNT)
           PERFORM WRITE-ALL-ACCOUNTS
           DISPLAY "ACCOUNT-CREATED|" WS-IN-ACCT-ID
           DISPLAY "RESULT|00".

       READ-ACCOUNT.
           PERFORM LOAD-ALL-ACCOUNTS
           PERFORM FIND-ACCOUNT
           IF WS-FOUND-FLAG = 'N'
               DISPLAY "RESULT|03"
               EXIT PARAGRAPH
           END-IF
           DISPLAY "ACCOUNT|"
               WS-A-ID(WS-FOUND-IDX) "|"
               WS-A-NAME(WS-FOUND-IDX) "|"
               WS-A-TYPE(WS-FOUND-IDX) "|"
               WS-A-BALANCE(WS-FOUND-IDX) "|"
               WS-A-STATUS(WS-FOUND-IDX) "|"
               WS-A-OPEN(WS-FOUND-IDX) "|"
               WS-A-ACTIVITY(WS-FOUND-IDX)
           DISPLAY "RESULT|00".

       UPDATE-ACCOUNT.
           PERFORM LOAD-ALL-ACCOUNTS
           PERFORM FIND-ACCOUNT
           IF WS-FOUND-FLAG = 'N'
               DISPLAY "RESULT|03"
               EXIT PARAGRAPH
           END-IF
           MOVE WS-IN-STATUS TO WS-A-STATUS(WS-FOUND-IDX)
           MOVE 20260217 TO WS-A-ACTIVITY(WS-FOUND-IDX)
           PERFORM WRITE-ALL-ACCOUNTS
           DISPLAY "ACCOUNT-UPDATED|" WS-IN-ACCT-ID
           DISPLAY "RESULT|00".

       CLOSE-ACCOUNT.
           PERFORM LOAD-ALL-ACCOUNTS
           PERFORM FIND-ACCOUNT
           IF WS-FOUND-FLAG = 'N'
               DISPLAY "RESULT|03"
               EXIT PARAGRAPH
           END-IF
           MOVE 'C' TO WS-A-STATUS(WS-FOUND-IDX)
           MOVE 20260217 TO WS-A-ACTIVITY(WS-FOUND-IDX)
           PERFORM WRITE-ALL-ACCOUNTS
           DISPLAY "ACCOUNT-CLOSED|" WS-IN-ACCT-ID
           DISPLAY "RESULT|00".
