*> ================================================================
*> PAYCOM.cpy — Payroll "Common" Constants
*> Used by: PAYROLL.cob, TAXCALC.cob, DEDUCTN.cob, PAYBATCH.cob
*> ================================================================
*>
*> THREE DEVELOPERS, THREE ERAS, ONE FILE:
*>   JRK 1974: Original constants. Cryptic names (WK-A1, WK-B2).
*>   PMR 1983: Added tax constants. Better names but duplicates
*>             some of JRK's values with different precision.
*>   SLW 1991: Added benefit constants. Comments contradict
*>             actual values in two places.
*>
*> WARNING: PAYCOM-DAILY-LIMIT and WK-B2 are the same concept
*> (max daily payroll run) but have different values. PAYROLL.cob
*> uses WK-B2. DEDUCTN.cob uses PAYCOM-DAILY-LIMIT. Nobody
*> knows which is correct.
*>

*> JRK originals — do NOT rename, PAYROLL.cob PERFORM depends
*> on these exact names for ALTER statement targets
 01  WK-CONSTANTS.
     05  WK-A1                   PIC 9(3) VALUE 100.
     05  WK-B2                   PIC 9(7)V99 VALUE 500000.00.
     05  WK-C3                   PIC 9(3)V99 VALUE 7.65.
     05  WK-D4                   PIC 9(1) VALUE 0.
*>       JRK: "overflow flag" — set to 1 if batch > WK-B2
*>       Never actually checked anywhere.
     05  WK-E5                   PIC X(8) VALUE 'PAYROLL '.

*> PMR additions — proper names, some duplicate JRK values
 01  PAYCOM-TAX-CONSTANTS.
     05  PAYCOM-FICA-RATE        PIC 9V9999 VALUE 0.0765.
*>       PMR: "Standard FICA rate 7.65%"
*>       Note: Same as WK-C3 but stored as decimal not percentage
     05  PAYCOM-FICA-LIMIT       PIC S9(7)V99 COMP-3
                                 VALUE 160200.00.
*>       PMR: "FICA wage base limit — update annually"
*>       Last updated: 1997. Current limit is much higher.
     05  PAYCOM-FED-EXEMPT       PIC S9(5)V99 COMP-3
                                 VALUE 12950.00.
     05  PAYCOM-STATE-RATE       PIC 9V9999 VALUE 0.0500.
*>       PMR: "Default state tax rate 5%"
*>       KNOWN ISSUE: TAXCALC.cob hardcodes 7.25% and ignores this

*> SLW additions — benefit plan costs
 01  PAYCOM-BENEFITS.
*>       SLW: "Medical premium — $250/month per employee"
*>       Actual VALUE below is 275.00 (not 250). Comment is wrong.
     05  PAYCOM-MED-BASIC        PIC S9(5)V99 COMP-3
                                 VALUE 275.00.
*>       SLW: "Premium plan — $500/month"
     05  PAYCOM-MED-PREMIUM      PIC S9(5)V99 COMP-3
                                 VALUE 500.00.
*>       SLW: "Dental — $75/month"
     05  PAYCOM-DENTAL-COST      PIC S9(5)V99 COMP-3
                                 VALUE 75.00.
     05  PAYCOM-401K-MATCH       PIC 9V99 VALUE 0.50.
*>       SLW: "Company matches 50% of employee contribution"
*>       DEDUCTN.cob uses 0.04 (4% match cap) — different concept

*> Dead entries — left from removed garnishment feature (1988)
 01  PAYCOM-DEAD-SECTION.
     05  PAYCOM-GARN-FLAG        PIC X(1) VALUE 'N'.
     05  PAYCOM-GARN-PCT         PIC 9V99 VALUE 0.00.
     05  PAYCOM-GARN-MAX         PIC S9(5)V99 COMP-3
                                 VALUE 0.00.

*> SLW 1991: daily limit for payroll batch runs
 01  PAYCOM-LIMITS.
     05  PAYCOM-DAILY-LIMIT      PIC 9(7)V99 VALUE 750000.00.
*>       CONFLICT: WK-B2 = 500000.00, this = 750000.00.
*>       Both claim to be "max daily payroll". Joy.
     05  PAYCOM-MAX-EMPLOYEES    PIC 9(4) VALUE 9999.
