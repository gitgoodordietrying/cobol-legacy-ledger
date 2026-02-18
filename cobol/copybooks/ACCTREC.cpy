*================================================================*
* ACCTREC.cpy — Account Record Layout
* Used by: ACCOUNTS.cob, TRANSACT.cob, REPORTS.cob, VALIDATE.cob
*================================================================*
 01  ACCOUNT-RECORD.
     05  ACCT-ID              PIC X(10).
     05  ACCT-NAME            PIC X(30).
     05  ACCT-TYPE            PIC X(1).
         88  ACCT-CHECKING    VALUE 'C'.
         88  ACCT-SAVINGS     VALUE 'S'.
     05  ACCT-BALANCE         PIC S9(10)V99.
     05  ACCT-STATUS          PIC X(1).
         88  ACCT-ACTIVE      VALUE 'A'.
         88  ACCT-CLOSED      VALUE 'C'.
         88  ACCT-FROZEN      VALUE 'F'.
     05  ACCT-OPEN-DATE       PIC 9(8).
     05  ACCT-LAST-ACTIVITY   PIC 9(8).
