# 02_COBOL_AND_DATA

COBOL programs, copybooks, record layouts, and data seeding strategy.

---

> **IMPORTANT:** Read `COBOL_STYLE_REFERENCE.md` and `COBOL_SUPPLEMENTS.md` before implementing any COBOL program. Run the smoke test before writing ACCOUNTS.cob. These reference documents establish the GnuCOBOL text-file I/O patterns used throughout the system.

---

## Copybooks (Shared Record Layouts)

### ACCTREC.cpy — Account Record Layout

**File location:** `cobol/copybooks/ACCTREC.cpy`
**Total length:** 70 bytes per record
**Used by:** ACCOUNTS.cob, TRANSACT.cob, REPORTS.cob, VALIDATE.cob

```cobol
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
```

**Record breakdown:**
- Bytes 1–10: Account ID (left-justified, space-padded)
- Bytes 11–40: Account name (left-justified, space-padded)
- Byte 41: Account type (C = checking, S = savings)
- Bytes 42–53: Balance (11 digits + 2 decimals, signed)
- Byte 54: Status (A = active, C = closed, F = frozen)
- Bytes 55–62: Open date (YYYYMMDD)
- Bytes 63–70: Last activity (YYYYMMDD)

**Example record (fixed-width):**
```
ACT-A-001 Maria Santos                  C000001542050A2024010120240101
```

**Byte breakdown:**
- `ACT-A-001 ` → 10 bytes (right-padded with 1 space)
- `Maria Santos                  ` → 30 bytes (right-padded with 18 spaces)
- `C` → 1 byte (account type)
- `000001542050` → 12 bytes (no decimal point; `V` is implied, $15,420.50 = 1542050 cents = 12 digits)
- `A` → 1 byte (status)
- `20240101` → 8 bytes (open date YYYYMMDD)
- `20240101` → 8 bytes (last activity YYYYMMDD)
- **Total: 70 bytes ✓**

*Note: COBOL's `V` is an implied decimal — no byte is stored. The balance $15,420.50 is stored as 000001542050 (12 digits representing cents).*

---

### TRANSREC.cpy — Transaction Record Layout

**File location:** `cobol/copybooks/TRANSREC.cpy`
**Total length:** 103 bytes per record
**Used by:** TRANSACT.cob, REPORTS.cob, VALIDATE.cob

```cobol
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
```

**Record breakdown:**
- Bytes 1–12: Transaction ID (TRX-xxxxxxxxxx)
- Bytes 13–22: Account ID
- Byte 23: Transaction type (D/W/T/I/F)
- Bytes 24–35: Amount (11 digits + 2 decimals, signed)
- Bytes 36–43: Date (YYYYMMDD)
- Bytes 44–49: Time (HHMMSS)
- Bytes 50–89: Description (40 chars)
- Bytes 90–91: Status (00=success, 01=NSF, 02=limit, 03=bad account, 04=frozen)
- Bytes 92–103: Batch ID (BAT-xxxxxxxxxx or empty)

**Example record (fixed-width):**
```
TRX-20240101ACCT000001D0000015420.5020240101101530Direct deposit - Employer payroll00
```

---

### COMCODE.cpy — Common Codes and Constants

**File location:** `cobol/copybooks/COMCODE.cpy`
**Purpose:** Shared status codes, bank IDs, and constants (new file)

```cobol
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
```

---

## COBOL Programs

### ACCOUNTS.cob — Account Lifecycle Management

**File location:** `cobol/src/ACCOUNTS.cob`
**Operations:** CREATE, READ, UPDATE, CLOSE, LIST
**I/O Files:** ACCOUNTS.DAT (read/write), OUTPUT.DAT (results)
**Purpose:** Manage account creation, queries, and status changes

*(Full source copied from v1 exactly — 381 lines)*

**Key paragraphs:**
- `CREATE-ACCOUNT` — adds a new account to ACCOUNTS.DAT
- `READ-ACCOUNT` — finds and displays a single account
- `UPDATE-ACCOUNT` — modifies name or status
- `CLOSE-ACCOUNT` — marks account as closed (balance must be zero)
- `LIST-ACCOUNTS` — displays all accounts
- `CHECK-DUPLICATE` — searches for existing account ID
- `LOAD-ALL-ACCOUNTS` — loads all accounts into working storage
- `WRITE-ALL-ACCOUNTS` — rewrites entire file from working storage

**Output format:** Pipe-delimited to STDOUT
```
OK|CREATED|ACCT000001|Maria Santos|C|15420.50|A|20240101
ACCOUNT|ACCT000001|Maria Santos|C|15420.50|A|20240101|20240101
ERROR|ACCOUNT NOT FOUND: ACCT000099
RESULT|00
```

**Known issues (see KNOWN_ISSUES.md):**
- A1: OCCURS 100 TIMES — silent overflow if >100 accounts
- A2: Full sequential scan for every READ/UPDATE

**To implement:**
1. Copy `cobol/src/ACCOUNTS.cob` from v1 repo as-is
2. No modifications
3. Compile with `cobc -x -free ACCOUNTS.cob`

---

### TRANSACT.cob — Transaction Processing Engine

**File location:** `cobol/src/TRANSACT.cob`
**Operations:** DEPOSIT, WITHDRAW, TRANSFER, BATCH
**I/O Files:** ACCOUNTS.DAT (read/write), TRANSACT.DAT (append), BATCH-INPUT.DAT (read)
**Purpose:** Execute transactions with validation

*(Full source copied from v1 exactly — 708 lines)*

**Key paragraphs:**
- `PROCESS-DEPOSIT` — add funds to account
- `PROCESS-WITHDRAW` — remove funds (with NSF + daily limit checks)
- `PROCESS-TRANSFER` — move funds between two accounts
- `PROCESS-BATCH` — sequential batch processing (nightly settlement mode)
- `BATCH-DEPOSIT`, `BATCH-WITHDRAW`, `BATCH-TRANSFER`, `BATCH-FEE` — batch variants
- `LOAD-ACCOUNTS` — cache all accounts in working storage
- `SAVE-ACCOUNTS` — rewrite entire ACCOUNTS.DAT
- `WRITE-TRANSACTION-RECORD` — append to TRANSACT.DAT

**Output format:** Pipe-delimited to STDOUT
```
OK|DEPOSIT|TRX-20240101ACCT000001|ACCT000001|3200.00|18620.50|Maria Santos
OK|WITHDRAW|TRX-20240101ACCT000004|ACCT000004|3000.00|ERROR|INSUFFICIENT FUNDS
OK|TRANSFER|TRX-20240101ACCT000002|ACCT000002|ACCT000001|5000.00|79200.00|20620.50
BATCH|BEGIN|BAT20240102080000
BATCH-TX|1|D|ACCT000001|3200.00|Direct deposit - Employer payroll
BATCH-TX-RESULT|1|SUCCESS|00|TRX-xxx|18620.50|Maria Santos
...
BATCH|END|BAT20240102080000|TOTAL=15|SUCCESS=14|FAILED=1
RESULT|00
```

**Known issues (see KNOWN_ISSUES.md):**
- T1–T9: TRACE display lines in production paths
- T10: WS-DAILY-TOTAL not persisted (resets per run)
- T11: BATCH-FEE allows negative balance
- T12: WS-IN-ACCT-ID clobbered during target lookup

**To implement:**
1. Copy `cobol/src/TRANSACT.cob` from v1 repo as-is
2. No modifications
3. Compile with `cobc -x -free TRANSACT.cob`

---

### VALIDATE.cob — Business Rules & Validation

**File location:** `cobol/src/VALIDATE.cob`
**Purpose:** Cross-check account and transaction rules
**Operations:** CHECK-BALANCE, CHECK-LIMIT, CHECK-STATUS, VALIDATE-RECORD

**I/O Files:** ACCOUNTS.DAT (read-only)

**Input (via WORKING-STORAGE):**
- `WS-IN-ACCT-ID` — account to validate
- `WS-IN-AMOUNT` — transaction amount
- `WS-IN-TYPE` — transaction type (D/W/T/I/F)

**Output (via WORKING-STORAGE + DISPLAY):**
- `RESULT-CODE` — validation result (00-04 or 99)

**Key paragraphs:**
- `CHECK-ACCOUNT-STATUS` — Set RESULT-CODE '04' if ACCT-STATUS = 'F', '03' if account not found
- `CHECK-BALANCE` — Set RESULT-CODE '01' if ACCT-BALANCE < WS-IN-AMOUNT (for withdrawals only)
- `CHECK-DAILY-LIMIT` — Set RESULT-CODE '02' if WS-IN-AMOUNT > DAILY-LIMIT
- `VALIDATE-RECORD` — Call above checks in sequence; return first failure or '00' for success

**Output format:** `RESULT|RC` where RC is 00-04 or 99 (pipe-delimited to STDOUT)

**Usage:** Called from TRANSACT.cob before any DEBIT operation (WITHDRAW, TRANSFER, FEE). Independently verifies the Python bridge's business logic validation rules.

---

### REPORTS.cob — Reporting and Reconciliation

**File location:** `cobol/src/REPORTS.cob`
**Purpose:** Generate ledger reports for human review
**Reports:** STATEMENT, LEDGER, EOD (end-of-day), AUDIT

**I/O Files:** ACCOUNTS.DAT (read-only), TRANSACT.DAT (read-only)

**Operations accepted on command line:** STATEMENT, LEDGER, EOD, AUDIT

**Key paragraphs:**
- `PRINT-STATEMENT` — Filter TRANSACT.DAT for one ACCT-ID, display all transactions in date order
- `PRINT-LEDGER` — Read all of ACCOUNTS.DAT, display each account: ID|NAME|TYPE|BALANCE|STATUS
- `PRINT-EOD` — Sum all ACCT-BALANCE by account type (checking vs. savings); count transactions by status code
- `PRINT-AUDIT` — Display full TRANSACT.DAT with all fields (ID|ACCOUNT|TYPE|AMOUNT|DATE|TIME|DESC|STATUS|BATCH-ID)

**Output format:** Pipe-delimited to STDOUT, one record per line

**Example outputs:**
```
STATEMENT for ACT-A-001:
STATEMENT|ACT-A-001|Maria Santos
TX|TRX-xxx|D|3200.00|20240101
TX|TRX-yyy|W|500.00|20240102

LEDGER:
ACCOUNT|ACT-A-001|Maria Santos|C|15420.50|A
ACCOUNT|ACT-A-002|James Chen|S|84200.00|A

EOD:
SUMMARY|TOTAL-CHECKING|668671.75|42|ACCOUNTS
SUMMARY|TOTAL-SAVINGS|1209100.00|38|ACCOUNTS
SUMMARY|TOTAL-TRANSACTIONS|150|142 SUCCESS|8 FAILED

AUDIT:
AUDIT|TRX-20240101|ACT-A-001|D|3200.00|20240101|101530|Direct deposit|00|BAT20240102
AUDIT|TRX-20240102|ACT-A-002|I|210.50|20240102|000000|Interest accrual|00|
```

---

## Known Issues (KNOWN_ISSUES.md)

**File location:** `cobol/KNOWN_ISSUES.md`
**Purpose:** Document all bugs found in the COBOL layer (do NOT fix them)

```markdown
# COBOL Known Issues

## ACCOUNTS.cob

### A1: Silent Overflow on Account Count
**Issue:** `LOAD-ALL-ACCOUNTS` uses `OCCURS 100 TIMES` for the temp account array.
If a bank has >100 accounts, the 101st account is silently lost.

**Impact:** In production, if a branch opens its 101st account, it disappears from the ledger.
The Python bridge must catch this with account_count >= 100 warning.

**No Fix:** This reflects real COBOL systems where array bounds aren't always validated.

### A2: O(n) Sequential Scan
**Issue:** Every READ or UPDATE operation scans the entire ACCOUNTS.DAT file sequentially.
With 8 accounts per bank, this is negligible. With 10,000 accounts, this becomes a bottleneck.

**Impact:** Realistic legacy system behavior. Modern databases use indexes; COBOL doesn't.

**No Fix:** This teaches why Python bridge optimizes by caching accounts in SQLite.

## TRANSACT.cob

### T1–T9: Debug TRACE Lines
**Issue:** Multiple `DISPLAY 'TRACE|...'` lines remain in the PROCEDURE DIVISION.
These output to stdout during normal operations.

**Example:**
```
TRACE|PERFORM PROCESS-DEPOSIT
TRACE|MOVE 3200.00 TO TRANS-AMOUNT
TRACE|ADD TRANS-AMOUNT TO ACCT-BALANCE
TRACE|WRITE TRANSACTION-RECORD
```

**Impact:** Makes stdout noisy but provides visibility into COBOL execution path.
The Python bridge must parse TRACE lines out of the output stream.

**No Fix:** This is authentic. Legacy COBOL often leaves debug lines in production.

### T10: WS-DAILY-TOTAL Not Persisted
**Issue:** The daily withdrawal limit is stored in `WS-DAILY-TOTAL PIC 9(10)V99`.
This is in WORKING-STORAGE, not a file, so it resets to 0 every time TRANSACT runs.

**Impact:** The $10,000 daily limit applies PER RUN, not PER DAY.
In real banking, limits are tracked in a separate daily limit file. Here it's simplified.

**No Fix:** Phase 2 Python coordinator should track daily limits in SQLite.

### T11: Negative Balance Floor
**Issue:** BATCH-FEE subtracts a fee from an account balance without checking if it goes negative.
```cobol
SUBTRACT WS-IN-AMOUNT FROM WS-A-BAL(WS-FOUND-IDX)
```

**Impact:** Fees can drive an account balance into the negative.
The Python bridge should reject or flag this.

**No Fix:** This demonstrates real-world edge cases.

### T12: Account ID Clobbered During TRANSFER
**Issue:** In `BATCH-TRANSFER`, when looking up the target account, the code does:
```cobol
MOVE WS-IN-TARGET-ID TO WS-IN-ACCT-ID
PERFORM FIND-ACCOUNT
```

This overwrites the source account ID. Later code restores it with:
```cobol
MOVE WS-A-ID(WS-IDX) TO WS-IN-ACCT-ID
```

But this pattern is fragile and could cause subtle bugs if the code is refactored.

**No Fix:** This reflects real COBOL where variable reuse was economical on memory-constrained systems.
```

---

## Account Roster (All 42 Accounts — 37 Customer + 5 Nostro)

### BANK_A: First National (8 customer accounts)

| ID | Name | Type | Opening Balance | Purpose |
|----|------|------|-----------------|---------|
| ACT-A-001 | Maria Santos | Checking | $15,420.50 | Payroll recipient, high activity |
| ACT-A-002 | James Chen | Savings | $84,200.00 | Long-term savings, low activity |
| ACT-A-003 | Oakwood Properties LLC | Checking | $342,000.00 | Business account, wire transfers |
| ACT-A-004 | Sarah Williams | Checking | $2,150.75 | Low balance, near NSF (demo target) |
| ACT-A-005 | Robert Kim | Savings | $28,900.00 | Personal savings, retirement-focused |
| ACT-A-006 | Elena Petrov | Checking | $6,800.00 | Near CTR threshold ($10k) |
| ACT-A-007 | Thompson & Associates | Checking | $128,500.00 | Professional services, high-value |
| ACT-A-008 | David Okafor | Checking | $950.00 | Very low balance (fee impact demo) |

### BANK_B: Commerce Trust (7 customer accounts)

| ID | Name | Type | Opening Balance | Purpose |
|----|------|------|-----------------|---------|
| ACT-B-001 | Acme Manufacturing | Checking | $245,600.00 | Payroll distribution hub |
| ACT-B-002 | Global Logistics | Checking | $157,300.00 | Import/export activity |
| ACT-B-003 | TechStart Ventures | Savings | $89,500.00 | VC-backed startup |
| ACT-B-004 | Peninsula Realty | Checking | $321,000.00 | Real estate escrows |
| ACT-B-005 | NorthSide Clinic | Checking | $45,200.00 | Medical practice |
| ACT-B-006 | Riverside Retail | Checking | $67,800.00 | Multi-location retail |
| ACT-B-007 | Harbor Marine Lease | Savings | $195,000.00 | Equipment financing |

### BANK_C: Pacific Savings (8 customer accounts)

| ID | Name | Type | Opening Balance | Purpose |
|----|------|------|-----------------|---------|
| ACT-C-001 | Lisa Wong | Savings | $125,400.00 | High-balance customer |
| ACT-C-002 | Michael O'Brien | Checking | $18,900.00 | Regular activity |
| ACT-C-003 | Greenfield Properties Inc | Checking | $512,000.00 | Real estate developer |
| ACT-C-004 | Nina Kumar | Savings | $92,300.00 | Retirement account |
| ACT-C-005 | Pacific Coast Vineyards | Checking | $156,700.00 | Agricultural business |
| ACT-C-006 | Dr. Amanda Lee | Checking | $203,500.00 | Medical professional |
| ACT-C-007 | Coastal Tourism LLC | Checking | $78,200.00 | Hospitality/travel |
| ACT-C-008 | Raymond Peterson | Savings | $41,100.00 | Long-term saver |

**BANK_C is the TAMPER TARGET.** In Phase 3 demo, we corrupt one account here (change balance or add ghost transaction).

### BANK_D: Heritage Federal (6 customer accounts)

| ID | Name | Type | Opening Balance | Purpose |
|----|------|------|-----------------|---------|
| ACT-D-001 | Westchester Trust | Checking | $2,100,000.00 | High-net-worth umbrella |
| ACT-D-002 | Birch Estate Partners | Checking | $856,000.00 | Trust management |
| ACT-D-003 | Alpine Investment Club | Savings | $445,000.00 | Collective investment |
| ACT-D-004 | Heritage Pension Fund | Checking | $5,200,000.00 | Pension administration |
| ACT-D-005 | Laurel Foundation | Savings | $750,000.00 | Charitable giving |
| ACT-D-006 | Monument Wealth Advisory | Checking | $189,000.00 | Wealth management |

### BANK_E: Metro Credit Union (8 customer accounts)

| ID | Name | Type | Opening Balance | Purpose |
|----|------|------|-----------------|---------|
| ACT-E-001 | Community Development Corp | Checking | $234,000.00 | Non-profit |
| ACT-E-002 | Angela Rodriguez | Checking | $12,400.00 | Community member |
| ACT-E-003 | Small Business Loan Fund | Checking | $456,000.00 | SBA lending |
| ACT-E-004 | Marcus Thompson | Savings | $67,800.00 | Teacher, long-term saver |
| ACT-E-005 | Metro Food Bank | Checking | $98,500.00 | Social services |
| ACT-E-006 | Youth Programs Initiative | Savings | $175,200.00 | Community programs |
| ACT-E-007 | Chen Family Credit | Checking | $234,100.00 | Multigenerational account |
| ACT-E-008 | Riverside Senior Center | Checking | $89,300.00 | Community center |

### CLEARING: Central Clearing House (5 nostro accounts)

| ID | Name | Type | Opening Balance | Purpose |
|----|------|------|-----------------|---------|
| NST-BANK-A | First National Nostro | Checking | $0.00 | Settlement account for BANK_A |
| NST-BANK-B | Commerce Trust Nostro | Checking | $0.00 | Settlement account for BANK_B |
| NST-BANK-C | Pacific Savings Nostro | Checking | $0.00 | Settlement account for BANK_C |
| NST-BANK-D | Heritage Federal Nostro | Checking | $0.00 | Settlement account for BANK_D |
| NST-BANK-E | Metro CU Nostro | Checking | $0.00 | Settlement account for BANK_E |

**All nostro accounts start at $0.00.** During each day's batch settlement, debits are posted to payers' nostro, credits to receivers' nostro. At end-of-day, the coordinator prints net positions (sum should = $0.00).

---

## Batch Scenario (BATCH-INPUT.DAT)

**File location:** `banks/{NODE}/BATCH-INPUT.DAT`
**Format:** Pipe-delimited, one transaction per line

**Format Details:**
```
D/W/I/F transactions:  ACCOUNT_ID|TYPE|AMOUNT|DESCRIPTION
T (transfer) transactions: ACCOUNT_ID|T|AMOUNT|DESCRIPTION|TARGET_ID

Fields:
  ACCOUNT_ID — source account
  TYPE — D=deposit, W=withdraw, T=transfer, I=interest, F=fee
  AMOUNT — decimal, e.g. 5000.00
  DESCRIPTION — free text (no pipes)
  TARGET_ID — (transfers only) destination account ID
```

**Sample batch (30 transactions, ~4 hours of banking):**

```
ACT-A-001|D|3200.00|Direct deposit - Employer payroll
ACT-A-002|I|210.50|Quarterly interest payment
ACT-A-003|W|45000.00|Wire transfer - Property tax payment
ACT-A-005|D|1850.00|Direct deposit - Consulting income
ACT-A-004|W|3000.00|ACH - Auto loan payment
ACT-A-006|D|9500.00|Mobile deposit - Personal check
ACT-A-002|T|5000.00|Transfer to checking - Monthly expenses|ACT-A-001
ACT-A-003|T|25000.00|Vendor payment - Legal services|ACT-A-007
ACT-A-008|F|12.00|Monthly maintenance fee
ACT-A-005|W|500.00|ATM withdrawal
ACT-A-001|D|1500.00|Freelance payment - Web design
ACT-A-007|W|2340.00|Commercial utility bill payment
ACT-A-008|D|275.00|Cash deposit - Branch
ACT-A-005|T|3000.00|Personal transfer|ACT-A-006
ACT-A-003|I|856.25|Daily interest accrual - Business account
```

**Additional batches for other nodes:**

```
# BANK_B batch (5 transactions — commercial bank pattern)
ACT-B-001|D|125000.00|ACH payroll deposit - Acme employees
ACT-B-002|W|45000.00|Import payment - Pacific shipping
ACT-B-003|I|223.75|Monthly interest - TechStart savings
ACT-B-004|W|75000.00|Escrow disbursement - Peninsula closing
ACT-B-005|D|12400.00|Insurance payment - NorthSide receivables

# BANK_C batch (5 transactions — savings bank pattern)
ACT-C-001|I|313.50|Quarterly interest - Lisa Wong savings
ACT-C-002|D|5000.00|Cash deposit - O'Brien branch
ACT-C-003|W|100000.00|Wire transfer - Greenfield closing costs
ACT-C-004|I|230.75|Monthly interest - Nina Kumar retirement
ACT-C-005|D|18500.00|Agricultural deposit - vineyard harvest revenue

# BANK_D batch (4 transactions — wealth management pattern)
ACT-D-001|T|500000.00|Trust distribution - Westchester quarterly|ACT-D-006
ACT-D-002|I|2140.00|Monthly interest - Birch estate trust
ACT-D-003|D|50000.00|Investment contribution - Alpine club
ACT-D-005|W|25000.00|Grant disbursement - Laurel Foundation

# BANK_E batch (5 transactions — credit union pattern)
ACT-E-001|D|35000.00|Grant deposit - HUD community development
ACT-E-002|D|2850.00|Direct deposit - Angela Rodriguez payroll
ACT-E-003|W|80000.00|SBA loan disbursement - small business
ACT-E-004|I|169.50|Quarterly interest - Marcus Thompson savings
ACT-E-005|D|4200.00|Donation - Metro Food Bank fundraiser

# CLEARING batch (4 nostro settlement entries — run after bank batches)
NST-BANK-A|D|125000.00|Settlement credit - BANK_B payroll transfer
NST-BANK-B|W|125000.00|Settlement debit - payroll origin BANK_A
NST-BANK-C|D|100000.00|Settlement credit - BANK_A wire
NST-BANK-D|W|500000.00|Settlement debit - trust distribution BANK_D
```

**Semantics:**
- D = DEPOSIT (add to account)
- W = WITHDRAW (subtract from account)
- T = TRANSFER (subtract from source, add to target — 5 fields)
- I = INTEREST (add to account, periodic)
- F = FEE (subtract from account)

**For inter-bank transfers** (Phase 2): TARGET_ID points to an account in a different bank (e.g., `ACT-B-001`). The CLEARING node processes this as two transactions: debit source's nostro, credit target's nostro.

---

## Data Seeding (scripts/seed.sh)

**Purpose:** Populate all 6 node directories with seeded ACCOUNTS.DAT files

**Pseudocode:**
```bash
#!/bin/bash

# For each node:
for node in BANK_A BANK_B BANK_C BANK_D BANK_E CLEARING; do
  mkdir -p banks/$node

  # Create ACCOUNTS.DAT with seeded records (fixed-width, line-sequential)
  # Use the account roster above
  # Write one account per line (ACCTREC format)

  # Create empty TRANSACT.DAT (will be populated by COBOL runs)
  # Create BATCH-INPUT.DAT with the sample batch
done

echo "Seeded BANK_A: 8 accounts"
echo "Seeded BANK_B: 7 accounts"
echo "Seeded BANK_C: 8 accounts"
echo "Seeded BANK_D: 6 accounts"
echo "Seeded BANK_E: 8 accounts"
echo "Seeded CLEARING: 5 nostro accounts"
```

**Key detail:** Records are fixed-width (70 bytes for ACCTREC, 103 bytes for TRANSREC). Use COBOL PIC clauses as guide for byte alignment.

---

## Compilation (scripts/build.sh)

**Tool:** GnuCOBOL (`cobc`)
**Flags:** `-x -free -I ../copybooks` (executable, free-form source, copybook include path)

**Full build.sh script:**
```bash
#!/bin/bash
set -e

if ! command -v cobc &> /dev/null; then
  echo "cobc not found. Skipping COBOL compilation."
  echo "Continuing in Python-only mode (SQLite sync, no COBOL execution)"
  exit 0
fi

mkdir -p cobol/bin
cd cobol/src

cobc -x -free -I ../copybooks ACCOUNTS.cob -o ../bin/ACCOUNTS
cobc -x -free -I ../copybooks TRANSACT.cob -o ../bin/TRANSACT
cobc -x -free -I ../copybooks VALIDATE.cob -o ../bin/VALIDATE
cobc -x -free -I ../copybooks REPORTS.cob -o ../bin/REPORTS

echo "Compiled: ACCOUNTS, TRANSACT, VALIDATE, REPORTS → cobol/bin/"
```

**Key detail:** The `-I ../copybooks` flag is required so `COPY` statements in COBOL programs can resolve their copybook paths. Without it, compilation will fail with "copybook not found" errors.

**If `cobc` not installed:**
The script gracefully exits with a message. The system continues in Python-only mode (SQLite sync, no COBOL execution), which is valid for Phase 1 testing.

---

## Next Steps

1. **Read `COBOL_STYLE_REFERENCE.md` and COBOL_SUPPLEMENTS.md** — Understand GnuCOBOL patterns and run the smoke test
2. **Implement COBOL programs** from the specifications in this document (ACCOUNTS, TRANSACT, VALIDATE, REPORTS)
3. **Create copybooks** — ACCTREC.cpy, TRANSREC.cpy, COMCODE.cpy (specs provided above)
4. **Create `cobol/KNOWN_ISSUES.md`** — Use Supplement B template from COBOL_SUPPLEMENTS.md
5. **Create `scripts/build.sh`** — Use the full script provided above (includes `-I ../copybooks` flag)
6. **Create `scripts/seed.sh`** — Populate all 6 nodes with seeded ACCOUNTS.DAT using batch samples provided
7. **Compile COBOL** via `build.sh` (or gracefully skip if cobc unavailable)
8. **Verify:** seed.sh runs, bridge.py can list accounts from all 6 nodes

**Critical:** Do not copy from an external v1 repo. Implement from the complete specifications provided in this document. The full program behaviors, I/O contracts, and output formats are all defined here.

**Next document:** `03_PYTHON_BACKEND.md` for the bridge implementation.
