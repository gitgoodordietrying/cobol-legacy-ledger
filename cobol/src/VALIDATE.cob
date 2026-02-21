      *> ================================================================
      *> VALIDATE.cob — Business Rules & Validation
      *> System: cobol-legacy-ledger | Purpose: Validate transactions
      *> Operations: CHECK-BALANCE, CHECK-LIMIT, CHECK-STATUS
      *> Output Format: RESULT|{RC} to STDOUT
      *> ================================================================
       IDENTIFICATION DIVISION.
       PROGRAM-ID. VALIDATE.

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
       01  WS-IN-ACCT-ID          PIC X(10) VALUE SPACES.
       01  WS-IN-AMOUNT           PIC S9(10)V99 VALUE 0.
       01  WS-RESULT-CODE         PIC X(2) VALUE '00'.
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
       01  WS-DAILY-LIMIT         PIC 9(10)V99 VALUE 50000.00.
       COPY "COMCODE.cpy".

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           ACCEPT WS-IN-ACCT-ID FROM COMMAND-LINE
           ACCEPT WS-IN-AMOUNT FROM COMMAND-LINE

           PERFORM LOAD-ALL-ACCOUNTS
           PERFORM FIND-ACCOUNT

           IF WS-FOUND-FLAG = 'N'
               MOVE RC-INVALID-ACCT TO WS-RESULT-CODE
               DISPLAY "RESULT|" WS-RESULT-CODE
               STOP RUN
           END-IF

           PERFORM CHECK-ACCOUNT-STATUS
           IF WS-RESULT-CODE NOT = '00'
               DISPLAY "RESULT|" WS-RESULT-CODE
               STOP RUN
           END-IF

           PERFORM CHECK-BALANCE
           IF WS-RESULT-CODE NOT = '00'
               DISPLAY "RESULT|" WS-RESULT-CODE
               STOP RUN
           END-IF

           PERFORM CHECK-DAILY-LIMIT
           IF WS-RESULT-CODE NOT = '00'
               DISPLAY "RESULT|" WS-RESULT-CODE
               STOP RUN
           END-IF

           DISPLAY "RESULT|" WS-RESULT-CODE

           STOP RUN.

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

       CHECK-ACCOUNT-STATUS.
           MOVE '00' TO WS-RESULT-CODE
           IF WS-A-STATUS(WS-FOUND-IDX) = 'F'
               MOVE RC-ACCOUNT-FROZEN TO WS-RESULT-CODE
               EXIT PARAGRAPH
           END-IF.

       CHECK-BALANCE.
           MOVE '00' TO WS-RESULT-CODE
           IF WS-A-BALANCE(WS-FOUND-IDX) < WS-IN-AMOUNT
               MOVE RC-NSF TO WS-RESULT-CODE
               EXIT PARAGRAPH
           END-IF.

       CHECK-DAILY-LIMIT.
           MOVE '00' TO WS-RESULT-CODE
           IF WS-IN-AMOUNT > WS-DAILY-LIMIT
               MOVE RC-LIMIT-EXCEEDED TO WS-RESULT-CODE
               EXIT PARAGRAPH
           END-IF.
