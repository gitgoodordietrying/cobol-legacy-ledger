      *================================================================*
      * SMOKETEST.cob — Compiler and I/O verification
      * Tests: compilation, copybook resolution, file write, file read,
      *        fixed-width record format, pipe-delimited DISPLAY output
      * Compile: cobc -x -free -I ../copybooks SMOKETEST.cob -o ../bin/SMOKETEST
      * Run:     cd banks/BANK_A && ../../cobol/bin/SMOKETEST
      *================================================================*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SMOKETEST.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ACCOUNT-FILE
               ASSIGN TO "TEST-ACCOUNTS.DAT"
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-FILE-STATUS.

       DATA DIVISION.
       FILE SECTION.
       FD  ACCOUNT-FILE.
       COPY "ACCTREC.cpy".

       WORKING-STORAGE SECTION.
       01  WS-FILE-STATUS         PIC XX VALUE SPACES.
           88  WS-FILE-OK         VALUE '00'.
           88  WS-FILE-EOF        VALUE '10'.
       01  WS-RECORD-COUNT        PIC 9(4) VALUE 0.

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           PERFORM WRITE-TEST-RECORD
           PERFORM READ-TEST-RECORD
           PERFORM CLEANUP
           STOP RUN.

       WRITE-TEST-RECORD.
           OPEN OUTPUT ACCOUNT-FILE
           IF NOT WS-FILE-OK
               DISPLAY "ERROR|FILE-OPEN-WRITE|" WS-FILE-STATUS
               STOP RUN
           END-IF

           INITIALIZE ACCOUNT-RECORD
           MOVE "ACT-T-001"      TO ACCT-ID
           MOVE "Smoke Test User" TO ACCT-NAME
           MOVE "C"              TO ACCT-TYPE
           MOVE 12345.67         TO ACCT-BALANCE
           MOVE "A"              TO ACCT-STATUS
           MOVE 20260217         TO ACCT-OPEN-DATE
           MOVE 20260217         TO ACCT-LAST-ACTIVITY

           WRITE ACCOUNT-RECORD
           IF NOT WS-FILE-OK
               DISPLAY "ERROR|FILE-WRITE|" WS-FILE-STATUS
               STOP RUN
           END-IF

           CLOSE ACCOUNT-FILE
           DISPLAY "OK|WRITE|ACT-T-001|Smoke Test User".

       READ-TEST-RECORD.
           OPEN INPUT ACCOUNT-FILE
           IF NOT WS-FILE-OK
               DISPLAY "ERROR|FILE-OPEN-READ|" WS-FILE-STATUS
               STOP RUN
           END-IF

           READ ACCOUNT-FILE
               AT END
                   DISPLAY "ERROR|EMPTY-FILE|No records found"
                   CLOSE ACCOUNT-FILE
                   STOP RUN
           END-READ

           IF NOT WS-FILE-OK AND NOT WS-FILE-EOF
               DISPLAY "ERROR|FILE-READ|" WS-FILE-STATUS
               CLOSE ACCOUNT-FILE
               STOP RUN
           END-IF

           DISPLAY "OK|READ|"
               ACCT-ID "|"
               ACCT-NAME "|"
               ACCT-TYPE "|"
               ACCT-BALANCE "|"
               ACCT-STATUS "|"
               ACCT-OPEN-DATE "|"
               ACCT-LAST-ACTIVITY

           CLOSE ACCOUNT-FILE.

       CLEANUP.
      *    Test file is left in banks/BANK_A/TEST-ACCOUNTS.DAT for inspection
           DISPLAY "SMOKE-TEST|PASS|All checks succeeded".
