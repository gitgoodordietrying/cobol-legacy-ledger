# Phase 2 Implementation Guide — Full COBOL + Python Bridge

## Overview

Phase 2 delivers complete banking logic in COBOL with Python bridge integration. The system operates in two modes:

- **Mode A (COBOL):** Full business logic in COBOL; Python observes via subprocess execution
- **Mode B (Python):** Falls back to Python validation if COBOL binaries unavailable

This guide shows how to test and verify the Phase 2 implementation.

---

## What Was Implemented

### 1. Four Complete COBOL Programs

#### **ACCOUNTS.cob** — Account Lifecycle
- **Operations:** LIST, CREATE, READ, UPDATE, CLOSE
- **Architecture:** In-memory OCCURS table (100 entries), load/find/save pattern
- **Output:** Pipe-delimited pipe | id | name | type | balance | status | open_date | last_activity

```cobol
LOAD-ALL-ACCOUNTS    → Reads entire ACCOUNTS.DAT into WS-ACCT-ENTRY table
FIND-ACCOUNT         → Binary search by WS-IN-ACCT-ID
WRITE-ALL-ACCOUNTS   → Persists table back to disk
LIST-ACCOUNTS        → Displays all accounts + RESULT|00
CREATE-ACCOUNT       → Adds new account, checks duplicate
READ-ACCOUNT         → Finds and displays single account
UPDATE-ACCOUNT       → Changes status (A/C/F)
CLOSE-ACCOUNT        → Sets status to 'C'
```

#### **TRANSACT.cob** — Transaction Engine (Core Demo)
- **Operations:** DEPOSIT, WITHDRAW, TRANSFER, BATCH
- **Output:** Columnar batch trace per COBOL_SUPPLEMENTS.md Supplement A

```
SEQ  STATUS  TYPE  AMOUNT        ACCOUNT     BALANCE-AFTER  DESCRIPTION
001  OK      DEP   $  5,000.00   ACT-A-001   $ 20,420.50   Payroll deposit — Santos
 ** COMPLIANCE NOTE: Deposit $9,500.00 within $500 of $10,000 CTR threshold
002  FAIL01  WDR   $ 25,000.00   ACT-A-002   $  8,234.15   Insufficient funds
```

**Features:**
- GENERATE-TX-ID: produces TRX-{A|B|C|D|E|Z}-NNNNNN (12 chars exactly)
- Account lookup, validation, balance update, transaction record write
- Compliance flag for large deposits (CTR threshold)
- BATCH mode: reads BATCH-INPUT.DAT, processes all records, outputs summary

#### **VALIDATE.cob** — Business Rules
- **Operations:** CHECK-ACCOUNT-STATUS, CHECK-BALANCE, CHECK-DAILY-LIMIT
- **Input:** account_id, amount
- **Output:** RESULT|{00|01|02|03|04}

```
00 = Success
01 = Insufficient funds (NSF)
02 = Daily limit exceeded
03 = Invalid account
04 = Account frozen
```

#### **REPORTS.cob** — Reporting
- **LEDGER:** All accounts grouped by type (checking/savings) with totals
- **STATEMENT:** Transaction history filtered by account ID
- **EOD:** End-of-day reconciliation with status code counts
- **AUDIT:** Complete transaction ledger dump

---

### 2. Python Bridge Wiring (Mode A Integration)

The bridge now calls COBOL subprocess and parses output:

```python
from python.bridge import COBOLBridge

# Initialize for a node
bridge = COBOLBridge(node="BANK_A", data_dir="banks", bin_dir="cobol/bin")

# List accounts (delegates to ACCOUNTS LIST)
accounts = bridge.list_accounts()  # Returns list of dicts

# Process transaction (delegates to TRANSACT subprocess)
result = bridge.process_transaction(
    account_id="ACT-A-001",
    tx_type="D",        # Deposit
    amount=5000.00,
    description="Payroll deposit"
)
# Returns: {status: "00", tx_id: "TRX-A-000001", new_balance: 20420.50, ...}

# Validate transaction (calls VALIDATE subprocess)
validation = bridge.validate_transaction_via_cobol("ACT-A-001", 1000.00)

# Get batch report (calls TRANSACT BATCH)
batch_result = bridge.process_batch_via_cobol()

# Get reports
ledger = bridge.get_reports_via_cobol("LEDGER")  # List of strings
statement = bridge.get_reports_via_cobol("STATEMENT", "ACT-A-001")
eod = bridge.get_reports_via_cobol("EOD")
audit = bridge.get_reports_via_cobol("AUDIT")

bridge.close()
```

**Key Features:**
- Subprocess execution with 5-second timeout
- Output parsing (pipe-delimited for data, status codes for validation)
- Fallback to Python validation if COBOL unavailable
- Integrity chain integration: wraps COBOL results in hash chain
- Per-node database (bank_a.db) with account and transaction tables
- Per-node HMAC keys for cryptographic verification

---

## Testing Instructions

### Step 1: Prepare Environment

```bash
# Create bank directories
mkdir -p banks/{BANK_A,BANK_B,BANK_C,BANK_D,BANK_E,CLEARING}

# Create ACCOUNTS.DAT and BATCH-INPUT.DAT (run Python seeding)
# Either: bash scripts/seed.sh
# Or manually run the Python blocks from seed.sh
```

### Step 2: Compile COBOL

```bash
# Automatic with Docker fallback
bash scripts/build.sh

# Expected output:
# BUILD SMOKETEST ... OK
# BUILD ACCOUNTS ... OK
# BUILD TRANSACT ... OK
# BUILD VALIDATE ... OK
# BUILD REPORTS ... OK
# All programs compiled successfully → cobol/bin/
```

### Step 3: Test Each Program Standalone

**ACCOUNTS LIST:**
```bash
cd banks/BANK_A
../../cobol/bin/ACCOUNTS LIST
# Output:
# ACCOUNT|ACT-A-001|Maria Santos|C|5000.00|A|20260217|20260217
# ACCOUNT|ACT-A-002|James Wilson|S|12500.00|A|20260217|20260217
# ... (8 accounts total)
# RESULT|00
```

**TRANSACT DEPOSIT:**
```bash
cd banks/BANK_A
../../cobol/bin/TRANSACT DEPOSIT ACT-A-001 1000.00 "Test deposit"
# Output:
# OK|DEPOSIT|TRX-A-000001|ACT-A-001|6000.00
# RESULT|00
```

**TRANSACT BATCH:**
```bash
cd banks/BANK_A
../../cobol/bin/TRANSACT BATCH
# Output: (columnar trace with compliance notes)
# ========================================================
#   LEGACY LEDGER — BATCH PROCESSING LOG
#   NODE: BANK_A — FIRST NATIONAL BANK
#   DATE: 2026-02-17  TIME: 10:15:30
# ...
# 001  OK      DEP   $  5,000.00   ACT-A-001   $ 20,420.50   ...
#  ** COMPLIANCE NOTE: ...
# ...
# --- END BATCH RUN ---
# ========================================================
#   BATCH SUMMARY
#   Total transactions read:     8
#   Successful:                  6
#   Failed:                      2
# ========================================================
# RESULT|00
```

**VALIDATE:**
```bash
cd banks/BANK_A
../../cobol/bin/VALIDATE ACT-A-001 1000.00
# Output:
# RESULT|00  (valid, sufficient funds)

# Test insufficient funds:
../../cobol/bin/VALIDATE ACT-A-001 1000000.00
# Output:
# RESULT|01  (insufficient funds)
```

**REPORTS LEDGER:**
```bash
cd banks/BANK_A
../../cobol/bin/REPORTS LEDGER
# Output: (all accounts + checking/savings totals)
# LEDGER|ACCOUNT DETAIL
# ACCOUNT|ACT-A-001|Maria Santos|C|5000.00|A|20260217|20260217
# ...
# SUMMARY|TOTAL-BALANCE|...
# SUMMARY|CHECKING-BALANCE|...
# SUMMARY|SAVINGS-BALANCE|...
# RESULT|00
```

### Step 4: Test Python Bridge Integration

```python
from pathlib import Path
from python.bridge import COBOLBridge

# Initialize all 6 nodes
nodes = ["BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E", "CLEARING"]
expected_counts = {
    "BANK_A": 8,
    "BANK_B": 7,
    "BANK_C": 8,
    "BANK_D": 6,
    "BANK_E": 8,
    "CLEARING": 5
}

for node in nodes:
    bridge = COBOLBridge(node=node, data_dir="banks", bin_dir="cobol/bin")
    accounts = bridge.list_accounts()
    actual = len(accounts)
    expected = expected_counts[node]
    status = "✓" if actual == expected else "✗"
    print(f"{status} {node}: {actual}/{expected} accounts")
    bridge.close()

# Expected output:
# ✓ BANK_A: 8/8 accounts
# ✓ BANK_B: 7/7 accounts
# ✓ BANK_C: 8/8 accounts
# ✓ BANK_D: 6/6 accounts
# ✓ BANK_E: 8/8 accounts
# ✓ CLEARING: 5/5 accounts
```

### Step 5: Test Transaction Processing

```python
from python.bridge import COBOLBridge

bridge = COBOLBridge(node="BANK_A")

# Test DEPOSIT
result = bridge.process_transaction(
    account_id="ACT-A-001",
    tx_type="D",
    amount=1000.00,
    description="Deposit test"
)
print(f"Deposit: {result['status']} - {result.get('tx_id', 'N/A')}")
# Expected: Deposit: 00 - TRX-A-000001

# Test WITHDRAW
result = bridge.process_transaction(
    account_id="ACT-A-002",
    tx_type="W",
    amount=100.00,
    description="Withdrawal test"
)
print(f"Withdraw: {result['status']}")
# Expected: Withdraw: 00

# Test NSF (insufficient funds)
result = bridge.process_transaction(
    account_id="ACT-A-001",
    tx_type="W",
    amount=1000000.00,
    description="Should fail"
)
print(f"NSF check: {result['status']}")
# Expected: NSF check: 01

bridge.close()
```

### Step 6: Test Integrity Chain

```python
from python.bridge import COBOLBridge

bridge = COBOLBridge(node="BANK_A")

# Process transaction (automatically recorded in chain)
bridge.process_transaction(
    account_id="ACT-A-001",
    tx_type="D",
    amount=1000.00,
    description="Test transaction"
)

# Verify chain
chain_valid = bridge.chain.verify_chain()
print(f"Chain valid: {chain_valid['valid']}")
print(f"Chain entries: {len(bridge.chain.get_chain_for_display())}")

# Try tampering
# (Modify SQLite directly, then verify)
# Expected: Chain detects tampering in <100ms

bridge.close()
```

---

## Phase 1 Gate Verification (5 Checks)

Run these to confirm Phase 2 complete:

```bash
# Check 1: COBOL compiles
bash scripts/build.sh
# Expected: All programs compiled successfully

# Check 2: Seeding works
bash scripts/seed.sh
# Expected: All 6 nodes seeded with accounts and batches

# Check 3: Bridge lists correct counts
python3 << 'EOF'
from python.bridge import COBOLBridge
expected = {'BANK_A':8,'BANK_B':7,'BANK_C':8,'BANK_D':6,'BANK_E':8,'CLEARING':5}
for node, count in expected.items():
    b = COBOLBridge(node=node, data_dir="banks", bin_dir="cobol/bin")
    assert len(b.list_accounts()) == count, f"{node} mismatch"
    print(f"✓ {node}: {count} accounts")
    b.close()
EOF

# Check 4: Transaction processes with status 00
python3 << 'EOF'
from python.bridge import COBOLBridge
b = COBOLBridge(node="BANK_A")
result = b.process_transaction("ACT-A-001", "D", 1000, "Test")
assert result['status'] == '00', f"Expected 00, got {result['status']}"
print(f"✓ Transaction status: {result['status']}")
b.close()
EOF

# Check 5: Integrity chain records and verifies
python3 << 'EOF'
from python.bridge import COBOLBridge
b = COBOLBridge(node="BANK_A")
b.process_transaction("ACT-A-001", "D", 1000, "Test")
chain_valid = b.chain.verify_chain()
assert chain_valid['valid'], "Chain verification failed"
print(f"✓ Chain valid: {chain_valid['valid']}")
b.close()
EOF
```

---

## Files Modified/Created

| File | Status | Change |
|------|--------|--------|
| `scripts/seed.sh` | ✓ Modified | Fixed dir naming, added BATCH-INPUT.DAT |
| `cobol/src/ACCOUNTS.cob` | ✓ Complete | Full rewrite: LIST, CREATE, READ, UPDATE, CLOSE |
| `cobol/src/TRANSACT.cob` | ✓ Complete | Full rewrite: DEPOSIT, WITHDRAW, TRANSFER, BATCH |
| `cobol/src/VALIDATE.cob` | ✓ Complete | Fixed: proper account search, 3-paragraph validation |
| `cobol/src/REPORTS.cob` | ✓ Complete | Full: LEDGER, STATEMENT, EOD, AUDIT |
| `python/bridge.py` | ✓ Modified | Fixed paths, added subprocess methods, balance parser |
| `python/integrity.py` | ✓ Ready | (No changes, already functional) |
| `python/auth.py` | ✓ Ready | (No changes, already functional) |
| `python/cli.py` | ✓ Ready | (No changes, already functional) |

---

## Architecture Notes

### Transaction ID Format
- Format: `TRX-{NODE_CODE}-{SEQUENCE}`
- Example: `TRX-A-000001` (12 chars exactly, fits PIC X(12))
- Node codes: A, B, C, D, E (banks), Z (clearing)
- Sequence: 6-digit counter per node, auto-incrementing

### Status Codes
```
00 = Success
01 = Insufficient funds (NSF)
02 = Daily limit exceeded
03 = Invalid account
04 = Account frozen
99 = System error
```

### Batch Processing
- Reads BATCH-INPUT.DAT (pipe-delimited)
- Format: `ACCOUNT|TYPE|AMOUNT|DESC` or `ACCOUNT|T|AMOUNT|DESC|TARGET`
- Types: D=deposit, W=withdraw, T=transfer, I=interest, F=fee
- Output: Columnar trace with compliance notes and summary statistics

### Database Schema
Each node has per-node SQLite database:
```
accounts (id, name, type, balance, status, open_date, last_activity)
transactions (tx_id, account_id, type, amount, timestamp, description, status)
chain_entries (id, tx_data_hash, previous_hash, hmac_signature, created_at)
```

---

## Next Steps (Phase 3)

1. **Frontend Console** — Static HTML/CSS/JS
   - Account list view
   - Transaction entry form
   - Batch processing dashboard
   - Integrity verification display

2. **REST API** — Python FastAPI wrapper
   - List accounts
   - Process transaction
   - View reports
   - Verify chain

3. **Demo Script** — End-to-end scenario
   - Process 8 transactions
   - Run batch
   - Corrupt one account
   - Show tampering detection in <100ms

---

## Quick Reference

### Start Bridge
```python
from python.bridge import COBOLBridge
b = COBOLBridge(node="BANK_A")
```

### List Accounts
```python
accounts = b.list_accounts()
for acct in accounts:
    print(f"{acct['id']}: ${acct['balance']:.2f}")
```

### Process Transaction
```python
result = b.process_transaction("ACT-A-001", "D", 1000.00, "Deposit")
if result['status'] == '00':
    print(f"Transaction {result['tx_id']} processed")
else:
    print(f"Error: {result['message']}")
```

### Run Batch
```python
batch = b.process_batch_via_cobol()
for line in batch['output']:
    print(line)
print(f"Summary: {batch['summary']}")
```

### Get Reports
```python
ledger = b.get_reports_via_cobol("LEDGER")
for line in ledger:
    print(line)
```

### Verify Chain
```python
chain_valid = b.chain.verify_chain()
print(f"Chain valid: {chain_valid['valid']}")
```

### Close
```python
b.close()
```

---

**Status: Phase 2 Complete ✅**
All COBOL programs implemented and wired to Python bridge.
Ready for Phase 3 (Frontend/Console) and comprehensive testing.
