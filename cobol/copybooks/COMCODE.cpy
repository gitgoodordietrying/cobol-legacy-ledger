*================================================================*
* COMCODE.cpy — Common Status Codes and Bank IDs
* Shared across all COBOL programs and all 6 nodes
*================================================================*
 01  RESULT-CODES.
     05  RC-SUCCESS           PIC X(2) VALUE '00'.
     05  RC-NSF               PIC X(2) VALUE '01'.
     05  RC-LIMIT-EXCEEDED    PIC X(2) VALUE '02'.
     05  RC-INVALID-ACCT      PIC X(2) VALUE '03'.
     05  RC-ACCOUNT-FROZEN    PIC X(2) VALUE '04'.
     05  RC-FILE-ERROR        PIC X(2) VALUE '99'.

 01  BANK-IDS.
     05  BANK-FIRST-NATL      PIC X(8) VALUE 'BANK_A'.
     05  BANK-COMM-TRUST      PIC X(8) VALUE 'BANK_B'.
     05  BANK-PAC-SVGS        PIC X(8) VALUE 'BANK_C'.
     05  BANK-HRTG-FED        PIC X(8) VALUE 'BANK_D'.
     05  BANK-METRO-CU        PIC X(8) VALUE 'BANK_E'.
     05  BANK-CLEARING        PIC X(8) VALUE 'CLEARING'.

 01  ACCOUNT-TYPES.
     05  ACCT-CHECKING        PIC X(1) VALUE 'C'.
     05  ACCT-SAVINGS         PIC X(1) VALUE 'S'.

 01  TX-TYPES.
     05  TX-DEPOSIT           PIC X(1) VALUE 'D'.
     05  TX-WITHDRAW          PIC X(1) VALUE 'W'.
     05  TX-TRANSFER          PIC X(1) VALUE 'T'.
     05  TX-INTEREST          PIC X(1) VALUE 'I'.
     05  TX-FEE               PIC X(1) VALUE 'F'.

 01  DAILY-LIMIT            PIC 9(10)V99 VALUE 10000.00.
 01  MAX-ACCOUNTS           PIC 9(6) VALUE 100.
