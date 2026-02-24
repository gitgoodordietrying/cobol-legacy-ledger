*> ================================================================
*> SIMREC.cpy — Simulation Working-Storage Variables
*> Used by: SIMULATE.cob, SETTLE.cob
*>
*> Provides working-storage for the hub-and-spoke inter-bank
*> settlement simulation. Includes pseudo-random seed generation,
*> transaction counters, and outbound record formatting.
*> ================================================================
 01  WS-SIM-PARAMS.
     05  WS-BANK-CODE        PIC X(8).
     05  WS-DAY-NUM          PIC 9(3).
     05  WS-DAY-NUM-STR      PIC X(5).
     05  WS-BANK-SEED        PIC 9(5).
     05  WS-NODE-LETTER      PIC X(1).
     05  WS-SEED             PIC 9(5).
     05  WS-SEED2            PIC 9(5).
     05  WS-TX-SEQ           PIC 9(3) VALUE 0.

 01  WS-SIM-COUNTERS.
     05  WS-SIM-DEPOSITS     PIC 9(5) VALUE 0.
     05  WS-SIM-WITHDRAWALS  PIC 9(5) VALUE 0.
     05  WS-SIM-TRANSFERS    PIC 9(5) VALUE 0.
     05  WS-SIM-OUTBOUND     PIC 9(5) VALUE 0.
     05  WS-SIM-FAILED       PIC 9(5) VALUE 0.
     05  WS-SIM-TOTAL        PIC 9(5) VALUE 0.

 01  WS-SIM-WORK.
     05  WS-SIM-AMOUNT       PIC S9(10)V99 VALUE 0.
     05  WS-SIM-RESULT       PIC X(2) VALUE '00'.
     05  WS-SIM-TYPE         PIC X(1) VALUE SPACES.
     05  WS-SIM-DESC         PIC X(40) VALUE SPACES.
     05  WS-TARGET-IDX       PIC 9(3) VALUE 0.
     05  WS-TARGET-BANK      PIC 9(1) VALUE 0.
     05  WS-TARGET-BANK-LTR  PIC X(1) VALUE SPACES.
     05  WS-TARGET-ACCT-NUM  PIC 9(1) VALUE 0.
     05  WS-OB-DEST-ID       PIC X(10) VALUE SPACES.
     05  WS-AMT-DISPLAY      PIC 9(8)V99.
     05  WS-AMT-REDEF REDEFINES WS-AMT-DISPLAY.
         10  WS-AMT-INT-PART PIC 9(8).
         10  WS-AMT-DEC-PART PIC 99.
     05  WS-AMT-STRING       PIC X(12).

 01  WS-SETTLE-WORK.
     05  WS-STL-SEQ          PIC 9(5) VALUE 0.
     05  WS-STL-TOTAL-VOL    PIC S9(12)V99 VALUE 0.
     05  WS-STL-COUNT        PIC 9(5) VALUE 0.
     05  WS-STL-SOURCE-LTR   PIC X(1).
     05  WS-STL-DEST-LTR     PIC X(1).
     05  WS-STL-NOSTRO-ID    PIC X(10).
     05  WS-STL-SRC-IDX      PIC 9(3).
     05  WS-STL-DST-IDX      PIC 9(3).
     05  WS-STL-AMOUNT       PIC S9(10)V99 VALUE 0.
     05  WS-STL-AMT-STR      PIC X(15).

 01  WS-OB-PARSE.
     05  WS-OBP-SOURCE       PIC X(10).
     05  WS-OBP-DEST         PIC X(10).
     05  WS-OBP-AMT-STR      PIC X(15).
     05  WS-OBP-DESC         PIC X(40).
     05  WS-OBP-DAY-STR      PIC X(5).
