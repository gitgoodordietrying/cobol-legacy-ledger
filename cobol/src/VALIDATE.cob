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
       COPY "COMCODE.cpy".

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           ACCEPT WS-IN-ACCT-ID FROM COMMAND-LINE

           PERFORM VALIDATE-RECORD

           DISPLAY "RESULT|" WS-RESULT-CODE

           STOP RUN.

       VALIDATE-RECORD.
           OPEN INPUT ACCOUNTS-FILE
           READ ACCOUNTS-FILE
               AT END
                   MOVE RC-INVALID-ACCT TO WS-RESULT-CODE
                   CLOSE ACCOUNTS-FILE
                   EXIT PARAGRAPH
           END-READ
           CLOSE ACCOUNTS-FILE

           IF ACCT-STATUS = "F"
               MOVE RC-ACCOUNT-FROZEN TO WS-RESULT-CODE
           END-IF

           IF ACCT-BALANCE < WS-IN-AMOUNT
               MOVE RC-NSF TO WS-RESULT-CODE
           END-IF

           IF WS-IN-AMOUNT > DAILY-LIMIT
               MOVE RC-LIMIT-EXCEEDED TO WS-RESULT-CODE
           END-IF.
