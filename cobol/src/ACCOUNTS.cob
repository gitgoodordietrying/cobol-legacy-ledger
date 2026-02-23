      *>================================================================*
      *>  Program:     ACCOUNTS.cob
      *>  System:      LEGACY LEDGER — Account Lifecycle Management
      *>  Node:        All (same binary, per-node data directories)
      *>  Author:      AKD Solutions
      *>  Written:     2026-02-17
      *>  Modified:    2026-02-23
      *>
      *>  Purpose:
      *>    Account master file CRUD operations. Creates, reads,
      *>    updates, and lists customer and nostro accounts stored
      *>    in the node's ACCOUNTS.DAT sequential file.
      *>
      *>  Operations (via command-line argument):
      *>    CREATE  — Add new account to master file
      *>    READ    — Display single account by ID
      *>    LIST    — Display all active accounts
      *>    UPDATE  — Modify account status
      *>    CLOSE   — Set account status to 'C' (closed)
      *>
      *>  Files:
      *>    Input/Output: ACCOUNTS.DAT (LINE SEQUENTIAL, 70-byte records)
      *>
      *>  Copybooks:
      *>    ACCTREC.cpy  — Account record layout (70 bytes)
      *>    COMCODE.cpy  — Shared status codes and bank identifiers
      *>    ACCTIO.cpy   — Shared account I/O paragraphs
      *>
      *>  Output Format (to STDOUT, pipe-delimited):
      *>    Account: ACCOUNT|ACCT-ID|NAME|TYPE|BALANCE|STATUS|OPENED|LASTACT
      *>    Created: ACCOUNT-CREATED|ACCT-ID
      *>    Updated: ACCOUNT-UPDATED|ACCT-ID
      *>    Closed:  ACCOUNT-CLOSED|ACCT-ID
      *>    Result:  RESULT|XX  (where XX = status code from COMCODE.cpy)
      *>
      *>  Exit Codes:
      *>    RESULT|00 — Success
      *>    RESULT|03 — Account not found (or duplicate on CREATE)
      *>    RESULT|99 — Invalid operation or file I/O error
      *>
      *>  Dependencies:
      *>    Requires ACCOUNTS.DAT to exist in CWD (working directory).
      *>    CWD is set by the Python bridge to banks/{NODE}/.
      *>    If file does not exist, returns RESULT|99 on READ/LIST,
      *>    or creates it on first CREATE.
      *>
      *>  Change Log:
      *>    2026-02-17  AKD  Initial implementation — Phase 1
      *>    2026-02-23  AKD  Production headers, dynamic dates,
      *>                     file status checks, copybook extraction
      *>
      *>================================================================*
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
       01  WS-CURRENT-DATE        PIC 9(8) VALUE 0.
       01  WS-CURRENT-TIME        PIC 9(6) VALUE 0.
       COPY "ACCTIO.cpy".
       COPY "COMCODE.cpy".

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           ACCEPT WS-CURRENT-DATE FROM DATE YYYYMMDD
           ACCEPT WS-CURRENT-TIME FROM TIME
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
           MOVE WS-CURRENT-DATE TO WS-A-OPEN(WS-ACCOUNT-COUNT)
           MOVE WS-CURRENT-DATE TO WS-A-ACTIVITY(WS-ACCOUNT-COUNT)
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
           MOVE WS-CURRENT-DATE TO WS-A-ACTIVITY(WS-FOUND-IDX)
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
           MOVE WS-CURRENT-DATE TO WS-A-ACTIVITY(WS-FOUND-IDX)
           PERFORM WRITE-ALL-ACCOUNTS
           DISPLAY "ACCOUNT-CLOSED|" WS-IN-ACCT-ID
           DISPLAY "RESULT|00".
