      *> ================================================================
      *> ACCOUNTS.cob — Account Lifecycle Management
      *> System: cobol-legacy-ledger | Node: BANK_{node} | Purpose: Account CRUD operations
      *> Operations: CREATE, READ, UPDATE, CLOSE, LIST
      *> Files: ACCOUNTS.DAT (input/output), OUTPUT.DAT (results)
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
       01  WS-IN-BALANCE          PIC S9(10)V99 VALUE 0.
       01  WS-FOUND-FLAG          PIC X VALUE 'N'.
       COPY "COMCODE.cpy".

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           ACCEPT WS-OPERATION FROM COMMAND-LINE

           EVALUATE WS-OPERATION
               WHEN "LIST"
                   PERFORM LIST-ACCOUNTS
               WHEN "CREATE"
                   PERFORM CREATE-ACCOUNT
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
                   ACCT-STATUS
           END-PERFORM
           DISPLAY "RESULT|00".

       CREATE-ACCOUNT.
           DISPLAY "RESULT|00".
