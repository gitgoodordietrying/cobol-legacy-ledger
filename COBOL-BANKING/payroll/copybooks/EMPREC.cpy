*> ================================================================
*> EMPREC.cpy — Employee Record Layout (95 bytes, LINE SEQUENTIAL)
*> Used by: PAYROLL.cob, TAXCALC.cob, DEDUCTN.cob, PAYBATCH.cob
*> ================================================================
*>
*> LEGACY NOTE (JRK, 1974): Original layout designed for IBM 3270
*> terminal screen width. Extended in 1991 by SLW for benefits.
*>
*> MAINFRAME vs. DEMO:
*>   On a real IBM mainframe, salary/rate fields would use COMP-3
*>   (packed decimal) and hours/counters would use COMP (binary)
*>   for System/390 throughput optimization. Here we use DISPLAY
*>   format for LINE SEQUENTIAL file compatibility, but the mixed
*>   COMP types appear in WORKING-STORAGE computation fields
*>   throughout the programs — which is where the real anti-pattern
*>   lives (implicit type conversions on every COMPUTE).
*>
*> COMP-3 CONCEPT: Packed decimal — 2 digits per byte + sign nibble.
*>   PIC S9(7)V99 COMP-3 = 5 bytes. IBM AP/SP/MP/DP instructions
*>   operate directly on packed decimal without conversion.
*>
*> COMP CONCEPT: Binary — PIC S9(4) COMP = 2-byte halfword.
*>   Range -32768 to +32767. Faster for integer comparisons.
*>
*> WARNING: Do NOT change field order. JCL job PAYRL210 depends
*> on byte offsets for SORT FIELDS. See JCL member PAYRL210 in
*> SYS1.PROCLIB (if you can find it).
*>
*> Layout (95 bytes total):
*>   Bytes 01-07:  EMP-ID            PIC X(7)
*>   Bytes 08-32:  EMP-NAME          PIC X(25)
*>   Bytes 33-40:  EMP-BANK-CODE     PIC X(8)
*>   Bytes 41-50:  EMP-ACCT-ID       PIC X(10)
*>   Bytes 51-59:  EMP-SALARY        PIC S9(7)V99  (DISPLAY, 9 bytes)
*>   Bytes 60-64:  EMP-HOURLY-RATE   PIC S9(3)V99  (DISPLAY, 5 bytes)
*>   Bytes 65-68:  EMP-HOURS-WORKED  PIC S9(4)     (DISPLAY, 4 bytes)
*>   Bytes 69-72:  EMP-PAY-PERIODS   PIC S9(4)     (DISPLAY, 4 bytes)
*>   Byte  73:     EMP-STATUS        PIC X(1)
*>   Byte  74:     EMP-PAY-TYPE      PIC X(1)
*>   Bytes 75-76:  EMP-TAX-BRACKET   PIC 9(2)
*>   Bytes 77-84:  EMP-HIRE-DATE     PIC 9(8)
*>   Bytes 85-88:  EMP-DEPT-CODE     PIC X(4)
*>   Byte  89:     EMP-MEDICAL-PLAN  PIC X(1)
*>   Byte  90:     EMP-DENTAL-FLAG   PIC X(1)
*>   Bytes 91-93:  EMP-401K-PCT      PIC 9V99
*>   Bytes 94-95:  EMP-FILLER        PIC X(2)
*>
 01  EMPLOYEE-RECORD.
     05  EMP-ID                  PIC X(7).
     05  EMP-NAME                PIC X(25).
     05  EMP-BANK-CODE           PIC X(8).
     05  EMP-ACCT-ID             PIC X(10).
*>   DISPLAY format for file I/O. On a mainframe these would be
*>   COMP-3 packed decimal for throughput — see WORKING-STORAGE
*>   fields in each program for the COMP-3 computation pattern.
     05  EMP-SALARY              PIC S9(7)V99.
     05  EMP-HOURLY-RATE         PIC S9(3)V99.
     05  EMP-HOURS-WORKED        PIC S9(4).
     05  EMP-PAY-PERIODS         PIC S9(4).
     05  EMP-STATUS              PIC X(1).
         88  EMP-ACTIVE          VALUE 'A'.
         88  EMP-TERMINATED      VALUE 'T'.
         88  EMP-ON-LEAVE        VALUE 'L'.
     05  EMP-PAY-TYPE            PIC X(1).
         88  EMP-SALARIED        VALUE 'S'.
         88  EMP-HOURLY          VALUE 'H'.
     05  EMP-TAX-BRACKET         PIC 9(2).
     05  EMP-HIRE-DATE           PIC 9(8).
     05  EMP-DEPT-CODE           PIC X(4).
*>   SLW 1991: Added deduction fields. Should have been a
*>   separate copybook but "we were in a hurry" (per SLW).
     05  EMP-MEDICAL-PLAN        PIC X(1).
         88  EMP-MED-NONE        VALUE 'N'.
         88  EMP-MED-BASIC       VALUE 'B'.
         88  EMP-MED-PREMIUM     VALUE 'P'.
     05  EMP-DENTAL-FLAG         PIC X(1).
         88  EMP-HAS-DENTAL      VALUE 'Y'.
         88  EMP-NO-DENTAL       VALUE 'N'.
     05  EMP-401K-PCT            PIC 9V99.
     05  EMP-FILLER              PIC X(2).
