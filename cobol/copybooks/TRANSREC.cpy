*================================================================*
* TRANSREC.cpy — Transaction Record Layout
* Used by: TRANSACT.cob, REPORTS.cob, VALIDATE.cob
*================================================================*
 01  TRANSACTION-RECORD.
     05  TRANS-ID             PIC X(12).
     05  TRANS-ACCT-ID        PIC X(10).
     05  TRANS-TYPE           PIC X(1).
         88  TRANS-DEPOSIT    VALUE 'D'.
         88  TRANS-WITHDRAW   VALUE 'W'.
         88  TRANS-TRANSFER   VALUE 'T'.
         88  TRANS-INTEREST   VALUE 'I'.
         88  TRANS-FEE        VALUE 'F'.
     05  TRANS-AMOUNT         PIC S9(10)V99.
     05  TRANS-DATE           PIC 9(8).
     05  TRANS-TIME           PIC 9(6).
     05  TRANS-DESC           PIC X(40).
     05  TRANS-STATUS         PIC X(2).
         88  TRANS-SUCCESS    VALUE '00'.
         88  TRANS-NSF        VALUE '01'.
         88  TRANS-LIMIT      VALUE '02'.
         88  TRANS-BAD-ACCT   VALUE '03'.
         88  TRANS-FROZEN     VALUE '04'.
     05  TRANS-BATCH-ID       PIC X(12).
