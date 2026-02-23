*> ================================================================
*> ACCTIO.cpy — Shared Account I/O Working-Storage Variables
*> Used by: ACCOUNTS.cob, TRANSACT.cob, VALIDATE.cob,
*>          INTEREST.cob, FEES.cob, RECONCILE.cpy
*>
*> Provides the in-memory account table and search index variables
*> used by LOAD-ALL-ACCOUNTS, FIND-ACCOUNT, and WRITE-ALL-ACCOUNTS
*> paragraphs across all programs that operate on ACCOUNTS.DAT.
*>
*> Usage: COPY "ACCTIO.cpy" in WORKING-STORAGE SECTION.
*>
*> Note: PROCEDURE DIVISION paragraphs (LOAD-ALL-ACCOUNTS,
*> FIND-ACCOUNT, WRITE-ALL-ACCOUNTS) follow a shared pattern
*> but remain in each program to allow per-program customization
*> (e.g., TRANSACT names its write paragraph SAVE-ALL-ACCOUNTS).
*> This is standard enterprise COBOL practice — shared data layout,
*> per-program procedure logic.
*> ================================================================
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
